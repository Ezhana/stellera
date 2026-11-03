"""认证业务逻辑：注册、登录、刷新旋转、登出与用户角色读取。

端点只负责 HTTP 语义（状态码、Cache-Control），业务规则集中在这里。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.base import ensure_utc, utcnow
from app.models.rbac import Role, UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.rbac.enforcer import EnforcerGuard, load_user_role_names
from app.security.passwords import dummy_verify, hash_password, verify_password
from app.security.tokens import IssuedToken, TokenError, TokenService, hash_token

MEMBER_ROLE = "member"


class AuthenticationError(Exception):
    """凭据/令牌无效；端点统一映射为 HTTP 401。"""

    def __init__(self, detail: str = "Invalid credentials") -> None:
        super().__init__(detail)
        self.detail = detail


class AuthConflictError(Exception):
    """注册冲突（用户名 / 邮箱已占用）；端点映射为 HTTP 409。"""

    def __init__(self, detail: str = "用户名或邮箱已被占用") -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class TokenPair:
    # user_id 不直接序列化给客户端，登录端点用它补齐 AuthResponse.user。
    user_id: int
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int


@dataclass(frozen=True)
class CurrentUser:
    user: User
    roles: tuple[str, ...]
    permissions: tuple[tuple[str, str], ...]


class AuthService:
    def __init__(
        self,
        settings: Settings,
        token_service: TokenService,
        guard: EnforcerGuard,
    ) -> None:
        self._settings = settings
        self._tokens = token_service
        self._guard = guard

    # ---------- 注册 ----------
    async def register(
        self,
        session: AsyncSession,
        *,
        username: str,
        email: str,
        password: str,
    ) -> TokenPair:
        """公开注册：创建会员账号、生成昵称、授予 member 角色并直接签发令牌。

        用户名 / 邮箱都已由 schema 归一成小写，这里再做一次大小写不敏感的唯一性检查；
        并发注册由数据库唯一约束兜底。昵称需要用户 id，flush 拿到自增主键后生成。
        """
        normalized_username = username.strip().lower()
        normalized_email = email.strip().lower()
        conflict = (
            await session.execute(
                select(User.id)
                .where(
                    or_(
                        func.lower(User.username) == normalized_username,
                        func.lower(User.email) == normalized_email,
                    )
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if conflict is not None:
            raise AuthConflictError()

        member_role_id = (
            await session.execute(select(Role.id).where(Role.name == MEMBER_ROLE))
        ).scalar_one_or_none()
        if member_role_id is None:
            raise AuthConflictError("角色数据未初始化，请联系管理员")

        user = User(
            username=normalized_username,
            email=normalized_email,
            hashed_password=hash_password(password),
            is_active=True,
        )
        session.add(user)
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise AuthConflictError() from exc

        # 自动昵称可被用户后续在个人资料里修改；展示名优先取昵称。
        user.nickname = f"用户{user.id:06d}"
        session.add(UserRole(user_id=user.id, role_id=member_role_id))
        await session.flush()
        # 先刷新 Casbin 投影再签发令牌，注册完成后立刻就能访问业务端点。
        self._guard.resync_user(user.id, [MEMBER_ROLE])
        pair = self._create_pair(session, user)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            self._guard.resync_user(user.id, [])
            raise AuthConflictError() from exc
        return pair

    # ---------- 登录 ----------
    async def authenticate(self, session: AsyncSession, username: str, password: str) -> User:
        normalized = username.strip().lower()
        user = (
            await session.execute(select(User).where(User.username == normalized))
        ).scalar_one_or_none()
        if user is None:
            # 不存在的用户也走一遍等价耗时的校验，降低用户名枚举的时序差异。
            dummy_verify()
            raise AuthenticationError("用户名或密码错误")
        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("用户名或密码错误")
        if not user.is_active:
            raise AuthenticationError("用户已被禁用")
        return user

    async def login(self, session: AsyncSession, username: str, password: str) -> TokenPair:
        user = await self.authenticate(session, username, password)
        # 每次登录重新从 PG 投影该用户的角色，角色变更在下一次登录后生效。
        role_names = await load_user_role_names(session, user.id)
        self._guard.resync_user(user.id, role_names)
        pair = self._create_pair(session, user)
        await session.commit()
        return pair

    # ---------- 刷新（旋转 + 重放检测） ----------
    async def refresh(self, session: AsyncSession, refresh_token: str) -> TokenPair:
        try:
            claims = self._tokens.decode_refresh_token(refresh_token)
        except TokenError as exc:
            raise AuthenticationError("Refresh token 无效或已过期") from exc

        record = (
            await session.execute(
                select(RefreshToken).where(
                    RefreshToken.jti == claims.jti,
                    RefreshToken.user_id == claims.user_id,
                )
            )
        ).scalar_one_or_none()

        now = utcnow()
        if (
            record is None
            or record.revoked_at is not None
            or record.token_hash != hash_token(refresh_token)
        ):
            # 旧令牌被重放（或签名有效但库里查不到）：吊销该用户全部 refresh token。
            await self._revoke_all(session, claims.user_id, now)
            await session.commit()
            raise AuthenticationError("Refresh token 已失效，请重新登录")

        if ensure_utc(record.expires_at) <= now:
            record.revoked_at = now
            await session.commit()
            raise AuthenticationError("Refresh token 已过期，请重新登录")

        user = await session.get(User, claims.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("用户不存在或已被禁用")

        new_refresh = self._tokens.create_refresh_token(user.id)
        record.revoked_at = now
        record.replaced_by_jti = new_refresh.jti
        session.add(self._refresh_row(user.id, new_refresh))
        pair = self._pair_from_tokens(
            user.id, self._tokens.create_access_token(user.id), new_refresh
        )
        await session.commit()
        return pair

    # ---------- 登出 ----------
    async def logout(self, session: AsyncSession, user_id: int) -> None:
        await self._revoke_all(session, user_id, utcnow())
        await session.commit()

    # ---------- /auth/me ----------
    async def resolve_user(self, session: AsyncSession, user_id: int) -> CurrentUser:
        user = await session.get(User, user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("用户不存在或已被禁用")
        roles = tuple(
            (
                await session.execute(
                    select(Role.name)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .where(UserRole.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        permissions = self._guard.implicit_permissions_for_user(user.id)
        return CurrentUser(user=user, roles=roles, permissions=permissions)

    # ---------- 内部工具 ----------
    def _create_pair(self, session: AsyncSession, user: User) -> TokenPair:
        access = self._tokens.create_access_token(user.id)
        refresh = self._tokens.create_refresh_token(user.id)
        session.add(self._refresh_row(user.id, refresh))
        return self._pair_from_tokens(user.id, access, refresh)

    def _pair_from_tokens(
        self, user_id: int, access: IssuedToken, refresh: IssuedToken
    ) -> TokenPair:
        return TokenPair(
            user_id=user_id,
            access_token=access.token,
            refresh_token=refresh.token,
            expires_in=self._settings.access_token_ttl_seconds,
            refresh_expires_in=self._settings.refresh_token_ttl_seconds,
        )

    @staticmethod
    def _refresh_row(user_id: int, refresh: IssuedToken) -> RefreshToken:
        return RefreshToken(
            jti=refresh.jti,
            user_id=user_id,
            token_hash=refresh.token_hash,
            expires_at=refresh.expires_at,
        )

    @staticmethod
    async def _revoke_all(session: AsyncSession, user_id: int, revoked_at: datetime) -> None:
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
