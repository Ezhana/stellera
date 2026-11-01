"""应用工厂与 ASGI 入口。

中间件顺序（外 -> 内）：CORS -> AuthenticationMiddleware -> CasbinRBACMiddleware。
Starlette 的 add_middleware 是后加的在最外层，所以按相反顺序注册。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.authentication import AuthenticationMiddleware

from app.api.router import router as api_router
from app.api.v1.endpoints.health import router as health_router
from app.core.config import Settings, get_settings
from app.db import create_engine, create_session_factory
from app.middleware.authentication import JWTAuthBackend
from app.middleware.rbac import CasbinRBACMiddleware
from app.rbac.enforcer import EnforcerGuard, build_enforcer, load_rbac_snapshot
from app.security.tokens import TokenService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory
    try:
        # 启动时把 PostgreSQL 中的 RBAC 全量投影到进程内 Casbin。
        async with session_factory() as session:
            snapshot = await load_rbac_snapshot(session)
        guard = EnforcerGuard(build_enforcer(settings.casbin_model_path, snapshot))
        app.state.enforcer = guard.enforcer
        app.state.enforcer_guard = guard
        yield
    finally:
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    docs_enabled = app_settings.docs_enabled

    app = FastAPI(
        title="Stellera Hub API",
        version="0.1.0",
        description="Stellera Hub 后端：Authlib JWT 登录 + pycasbin RBAC。",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = app_settings
    app.state.token_service = TokenService(app_settings)

    # 注意：这里的注册顺序决定执行顺序（后注册的在外层）。
    app.add_middleware(CasbinRBACMiddleware)
    app.add_middleware(
        AuthenticationMiddleware,
        backend=JWTAuthBackend(app.state.token_service),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        # 认证走 Authorization: Bearer，不使用 cookie，因此不需要 credentials。
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(health_router)
    return app


app = create_app()


def main() -> None:
    """`python -m app.main` 也可以启动（uvicorn 由 fastapi-cli 提供时用 `fastapi run`）。"""
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()


__all__ = ["app", "create_app", "lifespan", "main"]
