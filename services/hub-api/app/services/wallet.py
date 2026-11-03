"""钱包业务逻辑：余额、流水、汇总与兑换码入账。

余额变更与流水写入必须在同一事务内完成；本模块的函数只 flush，不 commit，
由调用方（端点 / FDE 服务 / 种子脚本）决定事务边界。
在线充值永远不开放：`ONLINE_RECHARGE_ENABLED` 恒为 False，充值只能走线下兑换码。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import ensure_utc, utcnow
from app.models.redeem import RedeemCode
from app.models.user import User
from app.models.wallet import Wallet, WalletTransaction
from app.services.system_settings import get_settings_map

TRANSACTION_TYPE_RECHARGE = "recharge"
TRANSACTION_TYPE_REDEEM = "redeem"
TRANSACTION_TYPE_ORDER_PAYMENT = "order_payment"
TRANSACTION_TYPE_ORDER_REFUND = "order_refund"
TRANSACTION_TYPE_ORDER_SETTLEMENT = "order_settlement"

DIRECTION_CREDIT = "credit"
DIRECTION_DEBIT = "debit"

REDEEM_STATUS_ACTIVE = "active"
REDEEM_STATUS_USED = "used"
REDEEM_STATUS_DISABLED = "disabled"

# FDE 订单资金事件在流水中的业务来源标识。
REFERENCE_TYPE_FDE_ORDER = "fde_order"

# 在线充值通道永久关闭：前端据此只展示兑换码入口。
ONLINE_RECHARGE_ENABLED = False


class WalletError(Exception):
    """钱包业务错误基类；端点按具体子类映射 HTTP 状态码。"""


class WalletNotFoundError(WalletError):
    """资源不存在（用户 / 兑换码），对应 HTTP 404。"""


class WalletConflictError(WalletError):
    """余额不足、兑换码不可用等业务冲突，对应 HTTP 409。"""


@dataclass(frozen=True)
class WalletSummary:
    """钱包首页汇总：余额、收支分类合计与充值入口说明。"""

    balance_cents: int
    usage_total_cents: int
    recharge_total_cents: int
    redeem_total_cents: int
    income_total_cents: int
    recharge_enabled: bool
    recharge_note: str
    support_contact: str


@dataclass(frozen=True)
class TransactionPage:
    """流水分页信封。"""

    items: tuple[WalletTransaction, ...]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class RedeemResult:
    """兑换结果：入账金额、兑换后余额与本次流水。"""

    amount_cents: int
    balance_cents: int
    transaction: WalletTransaction


async def get_or_create_wallet(
    session: AsyncSession, user_id: int, *, for_update: bool = False
) -> Wallet:
    """取用户钱包，不存在则创建（flush 拿主键）。

    `for_update=True` 时对行加锁；SQLite 测试会忽略 FOR UPDATE 子句，
    生产环境（PostgreSQL）由行锁保证同一钱包的并发变更串行化。
    """
    statement = select(Wallet).where(Wallet.user_id == user_id)
    if for_update:
        statement = statement.with_for_update()
    wallet = (await session.execute(statement)).scalar_one_or_none()
    if wallet is not None:
        return wallet

    if await session.get(User, user_id) is None:
        raise WalletNotFoundError("用户不存在")
    wallet = Wallet(user_id=user_id, balance_cents=0)
    session.add(wallet)
    await session.flush()
    return wallet


async def credit(
    session: AsyncSession,
    wallet: Wallet,
    amount_cents: int,
    *,
    type: str,
    description: str,
    reference_type: str | None = None,
    reference_id: int | None = None,
    created_at: datetime | None = None,
) -> WalletTransaction:
    """入账：更新余额并写一条 credit 流水（不 commit）。"""
    if amount_cents <= 0:
        raise WalletConflictError("入账金额必须为正数")
    wallet.balance_cents += amount_cents
    transaction = WalletTransaction(
        wallet_id=wallet.id,
        type=type,
        direction=DIRECTION_CREDIT,
        amount_cents=amount_cents,
        balance_after_cents=wallet.balance_cents,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        created_at=created_at or utcnow(),
    )
    session.add(transaction)
    await session.flush()
    return transaction


async def debit(
    session: AsyncSession,
    wallet: Wallet,
    amount_cents: int,
    *,
    type: str,
    description: str,
    reference_type: str | None = None,
    reference_id: int | None = None,
    created_at: datetime | None = None,
) -> WalletTransaction:
    """出账：余额不足直接抛冲突，且不修改余额（不 commit）。"""
    if amount_cents <= 0:
        raise WalletConflictError("出账金额必须为正数")
    if wallet.balance_cents < amount_cents:
        raise WalletConflictError("钱包余额不足")
    wallet.balance_cents -= amount_cents
    transaction = WalletTransaction(
        wallet_id=wallet.id,
        type=type,
        direction=DIRECTION_DEBIT,
        amount_cents=amount_cents,
        balance_after_cents=wallet.balance_cents,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        created_at=created_at or utcnow(),
    )
    session.add(transaction)
    await session.flush()
    return transaction


async def _sum_cents(
    session: AsyncSession,
    wallet_id: int,
    *,
    direction: str,
    types: tuple[str, ...] | None = None,
) -> int:
    statement = select(func.coalesce(func.sum(WalletTransaction.amount_cents), 0)).where(
        WalletTransaction.wallet_id == wallet_id,
        WalletTransaction.direction == direction,
    )
    if types is not None:
        statement = statement.where(WalletTransaction.type.in_(types))
    return int((await session.execute(statement)).scalar_one())


async def get_summary(session: AsyncSession, user_id: int) -> WalletSummary:
    """钱包汇总：支出合计按 debit 计，收入按 settlement / recharge / redeem 分类。"""
    wallet = await get_or_create_wallet(session, user_id)
    settings = await get_settings_map(session)
    return WalletSummary(
        balance_cents=wallet.balance_cents,
        usage_total_cents=await _sum_cents(session, wallet.id, direction=DIRECTION_DEBIT),
        recharge_total_cents=await _sum_cents(
            session, wallet.id, direction=DIRECTION_CREDIT, types=(TRANSACTION_TYPE_RECHARGE,)
        ),
        redeem_total_cents=await _sum_cents(
            session, wallet.id, direction=DIRECTION_CREDIT, types=(TRANSACTION_TYPE_REDEEM,)
        ),
        income_total_cents=await _sum_cents(
            session,
            wallet.id,
            direction=DIRECTION_CREDIT,
            types=(TRANSACTION_TYPE_ORDER_SETTLEMENT,),
        ),
        recharge_enabled=ONLINE_RECHARGE_ENABLED,
        recharge_note=settings["wallet_recharge_note"],
        support_contact=settings["support_contact"],
    )


async def list_transactions(
    session: AsyncSession,
    user_id: int,
    *,
    type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> TransactionPage:
    """流水分页：最新在前，同一时间按 id 倒序保证稳定。"""
    wallet = await get_or_create_wallet(session, user_id)
    filters = [WalletTransaction.wallet_id == wallet.id]
    if type is not None:
        filters.append(WalletTransaction.type == type)
    statement = (
        select(WalletTransaction)
        .where(*filters)
        .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(statement)).scalars().all()
    total = (
        await session.execute(select(func.count()).select_from(WalletTransaction).where(*filters))
    ).scalar_one()
    return TransactionPage(items=tuple(rows), total=total, page=page, page_size=page_size)


async def has_order_payment(session: AsyncSession, order_id: int) -> bool:
    """订单是否真的走过托管扣款；历史订单可能没有对应流水，结算/退款前必须确认。"""
    row = (
        await session.execute(
            select(WalletTransaction.id)
            .where(
                WalletTransaction.reference_type == REFERENCE_TYPE_FDE_ORDER,
                WalletTransaction.reference_id == order_id,
                WalletTransaction.type == TRANSACTION_TYPE_ORDER_PAYMENT,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return row is not None


async def redeem(session: AsyncSession, user_id: int, code: str) -> RedeemResult:
    """兑换码入账：先做状态校验，再用条件 UPDATE 原子占用，避免并发重复兑换。"""
    normalized = code.strip().upper()
    record = (
        await session.execute(select(RedeemCode).where(RedeemCode.code == normalized))
    ).scalar_one_or_none()
    if record is None:
        raise WalletNotFoundError("兑换码不存在")
    if record.status == REDEEM_STATUS_USED:
        raise WalletConflictError("兑换码已被使用")
    if record.status == REDEEM_STATUS_DISABLED:
        raise WalletConflictError("兑换码已停用")
    now = utcnow()
    if record.expires_at is not None and ensure_utc(record.expires_at) <= now:
        raise WalletConflictError("兑换码已过期")

    occupied = await session.execute(
        update(RedeemCode)
        .where(
            RedeemCode.id == record.id,
            RedeemCode.status == REDEEM_STATUS_ACTIVE,
            or_(RedeemCode.expires_at.is_(None), RedeemCode.expires_at > now),
        )
        .values(status=REDEEM_STATUS_USED, used_by_id=user_id, used_at=now)
        # 行内已有对象带 naive 时间（SQLite），跳过 ORM 同步评估以免时区比较报错。
        .execution_options(synchronize_session=False)
    )
    if getattr(occupied, "rowcount", 0) != 1:
        raise WalletConflictError("兑换码已被使用")

    wallet = await get_or_create_wallet(session, user_id, for_update=True)
    transaction = await credit(
        session,
        wallet,
        record.amount_cents,
        type=TRANSACTION_TYPE_REDEEM,
        description=f"兑换码 {normalized} 入账",
        created_at=now,
    )
    await session.commit()
    return RedeemResult(
        amount_cents=record.amount_cents,
        balance_cents=wallet.balance_cents,
        transaction=transaction,
    )


__all__ = [
    "DIRECTION_CREDIT",
    "DIRECTION_DEBIT",
    "ONLINE_RECHARGE_ENABLED",
    "REDEEM_STATUS_ACTIVE",
    "REDEEM_STATUS_DISABLED",
    "REDEEM_STATUS_USED",
    "REFERENCE_TYPE_FDE_ORDER",
    "TRANSACTION_TYPE_ORDER_PAYMENT",
    "TRANSACTION_TYPE_ORDER_REFUND",
    "TRANSACTION_TYPE_ORDER_SETTLEMENT",
    "TRANSACTION_TYPE_RECHARGE",
    "TRANSACTION_TYPE_REDEEM",
    "RedeemResult",
    "TransactionPage",
    "WalletConflictError",
    "WalletError",
    "WalletNotFoundError",
    "WalletSummary",
    "credit",
    "debit",
    "get_or_create_wallet",
    "get_summary",
    "has_order_payment",
    "list_transactions",
    "redeem",
]
