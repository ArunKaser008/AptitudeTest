from fastapi import APIRouter

from app.api.v1.routes.assessments import router as assessments_router
from app.api.v1.routes.authoring import router as authoring_router
from app.api.v1.routes.candidate import router as candidate_router

api_router = APIRouter()
api_router.include_router(assessments_router, tags=["assessments"])
api_router.include_router(authoring_router, tags=["authoring"])
api_router.include_router(candidate_router, tags=["candidate"])
