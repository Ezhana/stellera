"""种子数据脚本：幂等地写入角色、权限、演示账号与 FDE 演示订单。

用法（数据库表已由 Alembic 迁移创建后）：
    uv run python -m app.scripts.seed
入口脚本 scripts/entrypoint.sh 会在 `alembic upgrade head` 之后自动执行。

角色树：authenticated
├── viewer -> operator -> admin（原有后台角色链）
├── enterprise（企业发布方）
└── engineer（接单工程师）
- 所有登录用户都会被投影到 role:authenticated；
- admin 拥有全部 API 权限；
- SEED_DEMO_USERS=true 时额外创建 operator / viewer / enterprise / engineer
  演示账号，以及 10 条由企业演示账号发布、带工作日志的 FDE 演示订单。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.db import create_engine, create_session_factory
from app.models.base import utcnow
from app.models.fde import FdeOrder, FdeOrderLog
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User
from app.security.passwords import hash_password
from app.services.fde import (
    ESCROW_STATUS_HELD,
    ESCROW_STATUS_RELEASED,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_IN_PROGRESS,
    ORDER_STATUS_OPEN,
)

# (name, parent, description)
ROLE_DEFINITIONS: tuple[tuple[str, str | None, str], ...] = (
    ("authenticated", None, "所有已登录用户的基线角色"),
    ("viewer", "authenticated", "只读访问"),
    ("operator", "viewer", "运营写操作"),
    ("admin", "operator", "全部权限"),
    ("enterprise", "authenticated", "企业发布方：发布需求 / 确认交付 / 取消订单"),
    ("engineer", "authenticated", "接单工程师：认领订单 / 提交工作日志"),
)

# (role, object, action, description)
# 只保留当前上线的模块（auth + FDE 订单）；wallet / plaza / 旧 orders 已下线，
# 不再写入权限表，避免前端权限卡片出现不存在的模块。
PERMISSION_DEFINITIONS: tuple[tuple[str, str, str, str], ...] = (
    ("authenticated", "/api/v1/auth/me", "^GET$", "读取当前用户"),
    ("authenticated", "/api/v1/auth/logout", "^POST$", "登出并吊销 refresh token"),
    ("admin", "/api/v1/*", "^(GET|POST|PUT|PATCH|DELETE)$", "全部业务 API 权限"),
    # ---------- FDE 订单模块 ----------
    ("authenticated", "/api/v1/fde/orders", "^GET$", "只读：FDE 订单大厅"),
    ("authenticated", "/api/v1/fde/orders/*", "^GET$", "只读：FDE 订单详情 / 我发布的"),
    ("enterprise", "/api/v1/fde/orders", "^POST$", "企业：发布 FDE 需求"),
    ("enterprise", "/api/v1/fde/orders/*/complete", "^POST$", "企业：确认交付并释放托管资金"),
    ("enterprise", "/api/v1/fde/orders/*/cancel", "^POST$", "企业：取消订单并退回托管资金"),
    ("engineer", "/api/v1/fde/orders/*/claim", "^POST$", "工程师：认领订单"),
    ("engineer", "/api/v1/fde/orders/*/logs", "^POST$", "工程师：提交工作日志"),
)

DEMO_OPERATOR_USERNAME = "operator"
DEMO_VIEWER_USERNAME = "viewer"
DEMO_ENTERPRISE_USERNAME = "enterprise"
DEMO_ENGINEER_USERNAME = "engineer"


@dataclass(frozen=True)
class DemoWorkLog:
    """演示工作日志：相对“当前时间”的天数偏移，保证反复重建时顺序稳定。"""

    content: str
    worked_hours: float | None
    days_ago: int


@dataclass(frozen=True)
class DemoOrderDefinition:
    """一条 FDE 演示订单的完整定义（单号固定，用于幂等判断）。"""

    code: str
    title: str
    industry: str
    description: str
    delivery_days: int
    price_cents: int
    status: str
    created_days_ago: int
    claimed_days_ago: int | None = None
    completed_days_ago: int | None = None
    logs: tuple[DemoWorkLog, ...] = ()


# 订单大厅首屏数据：5 条 open、3 条 in_progress、2 条 completed，
# 行业覆盖 7 个方向，发布时间/预算/交付周期都拉开差距，方便前端演示排序与筛选。
DEMO_ORDER_DEFINITIONS: tuple[DemoOrderDefinition, ...] = (
    DemoOrderDefinition(
        code="FDE-DEMO-0001",
        title="医疗影像 AI 辅助诊断 PoC",
        industry="医疗健康",
        description="基于胸部 CT 影像构建肺结节检出模型，输出辅助诊断报告并接入院内 PACS。",
        delivery_days=21,
        price_cents=8_600_000,
        status=ORDER_STATUS_OPEN,
        created_days_ago=60,
    ),
    DemoOrderDefinition(
        code="FDE-DEMO-0002",
        title="保险理赔单证 OCR 识别流水线",
        industry="金融保险",
        description="对理赔材料做分类与关键字段抽取，对接现有理赔系统，识别准确率目标 95%。",
        delivery_days=14,
        price_cents=3_200_000,
        status=ORDER_STATUS_OPEN,
        created_days_ago=52,
    ),
    DemoOrderDefinition(
        code="FDE-DEMO-0003",
        title="产线设备预测性维护看板",
        industry="智能制造",
        description="采集 CNC 设备振动与温度数据，构建剩余寿命预测模型并交付可视化看板。",
        delivery_days=30,
        price_cents=12_500_000,
        status=ORDER_STATUS_OPEN,
        created_days_ago=45,
    ),
    DemoOrderDefinition(
        code="FDE-DEMO-0004",
        title="光伏电站发电量预测模型",
        industry="能源电力",
        description="融合气象预报与历史发电数据，按 15 分钟粒度预测未来 72 小时发电量。",
        delivery_days=45,
        price_cents=18_000_000,
        status=ORDER_STATUS_OPEN,
        created_days_ago=38,
    ),
    DemoOrderDefinition(
        code="FDE-DEMO-0005",
        title="会员复购推荐引擎冷启动",
        industry="零售消费",
        description="在缺少用户行为数据的前提下，用商品画像与人群标签做复购推荐冷启动。",
        delivery_days=18,
        price_cents=5_800_000,
        status=ORDER_STATUS_OPEN,
        created_days_ago=30,
    ),
    DemoOrderDefinition(
        code="FDE-DEMO-0006",
        title="高校科研数据标注与质检平台",
        industry="教育科研",
        description="搭建多模态科研数据标注平台，支持标注任务分发、质检抽检与统计报表。",
        delivery_days=25,
        price_cents=7_400_000,
        status=ORDER_STATUS_IN_PROGRESS,
        created_days_ago=24,
        claimed_days_ago=20,
        logs=(
            DemoWorkLog(
                content="完成标注任务模型设计与数据字典梳理，输出字段说明文档。",
                worked_hours=6.0,
                days_ago=18,
            ),
            DemoWorkLog(
                content="交付第一版标注与质检流程原型，等待业务方评审。",
                worked_hours=5.5,
                days_ago=9,
            ),
        ),
    ),
    DemoOrderDefinition(
        code="FDE-DEMO-0007",
        title="政务热线工单智能分派",
        industry="政务公共服务",
        description="对 12345 热线工单做意图识别与属地分派，缩短转办链路并统计办理时效。",
        delivery_days=35,
        price_cents=9_900_000,
        status=ORDER_STATUS_IN_PROGRESS,
        created_days_ago=18,
        claimed_days_ago=15,
        logs=(
            DemoWorkLog(
                content="梳理 32 类工单标签体系，完成 3 个月历史工单清洗。",
                worked_hours=7.0,
                days_ago=13,
            ),
            DemoWorkLog(
                content="训练意图分类基线模型，准确率 88.6%，已提交评估报告。",
                worked_hours=8.0,
                days_ago=8,
            ),
            DemoWorkLog(
                content="联调分派规则引擎，补充属地兜底策略。",
                worked_hours=6.5,
                days_ago=3,
            ),
        ),
    ),
    DemoOrderDefinition(
        code="FDE-DEMO-0008",
        title="电子病历数据结构化抽取",
        industry="医疗健康",
        description="从自由文本电子病历中抽取诊断、用药与手术信息，输出结构化 JSON 接口。",
        delivery_days=20,
        price_cents=6_600_000,
        status=ORDER_STATUS_IN_PROGRESS,
        created_days_ago=12,
        claimed_days_ago=10,
        logs=(
            DemoWorkLog(
                content="完成脱敏样本集构建与抽取字段确认，进入模型微调阶段。",
                worked_hours=4.0,
                days_ago=6,
            ),
        ),
    ),
    DemoOrderDefinition(
        code="FDE-DEMO-0009",
        title="工业质检缺陷检测模型交付",
        industry="智能制造",
        description="面向 3C 结构件外观质检，交付缺陷检测模型与边缘推理服务部署方案。",
        delivery_days=28,
        price_cents=11_200_000,
        status=ORDER_STATUS_COMPLETED,
        created_days_ago=90,
        claimed_days_ago=85,
        completed_days_ago=60,
        logs=(
            DemoWorkLog(
                content="完成缺陷样本标注规范与基线模型，漏检率 1.8%。",
                worked_hours=7.5,
                days_ago=80,
            ),
            DemoWorkLog(
                content="现场部署边缘推理服务并通过产线验收，交付运维手册。",
                worked_hours=9.0,
                days_ago=65,
            ),
        ),
    ),
    DemoOrderDefinition(
        code="FDE-DEMO-0010",
        title="信贷反欺诈规则引擎 PoC",
        industry="金融保险",
        description="基于历史进件数据构建反欺诈规则与评分卡，输出可解释的拒贷原因。",
        delivery_days=16,
        price_cents=4_500_000,
        status=ORDER_STATUS_COMPLETED,
        created_days_ago=75,
        claimed_days_ago=70,
        completed_days_ago=55,
        logs=(
            DemoWorkLog(
                content="完成特征工程与规则挖掘，覆盖 12 类高风险团伙特征。",
                worked_hours=6.0,
                days_ago=66,
            ),
            DemoWorkLog(
                content="上线灰度评分卡，欺诈拦截率提升 23%。",
                worked_hours=5.5,
                days_ago=60,
            ),
            DemoWorkLog(
                content="整理 PoC 结项报告与规则维护说明，交付验收。",
                worked_hours=4.0,
                days_ago=57,
            ),
        ),
    ),
)


@dataclass(frozen=True)
class SeedResult:
    created_users: tuple[str, ...]
    created_roles: tuple[str, ...]
    created_permissions: int
    created_orders: int


async def _seed_roles(session: AsyncSession, result_created: list[str]) -> dict[str, Role]:
    existing = {role.name: role for role in (await session.execute(select(Role))).scalars()}
    for name, _parent, description in ROLE_DEFINITIONS:
        if name in existing:
            continue
        role = Role(name=name, description=description)
        session.add(role)
        existing[name] = role
        result_created.append(name)
    await session.flush()

    # 角色树需要拿到自增 id 之后再回填 parent_id。
    for name, parent_name, _description in ROLE_DEFINITIONS:
        parent = existing.get(parent_name) if parent_name else None
        existing[name].parent_id = parent.id if parent else None
    await session.flush()
    return existing


async def _seed_permissions(session: AsyncSession, roles: dict[str, Role]) -> int:
    existing_permissions = {
        (permission.object, permission.action): permission
        for permission in (await session.execute(select(Permission))).scalars()
    }
    existing_links = {
        (link.role_id, link.permission_id)
        for link in (await session.execute(select(RolePermission))).scalars()
    }
    created = 0
    for role_name, object_pattern, action_pattern, description in PERMISSION_DEFINITIONS:
        role = roles[role_name]
        permission = existing_permissions.get((object_pattern, action_pattern))
        if permission is None:
            permission = Permission(
                object=object_pattern,
                action=action_pattern,
                description=description,
            )
            session.add(permission)
            await session.flush()
            existing_permissions[(object_pattern, action_pattern)] = permission
            created += 1
        if (role.id, permission.id) not in existing_links:
            session.add(RolePermission(role_id=role.id, permission_id=permission.id))
            existing_links.add((role.id, permission.id))
    return created


async def _ensure_user(
    session: AsyncSession,
    *,
    username: str,
    email: str,
    password: str,
    full_name: str,
    role: Role,
    created: list[str],
) -> User:
    user = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        created.append(username)

    existing_link = (
        await session.execute(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == role.id,
            )
        )
    ).scalar_one_or_none()
    if existing_link is None:
        session.add(UserRole(user_id=user.id, role_id=role.id))
    return user


async def _seed_demo_orders(session: AsyncSession, publisher: User, engineer: User) -> int:
    """写入 10 条 FDE 演示订单；单号已存在则跳过，保证可重复执行。"""
    existing_codes = set(
        (
            await session.execute(
                select(FdeOrder.code).where(
                    FdeOrder.code.in_([definition.code for definition in DEMO_ORDER_DEFINITIONS])
                )
            )
        ).scalars()
    )
    now = utcnow()
    created = 0
    for definition in DEMO_ORDER_DEFINITIONS:
        if definition.code in existing_codes:
            continue
        created_at = now - timedelta(days=definition.created_days_ago)
        claimed_at = (
            now - timedelta(days=definition.claimed_days_ago)
            if definition.claimed_days_ago is not None
            else None
        )
        completed_at = (
            now - timedelta(days=definition.completed_days_ago)
            if definition.completed_days_ago is not None
            else None
        )
        order = FdeOrder(
            code=definition.code,
            title=definition.title,
            industry=definition.industry,
            description=definition.description,
            delivery_days=definition.delivery_days,
            price_cents=definition.price_cents,
            status=definition.status,
            escrow_status=(
                ESCROW_STATUS_RELEASED
                if definition.status == ORDER_STATUS_COMPLETED
                else ESCROW_STATUS_HELD
            ),
            publisher_id=publisher.id,
            engineer_id=engineer.id if definition.status != ORDER_STATUS_OPEN else None,
            claimed_at=claimed_at,
            completed_at=completed_at,
            created_at=created_at,
            updated_at=completed_at or claimed_at or created_at,
        )
        session.add(order)
        # 日志需要 order.id，先 flush 拿到自增主键。
        await session.flush()
        for log_definition in definition.logs:
            session.add(
                FdeOrderLog(
                    order_id=order.id,
                    author_id=engineer.id,
                    content=log_definition.content,
                    worked_hours=log_definition.worked_hours,
                    created_at=now - timedelta(days=log_definition.days_ago),
                )
            )
        created += 1
    return created


async def seed_database(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> SeedResult:
    created_users: list[str] = []
    created_roles: list[str] = []
    async with session_factory() as session:
        roles = await _seed_roles(session, created_roles)
        created_permissions = await _seed_permissions(session, roles)

        await _ensure_user(
            session,
            username=settings.seed_admin_username.strip().lower(),
            email=settings.seed_admin_email.strip().lower(),
            password=settings.seed_admin_password,
            full_name="系统管理员",
            role=roles["admin"],
            created=created_users,
        )
        enterprise: User | None = None
        engineer: User | None = None
        if settings.seed_demo_users:
            await _ensure_user(
                session,
                username=DEMO_OPERATOR_USERNAME,
                email=f"{DEMO_OPERATOR_USERNAME}@example.com",
                password=settings.seed_operator_password,
                full_name="运营（演示）",
                role=roles["operator"],
                created=created_users,
            )
            await _ensure_user(
                session,
                username=DEMO_VIEWER_USERNAME,
                email=f"{DEMO_VIEWER_USERNAME}@example.com",
                password=settings.seed_viewer_password,
                full_name="访客（演示）",
                role=roles["viewer"],
                created=created_users,
            )
            enterprise = await _ensure_user(
                session,
                username=DEMO_ENTERPRISE_USERNAME,
                email=f"{DEMO_ENTERPRISE_USERNAME}@example.com",
                password=settings.seed_enterprise_password,
                full_name="企业（演示）",
                role=roles["enterprise"],
                created=created_users,
            )
            engineer = await _ensure_user(
                session,
                username=DEMO_ENGINEER_USERNAME,
                email=f"{DEMO_ENGINEER_USERNAME}@example.com",
                password=settings.seed_engineer_password,
                full_name="工程师（演示）",
                role=roles["engineer"],
                created=created_users,
            )

        created_orders = 0
        if enterprise is not None and engineer is not None:
            # 演示订单必须在演示用户（发布方/工程师）存在之后写入。
            created_orders = await _seed_demo_orders(session, enterprise, engineer)
        await session.commit()

    return SeedResult(
        created_users=tuple(created_users),
        created_roles=tuple(created_roles),
        created_permissions=created_permissions,
        created_orders=created_orders,
    )


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        result = await seed_database(settings, session_factory)
    finally:
        await engine.dispose()
    print(
        "seed done: "
        f"roles+{len(result.created_roles)} {list(result.created_roles)}, "
        f"permissions+{result.created_permissions}, "
        f"users+{len(result.created_users)} {list(result.created_users)}, "
        f"fde_orders+{result.created_orders}"
    )


if __name__ == "__main__":
    asyncio.run(main())
