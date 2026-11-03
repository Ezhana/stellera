"""钱包端点：汇总、流水分页与兑换码入账。

任意已登录用户都可以访问自己的钱包；权限由 RBAC 种子授予 authenticated。
HTTP 语义（状态码、响应模型）只在这里处理，业务规则集中在 app/services/wallet.py。
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUserDep, SessionDep
from app.models.base import ensure_utc
from app.models.wallet import WalletTransaction
from app.schemas.wallet import (
    RedeemRequest,
    RedeemResponse,
    TransactionDirection,
    TransactionType,
    WalletSummaryResponse,
    WalletTransactionListResponse,
    WalletTransactionResponse,
)
from app.services import wallet as wallet_service
from app.services.wallet import (
    TransactionPage,
    WalletError,
    WalletNotFoundError,
    WalletSummary,
)

router = APIRouter(prefix="/wallet", tags=["wallet"])


def _transaction_response(transaction: WalletTransaction) -> WalletTransactionResponse:
    return WalletTransactionResponse(
        id=transaction.id,
        type=cast(TransactionType, transaction.type),
        direction=cast(TransactionDirection, transaction.direction),
        amount_cents=transaction.amount_cents,
        balance_after_cents=transaction.balance_after_cents,
        description=transaction.description,
        reference_type=transaction.reference_type,
        reference_id=transaction.reference_id,
        created_at=ensure_utc(transaction.created_at),
    )


def _summary_response(summary: WalletSummary) -> WalletSummaryResponse:
    return WalletSummaryResponse(
        balance_cents=summary.balance_cents,
        usage_total_cents=summary.usage_total_cents,
        recharge_total_cents=summary.recharge_total_cents,
        redeem_total_cents=summary.redeem_total_cents,
        income_total_cents=summary.income_total_cents,
        recharge_enabled=summary.recharge_enabled,
        recharge_note=summary.recharge_note,
        support_contact=summary.support_contact,
    )


def _page_response(page: TransactionPage) -> WalletTransactionListResponse:
    return WalletTransactionListResponse(
        items=[_transaction_response(item) for item in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


def _http_error(exc: WalletError) -> HTTPException:
    """把业务错误映射为 HTTP 状态码：资源不存在 404，其余冲突 409。"""
    if isinstance(exc, WalletNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    else:
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=status_code, detail=str(exc))


@router.get("", response_model=WalletSummaryResponse)
async def get_wallet_summary(
    principal: CurrentUserDep,
    session: SessionDep,
) -> WalletSummaryResponse:
    """我的钱包：余额、收支分类合计与充值入口说明。"""
    try:
        summary = await wallet_service.get_summary(session, principal.user_id)
    except WalletError as exc:
        raise _http_error(exc) from exc
    return _summary_response(summary)


@router.get("/transactions", response_model=WalletTransactionListResponse)
async def list_wallet_transactions(
    principal: CurrentUserDep,
    session: SessionDep,
    type_filter: Annotated[TransactionType | None, Query(alias="type")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WalletTransactionListResponse:
    """我的流水：最新在前，可按资金类型过滤与分页。"""
    try:
        result = await wallet_service.list_transactions(
            session,
            principal.user_id,
            type=type_filter,
            page=page,
            page_size=page_size,
        )
    except WalletError as exc:
        raise _http_error(exc) from exc
    return _page_response(result)


@router.post("/redeem", response_model=RedeemResponse)
async def redeem_code(
    payload: RedeemRequest,
    principal: CurrentUserDep,
    session: SessionDep,
) -> RedeemResponse:
    """兑换码入账：码不存在 404，已用 / 停用 / 过期 / 余额冲突 409。"""
    try:
        result = await wallet_service.redeem(session, principal.user_id, payload.code)
    except WalletError as exc:
        raise _http_error(exc) from exc
    return RedeemResponse(
        amount_cents=result.amount_cents,
        balance_cents=result.balance_cents,
        transaction=_transaction_response(result.transaction),
    )


__all__ = ["router"]
