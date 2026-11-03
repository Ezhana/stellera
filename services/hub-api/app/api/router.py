"""API 路由聚合：业务接口统一挂在 /api/v1 下。"""

from fastapi import APIRouter

from app.api.v1.router import router as v1_router

router = APIRouter(prefix="/api")

router.include_router(v1_router, prefix="/v1")
