"""认证端点。

固定五个路由（/login 额外返回 user，省掉一次 /me 往返）：
- POST /api/v1/auth/login   JSON 用户名密码
- POST /api/v1/auth/token   OAuth2 password form（Swagger Authorize 用）
- POST /api/v1/auth/refresh 旋转 refresh token
- POST /api/v1/auth/logout  吊销该用户全部 refresh token
- GET  /api/v1/auth/me      当前用户、角色与 Casbin 隐式权限

令牌类响应统一带 Cache-Control: no-store，避免中间层缓存。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUserDep, SessionDep, get_auth_service
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    PermissionItem,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthenticationError, AuthService, CurrentUser, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])

NO_STORE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _token_response(pair: TokenPair) -> TokenResponse:
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
        refresh_expires_in=pair.refresh_expires_in,
    )


def _user_response(current: CurrentUser) -> UserResponse:
    return UserResponse(
        id=current.user.id,
        username=current.user.username,
        email=current.user.email,
        full_name=current.user.full_name,
        is_active=current.user.is_active,
        roles=sorted(current.roles),
        permissions=[
            PermissionItem(object=object_pattern, action=action)
            for object_pattern, action in current.permissions
        ],
    )


def _auth_response(pair: TokenPair, current: CurrentUser) -> AuthResponse:
    return AuthResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
        refresh_expires_in=pair.refresh_expires_in,
        user=_user_response(current),
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer", **NO_STORE_HEADERS},
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    session: SessionDep,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthResponse:
    try:
        pair = await service.login(session, payload.username, payload.password)
        current = await service.resolve_user(session, pair.user_id)
    except AuthenticationError as exc:
        raise _unauthorized(exc.detail) from exc
    response.headers.update(NO_STORE_HEADERS)
    return _auth_response(pair, current)


@router.post("/token", response_model=TokenResponse)
async def token(
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """OAuth2 Password Grant 形式，供 Swagger UI 的 Authorize 按钮使用。"""
    try:
        pair = await service.login(session, form.username, form.password)
    except AuthenticationError as exc:
        raise _unauthorized(exc.detail) from exc
    response.headers.update(NO_STORE_HEADERS)
    return _token_response(pair)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    response: Response,
    session: SessionDep,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    try:
        pair = await service.refresh(session, payload.refresh_token)
    except AuthenticationError as exc:
        raise _unauthorized(exc.detail) from exc
    response.headers.update(NO_STORE_HEADERS)
    return _token_response(pair)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    principal: CurrentUserDep,
    session: SessionDep,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    await service.logout(session, principal.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=NO_STORE_HEADERS)


@router.get("/me", response_model=UserResponse)
async def me(
    principal: CurrentUserDep,
    session: SessionDep,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    try:
        current = await service.resolve_user(session, principal.user_id)
    except AuthenticationError as exc:
        raise _unauthorized(exc.detail) from exc
    return _user_response(current)
