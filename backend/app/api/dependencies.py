from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import CandidateSession
from app.services.assessment_service import find_candidate_session

DatabaseSession = Annotated[Session, Depends(get_db)]


def require_candidate_session(
    db: DatabaseSession,
    candidate_token: Annotated[str | None, Header(alias="X-Candidate-Token")] = None,
) -> CandidateSession:
    return find_candidate_session(db, candidate_token)


Candidate = Annotated[CandidateSession, Depends(require_candidate_session)]
