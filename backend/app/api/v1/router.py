from fastapi import APIRouter

from app.api.v1.routes.assessments import router as assessments_router

api_router = APIRouter()
api_router.include_router(assessments_router, tags=["assessments"])
