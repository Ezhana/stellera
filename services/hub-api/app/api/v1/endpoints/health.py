"""健康检查：存活探针与就绪探针。

/health 只表示进程活着；/health/ready 额外检查数据库与 Casbin 是否就绪，
供 Docker healthcheck / K8s readinessProbe / nginx upstream 使用。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(request: Request) -> dict[str, object]:
    checks: dict[str, str] = {}
    try:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - 就绪检查要把任何依赖失败转成 503
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database not ready",
            headers={"X-Error": type(exc).__name__},
        ) from exc

    if getattr(request.app.state, "enforcer_guard", None) is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="rbac not ready"
        )
    checks["rbac"] = "ok"
    return {"status": "ready", "checks": checks}
