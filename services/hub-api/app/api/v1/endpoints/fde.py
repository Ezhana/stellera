"""FDE 订单端点：订单大厅、我发布的、我接到的、发布 / 取消 / 工作日志 /
申请接单 / 申请交付 / 我的申请 / 收到的申请 / 审批 + 实时推送。

路由声明顺序很重要：`/orders/mine`、`/orders/assigned` 必须放在
`/orders/{order_id}` 之前，否则会被路径参数当作订单 id 吞掉。HTTP 语义
（状态码、响应模型）只在这里处理，业务规则集中在 app/services/fde.py。

实时推送走 `WebSocket /api/v1/fde/ws?token=<access_token>`：浏览器 WebSocket
无法设置 Authorization 头，因此令牌从 query 读取并用 app 的 TokenService 校验
（Casbin 中间件只覆盖 HTTP scope，不会拦 WebSocket）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.summaries import user_ref
from app.models.base import ensure_utc
from app.models.fde import FdeOrderLog
from app.realtime.hub import RealtimeHub
from app.schemas.fde import (
    ApplicationReviewRequest,
    ApplicationStatus,
    ApplicationType,
    EscrowStatus,
    OrderApplicationCreateRequest,
    OrderApplicationListResponse,
    OrderApplicationResponse,
    OrderCreateRequest,
    OrderDetailResponse,
    OrderListResponse,
    OrderResponse,
    OrderStatus,
    WorkLogCreateRequest,
    WorkLogResponse,
)
from app.security.tokens import TokenError
from app.services import fde as fde_service
from app.services.fde import (
    ApplicationRecord,
    FdeError,
    FdeForbiddenError,
    FdeNotFoundError,
    OrderAggregate,
    OrderDetail,
    OrderPage,
)

router = APIRouter(prefix="/fde", tags=["fde"])

# 自定义关闭码：令牌缺失/无效时通知浏览器清理会话并跳转登录。
WS_CLOSE_UNAUTHORIZED = 4401
# 1013 = Try Again Later：服务尚未完成初始化（拿不到实时推送 hub）。
WS_CLOSE_UNAVAILABLE = 1013


def _order_response(aggregate: OrderAggregate) -> OrderResponse:
    order = aggregate.order
    return OrderResponse(
        id=order.id,
        code=order.code,
        title=order.title,
        industry=order.industry,
        description=order.description,
        delivery_days=order.delivery_days,
        price_cents=order.price_cents,
        status=cast(OrderStatus, order.status),
        escrow_status=cast(EscrowStatus, order.escrow_status),
        publisher=user_ref(order.publisher),
        engineer=user_ref(order.engineer) if order.engineer is not None else None,
        work_log_count=aggregate.work_log_count,
        created_at=ensure_utc(order.created_at),
        updated_at=ensure_utc(order.updated_at),
        claimed_at=ensure_utc(order.claimed_at) if order.claimed_at else None,
        completed_at=ensure_utc(order.completed_at) if order.completed_at else None,
    )


def _log_response(log: FdeOrderLog) -> WorkLogResponse:
    return WorkLogResponse(
        id=log.id,
        order_id=log.order_id,
        author=user_ref(log.author),
        content=log.content,
        worked_hours=log.worked_hours,
        created_at=ensure_utc(log.created_at),
    )


def _page_response(page: OrderPage) -> OrderListResponse:
    return OrderListResponse(
        items=[_order_response(item) for item in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


def _detail_response(detail: OrderDetail) -> OrderDetailResponse:
    aggregate = OrderAggregate(order=detail.order, work_log_count=detail.work_log_count)
    return OrderDetailResponse(
        **_order_response(aggregate).model_dump(),
        logs=[_log_response(log) for log in detail.logs],
        applications=[
            _application_response(
                ApplicationRecord(
                    application=application,
                    work_log_count=detail.work_log_count,
                )
            )
            for application in detail.applications
        ],
    )


def _application_response(record: ApplicationRecord) -> OrderApplicationResponse:
    application = record.application
    return OrderApplicationResponse(
        id=application.id,
        order=_order_response(
            OrderAggregate(order=application.order, work_log_count=record.work_log_count)
        ),
        type=cast(ApplicationType, application.type),
        status=cast(ApplicationStatus, application.status),
        message=application.message,
        review_note=application.review_note,
        applicant=user_ref(application.applicant),
        reviewer=user_ref(application.reviewer) if application.reviewer is not None else None,
        reviewed_at=ensure_utc(application.reviewed_at) if application.reviewed_at else None,
        created_at=ensure_utc(application.created_at),
    )


def _application_list_response(page: fde_service.ApplicationPage) -> OrderApplicationListResponse:
    return OrderApplicationListResponse(
        items=[_application_response(item) for item in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


def _note(payload: ApplicationReviewRequest | None) -> str | None:
    if payload is None or payload.note is None:
        return None
    note = payload.note.strip()
    return note or None


def _http_error(exc: FdeError) -> HTTPException:
    """把业务错误映射为 HTTP 状态码：404 / 403 / 409。"""
    if isinstance(exc, FdeNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, FdeForbiddenError):
        status_code = status.HTTP_403_FORBIDDEN
    else:
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=status_code, detail=str(exc))


async def _broadcast(request: Request, event_type: str, aggregate: OrderAggregate) -> None:
    """向所有在线客户端广播一条订单事件；hub 未就绪时静默跳过。"""
    hub: RealtimeHub | None = getattr(request.app.state, "realtime_hub", None)
    if hub is None:
        return
    await hub.broadcast(
        {"type": event_type, "order": _order_response(aggregate).model_dump(mode="json")}
    )


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    _principal: CurrentUserDep,
    session: SessionDep,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
    industry: Annotated[str | None, Query(max_length=64)] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderListResponse:
    """订单大厅：支持状态 / 行业 / 关键字过滤与分页，最新发布优先。"""
    result = await fde_service.list_orders(
        session,
        status=status_filter,
        industry=industry,
        q=q,
        page=page,
        page_size=page_size,
    )
    return _page_response(result)


@router.get("/orders/mine", response_model=OrderListResponse)
async def list_my_orders(
    principal: CurrentUserDep,
    session: SessionDep,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderListResponse:
    """我发布的：只返回当前用户发布的订单。"""
    result = await fde_service.list_orders_by_publisher(
        session,
        publisher_id=principal.user_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return _page_response(result)


@router.get("/orders/assigned", response_model=OrderListResponse)
async def list_assigned_orders(
    principal: CurrentUserDep,
    session: SessionDep,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderListResponse:
    """我接到的：只返回当前用户接单的订单。"""
    result = await fde_service.list_orders_by_engineer(
        session,
        engineer_id=principal.user_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return _page_response(result)


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: int,
    _principal: CurrentUserDep,
    session: SessionDep,
) -> OrderDetailResponse:
    """订单详情：附带工作日志（最旧在前）。"""
    try:
        detail = await fde_service.get_order_detail(session, order_id)
    except FdeError as exc:
        raise _http_error(exc) from exc
    return _detail_response(detail)


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    payload: OrderCreateRequest,
    request: Request,
    principal: CurrentUserDep,
    session: SessionDep,
) -> OrderResponse:
    """发布需求：发布者自动成为 publisher，初始 open + 托管 held。"""
    try:
        aggregate = await fde_service.create_order(
            session,
            publisher_id=principal.user_id,
            title=payload.title,
            industry=payload.industry,
            description=payload.description,
            delivery_days=payload.delivery_days,
            price_cents=payload.price_cents,
        )
    except FdeError as exc:
        raise _http_error(exc) from exc
    await _broadcast(request, "order.created", aggregate)
    return _order_response(aggregate)


@router.post(
    "/orders/{order_id}/applications",
    response_model=OrderApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_application(
    order_id: int,
    payload: OrderApplicationCreateRequest,
    principal: CurrentUserDep,
    session: SessionDep,
) -> OrderApplicationResponse:
    """申请接单（accept）或申请交付（delivery）：只落 pending 申请，不直接改订单状态。"""
    try:
        record = await fde_service.create_application(
            session,
            order_id=order_id,
            applicant_id=principal.user_id,
            application_type=payload.type,
            message=payload.message.strip() if payload.message else None,
        )
    except FdeError as exc:
        raise _http_error(exc) from exc
    return _application_response(record)


@router.post(
    "/orders/{order_id}/logs",
    response_model=WorkLogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_work_log(
    order_id: int,
    payload: WorkLogCreateRequest,
    request: Request,
    principal: CurrentUserDep,
    session: SessionDep,
) -> WorkLogResponse:
    """接单工程师提交工作日志；推送刷新后的 work_log_count。"""
    try:
        result = await fde_service.add_work_log(
            session,
            order_id=order_id,
            actor_id=principal.user_id,
            content=payload.content,
            worked_hours=payload.worked_hours,
        )
    except FdeError as exc:
        raise _http_error(exc) from exc
    await _broadcast(request, "order.updated", result.order)
    return _log_response(result.log)


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: int,
    request: Request,
    principal: CurrentUserDep,
    session: SessionDep,
) -> OrderResponse:
    """发布者取消待接单订单：open -> cancelled，托管资金 refunded，pending 申请驳回。"""
    try:
        aggregate = await fde_service.cancel_order(
            session, order_id=order_id, actor_id=principal.user_id
        )
    except FdeError as exc:
        raise _http_error(exc) from exc
    await _broadcast(request, "order.updated", aggregate)
    return _order_response(aggregate)


@router.get("/applications/mine", response_model=OrderApplicationListResponse)
async def list_my_applications(
    principal: CurrentUserDep,
    session: SessionDep,
    type_filter: Annotated[ApplicationType | None, Query(alias="type")] = None,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderApplicationListResponse:
    """我发起的申请：可按类型 / 状态过滤，最新在前。"""
    result = await fde_service.list_my_applications(
        session,
        applicant_id=principal.user_id,
        type=type_filter,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return _application_list_response(result)


@router.get("/applications/received", response_model=OrderApplicationListResponse)
async def list_received_applications(
    principal: CurrentUserDep,
    session: SessionDep,
    type_filter: Annotated[ApplicationType | None, Query(alias="type")] = None,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderApplicationListResponse:
    """我发布的订单收到的申请：可按类型 / 状态过滤，最新在前。"""
    result = await fde_service.list_received_applications(
        session,
        publisher_id=principal.user_id,
        type=type_filter,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return _application_list_response(result)


@router.post(
    "/applications/{application_id}/approve",
    response_model=OrderApplicationResponse,
)
async def approve_application(
    application_id: int,
    request: Request,
    principal: CurrentUserDep,
    session: SessionDep,
    payload: ApplicationReviewRequest | None = None,
) -> OrderApplicationResponse:
    """发布者（或管理员）通过申请；订单状态变化时广播 order.updated。"""
    try:
        result = await fde_service.approve_application(
            session,
            application_id=application_id,
            actor_id=principal.user_id,
            note=_note(payload),
        )
    except FdeError as exc:
        raise _http_error(exc) from exc
    if result.order_changed:
        await _broadcast(
            request,
            "order.updated",
            OrderAggregate(
                order=result.record.application.order,
                work_log_count=result.record.work_log_count,
            ),
        )
    return _application_response(result.record)


@router.post(
    "/applications/{application_id}/reject",
    response_model=OrderApplicationResponse,
)
async def reject_application(
    application_id: int,
    principal: CurrentUserDep,
    session: SessionDep,
    payload: ApplicationReviewRequest | None = None,
) -> OrderApplicationResponse:
    """发布者（或管理员）驳回申请：订单状态不变，不广播。"""
    try:
        result = await fde_service.reject_application(
            session,
            application_id=application_id,
            actor_id=principal.user_id,
            note=_note(payload),
        )
    except FdeError as exc:
        raise _http_error(exc) from exc
    return _application_response(result.record)


@router.post(
    "/applications/{application_id}/withdraw",
    response_model=OrderApplicationResponse,
)
async def withdraw_application(
    application_id: int,
    principal: CurrentUserDep,
    session: SessionDep,
) -> OrderApplicationResponse:
    """申请人本人撤回 pending 申请：订单状态不变，不广播。"""
    try:
        result = await fde_service.withdraw_application(
            session, application_id=application_id, actor_id=principal.user_id
        )
    except FdeError as exc:
        raise _http_error(exc) from exc
    return _application_response(result.record)


@router.websocket("/ws")
async def order_feed(
    websocket: WebSocket,
    token: Annotated[str | None, Query()] = None,
) -> None:
    """订单实时推送：query 参数携带 access token；连接后先发 connected 帧。

    鉴权失败必须“先 accept 再 close(4401)”：浏览器只有在完成握手后才能观察到
    自定义关闭码；握手阶段直接拒绝只会得到 1006，前端无法据此停止重连。
    """
    hub: RealtimeHub | None = getattr(websocket.app.state, "realtime_hub", None)
    token_service = websocket.app.state.token_service
    user_token = token.strip() if token else ""

    if hub is None:
        await websocket.close(code=WS_CLOSE_UNAVAILABLE)
        return

    await websocket.accept()
    if not user_token:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return
    try:
        token_service.decode_access_token(user_token)
    except TokenError:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return

    await hub.connect(websocket)
    server_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        await websocket.send_json({"type": "connected", "server_time": server_time})
        while True:
            # 协议目前没有上行消息；持续读取只为感知断开（客户端主动关闭会抛异常）。
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(websocket)


__all__ = ["router"]
