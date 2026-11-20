from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.models import (
    Assessment,
    AssessmentConfigVersion,
    AssessmentQuestionPool,
    AssessmentSection,
    QuestionVersion,
)
from app.schemas import (
    AssessmentCloneIn,
    AssessmentConfigUpdateIn,
    AssessmentCreateIn,
    AuthoringAssessmentOut,
    AuthoringSectionIn,
    QuestionDraftIn,
    QuestionListOut,
    QuestionOut,
    SectionReadinessOut,
)
from app.services.assessment_service import DomainError, _eligible_pools, _is_ready


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _question_dict(question: QuestionVersion, usage_count: int) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        logical_id=question.logical_id,
        version_number=question.version_number,
        status=question.status,
        question_type=question.question_type,
        prompt=question.prompt,
        stimulus=question.stimulus,
        topic=question.topic,
        difficulty=question.difficulty,
        options=question.options,
        correct_answer=question.correct_answer,
        explanation=question.explanation,
        marks=question.marks,
        negative_marks=question.negative_marks,
        source_reference=question.source_reference,
        verified_at=question.verified_at,
        usage_count=usage_count,
    )


def _active_usage_query():
    return (
        select(
            AssessmentQuestionPool.question_version_id.label("question_version_id"),
            func.count(AssessmentQuestionPool.id).label("usage_count"),
        )
        .join(AssessmentSection, AssessmentSection.id == AssessmentQuestionPool.section_id)
        .join(
            AssessmentConfigVersion,
            AssessmentConfigVersion.id == AssessmentSection.config_version_id,
        )
        .join(Assessment, Assessment.id == AssessmentConfigVersion.assessment_id)
        .where(
            Assessment.status == "published",
            AssessmentConfigVersion.status == "published",
        )
        .group_by(AssessmentQuestionPool.question_version_id)
        .subquery()
    )


def list_questions(
    db: Session,
    *,
    search: str | None,
    topic: str | None,
    difficulty: str | None,
    status: str | None,
    verified: bool | None,
    page: int,
    page_size: int,
) -> QuestionListOut:
    usage = _active_usage_query()
    statement = select(QuestionVersion, func.coalesce(usage.c.usage_count, 0)).outerjoin(
        usage, usage.c.question_version_id == QuestionVersion.id
    )
    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                QuestionVersion.prompt.ilike(pattern),
                QuestionVersion.topic.ilike(pattern),
                QuestionVersion.explanation.ilike(pattern),
            )
        )
    if topic:
        filters.append(QuestionVersion.topic == topic)
    if difficulty:
        filters.append(QuestionVersion.difficulty == difficulty)
    if status:
        filters.append(QuestionVersion.status == status)
    if verified is not None:
        filters.append(QuestionVersion.verified_at.is_not(None) if verified else QuestionVersion.verified_at.is_(None))
    if filters:
        statement = statement.where(*filters)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.execute(
        statement.order_by(QuestionVersion.updated_at.desc(), QuestionVersion.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return QuestionListOut(
        items=[_question_dict(question, int(usage_count)) for question, usage_count in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def _set_question_fields(question: QuestionVersion, payload: QuestionDraftIn) -> None:
    data = payload.model_dump(mode="json")
    question.question_type = data["question_type"]
    question.prompt = data["prompt"]
    question.stimulus = data["stimulus"]
    question.topic = data["topic"]
    question.difficulty = data["difficulty"]
    question.options = data["options"]
    question.correct_answer = data["correct_answer"]
    question.explanation = data["explanation"]
    question.marks = data["marks"]
    question.negative_marks = data["negative_marks"]
    question.source_reference = data["source_reference"]


def create_question(db: Session, payload: QuestionDraftIn) -> QuestionOut:
    question = QuestionVersion(
        logical_id=uuid.uuid4(),
        version_number=1,
        status="draft",
        verified_at=None,
        **payload.model_dump(mode="json"),
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return _question_dict(question, 0)


def create_questions(db: Session, payloads: Sequence[QuestionDraftIn]) -> list[QuestionOut]:
    questions = [
        QuestionVersion(
            logical_id=uuid.uuid4(),
            version_number=1,
            status="draft",
            verified_at=None,
            **payload.model_dump(mode="json"),
        )
        for payload in payloads
    ]
    db.add_all(questions)
    db.commit()
    return [_question_dict(question, 0) for question in questions]


def update_question(
    db: Session,
    question_id: uuid.UUID,
    payload: QuestionDraftIn,
) -> QuestionOut:
    current = db.scalar(
        select(QuestionVersion)
        .where(QuestionVersion.id == question_id)
        .with_for_update()
    )
    if current is None:
        raise DomainError(404, "question_not_found", "The requested question was not found.")
    if current.status == "archived":
        raise DomainError(409, "question_archived", "Archived questions cannot be edited.")
    if current.status == "draft":
        _set_question_fields(current, payload)
        current.verified_at = None
        updated = current
    else:
        next_version = (db.scalar(
            select(func.max(QuestionVersion.version_number)).where(
                QuestionVersion.logical_id == current.logical_id
            )
        ) or current.version_number) + 1
        updated = QuestionVersion(
            logical_id=current.logical_id,
            version_number=next_version,
            status="draft",
            verified_at=None,
            **payload.model_dump(mode="json"),
        )
        db.add(updated)
    db.commit()
    db.refresh(updated)
    return _question_dict(updated, 0)


def verify_and_publish_question(db: Session, question_id: uuid.UUID) -> QuestionOut:
    question = db.scalar(
        select(QuestionVersion)
        .where(QuestionVersion.id == question_id)
        .with_for_update()
    )
    if question is None:
        raise DomainError(404, "question_not_found", "The requested question was not found.")
    if question.status == "archived":
        raise DomainError(409, "question_archived", "Archived questions cannot be published.")
    if question.status == "published":
        return _question_dict(question, 0)
    try:
        QuestionDraftIn.model_validate({
            "question_type": question.question_type,
            "prompt": question.prompt,
            "stimulus": question.stimulus,
            "topic": question.topic,
            "difficulty": question.difficulty,
            "options": question.options,
            "correct_answer": question.correct_answer,
            "explanation": question.explanation,
            "marks": question.marks,
            "negative_marks": question.negative_marks,
            "source_reference": question.source_reference,
        })
    except ValidationError as error:
        raise DomainError(422, "invalid_question_content", "The question content is incomplete or invalid.") from error
    if not question.explanation.strip():
        raise DomainError(422, "invalid_question_content", "A verified explanation is required before publishing.")
    question.verified_at = _now()
    question.status = "published"
    db.commit()
    db.refresh(question)
    return _question_dict(question, 0)


def archive_question(db: Session, question_id: uuid.UUID) -> int:
    question = db.scalar(
        select(QuestionVersion)
        .where(QuestionVersion.id == question_id)
        .with_for_update()
    )
    if question is None:
        raise DomainError(404, "question_not_found", "The requested question was not found.")
    usage_query = _active_usage_query()
    usage = db.scalar(
        select(func.coalesce(usage_query.c.usage_count, 0)).where(
            usage_query.c.question_version_id == question_id
        )
    ) or 0
    question.status = "archived"
    db.commit()
    return usage


def _section_counts(db: Session, sections: Sequence[AssessmentSection]) -> list[SectionReadinessOut]:
    pools = _eligible_pools(db, [section.id for section in sections])
    return [
        SectionReadinessOut(
            id=section.id,
            section_key=section.section_key,
            title=section.title,
            position=section.position,
            question_count=section.question_count,
            marks_per_question=section.marks_per_question,
            negative_marks=section.negative_marks,
            eligible_verified_count=len(pools.get(section.id, [])),
            ready=len(pools.get(section.id, [])) >= section.question_count,
            question_version_ids=list(db.scalars(
                select(AssessmentQuestionPool.question_version_id).where(
                    AssessmentQuestionPool.section_id == section.id
                )
            )),
        )
        for section in sections
    ]


def _latest_config(db: Session, assessment_id: uuid.UUID) -> AssessmentConfigVersion | None:
    return db.scalar(
        select(AssessmentConfigVersion)
        .where(AssessmentConfigVersion.assessment_id == assessment_id)
        .order_by(AssessmentConfigVersion.version_number.desc())
        .limit(1)
    )


def _authoring_assessment_out(
    db: Session,
    assessment: Assessment,
    config: AssessmentConfigVersion | None,
) -> AuthoringAssessmentOut:
    if config is None:
        return AuthoringAssessmentOut(
            id=assessment.id,
            slug=assessment.slug,
            title=assessment.title,
            description=assessment.description,
            status=assessment.status,
            config_version_id=None,
            config_version_number=None,
            config_status=None,
            duration_seconds=None,
            scoring_policy={},
            eligible_verified_count=0,
            required_question_count=0,
            ready=False,
            sections=[],
        )
    sections = list(
        db.scalars(
            select(AssessmentSection)
            .where(AssessmentSection.config_version_id == config.id)
            .order_by(AssessmentSection.position)
        )
    )
    readiness = _section_counts(db, sections)
    return AuthoringAssessmentOut(
        id=assessment.id,
        slug=assessment.slug,
        title=assessment.title,
        description=assessment.description,
        status=assessment.status,
        config_version_id=config.id,
        config_version_number=config.version_number,
        config_status=config.status,
        duration_seconds=config.duration_seconds,
        show_explanations_after_submission=config.show_explanations_after_submission,
        randomize_questions=config.randomize_questions,
        randomize_options=config.randomize_options,
        scoring_policy=config.scoring_policy,
        eligible_verified_count=sum(item.eligible_verified_count for item in readiness),
        required_question_count=sum(item.question_count for item in readiness),
        ready=bool(readiness) and all(item.ready for item in readiness),
        sections=readiness,
    )


def list_assessments(db: Session) -> list[AuthoringAssessmentOut]:
    result = []
    for assessment in db.scalars(select(Assessment).order_by(Assessment.title)):
        result.append(_authoring_assessment_out(db, assessment, _latest_config(db, assessment.id)))
    return result


def _add_sections(
    db: Session,
    config: AssessmentConfigVersion,
    sections: Sequence[AuthoringSectionIn],
) -> list[AssessmentSection]:
    keys = [section.section_key for section in sections]
    positions = [section.position for section in sections]
    if len(set(keys)) != len(keys) or len(set(positions)) != len(positions):
        raise DomainError(422, "invalid_sections", "Section keys and positions must be unique.")
    result = []
    for section_input in sorted(sections, key=lambda item: item.position):
        section = AssessmentSection(
            config_version_id=config.id,
            section_key=section_input.section_key,
            title=section_input.title,
            position=section_input.position,
            question_count=section_input.question_count,
            marks_per_question=section_input.marks_per_question,
            negative_marks=section_input.negative_marks,
        )
        db.add(section)
        db.flush()
        if section_input.question_version_ids:
            found = set(db.scalars(
                select(QuestionVersion.id).where(
                    QuestionVersion.id.in_(section_input.question_version_ids)
                )
            ))
            if found != set(section_input.question_version_ids):
                raise DomainError(422, "question_not_found", "One or more pool questions do not exist.")
            db.add_all(
                AssessmentQuestionPool(section_id=section.id, question_version_id=question_id)
                for question_id in section_input.question_version_ids
            )
        result.append(section)
    return result


def _create_config(
    db: Session,
    assessment: Assessment,
    *,
    version_number: int,
    status: str,
    duration_seconds: int,
    show_explanations_after_submission: bool,
    randomize_questions: bool,
    randomize_options: bool,
    scoring_policy: dict[str, Any],
    sections: Sequence[AuthoringSectionIn],
) -> AssessmentConfigVersion:
    config = AssessmentConfigVersion(
        assessment_id=assessment.id,
        version_number=version_number,
        status=status,
        duration_seconds=duration_seconds,
        show_explanations_after_submission=show_explanations_after_submission,
        randomize_questions=randomize_questions,
        randomize_options=randomize_options,
        scoring_policy=scoring_policy,
    )
    db.add(config)
    db.flush()
    _add_sections(db, config, sections)
    return config


def create_assessment(db: Session, payload: AssessmentCreateIn) -> AuthoringAssessmentOut:
    if db.scalar(select(Assessment.id).where(Assessment.slug == payload.slug)) is not None:
        raise DomainError(409, "assessment_slug_exists", "An assessment already uses this slug.")
    assessment = Assessment(
        slug=payload.slug,
        title=payload.title,
        description=payload.description,
        status="draft",
    )
    db.add(assessment)
    db.flush()
    config = _create_config(
        db,
        assessment,
        version_number=1,
        status="draft",
        duration_seconds=payload.duration_seconds,
        show_explanations_after_submission=payload.show_explanations_after_submission,
        randomize_questions=payload.randomize_questions,
        randomize_options=payload.randomize_options,
        scoring_policy=payload.scoring_policy,
        sections=payload.sections,
    )
    db.commit()
    return _authoring_assessment_out(db, assessment, config)


def clone_assessment(
    db: Session,
    assessment_id: uuid.UUID,
    payload: AssessmentCloneIn,
) -> AuthoringAssessmentOut:
    source = db.get(Assessment, assessment_id)
    if source is None:
        raise DomainError(404, "assessment_not_found", "The requested assessment was not found.")
    if db.scalar(select(Assessment.id).where(Assessment.slug == payload.slug)) is not None:
        raise DomainError(409, "assessment_slug_exists", "An assessment already uses this slug.")
    source_config = _latest_config(db, source.id)
    if source_config is None:
        raise DomainError(409, "assessment_config_missing", "The source assessment has no configuration to clone.")
    source_sections = list(
        db.scalars(
            select(AssessmentSection)
            .where(AssessmentSection.config_version_id == source_config.id)
            .order_by(AssessmentSection.position)
        )
    )
    section_inputs = []
    for section in source_sections:
        question_ids = list(db.scalars(
            select(AssessmentQuestionPool.question_version_id).where(
                AssessmentQuestionPool.section_id == section.id
            )
        ))
        section_inputs.append(AuthoringSectionIn(
            section_key=section.section_key,
            title=section.title,
            position=section.position,
            question_count=section.question_count,
            marks_per_question=section.marks_per_question,
            negative_marks=section.negative_marks,
            question_version_ids=question_ids,
        ))
    clone = Assessment(slug=payload.slug, title=payload.title, description=source.description, status="draft")
    db.add(clone)
    db.flush()
    config = _create_config(
        db,
        clone,
        version_number=1,
        status="draft",
        duration_seconds=source_config.duration_seconds,
        show_explanations_after_submission=source_config.show_explanations_after_submission,
        randomize_questions=source_config.randomize_questions,
        randomize_options=source_config.randomize_options,
        scoring_policy=source_config.scoring_policy,
        sections=section_inputs,
    )
    db.commit()
    return _authoring_assessment_out(db, clone, config)


def update_assessment_config(
    db: Session,
    assessment_id: uuid.UUID,
    payload: AssessmentConfigUpdateIn,
) -> AuthoringAssessmentOut:
    assessment = db.scalar(
        select(Assessment).where(Assessment.id == assessment_id).with_for_update()
    )
    if assessment is None:
        raise DomainError(404, "assessment_not_found", "The requested assessment was not found.")
    current = _latest_config(db, assessment.id)
    if current is not None and current.status == "draft":
        config = current
        old_sections = list(db.scalars(
            select(AssessmentSection).where(AssessmentSection.config_version_id == current.id)
        ))
        for section in old_sections:
            db.execute(
                AssessmentQuestionPool.__table__.delete().where(
                    AssessmentQuestionPool.section_id == section.id
                )
            )
            db.delete(section)
        db.flush()
        config.duration_seconds = payload.duration_seconds
        config.show_explanations_after_submission = payload.show_explanations_after_submission
        config.randomize_questions = payload.randomize_questions
        config.randomize_options = payload.randomize_options
        config.scoring_policy = payload.scoring_policy
    else:
        version_number = (db.scalar(
            select(func.max(AssessmentConfigVersion.version_number)).where(
                AssessmentConfigVersion.assessment_id == assessment.id
            )
        ) or 0) + 1
        config = AssessmentConfigVersion(
            assessment_id=assessment.id,
            version_number=version_number,
            status="draft",
            duration_seconds=payload.duration_seconds,
            show_explanations_after_submission=payload.show_explanations_after_submission,
            randomize_questions=payload.randomize_questions,
            randomize_options=payload.randomize_options,
            scoring_policy=payload.scoring_policy,
        )
        db.add(config)
        db.flush()
    _add_sections(db, config, payload.sections)
    if assessment.status == "published":
        assessment.status = "draft"
    db.commit()
    return _authoring_assessment_out(db, assessment, config)


def update_section_pool(
    db: Session,
    section_id: uuid.UUID,
    question_version_ids: list[uuid.UUID],
) -> SectionReadinessOut:
    section = db.scalar(
        select(AssessmentSection).where(AssessmentSection.id == section_id).with_for_update()
    )
    if section is None:
        raise DomainError(404, "section_not_found", "The requested assessment section was not found.")
    config = db.get(AssessmentConfigVersion, section.config_version_id)
    if config is None or config.status != "draft":
        raise DomainError(409, "published_config_immutable", "Question pools can only be changed on a draft config.")
    if len(set(question_version_ids)) != len(question_version_ids):
        raise DomainError(422, "duplicate_pool_question", "Question IDs in a pool must be unique.")
    found = set(db.scalars(
        select(QuestionVersion.id).where(QuestionVersion.id.in_(question_version_ids))
    )) if question_version_ids else set()
    if found != set(question_version_ids):
        raise DomainError(422, "question_not_found", "One or more pool questions do not exist.")
    db.execute(
        AssessmentQuestionPool.__table__.delete().where(AssessmentQuestionPool.section_id == section.id)
    )
    db.add_all(
        AssessmentQuestionPool(section_id=section.id, question_version_id=question_id)
        for question_id in question_version_ids
    )
    db.commit()
    db.refresh(section)
    return _section_counts(db, [section])[0]


def publish_assessment(db: Session, assessment_id: uuid.UUID) -> AuthoringAssessmentOut:
    assessment = db.scalar(
        select(Assessment).where(Assessment.id == assessment_id).with_for_update()
    )
    if assessment is None:
        raise DomainError(404, "assessment_not_found", "The requested assessment was not found.")
    config = _latest_config(db, assessment.id)
    if config is None:
        raise DomainError(409, "assessment_config_missing", "Create an assessment configuration before publishing.")
    sections = list(
        db.scalars(
            select(AssessmentSection)
            .where(AssessmentSection.config_version_id == config.id)
            .order_by(AssessmentSection.position)
        )
    )
    if not _is_ready(db, sections):
        readiness = _section_counts(db, sections)
        detail = ", ".join(
            f"{item.title}: {item.eligible_verified_count}/{item.question_count}"
            for item in readiness
            if not item.ready
        )
        raise DomainError(409, "assessment_not_ready", f"Every section must have enough verified published questions. {detail}")
    if config.status != "draft":
        raise DomainError(409, "assessment_config_not_draft", "Only the latest draft config can be published.")
    previous_published = db.scalars(
        select(AssessmentConfigVersion)
        .where(
            AssessmentConfigVersion.assessment_id == assessment.id,
            AssessmentConfigVersion.status == "published",
        )
        .with_for_update()
    )
    for previous in previous_published:
        previous.status = "archived"
    config.status = "published"
    assessment.status = "published"
    db.commit()
    return _authoring_assessment_out(db, assessment, config)
