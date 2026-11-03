"""v1 路由聚合。"""

from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, fde, profile, wallet

router = APIRouter()

router.include_router(auth.router)
router.include_router(profile.router)
router.include_router(fde.router)
router.include_router(wallet.router)
router.include_router(admin.router)
