from __future__ import annotations

import hashlib
import math
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentConfigVersion,
    AssessmentQuestionPool,
    AssessmentSection,
    AttemptQuestion,
    AttemptResponse,
    CandidateSession,
    QuestionVersion,
)
from app.schemas import (
    AssessmentOut,
    AssessmentSectionOut,
    AttemptDetailOut,
    AttemptOut,
    AttemptQuestionOut,
    AttemptResultOut,
    CandidateSessionOut,
    QuestionOptionOut,
    QuestionReviewOut,
    ResponseOut,
    SectionResultOut,
    TopicResultOut,
)


class DomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _attempt_duration(
    attempt: AssessmentAttempt,
    config: AssessmentConfigVersion,
) -> int:
    return attempt.duration_seconds or config.duration_seconds


def hash_candidate_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_candidate_session(db: Session) -> CandidateSessionOut:
    now = utc_now()
    token = secrets.token_urlsafe(32)
    session = CandidateSession(
        token_hash=hash_candidate_token(token),
        expires_at=now + timedelta(hours=get_settings().candidate_session_ttl_hours),
        last_seen_at=now,
    )
    db.add(session)
    db.commit()
    return CandidateSessionOut(session_token=token, expires_at=session.expires_at)


def find_candidate_session(db: Session, token: str | None) -> CandidateSession:
    if not token or len(token) > 256:
        raise DomainError(401, "candidate_session_required", "A valid candidate session is required.")
    candidate_session = db.scalar(
        select(CandidateSession).where(CandidateSession.token_hash == hash_candidate_token(token))
    )
    if (
        candidate_session is None
        or candidate_session.revoked_at is not None
        or as_utc(candidate_session.expires_at) <= utc_now()
    ):
        raise DomainError(401, "candidate_session_invalid", "The candidate session is invalid or expired.")
    return candidate_session


def _published_config(db: Session, assessment: Assessment) -> AssessmentConfigVersion | None:
    return db.scalar(
        select(AssessmentConfigVersion)
        .where(
            AssessmentConfigVersion.assessment_id == assessment.id,
            AssessmentConfigVersion.status == "published",
        )
        .order_by(AssessmentConfigVersion.version_number.desc())
        .limit(1)
    )


def _sections(db: Session, config_version_id: uuid.UUID) -> list[AssessmentSection]:
    return list(
        db.scalars(
            select(AssessmentSection)
            .where(AssessmentSection.config_version_id == config_version_id)
            .order_by(AssessmentSection.position)
        )
    )


def _eligible_pools(
    db: Session,
    section_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[QuestionVersion]]:
    pools: dict[uuid.UUID, list[QuestionVersion]] = defaultdict(list)
    if not section_ids:
        return pools
    rows = db.execute(
        select(AssessmentQuestionPool.section_id, QuestionVersion)
        .join(QuestionVersion, QuestionVersion.id == AssessmentQuestionPool.question_version_id)
        .where(
            AssessmentQuestionPool.section_id.in_(section_ids),
            QuestionVersion.status == "published",
            QuestionVersion.verified_at.is_not(None),
        )
    )
    for section_id, question in rows:
        pools[section_id].append(question)
    return pools


def _is_ready(
    db: Session,
    sections: list[AssessmentSection],
) -> bool:
    pools = _eligible_pools(db, [section.id for section in sections])
    return bool(sections) and all(
        len(pools[section.id]) >= section.question_count
        for section in sections
    )


def list_available_assessments(db: Session) -> list[AssessmentOut]:
    assessments = list(
        db.scalars(
            select(Assessment)
            .where(Assessment.status == "published")
            .order_by(Assessment.title)
        )
    )
    available: list[AssessmentOut] = []
    for assessment in assessments:
        config = _published_config(db, assessment)
        if config is None:
            continue
        sections = _sections(db, config.id)
        if not _is_ready(db, sections):
            continue
        eligible = _eligible_pools(db, [section.id for section in sections])
        available.append(
            AssessmentOut(
                slug=assessment.slug,
                title=assessment.title,
                description=assessment.description,
                duration_seconds=config.duration_seconds,
                question_count=sum(section.question_count for section in sections),
                sections=[
                    AssessmentSectionOut(title=section.title, question_count=section.question_count)
                    for section in sections
                ],
                difficulties=sorted({
                    question.difficulty
                    for pool in eligible.values()
                    for question in pool
                }),
            )
        )
    return available


def _assessment_by_slug(
    db: Session,
    assessment_slug: str,
) -> tuple[Assessment, AssessmentConfigVersion, list[AssessmentSection]]:
    assessment = db.scalar(
        select(Assessment).where(
            Assessment.slug == assessment_slug,
            Assessment.status == "published",
        )
    )
    if assessment is None:
        raise DomainError(404, "assessment_not_found", "The requested assessment is not available.")
    config = _published_config(db, assessment)
    if config is None:
        raise DomainError(404, "assessment_not_found", "The requested assessment is not available.")
    sections = _sections(db, config.id)
    if not _is_ready(db, sections):
        raise DomainError(409, "assessment_content_unavailable", "This assessment is not ready for candidates.")
    return assessment, config, sections


def _validate_question_content(question: QuestionVersion) -> list[dict[str, str]]:
    if question.question_type not in {"single_choice", "multi_choice", "numeric"}:
        raise DomainError(409, "unsupported_question_type", "This assessment contains an unsupported question type.")
    if not isinstance(question.options, list):
        raise DomainError(409, "invalid_question_content", "A published question has invalid options.")
    option_ids: list[str] = []
    options: list[dict[str, str]] = []
    for option in question.options:
        if (
            not isinstance(option, dict)
            or not isinstance(option.get("id"), str)
            or not option["id"].strip()
            or not isinstance(option.get("text"), str)
            or not option["text"].strip()
        ):
            raise DomainError(409, "invalid_question_content", "A published question has invalid options.")
        option_ids.append(option["id"])
        options.append({"id": option["id"], "text": option["text"]})
    if not isinstance(question.correct_answer, dict) or not question.explanation.strip():
        raise DomainError(409, "invalid_question_content", "A published question is missing verified answer content.")
    if question.question_type == "single_choice":
        correct_id = question.correct_answer.get("option_id")
        if (
            len(option_ids) < 2
            or len(set(option_ids)) != len(option_ids)
            or set(question.correct_answer) != {"option_id"}
            or correct_id not in option_ids
        ):
            raise DomainError(409, "invalid_question_content", "A published single-choice question has an invalid answer.")
    elif question.question_type == "multi_choice":
        correct_ids = question.correct_answer.get("option_ids")
        if (
            len(option_ids) < 2
            or len(set(option_ids)) != len(option_ids)
            or set(question.correct_answer) != {"option_ids"}
            or not isinstance(correct_ids, list)
            or not correct_ids
            or any(not isinstance(option_id, str) for option_id in correct_ids)
            or len(set(correct_ids)) != len(correct_ids)
            or not set(correct_ids).issubset(option_ids)
        ):
            raise DomainError(409, "invalid_question_content", "A published multiple-choice question has an invalid answer.")
    else:
        value = question.correct_answer.get("value")
        tolerance = question.correct_answer.get("tolerance", 0)
        if (
            options
            or set(question.correct_answer) - {"value", "tolerance"}
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or isinstance(tolerance, bool)
            or not isinstance(tolerance, (int, float))
            or not math.isfinite(tolerance)
            or tolerance < 0
        ):
            raise DomainError(409, "invalid_question_content", "A published numeric question has an invalid answer.")
    return options


def _validate_response(question: QuestionVersion, answer: dict[str, Any]) -> dict[str, Any]:
    options = _validate_question_content(question)
    option_ids = {option["id"] for option in options}
    if question.question_type == "single_choice":
        option_id = answer.get("option_id")
        if set(answer) != {"option_id"} or not isinstance(option_id, str) or option_id not in option_ids:
            raise DomainError(422, "invalid_response", "A single-choice response requires one valid option_id.")
    elif question.question_type == "multi_choice":
        option_ids_answer = answer.get("option_ids")
        if (
            set(answer) != {"option_ids"}
            or not isinstance(option_ids_answer, list)
            or not option_ids_answer
            or any(not isinstance(option_id, str) for option_id in option_ids_answer)
            or len(set(option_ids_answer)) != len(option_ids_answer)
            or not set(option_ids_answer).issubset(option_ids)
        ):
            raise DomainError(422, "invalid_response", "A multiple-choice response requires valid, unique option_ids.")
    else:
        value = answer.get("value")
        if (
            set(answer) != {"value"}
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise DomainError(422, "invalid_response", "A numeric response requires a finite numeric value.")
    return answer


def _response_is_correct(question: QuestionVersion, answer: dict[str, Any]) -> bool:
    correct_answer = question.correct_answer
    if question.question_type == "single_choice":
        return answer["option_id"] == correct_answer["option_id"]
    if question.question_type == "multi_choice":
        return set(answer["option_ids"]) == set(correct_answer["option_ids"])
    return abs(float(answer["value"]) - float(correct_answer["value"])) <= float(
        correct_answer.get("tolerance", 0)
    )


def _options_by_ids(question: QuestionVersion, option_order: list[str]) -> list[QuestionOptionOut]:
    options = _validate_question_content(question)
    by_id = {option["id"]: option for option in options}
    if len(option_order) != len(by_id) or set(option_order) != set(by_id):
        raise DomainError(500, "attempt_question_corrupt", "The saved attempt question is invalid.")
    return [QuestionOptionOut(**by_id[option_id]) for option_id in option_order]


def _attempt_question_rows(
    db: Session, attempt_id: uuid.UUID
) -> list[tuple[AttemptQuestion, AssessmentSection, QuestionVersion, AttemptResponse | None]]:
    rows = db.execute(
        select(AttemptQuestion, AssessmentSection, QuestionVersion, AttemptResponse)
        .join(AssessmentSection, AssessmentSection.id == AttemptQuestion.section_id)
        .join(QuestionVersion, QuestionVersion.id == AttemptQuestion.question_version_id)
        .outerjoin(AttemptResponse, AttemptResponse.attempt_question_id == AttemptQuestion.id)
        .where(AttemptQuestion.attempt_id == attempt_id)
        .order_by(AttemptQuestion.position)
    )
    return list(rows)


def _attempt_out(
    db: Session,
    attempt: AssessmentAttempt,
    assessment: Assessment,
    *,
    now: datetime | None = None,
) -> AttemptOut:
    question_count = db.scalar(
        select(func.count())
        .select_from(AttemptQuestion)
        .where(AttemptQuestion.attempt_id == attempt.id)
    ) or 0
    return AttemptOut(
        id=attempt.id,
        assessment_slug=assessment.slug,
        title=attempt.title_override or assessment.title,
        status=attempt.status,
        started_at=attempt.started_at,
        deadline_at=attempt.deadline_at,
        server_time=now or utc_now(),
        question_count=question_count,
        current_position=attempt.current_position,
    )


def _load_owned_attempt(
    db: Session,
    attempt_id: uuid.UUID,
    candidate_session_id: uuid.UUID,
    *,
    lock: bool = False,
) -> tuple[AssessmentAttempt, Assessment, AssessmentConfigVersion]:
    statement = (
        select(AssessmentAttempt, Assessment, AssessmentConfigVersion)
        .join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .join(AssessmentConfigVersion, AssessmentConfigVersion.id == AssessmentAttempt.config_version_id)
        .where(
            AssessmentAttempt.id == attempt_id,
            AssessmentAttempt.candidate_session_id == candidate_session_id,
        )
    )
    if lock:
        statement = statement.with_for_update()
    row = db.execute(statement).first()
    if row is None:
        raise DomainError(404, "attempt_not_found", "The assessment attempt was not found.")
    return row


def _attempt_question_payload(
    attempt_question: AttemptQuestion,
    section: AssessmentSection,
    question: QuestionVersion,
    response: AttemptResponse | None,
    *,
    include_answer: bool,
) -> AttemptQuestionOut:
    return AttemptQuestionOut(
        id=attempt_question.id,
        position=attempt_question.position,
        section=section.title,
        topic=question.topic,
        difficulty=question.difficulty,
        question_type=question.question_type,
        prompt=question.prompt,
        stimulus=question.stimulus,
        options=_options_by_ids(question, attempt_question.option_order),
        answer=response.answer if include_answer and response is not None else None,
        marked_for_review=attempt_question.marked_for_review,
        visited=attempt_question.visited_at is not None,
    )


def _finalize_attempt(
    db: Session,
    attempt: AssessmentAttempt,
    assessment: Assessment,
    config: AssessmentConfigVersion,
    now: datetime,
) -> AttemptResultOut:
    if attempt.result_snapshot is not None:
        return AttemptResultOut.model_validate(attempt.result_snapshot)

    rows = _attempt_question_rows(db, attempt.id)
    section_stats: dict[uuid.UUID, dict[str, Any]] = defaultdict(
        lambda: {
            "score": 0.0,
            "max_score": 0.0,
            "correct": 0,
            "incorrect": 0,
            "unanswered": 0,
            "attempted": 0,
        }
    )
    topic_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"correct": 0, "incorrect": 0, "unanswered": 0, "time_spent": 0, "count": 0}
    )
    total_score = 0.0
    max_score = 0.0
    correct_count = 0
    incorrect_count = 0
    unanswered_count = 0
    review: list[QuestionReviewOut] = []
    release_answers = config.show_explanations_after_submission

    for attempt_question, section, question, response in rows:
        stats = section_stats[section.id]
        topic = topic_stats[question.topic]
        topic["time_spent"] += attempt_question.time_spent_seconds
        topic["count"] += 1
        max_score += attempt_question.marks
        stats["max_score"] += attempt_question.marks
        is_correct: bool | None = None
        if response is None:
            unanswered_count += 1
            stats["unanswered"] += 1
            topic["unanswered"] += 1
        else:
            is_correct = _response_is_correct(question, response.answer)
            stats["attempted"] += 1
            if is_correct:
                total_score += attempt_question.marks
                correct_count += 1
                stats["correct"] += 1
                stats["score"] += attempt_question.marks
                topic["correct"] += 1
            else:
                total_score -= attempt_question.negative_marks
                incorrect_count += 1
                stats["incorrect"] += 1
                stats["score"] -= attempt_question.negative_marks
                topic["incorrect"] += 1

        review.append(
            QuestionReviewOut(
                question_id=question.id,
                position=attempt_question.position,
                section=section.title,
                topic=question.topic,
                prompt=question.prompt,
                stimulus=question.stimulus,
                options=_options_by_ids(question, attempt_question.option_order),
                answer=response.answer if response is not None else None,
                correct_answer=question.correct_answer if release_answers else None,
                explanation=question.explanation if release_answers else None,
                is_correct=is_correct if release_answers else None,
                time_spent_seconds=attempt_question.time_spent_seconds,
            )
        )

    if config.scoring_policy.get("minimum_score_zero", True):
        total_score = max(0.0, total_score)
        for stats in section_stats.values():
            stats["score"] = max(0.0, stats["score"])

    duration_seconds = _attempt_duration(attempt, config)
    elapsed_seconds = min(
        duration_seconds,
        max(0, duration_seconds - max(0, int((as_utc(attempt.deadline_at) - now).total_seconds()))),
    )
    sections = [
        SectionResultOut(
            section=section.title,
            score=round(section_stats[section.id]["score"], 2),
            max_score=round(section_stats[section.id]["max_score"], 2),
            correct=section_stats[section.id]["correct"],
            incorrect=section_stats[section.id]["incorrect"],
            unanswered=section_stats[section.id]["unanswered"],
            accuracy_percent=round(
                100 * section_stats[section.id]["correct"] / section_stats[section.id]["attempted"],
                2,
            )
            if section_stats[section.id]["attempted"]
            else 0.0,
        )
        for section in _sections(db, config.id)
    ]
    topics = [
        TopicResultOut(
            topic=topic_name,
            correct=stats["correct"],
            incorrect=stats["incorrect"],
            unanswered=stats["unanswered"],
            accuracy_percent=round(
                100 * stats["correct"] / (stats["correct"] + stats["incorrect"]),
                2,
            )
            if stats["correct"] + stats["incorrect"]
            else 0.0,
            avg_time_seconds=round(stats["time_spent"] / stats["count"], 2)
            if stats["count"]
            else 0.0,
        )
        for topic_name, stats in sorted(topic_stats.items())
    ]
    attempted_count = correct_count + incorrect_count
    maximum_score = round(max_score, 2)
    result = AttemptResultOut(
        attempt_id=attempt.id,
        assessment_slug=assessment.slug,
        assessment_title=attempt.title_override or assessment.title,
        status="expired" if now >= as_utc(attempt.deadline_at) else "submitted",
        score=round(total_score, 2),
        max_score=maximum_score,
        correct=correct_count,
        incorrect=incorrect_count,
        unanswered=unanswered_count,
        accuracy_percent=round(100 * correct_count / attempted_count, 2) if attempted_count else 0.0,
        attempt_rate_percent=round(100 * attempted_count / len(rows), 2) if rows else 0.0,
        elapsed_seconds=elapsed_seconds,
        sections=sections,
        review=review,
        topics=topics,
    )
    attempt.status = result.status
    attempt.submitted_at = now
    attempt.score = result.score
    attempt.result_snapshot = result.model_dump(mode="json")
    db.flush()
    return result


def create_attempt(
    db: Session,
    candidate_session: CandidateSession,
    assessment_slug: str,
    idempotency_key: str,
) -> AttemptOut:
    locked_session = db.scalar(
        select(CandidateSession)
        .where(CandidateSession.id == candidate_session.id)
        .with_for_update()
    )
    if locked_session is None:
        raise DomainError(401, "candidate_session_invalid", "The candidate session is invalid or expired.")
    existing = db.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.candidate_session_id == candidate_session.id,
            AssessmentAttempt.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.assessment_id != db.scalar(
            select(Assessment.id).where(Assessment.slug == assessment_slug)
        ):
            raise DomainError(409, "idempotency_key_reused", "This idempotency key was already used.")
        assessment = db.get(Assessment, existing.assessment_id)
        if assessment is None:
            raise DomainError(404, "assessment_not_found", "The assessment was not found.")
        db.commit()
        return _attempt_out(db, existing, assessment)

    assessment, config, sections = _assessment_by_slug(db, assessment_slug)
    now = utc_now()
    attempt = AssessmentAttempt(
        candidate_session_id=candidate_session.id,
        assessment_id=assessment.id,
        config_version_id=config.id,
        idempotency_key=idempotency_key,
        status="in_progress",
        started_at=now,
        deadline_at=now + timedelta(seconds=config.duration_seconds),
        duration_seconds=config.duration_seconds,
    )
    db.add(attempt)
    db.flush()

    previously_used: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    used_in_current_attempt: set[uuid.UUID] = set()
    prior_question_ids = db.execute(
        select(AttemptQuestion.section_id, AttemptQuestion.question_version_id)
        .join(AssessmentAttempt, AssessmentAttempt.id == AttemptQuestion.attempt_id)
        .where(
            AssessmentAttempt.candidate_session_id == candidate_session.id,
            AssessmentAttempt.assessment_id == assessment.id,
        )
    )
    for section_id, question_id in prior_question_ids:
        previously_used[section_id].add(question_id)

    position = 0
    eligible_pools = _eligible_pools(db, [section.id for section in sections])
    for section in sections:
        pool = eligible_pools.get(section.id, [])
        unseen = [
            question
            for question in pool
            if question.id not in previously_used[section.id]
            and question.id not in used_in_current_attempt
        ]
        if len(unseen) >= section.question_count:
            chosen = secrets.SystemRandom().sample(unseen, section.question_count)
        else:
            chosen = list(unseen)
            chosen_ids = {item.id for item in chosen} | used_in_current_attempt
            remaining = [question for question in pool if question.id not in chosen_ids]
            chosen.extend(secrets.SystemRandom().sample(remaining, section.question_count - len(chosen)))
        if config.randomize_questions:
            secrets.SystemRandom().shuffle(chosen)

        for question in chosen:
            used_in_current_attempt.add(question.id)
            options = _validate_question_content(question)
            option_ids = [option["id"] for option in options]
            if config.randomize_options:
                secrets.SystemRandom().shuffle(option_ids)
            db.add(
                AttemptQuestion(
                    attempt_id=attempt.id,
                    section_id=section.id,
                    question_version_id=question.id,
                    position=position,
                    option_order=option_ids,
                    marks=section.marks_per_question,
                    negative_marks=section.negative_marks,
                    time_spent_seconds=0,
                    visited_at=now if position == 0 else None,
                )
            )
            position += 1

    db.commit()
    db.refresh(attempt)
    return _attempt_out(db, attempt, assessment, now=now)


def create_weak_topic_practice(
    db: Session,
    candidate_session: CandidateSession,
    source_attempt_id: uuid.UUID,
    idempotency_key: str,
) -> AttemptOut:
    locked_session = db.scalar(
        select(CandidateSession)
        .where(CandidateSession.id == candidate_session.id)
        .with_for_update()
    )
    if locked_session is None:
        raise DomainError(401, "candidate_session_invalid", "The candidate session is invalid or expired.")

    source_attempt, assessment, config = _load_owned_attempt(
        db, source_attempt_id, candidate_session.id, lock=True
    )
    if source_attempt.status == "in_progress" or source_attempt.result_snapshot is None:
        raise DomainError(409, "source_attempt_incomplete", "Submit an assessment before starting weak-topic practice.")

    existing = db.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.candidate_session_id == candidate_session.id,
            AssessmentAttempt.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.assessment_id != assessment.id or existing.title_override is None:
            raise DomainError(409, "idempotency_key_reused", "This idempotency key was already used.")
        return _attempt_out(db, existing, assessment)

    result = AttemptResultOut.model_validate(source_attempt.result_snapshot)
    topic_results = result.topics
    if not topic_results:
        derived: dict[str, dict[str, int]] = defaultdict(
            lambda: {"correct": 0, "incorrect": 0, "unanswered": 0}
        )
        for _, _, question, response in _attempt_question_rows(db, source_attempt.id):
            if response is None:
                derived[question.topic]["unanswered"] += 1
            elif _response_is_correct(question, response.answer):
                derived[question.topic]["correct"] += 1
            else:
                derived[question.topic]["incorrect"] += 1
        topic_results = [
            TopicResultOut(
                topic=topic,
                correct=counts["correct"],
                incorrect=counts["incorrect"],
                unanswered=counts["unanswered"],
                accuracy_percent=round(
                    100 * counts["correct"] / (counts["correct"] + counts["incorrect"]),
                    2,
                )
                if counts["correct"] + counts["incorrect"]
                else 0,
                avg_time_seconds=0,
            )
            for topic, counts in derived.items()
        ]
    weakest_topics = [
        topic.topic
        for topic in sorted(
            topic_results,
            key=lambda item: (item.accuracy_percent, -item.avg_time_seconds, item.topic),
        )[:3]
    ]
    if not weakest_topics:
        raise DomainError(409, "practice_topics_unavailable", "This assessment has no topic diagnostics to practice.")

    sections = _sections(db, config.id)
    section_ids = [section.id for section in sections]
    if not section_ids:
        raise DomainError(409, "practice_questions_unavailable", "No question pool is available for this assessment.")
    eligible_rows = list(db.execute(
        select(AssessmentSection, QuestionVersion)
        .join(AssessmentQuestionPool, AssessmentQuestionPool.section_id == AssessmentSection.id)
        .join(QuestionVersion, QuestionVersion.id == AssessmentQuestionPool.question_version_id)
        .where(
            AssessmentSection.id.in_(section_ids),
            QuestionVersion.topic.in_(weakest_topics),
            QuestionVersion.status == "published",
            QuestionVersion.verified_at.is_not(None),
        )
    ))
    by_question: dict[uuid.UUID, tuple[AssessmentSection, QuestionVersion]] = {}
    for section, question in eligible_rows:
        by_question.setdefault(question.id, (section, question))
    candidates = list(by_question.values())
    if not candidates:
        raise DomainError(409, "practice_questions_unavailable", "No verified published questions are available for the weak topics.")

    prior_ids = set(db.scalars(
        select(AttemptQuestion.question_version_id)
        .join(AssessmentAttempt, AssessmentAttempt.id == AttemptQuestion.attempt_id)
        .where(
            AssessmentAttempt.candidate_session_id == candidate_session.id,
            AssessmentAttempt.assessment_id == assessment.id,
        )
    ))
    fresh_candidates = [
        item for item in candidates if item[1].id not in prior_ids
    ]
    desired_count = min(10, len(candidates))
    sample_from = fresh_candidates if len(fresh_candidates) >= desired_count else candidates
    chosen = secrets.SystemRandom().sample(sample_from, desired_count)
    if config.randomize_questions:
        secrets.SystemRandom().shuffle(chosen)

    now = utc_now()
    duration_seconds = min(config.duration_seconds, max(60, desired_count * 60))
    attempt = AssessmentAttempt(
        candidate_session_id=candidate_session.id,
        assessment_id=assessment.id,
        config_version_id=config.id,
        idempotency_key=idempotency_key,
        status="in_progress",
        started_at=now,
        deadline_at=now + timedelta(seconds=duration_seconds),
        duration_seconds=duration_seconds,
        title_override=f"Focused practice · {assessment.title}"[:200],
        current_position=0,
    )
    db.add(attempt)
    db.flush()
    for position, (section, question) in enumerate(chosen):
        options = _validate_question_content(question)
        option_order = [option["id"] for option in options]
        if config.randomize_options:
            secrets.SystemRandom().shuffle(option_order)
        db.add(AttemptQuestion(
            attempt_id=attempt.id,
            section_id=section.id,
            question_version_id=question.id,
            position=position,
            option_order=option_order,
            marks=section.marks_per_question,
            negative_marks=section.negative_marks,
            time_spent_seconds=0,
            visited_at=now if position == 0 else None,
        ))
    db.commit()
    db.refresh(attempt)
    return _attempt_out(db, attempt, assessment, now=now)


def get_attempt(
    db: Session,
    attempt_id: uuid.UUID,
    candidate_session_id: uuid.UUID,
) -> AttemptDetailOut:
    attempt, assessment, config = _load_owned_attempt(
        db, attempt_id, candidate_session_id
    )
    now = utc_now()
    if attempt.status == "in_progress" and as_utc(attempt.deadline_at) <= now:
        attempt, assessment, config = _load_owned_attempt(
            db, attempt_id, candidate_session_id, lock=True
        )
        if attempt.status == "in_progress":
            _finalize_attempt(db, attempt, assessment, config, now)
            db.commit()
    rows = _attempt_question_rows(db, attempt.id)
    return AttemptDetailOut(
        **_attempt_out(db, attempt, assessment, now=now).model_dump(),
        questions=[
            _attempt_question_payload(
                attempt_question,
                section,
                question,
                response,
                include_answer=False,
            )
            for attempt_question, section, question, response in rows
        ],
    )


def save_response(
    db: Session,
    candidate_session_id: uuid.UUID,
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    answer: dict[str, Any],
    time_spent_seconds: int,
) -> ResponseOut:
    attempt, assessment, config = _load_owned_attempt(
        db, attempt_id, candidate_session_id, lock=True
    )
    now = utc_now()
    if attempt.status != "in_progress":
        raise DomainError(409, "attempt_closed", "Responses cannot be changed after submission.")
    if as_utc(attempt.deadline_at) <= now:
        _finalize_attempt(db, attempt, assessment, config, now)
        db.commit()
        raise DomainError(409, "attempt_expired", "The assessment deadline has passed.")

    question_row = db.execute(
        select(AttemptQuestion, QuestionVersion)
        .join(QuestionVersion, QuestionVersion.id == AttemptQuestion.question_version_id)
        .where(
            AttemptQuestion.attempt_id == attempt.id,
            AttemptQuestion.id == question_id,
        )
    ).first()
    if question_row is None:
        raise DomainError(404, "attempt_question_not_found", "The question is not part of this attempt.")
    attempt_question, question = question_row
    _validate_response(question, answer)

    response = db.scalar(
        select(AttemptResponse).where(AttemptResponse.attempt_question_id == question_id)
    )
    if response is None:
        response = AttemptResponse(attempt_question_id=question_id, answer=answer)
        db.add(response)
    else:
        response.answer = answer
    attempt_question.time_spent_seconds = min(
        _attempt_duration(attempt, config),
        attempt_question.time_spent_seconds + time_spent_seconds,
    )
    db.commit()
    db.refresh(response)
    return ResponseOut(question_id=question_id, answer=response.answer, saved_at=response.updated_at)


def clear_response(
    db: Session,
    candidate_session_id: uuid.UUID,
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
) -> None:
    attempt, assessment, config = _load_owned_attempt(
        db, attempt_id, candidate_session_id, lock=True
    )
    now = utc_now()
    if attempt.status != "in_progress":
        raise DomainError(409, "attempt_closed", "Responses cannot be changed after submission.")
    if as_utc(attempt.deadline_at) <= now:
        _finalize_attempt(db, attempt, assessment, config, now)
        db.commit()
        raise DomainError(409, "attempt_expired", "The assessment deadline has passed.")
    question = db.scalar(
        select(AttemptQuestion).where(
            AttemptQuestion.attempt_id == attempt.id,
            AttemptQuestion.id == question_id,
        )
    )
    if question is None:
        raise DomainError(404, "attempt_question_not_found", "The question is not part of this attempt.")
    response = db.scalar(
        select(AttemptResponse).where(AttemptResponse.attempt_question_id == question_id)
    )
    if response is not None:
        db.delete(response)
        db.commit()


def set_review_flag(
    db: Session,
    candidate_session_id: uuid.UUID,
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    marked: bool,
) -> bool:
    attempt, assessment, config = _load_owned_attempt(
        db, attempt_id, candidate_session_id, lock=True
    )
    now = utc_now()
    if attempt.status != "in_progress":
        raise DomainError(409, "attempt_closed", "Review flags cannot be changed after submission.")
    if as_utc(attempt.deadline_at) <= now:
        _finalize_attempt(db, attempt, assessment, config, now)
        db.commit()
        raise DomainError(409, "attempt_expired", "The assessment deadline has passed.")
    question = db.scalar(
        select(AttemptQuestion).where(
            AttemptQuestion.attempt_id == attempt.id,
            AttemptQuestion.id == question_id,
        )
    )
    if question is None:
        raise DomainError(404, "attempt_question_not_found", "The question is not part of this attempt.")
    question.marked_for_review = marked
    db.commit()
    return question.marked_for_review


def update_question_position(
    db: Session,
    candidate_session_id: uuid.UUID,
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    time_spent_seconds: int,
) -> int:
    attempt, assessment, config = _load_owned_attempt(
        db, attempt_id, candidate_session_id, lock=True
    )
    now = utc_now()
    if attempt.status != "in_progress":
        raise DomainError(409, "attempt_closed", "Question navigation is closed after submission.")
    if as_utc(attempt.deadline_at) <= now:
        _finalize_attempt(db, attempt, assessment, config, now)
        db.commit()
        raise DomainError(409, "attempt_expired", "The assessment deadline has passed.")
    next_question = db.scalar(
        select(AttemptQuestion).where(
            AttemptQuestion.attempt_id == attempt.id,
            AttemptQuestion.id == question_id,
        )
    )
    if next_question is None:
        raise DomainError(404, "attempt_question_not_found", "The question is not part of this attempt.")
    current_question = db.scalar(
        select(AttemptQuestion).where(
            AttemptQuestion.attempt_id == attempt.id,
            AttemptQuestion.position == attempt.current_position,
        )
    )
    if current_question is not None:
        current_question.time_spent_seconds = min(
            _attempt_duration(attempt, config),
            current_question.time_spent_seconds + time_spent_seconds,
        )
    next_question.visited_at = next_question.visited_at or now
    attempt.current_position = next_question.position
    db.commit()
    return attempt.current_position


def submit_attempt(
    db: Session,
    candidate_session_id: uuid.UUID,
    attempt_id: uuid.UUID,
    *,
    question_id: uuid.UUID | None = None,
    time_spent_seconds: int = 0,
) -> AttemptResultOut:
    attempt, assessment, config = _load_owned_attempt(
        db, attempt_id, candidate_session_id, lock=True
    )
    if attempt.status != "in_progress" and attempt.result_snapshot is not None:
        return AttemptResultOut.model_validate(attempt.result_snapshot)
    if question_id is not None:
        active_question = db.scalar(
            select(AttemptQuestion).where(
                AttemptQuestion.attempt_id == attempt.id,
                AttemptQuestion.id == question_id,
            )
        )
        if active_question is None:
            raise DomainError(404, "attempt_question_not_found", "The question is not part of this attempt.")
        active_question.time_spent_seconds = min(
            _attempt_duration(attempt, config),
            active_question.time_spent_seconds + time_spent_seconds,
        )
    result = _finalize_attempt(db, attempt, assessment, config, utc_now())
    db.commit()
    return result


def get_attempt_result(
    db: Session,
    candidate_session_id: uuid.UUID,
    attempt_id: uuid.UUID,
) -> AttemptResultOut:
    attempt, assessment, config = _load_owned_attempt(
        db, attempt_id, candidate_session_id, lock=True
    )
    if attempt.status == "in_progress" and as_utc(attempt.deadline_at) <= utc_now():
        _finalize_attempt(db, attempt, assessment, config, utc_now())
        db.commit()
    if attempt.result_snapshot is None:
        raise DomainError(409, "attempt_not_submitted", "Submit the assessment before requesting results.")
    return AttemptResultOut.model_validate(attempt.result_snapshot)
