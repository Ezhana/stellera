"""FDE 订单业务逻辑：申请审批状态机、托管资金流转、权限与查询。

订单状态机（发布者审批申请驱动）：
    open --申请接单 + 发布者通过--> in_progress --申请交付 + 发布者通过--> completed
    open --发布者取消--> cancelled
托管资金：held -> released（交付审批通过）/ refunded（取消）。
端点只负责 HTTP 状态码与实时推送；所有业务规则集中在这里。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import utcnow
from app.models.fde import FdeOrder, FdeOrderApplication, FdeOrderLog
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

APPLICATION_TYPE_ACCEPT = "accept"
APPLICATION_TYPE_DELIVERY = "delivery"

APPLICATION_STATUS_PENDING = "pending"
APPLICATION_STATUS_APPROVED = "approved"
APPLICATION_STATUS_REJECTED = "rejected"
APPLICATION_STATUS_WITHDRAWN = "withdrawn"

ADMIN_ROLE = "admin"


class FdeError(Exception):
    """FDE 业务错误基类；端点按具体子类映射 HTTP 状态码。"""


class FdeNotFoundError(FdeError):
    """资源不存在，对应 HTTP 404。"""


class FdeConflictError(FdeError):
    """状态机冲突（重复申请、状态不允许等），对应 HTTP 409。"""


class FdeForbiddenError(FdeError):
    """已认证但无权执行该业务动作，对应 HTTP 403。"""


@dataclass(frozen=True)
class OrderAggregate:
    """订单 + 工作日志数；列表、写操作响应与实时推送共用。"""

    order: FdeOrder
    work_log_count: int


@dataclass(frozen=True)
class OrderDetail:
    """订单详情：订单、日志数与日志列表、全部申请（均按时间正序）。"""

    order: FdeOrder
    work_log_count: int
    logs: tuple[FdeOrderLog, ...]
    applications: tuple[FdeOrderApplication, ...]


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


@dataclass(frozen=True)
class ApplicationRecord:
    """申请项 + 所属订单的日志数（构造 OrderResponse 需要）。"""

    application: FdeOrderApplication
    work_log_count: int


@dataclass(frozen=True)
class ApplicationPage:
    """分页结果，对应 OrderApplicationListResponse。"""

    items: tuple[ApplicationRecord, ...]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class ApplicationResult:
    """审批 / 撤回结果；order_changed 决定端点是否广播 order.updated。"""

    record: ApplicationRecord
    order_changed: bool


def _order_options() -> list[Any]:
    """订单响应需要的关联：发布企业、接单工程师（用户角色由 selectin 自动预加载）。"""
    return [selectinload(FdeOrder.publisher), selectinload(FdeOrder.engineer)]


def _application_options() -> list[Any]:
    """申请响应的关联：订单（含发布者 / 工程师）、申请人、审批人。"""
    return [
        selectinload(FdeOrderApplication.order).selectinload(FdeOrder.publisher),
        selectinload(FdeOrderApplication.order).selectinload(FdeOrder.engineer),
        selectinload(FdeOrderApplication.applicant),
        selectinload(FdeOrderApplication.reviewer),
    ]


def _build_filters(
    *,
    status: str | None,
    industry: str | None,
    q: str | None,
    publisher_id: int | None,
    engineer_id: int | None = None,
) -> list[Any]:
    """把查询参数翻译成 SQL 条件；列表与计数复用同一组条件。"""
    filters: list[Any] = []
    if publisher_id is not None:
        filters.append(FdeOrder.publisher_id == publisher_id)
    if engineer_id is not None:
        filters.append(FdeOrder.engineer_id == engineer_id)
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


async def _get_application(session: AsyncSession, application_id: int) -> FdeOrderApplication:
    application = (
        await session.execute(
            select(FdeOrderApplication)
            .where(FdeOrderApplication.id == application_id)
            .options(*_application_options())
        )
    ).scalar_one_or_none()
    if application is None:
        raise FdeNotFoundError("申请不存在")
    return application


async def _count_logs(session: AsyncSession, order_id: int) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(FdeOrderLog).where(FdeOrderLog.order_id == order_id)
        )
    ).scalar_one()


async def _log_counts(session: AsyncSession, order_ids: list[int]) -> dict[int, int]:
    """批量统计日志数，避免申请列表逐条查询（N+1）。"""
    if not order_ids:
        return {}
    rows = (
        await session.execute(
            select(FdeOrderLog.order_id, func.count(FdeOrderLog.id))
            .where(FdeOrderLog.order_id.in_(order_ids))
            .group_by(FdeOrderLog.order_id)
        )
    ).all()
    return {int(order_id): int(count) for order_id, count in rows}


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


async def _reject_pending_applications(
    session: AsyncSession,
    *,
    order_id: int,
    application_type: str,
    reviewer_id: int,
    reviewed_at: datetime,
    review_note: str,
    exclude_id: int | None = None,
) -> None:
    """把同一订单下其它 pending 申请批量置为 rejected（审批 / 取消时清理）。"""
    statement = update(FdeOrderApplication).where(
        FdeOrderApplication.order_id == order_id,
        FdeOrderApplication.type == application_type,
        FdeOrderApplication.status == APPLICATION_STATUS_PENDING,
    )
    if exclude_id is not None:
        statement = statement.where(FdeOrderApplication.id != exclude_id)
    await session.execute(
        statement.values(
            status=APPLICATION_STATUS_REJECTED,
            reviewer_id=reviewer_id,
            reviewed_at=reviewed_at,
            review_note=review_note,
        ).execution_options(synchronize_session=False)
    )


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


async def list_orders_by_engineer(
    session: AsyncSession,
    *,
    engineer_id: int,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> OrderPage:
    """“我接到的”：只返回当前用户接单的订单，同样按最新优先。"""
    return await _list_page(
        session,
        filters=_build_filters(
            status=status, industry=None, q=None, publisher_id=None, engineer_id=engineer_id
        ),
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
    """订单详情：附带工作日志与全部申请（形成审批历史），均按时间正序。"""
    order = (
        await session.execute(
            select(FdeOrder)
            .where(FdeOrder.id == order_id)
            .options(
                *_order_options(),
                selectinload(FdeOrder.logs).selectinload(FdeOrderLog.author),
                selectinload(FdeOrder.applications).selectinload(FdeOrderApplication.order),
                selectinload(FdeOrder.applications).selectinload(FdeOrderApplication.applicant),
                selectinload(FdeOrder.applications).selectinload(FdeOrderApplication.reviewer),
            )
        )
    ).scalar_one_or_none()
    if order is None:
        raise FdeNotFoundError("订单不存在")
    logs = tuple(order.logs)
    return OrderDetail(
        order=order,
        work_log_count=len(logs),
        logs=logs,
        applications=tuple(order.applications),
    )


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


async def create_application(
    session: AsyncSession,
    *,
    order_id: int,
    applicant_id: int,
    application_type: str,
    message: str | None,
) -> ApplicationRecord:
    """申请接单 / 申请交付：只创建 pending 申请，不直接改订单状态。"""
    order = await _get_order(session, order_id)
    if application_type == APPLICATION_TYPE_ACCEPT:
        if order.publisher_id == applicant_id:
            raise FdeConflictError("不能申请自己发布的订单")
        if order.status != ORDER_STATUS_OPEN:
            raise FdeConflictError("订单不在待接单状态，无法申请接单")
        duplicate = (
            await session.execute(
                select(FdeOrderApplication.id)
                .where(
                    FdeOrderApplication.order_id == order_id,
                    FdeOrderApplication.applicant_id == applicant_id,
                    FdeOrderApplication.type == APPLICATION_TYPE_ACCEPT,
                    FdeOrderApplication.status == APPLICATION_STATUS_PENDING,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise FdeConflictError("已提交过申请，请等待审批")
    elif application_type == APPLICATION_TYPE_DELIVERY:
        if order.status != ORDER_STATUS_IN_PROGRESS:
            raise FdeConflictError("订单不在进行中，无法申请交付")
        if order.engineer_id != applicant_id:
            raise FdeForbiddenError("只有接单工程师可以申请交付")
        duplicate = (
            await session.execute(
                select(FdeOrderApplication.id)
                .where(
                    FdeOrderApplication.order_id == order_id,
                    FdeOrderApplication.applicant_id == applicant_id,
                    FdeOrderApplication.type == APPLICATION_TYPE_DELIVERY,
                    FdeOrderApplication.status == APPLICATION_STATUS_PENDING,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise FdeConflictError("已提交过交付申请，请等待审批")
    else:
        raise FdeConflictError("未知的申请类型")

    applicant = await session.get(User, applicant_id)
    if applicant is None:
        raise FdeForbiddenError("当前用户不存在或已被禁用")
    application = FdeOrderApplication(
        order=order,
        applicant=applicant,
        type=application_type,
        status=APPLICATION_STATUS_PENDING,
        message=message,
        created_at=utcnow(),
    )
    session.add(application)
    await session.flush()
    await session.commit()
    return ApplicationRecord(
        application=application, work_log_count=await _count_logs(session, order.id)
    )


async def _list_applications(
    session: AsyncSession,
    *,
    filters: list[Any],
    page: int,
    page_size: int,
) -> ApplicationPage:
    statement = (
        select(FdeOrderApplication)
        .where(*filters)
        .options(*_application_options())
        .order_by(FdeOrderApplication.created_at.desc(), FdeOrderApplication.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(statement)).scalars().all()
    total = (
        await session.execute(select(func.count()).select_from(FdeOrderApplication).where(*filters))
    ).scalar_one()
    counts = await _log_counts(session, [row.order_id for row in rows])
    items = tuple(
        ApplicationRecord(application=row, work_log_count=counts.get(row.order_id, 0))
        for row in rows
    )
    return ApplicationPage(items=items, total=total, page=page, page_size=page_size)


async def list_my_applications(
    session: AsyncSession,
    *,
    applicant_id: int,
    type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> ApplicationPage:
    """我发起的申请：可按类型 / 状态过滤，最新在前。"""
    filters: list[Any] = [FdeOrderApplication.applicant_id == applicant_id]
    if type is not None:
        filters.append(FdeOrderApplication.type == type)
    if status is not None:
        filters.append(FdeOrderApplication.status == status)
    return await _list_applications(session, filters=filters, page=page, page_size=page_size)


async def list_received_applications(
    session: AsyncSession,
    *,
    publisher_id: int,
    type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> ApplicationPage:
    """我发布的订单收到的申请：按订单发布者归属过滤。"""
    filters: list[Any] = [
        FdeOrderApplication.order_id.in_(
            select(FdeOrder.id).where(FdeOrder.publisher_id == publisher_id)
        )
    ]
    if type is not None:
        filters.append(FdeOrderApplication.type == type)
    if status is not None:
        filters.append(FdeOrderApplication.status == status)
    return await _list_applications(session, filters=filters, page=page, page_size=page_size)


async def approve_application(
    session: AsyncSession,
    *,
    application_id: int,
    actor_id: int,
    note: str | None = None,
) -> ApplicationResult:
    """发布者（或管理员）通过申请：接单 -> in_progress，交付 -> completed + 结算。"""
    application = await _get_application(session, application_id)
    order = application.order
    await _require_publisher_or_admin(session, order, actor_id, action="审批申请")
    if application.status != APPLICATION_STATUS_PENDING:
        raise FdeConflictError("申请已处理，无法重复审批")
    reviewer = await session.get(User, actor_id)
    if reviewer is None:
        raise FdeForbiddenError("当前用户不存在或已被禁用")

    now = utcnow()
    if application.type == APPLICATION_TYPE_ACCEPT:
        if order.status != ORDER_STATUS_OPEN:
            raise FdeConflictError("订单已被接单或状态已变化")
        order.engineer = application.applicant
        order.status = ORDER_STATUS_IN_PROGRESS
        order.claimed_at = now
        order.updated_at = now
        await _reject_pending_applications(
            session,
            order_id=order.id,
            application_type=APPLICATION_TYPE_ACCEPT,
            reviewer_id=actor_id,
            reviewed_at=now,
            review_note="订单已被其他申请人接单",
            exclude_id=application.id,
        )
    elif application.type == APPLICATION_TYPE_DELIVERY:
        if order.status != ORDER_STATUS_IN_PROGRESS:
            raise FdeConflictError("订单不在进行中，无法确认交付")
        order.status = ORDER_STATUS_COMPLETED
        order.escrow_status = ESCROW_STATUS_RELEASED
        order.completed_at = now
        order.updated_at = now
        # 只有真实扣过托管款的订单才放款；历史/直接写库的订单不凭空结算。
        if order.engineer_id is not None and await wallet_service.has_order_payment(
            session, order.id
        ):
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
        await _reject_pending_applications(
            session,
            order_id=order.id,
            application_type=APPLICATION_TYPE_DELIVERY,
            reviewer_id=actor_id,
            reviewed_at=now,
            review_note="订单已完成交付",
            exclude_id=application.id,
        )
    else:
        raise FdeConflictError("未知的申请类型")

    application.status = APPLICATION_STATUS_APPROVED
    application.reviewer = reviewer
    application.reviewed_at = now
    application.review_note = note
    await session.flush()
    await session.commit()
    return ApplicationResult(
        record=ApplicationRecord(
            application=application,
            work_log_count=await _count_logs(session, order.id),
        ),
        order_changed=True,
    )


async def reject_application(
    session: AsyncSession,
    *,
    application_id: int,
    actor_id: int,
    note: str | None = None,
) -> ApplicationResult:
    """发布者（或管理员）驳回申请：订单状态不变。"""
    application = await _get_application(session, application_id)
    await _require_publisher_or_admin(session, application.order, actor_id, action="审批申请")
    if application.status != APPLICATION_STATUS_PENDING:
        raise FdeConflictError("申请已处理，无法重复审批")
    reviewer = await session.get(User, actor_id)
    if reviewer is None:
        raise FdeForbiddenError("当前用户不存在或已被禁用")

    now = utcnow()
    application.status = APPLICATION_STATUS_REJECTED
    application.reviewer = reviewer
    application.reviewed_at = now
    application.review_note = note
    await session.flush()
    await session.commit()
    return ApplicationResult(
        record=ApplicationRecord(
            application=application,
            work_log_count=await _count_logs(session, application.order_id),
        ),
        order_changed=False,
    )


async def withdraw_application(
    session: AsyncSession,
    *,
    application_id: int,
    actor_id: int,
) -> ApplicationResult:
    """申请人本人撤回 pending 申请：订单状态不变。"""
    application = await _get_application(session, application_id)
    if application.applicant_id != actor_id:
        raise FdeForbiddenError("只有申请人可以撤回申请")
    if application.status != APPLICATION_STATUS_PENDING:
        raise FdeConflictError("申请已处理，无法撤回")

    application.status = APPLICATION_STATUS_WITHDRAWN
    await session.flush()
    await session.commit()
    return ApplicationResult(
        record=ApplicationRecord(
            application=application,
            work_log_count=await _count_logs(session, application.order_id),
        ),
        order_changed=False,
    )


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


async def cancel_order(session: AsyncSession, *, order_id: int, actor_id: int) -> OrderAggregate:
    """发布方（或管理员）取消待接单订单：open -> cancelled，退款并驳回 pending 申请。"""
    order = await _get_order(session, order_id)
    if order.status != ORDER_STATUS_OPEN:
        raise FdeConflictError("订单不在待接单状态，无法取消")
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
    # 取消后该订单不再需要任何待审批的接单申请。
    await _reject_pending_applications(
        session,
        order_id=order.id,
        application_type=APPLICATION_TYPE_ACCEPT,
        reviewer_id=actor_id,
        reviewed_at=now,
        review_note="订单已取消",
    )
    await session.flush()
    await session.commit()
    return OrderAggregate(order=order, work_log_count=await _count_logs(session, order.id))


__all__ = [
    "APPLICATION_STATUS_APPROVED",
    "APPLICATION_STATUS_PENDING",
    "APPLICATION_STATUS_REJECTED",
    "APPLICATION_STATUS_WITHDRAWN",
    "APPLICATION_TYPE_ACCEPT",
    "APPLICATION_TYPE_DELIVERY",
    "ApplicationPage",
    "ApplicationRecord",
    "ApplicationResult",
    "FdeConflictError",
    "FdeError",
    "FdeForbiddenError",
    "FdeNotFoundError",
    "OrderAggregate",
    "OrderDetail",
    "OrderPage",
    "WorkLogResult",
    "add_work_log",
    "approve_application",
    "cancel_order",
    "create_application",
    "create_order",
    "get_order_detail",
    "list_my_applications",
    "list_orders",
    "list_orders_by_engineer",
    "list_orders_by_publisher",
    "list_received_applications",
    "reject_application",
    "withdraw_application",
]
