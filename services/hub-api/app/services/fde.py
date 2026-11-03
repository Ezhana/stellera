"""FDE 订单业务逻辑：状态机、托管资金流转、权限与查询。

订单状态机：
    open --claim--> in_progress --complete--> completed
    open --cancel--> cancelled
托管资金：held -> released（complete）/ refunded（cancel）。
端点只负责 HTTP 状态码与实时推送；所有业务规则集中在这里。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import utcnow
from app.models.fde import FdeOrder, FdeOrderLog
from app.models.user import User
from app.rbac.enforcer import load_user_role_names
from app.services import wallet as wallet_service

ORDER_STATUS_OPEN = "open"
ORDER_STATUS_IN_PROGRESS = "in_progress"
ORDER_STATUS_COMPLETED = "completed"
ORDER_STATUS_CANCELLED = "cancelled"

ESCROW_STATUS_HELD = "held"
ESCROW_STATUS_RELEASED = "released"
ESCROW_STATUS_REFUNDED = "refunded"

ADMIN_ROLE = "admin"


class FdeError(Exception):
    """FDE 业务错误基类；端点按具体子类映射 HTTP 状态码。"""


class FdeNotFoundError(FdeError):
    """资源不存在，对应 HTTP 404。"""


class FdeConflictError(FdeError):
    """状态机冲突（已认领、状态不允许等），对应 HTTP 409。"""


class FdeForbiddenError(FdeError):
    """已认证但无权执行该业务动作，对应 HTTP 403。"""


@dataclass(frozen=True)
class OrderAggregate:
    """订单 + 工作日志数；列表、写操作响应与实时推送共用。"""

    order: FdeOrder
    work_log_count: int


@dataclass(frozen=True)
class OrderDetail:
    """订单详情：订单、日志数与日志列表（按时间正序）。"""

    order: FdeOrder
    work_log_count: int
    logs: tuple[FdeOrderLog, ...]


@dataclass(frozen=True)
class OrderPage:
    """分页结果，对应 OrderListResponse。"""

    items: tuple[OrderAggregate, ...]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class WorkLogResult:
    """提交日志的结果：新日志 + 刷新过日志数的订单（用于推送）。"""

    log: FdeOrderLog
    order: OrderAggregate


def _order_options() -> list[Any]:
    """订单响应需要的关联：发布企业、接单工程师。"""
    return [selectinload(FdeOrder.publisher), selectinload(FdeOrder.engineer)]


def _build_filters(
    *,
    status: str | None,
    industry: str | None,
    q: str | None,
    publisher_id: int | None,
) -> list[Any]:
    """把查询参数翻译成 SQL 条件；列表与计数复用同一组条件。"""
    filters: list[Any] = []
    if publisher_id is not None:
        filters.append(FdeOrder.publisher_id == publisher_id)
    if status is not None:
        filters.append(FdeOrder.status == status)
    if industry is not None:
        filters.append(FdeOrder.industry == industry)
    if q is not None and q.strip():
        # 关键字在标题/单号/行业上做大小写不敏感的子串匹配（SQLite/PostgreSQL 都支持）。
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                FdeOrder.title.ilike(pattern),
                FdeOrder.code.ilike(pattern),
                FdeOrder.industry.ilike(pattern),
            )
        )
    return filters


async def _get_order(session: AsyncSession, order_id: int) -> FdeOrder:
    order = (
        await session.execute(
            select(FdeOrder).where(FdeOrder.id == order_id).options(*_order_options())
        )
    ).scalar_one_or_none()
    if order is None:
        raise FdeNotFoundError("订单不存在")
    return order


async def _count_logs(session: AsyncSession, order_id: int) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(FdeOrderLog).where(FdeOrderLog.order_id == order_id)
        )
    ).scalar_one()


async def _is_admin(session: AsyncSession, user_id: int) -> bool:
    return ADMIN_ROLE in await load_user_role_names(session, user_id)


async def _require_publisher_or_admin(
    session: AsyncSession, order: FdeOrder, actor_id: int, *, action: str
) -> None:
    if order.publisher_id == actor_id:
        return
    if await _is_admin(session, actor_id):
        return
    raise FdeForbiddenError(f"只有发布者可以{action}")


async def _next_order_code(session: AsyncSession) -> str:
    """生成 FDE-<year>-<4 位序号>；演示数据用 FDE-DEMO-* 前缀，不会冲突。"""
    prefix = f"FDE-{utcnow().year}-"
    existing = set(
        (
            await session.execute(select(FdeOrder.code).where(FdeOrder.code.like(f"{prefix}%")))
        ).scalars()
    )
    sequence = 1
    while f"{prefix}{sequence:04d}" in existing:
        sequence += 1
    return f"{prefix}{sequence:04d}"


async def list_orders(
    session: AsyncSession,
    *,
    status: str | None = None,
    industry: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> OrderPage:
    """订单大厅：按发布时间倒序分页。"""
    return await _list_page(
        session,
        filters=_build_filters(status=status, industry=industry, q=q, publisher_id=None),
        page=page,
        page_size=page_size,
    )


async def list_orders_by_publisher(
    session: AsyncSession,
    *,
    publisher_id: int,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> OrderPage:
    """“我发布的”：只返回当前用户发布的订单，同样按最新优先。"""
    return await _list_page(
        session,
        filters=_build_filters(status=status, industry=None, q=None, publisher_id=publisher_id),
        page=page,
        page_size=page_size,
    )


async def _list_page(
    session: AsyncSession, *, filters: list[Any], page: int, page_size: int
) -> OrderPage:
    # 日志数量用聚合子查询 join，避免每个订单再查一次（N+1）。
    log_counts = (
        select(FdeOrderLog.order_id, func.count(FdeOrderLog.id).label("log_count"))
        .group_by(FdeOrderLog.order_id)
        .subquery()
    )
    statement = (
        select(FdeOrder, func.coalesce(log_counts.c.log_count, 0))
        .outerjoin(log_counts, log_counts.c.order_id == FdeOrder.id)
        .where(*filters)
        .options(*_order_options())
        .order_by(FdeOrder.created_at.desc(), FdeOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(statement)).all()
    total = (
        await session.execute(select(func.count()).select_from(FdeOrder).where(*filters))
    ).scalar_one()

    items = tuple(OrderAggregate(order=row[0], work_log_count=int(row[1])) for row in rows)
    return OrderPage(items=items, total=total, page=page, page_size=page_size)


async def get_order_detail(session: AsyncSession, order_id: int) -> OrderDetail:
    """订单详情：附带工作日志（最旧在前）。"""
    order = (
        await session.execute(
            select(FdeOrder)
            .where(FdeOrder.id == order_id)
            .options(
                *_order_options(),
                selectinload(FdeOrder.logs).selectinload(FdeOrderLog.author),
            )
        )
    ).scalar_one_or_none()
    if order is None:
        raise FdeNotFoundError("订单不存在")
    logs = tuple(order.logs)
    return OrderDetail(order=order, work_log_count=len(logs), logs=logs)


async def create_order(
    session: AsyncSession,
    *,
    publisher_id: int,
    title: str,
    industry: str,
    description: str,
    delivery_days: int,
    price_cents: int,
) -> OrderAggregate:
    """发布需求：创建者即发布方，初始 open + 托管 held。"""
    publisher = await session.get(User, publisher_id)
    if publisher is None:
        raise FdeNotFoundError("发布者不存在")
    now = utcnow()
    order = FdeOrder(
        code=await _next_order_code(session),
        title=title,
        industry=industry,
        description=description,
        delivery_days=delivery_days,
        price_cents=price_cents,
        status=ORDER_STATUS_OPEN,
        escrow_status=ESCROW_STATUS_HELD,
        publisher=publisher,
        created_at=now,
        updated_at=now,
    )
    session.add(order)
    await session.flush()
    # 发布即扣款托管：与订单创建同一事务，余额不足时整单不落库。
    try:
        wallet = await wallet_service.get_or_create_wallet(session, publisher_id, for_update=True)
        await wallet_service.debit(
            session,
            wallet,
            price_cents,
            type=wallet_service.TRANSACTION_TYPE_ORDER_PAYMENT,
            description=f"发布订单 {order.code} 托管",
            reference_type=wallet_service.REFERENCE_TYPE_FDE_ORDER,
            reference_id=order.id,
            created_at=now,
        )
    except wallet_service.WalletConflictError as exc:
        raise FdeConflictError("钱包余额不足，请先充值或兑换") from exc
    await session.commit()
    return OrderAggregate(order=order, work_log_count=0)


async def claim_order(session: AsyncSession, *, order_id: int, actor_id: int) -> OrderAggregate:
    """工程师认领一个待认领订单。"""
    order = await _get_order(session, order_id)
    if order.publisher_id == actor_id:
        raise FdeConflictError("不能认领自己发布的订单")
    if order.status != ORDER_STATUS_OPEN or order.engineer_id is not None:
        raise FdeConflictError("订单已被认领或当前状态不可认领")
    engineer = await session.get(User, actor_id)
    if engineer is None:
        raise FdeForbiddenError("当前用户不存在或已被禁用")

    now = utcnow()
    order.engineer = engineer
    order.status = ORDER_STATUS_IN_PROGRESS
    order.claimed_at = now
    order.updated_at = now
    await session.flush()
    await session.commit()
    return OrderAggregate(order=order, work_log_count=await _count_logs(session, order.id))


async def add_work_log(
    session: AsyncSession,
    *,
    order_id: int,
    actor_id: int,
    content: str,
    worked_hours: float | None,
) -> WorkLogResult:
    """接单工程师（或管理员）在订单进行中提交工作日志。"""
    order = await _get_order(session, order_id)
    if order.status != ORDER_STATUS_IN_PROGRESS:
        raise FdeConflictError("订单不在进行中，无法提交工作日志")
    is_admin = await _is_admin(session, actor_id)
    if order.engineer_id != actor_id and not is_admin:
        raise FdeForbiddenError("只有接单工程师可以提交工作日志")

    author = await session.get(User, actor_id)
    if author is None:
        raise FdeForbiddenError("当前用户不存在或已被禁用")
    now = utcnow()
    log = FdeOrderLog(
        order_id=order.id,
        author=author,
        content=content,
        worked_hours=worked_hours,
        created_at=now,
    )
    # 有新日志意味着订单有活动，同步刷新 updated_at（大厅与详情都展示该字段）。
    order.updated_at = now
    session.add(log)
    await session.flush()
    await session.commit()
    aggregate = OrderAggregate(order=order, work_log_count=await _count_logs(session, order.id))
    return WorkLogResult(log=log, order=aggregate)


async def complete_order(session: AsyncSession, *, order_id: int, actor_id: int) -> OrderAggregate:
    """发布方（或管理员）确认交付：in_progress -> completed，托管资金放款。"""
    order = await _get_order(session, order_id)
    if order.status != ORDER_STATUS_IN_PROGRESS:
        raise FdeConflictError("订单不在进行中，无法完成")
    await _require_publisher_or_admin(session, order, actor_id, action="完成订单")

    now = utcnow()
    order.status = ORDER_STATUS_COMPLETED
    order.escrow_status = ESCROW_STATUS_RELEASED
    order.completed_at = now
    order.updated_at = now
    # 只有真实扣过托管款的订单才放款；历史/直接写库的订单不凭空结算。
    if order.engineer_id is not None and await wallet_service.has_order_payment(session, order.id):
        wallet = await wallet_service.get_or_create_wallet(
            session, order.engineer_id, for_update=True
        )
        await wallet_service.credit(
            session,
            wallet,
            order.price_cents,
            type=wallet_service.TRANSACTION_TYPE_ORDER_SETTLEMENT,
            description=f"订单 {order.code} 结算",
            reference_type=wallet_service.REFERENCE_TYPE_FDE_ORDER,
            reference_id=order.id,
            created_at=now,
        )
    await session.flush()
    await session.commit()
    return OrderAggregate(order=order, work_log_count=await _count_logs(session, order.id))


async def cancel_order(session: AsyncSession, *, order_id: int, actor_id: int) -> OrderAggregate:
    """发布方（或管理员）取消待认领订单：open -> cancelled，托管资金退回。"""
    order = await _get_order(session, order_id)
    if order.status != ORDER_STATUS_OPEN:
        raise FdeConflictError("订单不在待认领状态，无法取消")
    await _require_publisher_or_admin(session, order, actor_id, action="取消订单")

    now = utcnow()
    order.status = ORDER_STATUS_CANCELLED
    order.escrow_status = ESCROW_STATUS_REFUNDED
    order.updated_at = now
    # 只有真实扣过托管款的订单才退款；历史/直接写库的订单不凭空退款。
    if await wallet_service.has_order_payment(session, order.id):
        wallet = await wallet_service.get_or_create_wallet(
            session, order.publisher_id, for_update=True
        )
        await wallet_service.credit(
            session,
            wallet,
            order.price_cents,
            type=wallet_service.TRANSACTION_TYPE_ORDER_REFUND,
            description=f"取消订单 {order.code} 退款",
            reference_type=wallet_service.REFERENCE_TYPE_FDE_ORDER,
            reference_id=order.id,
            created_at=now,
        )
    await session.flush()
    await session.commit()
    return OrderAggregate(order=order, work_log_count=await _count_logs(session, order.id))


__all__ = [
    "FdeConflictError",
    "FdeError",
    "FdeForbiddenError",
    "FdeNotFoundError",
    "OrderAggregate",
    "OrderDetail",
    "OrderPage",
    "WorkLogResult",
    "add_work_log",
    "cancel_order",
    "claim_order",
    "complete_order",
    "create_order",
    "get_order_detail",
    "list_orders",
    "list_orders_by_publisher",
]
