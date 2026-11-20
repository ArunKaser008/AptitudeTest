from fastapi import APIRouter

from app.api.dependencies import Candidate, DatabaseSession
from app.schemas import CandidatePerformanceOut, RecommendationListOut
from app.services import analytics_service

router = APIRouter()


@router.get("/candidate/performance", response_model=CandidatePerformanceOut)
def candidate_performance(
    db: DatabaseSession,
    candidate: Candidate,
) -> CandidatePerformanceOut:
    return analytics_service.get_candidate_performance(db, candidate)


@router.get("/candidate/recommendations", response_model=RecommendationListOut)
def candidate_recommendations(
    db: DatabaseSession,
    candidate: Candidate,
) -> RecommendationListOut:
    return analytics_service.get_candidate_recommendations(db, candidate)
