"""
API v1 router combining all endpoints.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from fastapi import APIRouter

from web.api.v1.dashboard import router as dashboard_router
from web.api.v1.users import router as users_router
from web.api.v1.areas import router as areas_router
from web.api.v1.messages import router as messages_router
from web.api.v1.logs import router as logs_router
from web.api.v1.settings import router as settings_router
from web.api.v1.backups import router as backups_router
from web.api.v1.radio import router as radio_router
from web.api.v1.stats import router as stats_router


# Create main v1 router
api_router = APIRouter(prefix="/api/v1")

# Include all sub-routers
api_router.include_router(dashboard_router)
api_router.include_router(users_router)
api_router.include_router(areas_router)
api_router.include_router(messages_router)
api_router.include_router(logs_router)
api_router.include_router(settings_router)
api_router.include_router(backups_router)
api_router.include_router(radio_router)
api_router.include_router(stats_router)
