from fastapi import APIRouter

from app.api.health import router as health_router
from app.modules.activity.router import router as activity_router
from app.modules.auth.router import router as auth_router
from app.modules.chats.router import router as chats_router
from app.modules.deals.router import router as deals_router
from app.modules.matches.router import router as matches_router
from app.modules.offers.router import router as offers_router
from app.modules.admin.router import router as admin_router
from app.modules.profile.router import router as profile_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(matches_router)
api_router.include_router(offers_router)
api_router.include_router(chats_router)
api_router.include_router(deals_router)
api_router.include_router(activity_router)
api_router.include_router(admin_router)
