from __future__ import annotations

import asyncio
import csv
import io
import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Batch,
    College,
    PlacementAttemptAnswer,
    PlacementQuestion,
    PlacementTest,
    PlacementTestAttempt,
    PlacementTestQuestion,
    TestAssignment,
    Topic,
    User,
)
from app.placement_schemas import (
    AssignmentCreateIn,
    AssignmentOut,
    AssignmentUpdateIn,
    AttemptAnswerIn,
    AttemptOut,
    AttemptQuestionOut,
    AttemptResultOut,
    BatchCreateIn,
    BatchOut,
    CollegeCreateIn,
    CollegeOut,
    Difficulty,
    ExtractQuestionsIn,
    ExtractQuestionsOut,
    ExtractionRowError,
    GenerateTestIn,
    GenerateTestOut,
    QuestionBulkIn,
    QuestionBulkOut,
    QuestionListOut,
    QuestionOut,
    PracticeQuestionOut,
    PracticeSimilarIn,
    QuestionWriteIn,
    ReviewActionsIn,
    StudentAnalyticsOut,
    TestCreateIn,
    TestQuestionOrderIn,
    TestQuestionOrderOut,
    TestOut,
    TestUpdateIn,
)
from app.services import placement_generator

ADMIN_ROLES = ("platform_admin", "college_admin")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _college_id(user: User, requested: uuid.UUID | None = None) -> uuid.UUID | None:
    if user.role == "platform_admin":
        return requested
    if user.college_id is None:
        raise HTTPException(status_code=403, detail="A college tenant is required.")
    if requested is not None and requested != user.college_id:
        raise HTTPException(status_code=403, detail="The requested college is outside your tenant.")
    return user.college_id


def _require_admin(user: User) -> None:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Administrator permissions are required.")


def _topic_for_write(
    db: Session,
    *,
    slug: str,
    college_id: uuid.UUID | None,
    scope: str,
) -> Topic:
    topic = db.scalar(
        select(Topic).where(Topic.slug == slug, Topic.college_id == college_id)
    )
    if topic is None:
        topic = Topic(
            slug=slug,
            name=slug.replace("-", " ").title(),
            scope=scope,
            college_id=college_id,
        )
        db.add(topic)
        db.flush()
    return topic


def _question_out(question: PlacementQuestion, topic: Topic) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        college_id=question.college_id,
        scope=question.scope,
        status=question.status,
        topic_slug=topic.slug,
        topic_name=topic.name,
        subtopic=question.subtopic,
        question_type=question.question_type,
        payload=question.payload,
        difficulty=question.difficulty,
        estimated_seconds=question.estimated_seconds,
        company_tags=question.company_tags,
        source_type=question.source_type,
    )


def _visible_questions(user: User):
    if user.role == "platform_admin":
        return select(PlacementQuestion, Topic).join(Topic, Topic.id == PlacementQuestion.topic_id)
    return (
        select(PlacementQuestion, Topic)
        .join(Topic, Topic.id == PlacementQuestion.topic_id)
        .where(
            or_(
                PlacementQuestion.scope == "global",
                PlacementQuestion.college_id == user.college_id,
            )
        )
    )


def list_questions(
    db: Session,
    user: User,
    *,
    search: str | None,
    topic_slug: str | None,
    difficulty: Difficulty | None,
    scope: str | None,
    status: str | None,
    source_type: str | None,
    page: int,
    page_size: int,
) -> QuestionListOut:
    _require_admin(user)
    statement = _visible_questions(user)
    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(
            PlacementQuestion.payload["stem"].as_string().ilike(pattern),
            Topic.name.ilike(pattern),
            PlacementQuestion.subtopic.ilike(pattern),
        ))
    if topic_slug:
        filters.append(Topic.slug == topic_slug)
    if difficulty:
        filters.append(PlacementQuestion.difficulty == difficulty)
    if scope:
        filters.append(PlacementQuestion.scope == scope)
    if status:
        filters.append(PlacementQuestion.status == status)
    if source_type:
        filters.append(PlacementQuestion.source_type == source_type)
    if filters:
        statement = statement.where(*filters)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.execute(
        statement.order_by(PlacementQuestion.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return QuestionListOut(
        items=[_question_out(question, topic) for question, topic in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def _write_question(
    db: Session,
    user: User,
    payload: QuestionWriteIn,
    *,
    status: str = "draft",
    question: PlacementQuestion | None = None,
) -> PlacementQuestion:
    requested_college = payload.college_id
    if payload.scope == "global":
        if user.role != "platform_admin":
            raise HTTPException(status_code=403, detail="Only platform admins can create global questions.")
        college_id = None
    else:
        college_id = _college_id(user, requested_college)
        if college_id is None:
            raise HTTPException(status_code=422, detail="College questions require a college_id.")
    topic = _topic_for_write(
        db,
        slug=payload.topic_slug,
        college_id=college_id,
        scope=payload.scope,
    )
    data = payload.payload.model_dump(mode="json")
    if question is None:
        question = PlacementQuestion(
            college_id=college_id,
            topic_id=topic.id,
            created_by=user.id,
            scope=payload.scope,
            status=status,
            question_type=payload.question_type,
            subtopic=payload.subtopic,
            payload=data,
            difficulty=payload.payload.difficulty,
            estimated_seconds=payload.payload.estimated_seconds,
            company_tags=payload.payload.company_tags,
            source_type=payload.source_type,
        )
        db.add(question)
    else:
        question.college_id = college_id
        question.topic_id = topic.id
        question.scope = payload.scope
        question.question_type = payload.question_type
        question.subtopic = payload.subtopic
        question.payload = data
        question.difficulty = payload.payload.difficulty
        question.estimated_seconds = payload.payload.estimated_seconds
        question.company_tags = payload.payload.company_tags
        question.source_type = payload.source_type
        question.updated_by = user.id
    return question


def create_question(db: Session, user: User, payload: QuestionWriteIn) -> QuestionOut:
    _require_admin(user)
    question = _write_question(db, user, payload)
    db.commit()
    db.refresh(question)
    topic = db.get(Topic, question.topic_id)
    assert topic is not None
    return _question_out(question, topic)


def _editable_question(
    db: Session,
    user: User,
    question_id: uuid.UUID,
    *,
    allow_global_read: bool = False,
) -> tuple[PlacementQuestion, Topic]:
    row = db.execute(
        _visible_questions(user).where(PlacementQuestion.id == question_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    if user.role != "platform_admin" and row[0].scope == "global" and not allow_global_read:
        raise HTTPException(status_code=403, detail="Clone global questions before editing them.")
    return row[0], row[1]


def update_question(db: Session, user: User, question_id: uuid.UUID, payload: QuestionWriteIn) -> QuestionOut:
    _require_admin(user)
    question, _ = _editable_question(db, user, question_id)
    if question.status == "archived":
        raise HTTPException(status_code=409, detail="Archived questions cannot be edited.")
    _write_question(db, user, payload, status=question.status, question=question)
    db.commit()
    db.refresh(question)
    topic = db.get(Topic, question.topic_id)
    assert topic is not None
    return _question_out(question, topic)


def archive_question(db: Session, user: User, question_id: uuid.UUID) -> QuestionOut:
    _require_admin(user)
    question, topic = _editable_question(db, user, question_id)
    published_test_id = db.scalar(
        select(PlacementTest.id)
        .join(PlacementTestQuestion, PlacementTestQuestion.test_id == PlacementTest.id)
        .where(
            PlacementTestQuestion.question_id == question.id,
            PlacementTest.status == "published",
        )
        .limit(1)
    )
    if published_test_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Archive or replace published tests using this question before archiving it.",
        )
    question.status = "archived"
    question.updated_by = user.id
    db.commit()
    db.refresh(question)
    return _question_out(question, topic)


def clone_question_to_college(
    db: Session,
    user: User,
    question_id: uuid.UUID,
    college_id: uuid.UUID | None,
) -> QuestionOut:
    _require_admin(user)
    source, topic = _editable_question(db, user, question_id, allow_global_read=True)
    target_college = _college_id(user, college_id)
    if target_college is None:
        raise HTTPException(status_code=422, detail="A target college is required.")
    target_topic = _topic_for_write(
        db, slug=topic.slug, college_id=target_college, scope="college"
    )
    clone = PlacementQuestion(
        college_id=target_college,
        topic_id=target_topic.id,
        created_by=user.id,
        scope="college",
        status="draft",
        question_type=source.question_type,
        subtopic=source.subtopic,
        payload=dict(source.payload),
        difficulty=source.difficulty,
        estimated_seconds=source.estimated_seconds,
        company_tags=list(source.company_tags),
        source_type=source.source_type,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return _question_out(clone, target_topic)


def bulk_questions(db: Session, user: User, payload: QuestionBulkIn) -> QuestionBulkOut:
    _require_admin(user)
    rows = db.execute(
        _visible_questions(user).where(PlacementQuestion.id.in_(payload.question_ids))
    ).all()
    if len(rows) != len(set(payload.question_ids)):
        raise HTTPException(status_code=404, detail="One or more questions are outside your tenant or missing.")
    if user.role != "platform_admin" and any(question.college_id != user.college_id for question, _ in rows):
        raise HTTPException(status_code=403, detail="Clone global questions before using bulk actions.")
    if payload.action != "archive" and any(question.status == "archived" for question, _ in rows):
        raise HTTPException(status_code=409, detail="Archived questions cannot be changed.")
    if payload.action == "archive":
        published_question_ids = set(db.scalars(
            select(PlacementTestQuestion.question_id)
            .join(PlacementTest, PlacementTest.id == PlacementTestQuestion.test_id)
            .where(
                PlacementTestQuestion.question_id.in_(payload.question_ids),
                PlacementTest.status == "published",
            )
        ))
        if published_question_ids:
            raise HTTPException(
                status_code=409,
                detail="Archive or replace published tests using these questions before archiving them.",
            )
    if payload.action == "set_topic":
        target_college = rows[0][0].college_id
        topic = _topic_for_write(
            db, slug=payload.topic_slug or "", college_id=target_college,
            scope="global" if target_college is None else "college",
        )
        for question, _ in rows:
            if question.college_id != target_college:
                raise HTTPException(status_code=422, detail="Bulk topic updates must use one scope.")
            question.topic_id = topic.id
    for question, _ in rows:
        if payload.action == "activate":
            if question.status == "archived":
                raise HTTPException(status_code=409, detail="Archived questions cannot be activated.")
            question.status = "active"
        elif payload.action == "archive":
            question.status = "archived"
        elif payload.action == "set_difficulty":
            question.difficulty = payload.difficulty or question.difficulty
            question.payload = {**question.payload, "difficulty": question.difficulty}
        question.updated_by = user.id
    db.commit()
    return QuestionBulkOut(updated_count=len(rows))


def _test_out(db: Session, test: PlacementTest) -> TestOut:
    count = db.scalar(
        select(func.count()).select_from(PlacementTestQuestion).where(PlacementTestQuestion.test_id == test.id)
    ) or 0
    return TestOut(
        id=test.id,
        college_id=test.college_id,
        title=test.title,
        description=test.description,
        scope=test.scope,
        duration_minutes=test.duration_minutes,
        negative_marks=test.negative_marks,
        passing_cutoff_percent=test.passing_cutoff_percent,
        status=test.status,
        question_count=count,
    )


def _validate_test_questions(db: Session, user: User, payload: TestCreateIn) -> list[PlacementQuestion]:
    ids = [item.question_id for item in payload.question_ids]
    if not ids:
        raise HTTPException(status_code=422, detail="At least one question is required.")
    rows = list(db.scalars(
        select(PlacementQuestion).where(
            PlacementQuestion.id.in_(ids),
            PlacementQuestion.status == "active",
        )
    ))
    by_id = {question.id: question for question in rows}
    if len(by_id) != len(ids):
        raise HTTPException(status_code=422, detail="Test questions must exist and be active.")
    college_id = _college_id(user, payload.college_id)
    if payload.scope == "global" and user.role != "platform_admin":
        raise HTTPException(status_code=403, detail="Only platform admins can create global tests.")
    if payload.scope == "college" and college_id is None:
        raise HTTPException(status_code=422, detail="College tests require a college_id.")
    for question in rows:
        if question.scope == "college" and question.college_id != college_id:
            raise HTTPException(status_code=403, detail="A test cannot include another college's question.")
        if payload.scope == "global" and question.scope != "global":
            raise HTTPException(status_code=422, detail="Global tests can only use global questions.")
    return [by_id[question_id] for question_id in ids]


def create_test(db: Session, user: User, payload: TestCreateIn) -> TestOut:
    _require_admin(user)
    questions = _validate_test_questions(db, user, payload)
    college_id = None if payload.scope == "global" else _college_id(user, payload.college_id)
    test = PlacementTest(
        college_id=college_id,
        created_by=user.id,
        title=payload.title,
        description=payload.description,
        scope=payload.scope,
        duration_minutes=payload.duration_minutes,
        negative_marks=payload.negative_marks,
        passing_cutoff_percent=payload.passing_cutoff_percent,
        sections=[],
        status="draft",
    )
    db.add(test)
    db.flush()
    db.add_all(
        PlacementTestQuestion(
            test_id=test.id,
            question_id=question.id,
            position=position,
            section_name=link.section_name,
        )
        for position, (question, link) in enumerate(zip(questions, payload.question_ids))
    )
    db.commit()
    db.refresh(test)
    return _test_out(db, test)


def list_tests(db: Session, user: User) -> list[TestOut]:
    _require_admin(user)
    statement = select(PlacementTest)
    if user.role != "platform_admin":
        statement = statement.where(
            or_(PlacementTest.scope == "global", PlacementTest.college_id == user.college_id)
        )
    return [_test_out(db, test) for test in db.scalars(statement.order_by(PlacementTest.created_at.desc()))]


def set_test_status(db: Session, user: User, test_id: uuid.UUID, status: str) -> TestOut:
    _require_admin(user)
    statement = select(PlacementTest).where(PlacementTest.id == test_id).with_for_update()
    if user.role != "platform_admin":
        statement = statement.where(PlacementTest.college_id == user.college_id)
    test = db.scalar(statement)
    if test is None:
        raise HTTPException(status_code=404, detail="Test not found.")
    if status == "published":
        questions = list(db.execute(
            select(PlacementTestQuestion, PlacementQuestion)
            .join(PlacementQuestion, PlacementQuestion.id == PlacementTestQuestion.question_id)
            .where(PlacementTestQuestion.test_id == test.id)
        ))
        if not questions or any(question.status != "active" for _, question in questions):
            raise HTTPException(status_code=409, detail="Publish requires at least one active question.")
    test.status = status
    db.commit()
    db.refresh(test)
    return _test_out(db, test)


def update_test(db: Session, user: User, test_id: uuid.UUID, payload: TestUpdateIn) -> TestOut:
    _require_admin(user)
    statement = select(PlacementTest).where(PlacementTest.id == test_id).with_for_update()
    if user.role != "platform_admin":
        statement = statement.where(PlacementTest.college_id == user.college_id)
    test = db.scalar(statement)
    if test is None:
        raise HTTPException(status_code=404, detail="Test not found.")
    if test.status == "archived":
        raise HTTPException(status_code=409, detail="Archived tests cannot be edited.")
    for field, value in payload.model_dump().items():
        setattr(test, field, value)
    db.commit()
    db.refresh(test)
    return _test_out(db, test)


def create_test_assignment(db: Session, user: User, payload: AssignmentCreateIn) -> AssignmentOut:
    _require_admin(user)
    college_id = _college_id(user, payload.college_id)
    if college_id is None:
        raise HTTPException(status_code=422, detail="A college_id is required to assign a test.")
    test = db.get(PlacementTest, payload.test_id)
    if test is None or test.status != "published":
        raise HTTPException(status_code=404, detail="Published test not found.")
    if test.scope == "college" and test.college_id != college_id:
        raise HTTPException(status_code=403, detail="Test belongs to another college.")
    if test.scope == "global" and user.role == "college_admin":
        # College admins may assign global tests but cannot change the global blueprint.
        pass
    batches = list(db.scalars(
        select(Batch).where(Batch.id.in_(payload.batch_ids), Batch.college_id == college_id)
    )) if payload.batch_ids else []
    if len(batches) != len(set(payload.batch_ids)):
        raise HTTPException(status_code=403, detail="One or more batches are outside your college.")
    assignment = TestAssignment(
        test_id=test.id,
        college_id=college_id,
        batch_ids=[str(item) for item in payload.batch_ids],
        branches=payload.branches,
        graduation_year=payload.graduation_year,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        max_attempts=payload.max_attempts,
        status="active",
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return _assignment_out(assignment, test.title)


def update_test_assignment(
    db: Session,
    user: User,
    assignment_id: uuid.UUID,
    payload: AssignmentUpdateIn,
) -> AssignmentOut:
    _require_admin(user)
    statement = select(TestAssignment).where(TestAssignment.id == assignment_id).with_for_update()
    if user.role != "platform_admin":
        statement = statement.where(TestAssignment.college_id == user.college_id)
    assignment = db.scalar(statement)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    if assignment.status != "active":
        raise HTTPException(status_code=409, detail="Only active assignments can be edited.")
    batches = list(db.scalars(
        select(Batch).where(Batch.id.in_(payload.batch_ids), Batch.college_id == assignment.college_id)
    )) if payload.batch_ids else []
    if len(batches) != len(set(payload.batch_ids)):
        raise HTTPException(status_code=403, detail="One or more batches are outside this assignment's college.")
    assignment.batch_ids = [str(item) for item in payload.batch_ids]
    assignment.branches = payload.branches
    assignment.graduation_year = payload.graduation_year
    assignment.starts_at = payload.starts_at
    assignment.ends_at = payload.ends_at
    assignment.max_attempts = payload.max_attempts
    db.commit()
    db.refresh(assignment)
    test = db.get(PlacementTest, assignment.test_id)
    assert test is not None
    return _assignment_out(assignment, test.title)


def archive_test_assignment(
    db: Session,
    user: User,
    assignment_id: uuid.UUID,
) -> AssignmentOut:
    _require_admin(user)
    statement = select(TestAssignment).where(TestAssignment.id == assignment_id).with_for_update()
    if user.role != "platform_admin":
        statement = statement.where(TestAssignment.college_id == user.college_id)
    assignment = db.scalar(statement)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    assignment.status = "archived"
    db.commit()
    db.refresh(assignment)
    test = db.get(PlacementTest, assignment.test_id)
    assert test is not None
    return _assignment_out(assignment, test.title)


def list_assignments(db: Session, user: User) -> list[AssignmentOut]:
    _require_admin(user)
    statement = (
        select(TestAssignment, PlacementTest)
        .join(PlacementTest, PlacementTest.id == TestAssignment.test_id)
        .order_by(TestAssignment.starts_at.desc())
    )
    if user.role != "platform_admin":
        statement = statement.where(TestAssignment.college_id == user.college_id)
    return [
        _assignment_out(assignment, test.title)
        for assignment, test in db.execute(statement)
    ]


def update_test_question_order(
    db: Session,
    user: User,
    test_id: uuid.UUID,
    payload: TestQuestionOrderIn,
) -> TestOut:
    _require_admin(user)
    statement = select(PlacementTest).where(PlacementTest.id == test_id).with_for_update()
    if user.role != "platform_admin":
        statement = statement.where(PlacementTest.college_id == user.college_id)
    test = db.scalar(statement)
    if test is None:
        raise HTTPException(status_code=404, detail="Test not found.")
    if test.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft tests can be reordered.")
    ids = [row.question_id for row in payload.questions]
    question_statement = select(PlacementQuestion).where(
        PlacementQuestion.id.in_(ids),
        PlacementQuestion.status == "active",
    )
    found = {question.id: question for question in db.scalars(question_statement)}
    if len(found) != len(ids):
        raise HTTPException(status_code=422, detail="Every test question must exist and be active.")
    for question in found.values():
        if question.scope == "college" and question.college_id != test.college_id:
            raise HTTPException(status_code=403, detail="A test cannot include another college's question.")
        if test.scope == "global" and question.scope != "global":
            raise HTTPException(status_code=422, detail="Global tests can only use global questions.")
    for current in db.scalars(select(PlacementTestQuestion).where(PlacementTestQuestion.test_id == test.id)):
        db.delete(current)
    db.flush()
    db.add_all(
        PlacementTestQuestion(
            test_id=test.id,
            question_id=row.question_id,
            position=position,
            section_name=row.section_name,
        )
        for position, row in enumerate(payload.questions)
    )
    db.commit()
    db.refresh(test)
    return _test_out(db, test)


def get_test_question_order(
    db: Session,
    user: User,
    test_id: uuid.UUID,
) -> TestQuestionOrderOut:
    _require_admin(user)
    statement = select(PlacementTest).where(PlacementTest.id == test_id)
    if user.role != "platform_admin":
        statement = statement.where(PlacementTest.college_id == user.college_id)
    test = db.scalar(statement)
    if test is None:
        raise HTTPException(status_code=404, detail="Test not found.")
    links = db.scalars(
        select(PlacementTestQuestion)
        .where(PlacementTestQuestion.test_id == test.id)
        .order_by(PlacementTestQuestion.position)
    )
    return TestQuestionOrderOut(
        questions=[
            {"question_id": link.question_id, "section_name": link.section_name}
            for link in links
        ]
    )


async def replace_question_similar(
    db: Session,
    user: User,
    question_id: uuid.UUID,
    *,
    test_id: uuid.UUID,
    topic_slug: str | None,
    subtopic: str | None,
) -> QuestionOut:
    _require_admin(user)
    source, source_topic = _editable_question(db, user, question_id, allow_global_read=True)
    test_statement = select(PlacementTest).where(PlacementTest.id == test_id)
    if user.role != "platform_admin":
        test_statement = test_statement.where(PlacementTest.college_id == user.college_id)
    test = db.scalar(test_statement)
    if test is None:
        raise HTTPException(status_code=404, detail="Test not found.")
    if test.status != "draft":
        raise HTTPException(status_code=409, detail="Similar-question replacement is available on draft tests only.")
    link = db.scalar(select(PlacementTestQuestion).where(
        PlacementTestQuestion.test_id == test.id,
        PlacementTestQuestion.question_id == source.id,
    ))
    if link is None:
        raise HTTPException(status_code=404, detail="Question is not part of this test.")
    topic = db.get(Topic, source.topic_id)
    assert topic is not None
    requested_topic = topic_slug or topic.slug
    generated = await placement_generator.generate_question(
        prompt=source.payload["stem"],
        topic_slug=requested_topic,
        subtopic=subtopic or source.subtopic,
        difficulty=source.difficulty,
        company_tags=source.company_tags,
    )
    new_topic = _topic_for_write(
        db,
        slug=requested_topic,
        college_id=test.college_id,
        scope=test.scope,
    )
    replacement = PlacementQuestion(
        college_id=test.college_id,
        topic_id=new_topic.id,
        created_by=user.id,
        scope=test.scope,
        status="draft",
        question_type=generated.question_type,
        subtopic=generated.subtopic,
        payload=generated.model_dump(
            mode="json",
            exclude={"question_type", "topic_slug", "subtopic", "source_type", "derivation", "derived_result"},
        ),
        difficulty=generated.difficulty,
        estimated_seconds=generated.estimated_seconds,
        company_tags=generated.company_tags,
        source_type=generated.source_type,
    )
    db.add(replacement)
    db.flush()
    link.question_id = replacement.id
    db.commit()
    db.refresh(replacement)
    return _question_out(replacement, new_topic)


def create_placement_user(
    db: Session,
    creator: User,
    *,
    email: str,
    password_hash: str,
    display_name: str,
    role: str,
    college_id: uuid.UUID,
    batch_id: uuid.UUID | None,
) -> User:
    _require_admin(creator)
    target_college = _college_id(creator, college_id)
    if target_college is None:
        raise HTTPException(status_code=422, detail="College-scoped users require a college.")
    if role == "student":
        if batch_id is None:
            raise HTTPException(status_code=422, detail="Students must be assigned to a batch.")
        batch = db.get(Batch, batch_id)
        if batch is None or batch.college_id != target_college:
            raise HTTPException(status_code=403, detail="Student batch is outside the selected college.")
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="A user already uses this email.")
    user = User(
        email=email,
        password_hash=password_hash,
        display_name=display_name,
        role=role,
        college_id=target_college,
        batch_id=batch_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_colleges(db: Session) -> list[CollegeOut]:
    return [
        CollegeOut(id=college.id, slug=college.slug, name=college.name, status=college.status)
        for college in db.scalars(select(College).order_by(College.name))
    ]


def extract_uploaded_document(filename: str, data: bytes) -> str:
    suffix = filename.rsplit(".", 1)[-1].casefold()
    if suffix in {"txt", "csv", "md"}:
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise HTTPException(status_code=422, detail="Uploaded text must use UTF-8 encoding.") from error
    if suffix == "pdf":
        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
        except ImportError as error:
            raise HTTPException(status_code=503, detail="PDF extraction dependency is not installed.") from error
        try:
            reader = PdfReader(io.BytesIO(data))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except PdfReadError as error:
            raise HTTPException(status_code=422, detail="The uploaded PDF could not be read.") from error
    if suffix == "docx":
        try:
            from docx import Document
            from docx.opc.exceptions import PackageNotFoundError
        except ImportError as error:
            raise HTTPException(status_code=503, detail="DOCX extraction dependency is not installed.") from error
        try:
            document = Document(io.BytesIO(data))
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        except PackageNotFoundError as error:
            raise HTTPException(status_code=422, detail="The uploaded DOCX could not be read.") from error
    raise HTTPException(status_code=415, detail="Supported extraction formats are PDF, DOCX, CSV and TXT.")


def _assignment_out(assignment: TestAssignment, title: str) -> AssignmentOut:
    return AssignmentOut(
        id=assignment.id,
        test_id=assignment.test_id,
        college_id=assignment.college_id,
        batch_ids=assignment.batch_ids,
        branches=assignment.branches,
        graduation_year=assignment.graduation_year,
        starts_at=assignment.starts_at,
        ends_at=assignment.ends_at,
        max_attempts=assignment.max_attempts,
        status=assignment.status,
        test_title=title,
    )


def list_student_assignments(db: Session, user: User) -> list[AssignmentOut]:
    if user.role != "student" or user.college_id is None:
        raise HTTPException(status_code=403, detail="Student permissions are required.")
    rows = db.execute(
        select(TestAssignment, PlacementTest)
        .join(PlacementTest, PlacementTest.id == TestAssignment.test_id)
        .where(
            TestAssignment.college_id == user.college_id,
            TestAssignment.status == "active",
            PlacementTest.status == "published",
        )
        .order_by(TestAssignment.starts_at)
    )
    now = _now()
    eligible = []
    for assignment, test in rows:
        if _as_utc(assignment.starts_at) > now or (
            assignment.ends_at and _as_utc(assignment.ends_at) <= now
        ):
            continue
        if assignment.batch_ids and str(user.batch_id) not in assignment.batch_ids:
            continue
        batch = db.get(Batch, user.batch_id) if user.batch_id else None
        if assignment.branches and (batch is None or batch.branch not in assignment.branches):
            continue
        if assignment.graduation_year and (batch is None or batch.graduation_year != assignment.graduation_year):
            continue
        eligible.append(_assignment_out(assignment, test.title))
    return eligible


def _full_snapshot(question: PlacementQuestion, topic: Topic, link: PlacementTestQuestion) -> dict[str, Any]:
    return {
        "question_id": str(question.id),
        "position": link.position,
        "section_name": link.section_name,
        "topic_slug": topic.slug,
        "subtopic": question.subtopic,
        "question_type": question.question_type,
        "payload": question.payload,
        "difficulty": question.difficulty,
        "estimated_seconds": question.estimated_seconds,
        "company_tags": question.company_tags,
    }


def _attempt_question_out(snapshot: dict[str, Any], answer: PlacementAttemptAnswer | None) -> AttemptQuestionOut:
    payload = snapshot["payload"]
    return AttemptQuestionOut(
        position=snapshot["position"],
        section_name=snapshot["section_name"],
        question_id=uuid.UUID(snapshot["question_id"]),
        topic_slug=snapshot["topic_slug"],
        subtopic=snapshot["subtopic"],
        question_type=snapshot["question_type"],
        stem=payload["stem"],
        stimulus=payload.get("stimulus"),
        latex=payload.get("latex"),
        code_language=payload.get("code_language"),
        options=payload["options"],
        difficulty=snapshot["difficulty"],
        estimated_seconds=snapshot["estimated_seconds"],
        selected_option_id=answer.selected_option_id if answer else None,
        marked_for_review=answer.marked_for_review if answer else False,
    )


def _attempt_out(db: Session, attempt: PlacementTestAttempt, title: str) -> AttemptOut:
    answers = {
        answer.question_position: answer
        for answer in db.scalars(
            select(PlacementAttemptAnswer).where(PlacementAttemptAnswer.attempt_id == attempt.id)
        )
    }
    return AttemptOut(
        id=attempt.id,
        test_id=attempt.test_id,
        title=title,
        status=attempt.status,
        started_at=attempt.started_at,
        deadline_at=attempt.deadline_at,
        server_time=_now(),
        questions=[
            _attempt_question_out(snapshot, answers.get(snapshot["position"]))
            for snapshot in attempt.question_snapshot
        ],
    )


def _owned_attempt(db: Session, user: User, attempt_id: uuid.UUID, *, lock: bool = False) -> PlacementTestAttempt:
    statement = select(PlacementTestAttempt).where(
        PlacementTestAttempt.id == attempt_id,
        PlacementTestAttempt.user_id == user.id,
    )
    if lock:
        statement = statement.with_for_update()
    attempt = db.scalar(statement)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    return attempt


def start_attempt(db: Session, user: User, assignment_id: uuid.UUID) -> AttemptOut:
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can start assigned tests.")
    assignment, test = db.execute(
        select(TestAssignment, PlacementTest)
        .join(PlacementTest, PlacementTest.id == TestAssignment.test_id)
        .where(TestAssignment.id == assignment_id)
        .with_for_update()
    ).one_or_none() or (None, None)
    if assignment is None or test is None or assignment.college_id != user.college_id:
        raise HTTPException(status_code=404, detail="Assigned test not found.")
    if test.status != "published" or assignment.status != "active":
        raise HTTPException(status_code=409, detail="This test assignment is not active.")
    now = _now()
    if _as_utc(assignment.starts_at) > now or (
        assignment.ends_at and _as_utc(assignment.ends_at) <= now
    ):
        raise HTTPException(status_code=409, detail="This assignment is outside its scheduled window.")
    if assignment.batch_ids and str(user.batch_id) not in assignment.batch_ids:
        raise HTTPException(status_code=403, detail="This assignment is not for your batch.")
    batch = db.get(Batch, user.batch_id) if user.batch_id else None
    if assignment.branches and (batch is None or batch.branch not in assignment.branches):
        raise HTTPException(status_code=403, detail="This assignment is not for your branch.")
    if assignment.graduation_year and (batch is None or batch.graduation_year != assignment.graduation_year):
        raise HTTPException(status_code=403, detail="This assignment is not for your graduation year.")
    count = db.scalar(select(func.count()).select_from(PlacementTestAttempt).where(
        PlacementTestAttempt.assignment_id == assignment.id,
        PlacementTestAttempt.user_id == user.id,
    )) or 0
    if count >= assignment.max_attempts:
        raise HTTPException(status_code=409, detail="Maximum attempts for this assignment reached.")
    rows = list(db.execute(
        select(PlacementTestQuestion, PlacementQuestion, Topic)
        .join(PlacementQuestion, PlacementQuestion.id == PlacementTestQuestion.question_id)
        .join(Topic, Topic.id == PlacementQuestion.topic_id)
        .where(PlacementTestQuestion.test_id == test.id)
        .order_by(PlacementTestQuestion.position)
    ))
    if not rows:
        raise HTTPException(status_code=409, detail="The published test has no active questions.")
    if any(question.status != "active" for _, question, _ in rows):
        raise HTTPException(
            status_code=409,
            detail="This test includes archived questions and cannot start.",
        )
    snapshots = [_full_snapshot(question, topic, link) for link, question, topic in rows]
    attempt = PlacementTestAttempt(
        test_id=test.id,
        assignment_id=assignment.id,
        user_id=user.id,
        started_at=now,
        deadline_at=now + timedelta(minutes=test.duration_minutes),
        status="in_progress",
        question_snapshot=snapshots,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return _attempt_out(db, attempt, test.title)


def save_attempt_answer(
    db: Session,
    user: User,
    attempt_id: uuid.UUID,
    payload: AttemptAnswerIn,
) -> AttemptOut:
    attempt = _owned_attempt(db, user, attempt_id, lock=True)
    if attempt.status != "in_progress" or _as_utc(attempt.deadline_at) <= _now():
        raise HTTPException(status_code=409, detail="This attempt is no longer accepting answers.")
    if payload.question_position >= len(attempt.question_snapshot):
        raise HTTPException(status_code=404, detail="Question not found in this attempt.")
    snapshot = attempt.question_snapshot[payload.question_position]
    option_ids = {option["id"] for option in snapshot["payload"]["options"]}
    if payload.selected_option_id is not None and payload.selected_option_id not in option_ids:
        raise HTTPException(status_code=422, detail="The selected option is not part of this question.")
    answer = db.scalar(select(PlacementAttemptAnswer).where(
        PlacementAttemptAnswer.attempt_id == attempt.id,
        PlacementAttemptAnswer.question_position == payload.question_position,
    ))
    if answer is None:
        answer = PlacementAttemptAnswer(
            attempt_id=attempt.id,
            question_id=uuid.UUID(snapshot["question_id"]),
            question_position=payload.question_position,
            selected_option_id=payload.selected_option_id,
            marked_for_review=payload.marked_for_review,
            time_spent_seconds=payload.time_spent_seconds,
        )
        db.add(answer)
    else:
        answer.selected_option_id = payload.selected_option_id
        answer.marked_for_review = payload.marked_for_review
        answer.time_spent_seconds = max(answer.time_spent_seconds, payload.time_spent_seconds)
    db.commit()
    db.refresh(attempt)
    test = db.get(PlacementTest, attempt.test_id)
    assert test is not None
    return _attempt_out(db, attempt, test.title)


def _score_attempt(db: Session, attempt: PlacementTestAttempt, test: PlacementTest) -> dict[str, Any]:
    answers = {
        answer.question_position: answer
        for answer in db.scalars(select(PlacementAttemptAnswer).where(
            PlacementAttemptAnswer.attempt_id == attempt.id
        ))
    }
    correct = incorrect = unanswered = 0
    score = 0.0
    by_topic: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"correct": 0, "incorrect": 0, "unanswered": 0, "time": 0, "count": 0}
    )
    review_answers = []
    for snapshot in attempt.question_snapshot:
        position = snapshot["position"]
        answer = answers.get(position)
        payload = snapshot["payload"]
        selected_id = answer.selected_option_id if answer else None
        is_correct = selected_id == payload["correct_option_id"] if selected_id else None
        seconds = answer.time_spent_seconds if answer else 0
        target_seconds = snapshot["estimated_seconds"]
        if is_correct is True:
            correct += 1
            score += 1
            mistake_tag = "fast_accurate" if seconds <= target_seconds else "slow_accurate"
        elif is_correct is False:
            incorrect += 1
            score -= test.negative_marks
            mistake_tag = "overtime_trap" if seconds > target_seconds * 2 else "rushed_error"
        else:
            unanswered += 1
            mistake_tag = "unanswered"
        if answer:
            answer.is_correct = is_correct
            answer.mistake_tag = mistake_tag
        topic_stats = by_topic[snapshot["topic_slug"]]
        topic_stats[mistake_tag if mistake_tag == "unanswered" else ("correct" if is_correct else "incorrect")] += 1
        topic_stats["time"] += seconds
        topic_stats["count"] += 1
        review_answers.append({
            "question_id": snapshot["question_id"],
            "position": position,
            "topic_slug": snapshot["topic_slug"],
            "stem": payload["stem"],
            "options": payload["options"],
            "selected_option_id": selected_id,
            "correct_option_id": payload["correct_option_id"],
            "is_correct": is_correct,
            "time_spent_seconds": seconds,
            "mistake_tag": mistake_tag,
            "shortcut_solution": payload["shortcut_solution"],
            "concept_solution": payload["concept_solution"],
            "estimated_seconds": target_seconds,
        })
    score = max(0.0, score)
    max_score = float(len(attempt.question_snapshot))
    answered = correct + incorrect
    accuracy = round(100 * correct / answered, 2) if answered else 0
    score_percent = round(100 * score / max_score, 2) if max_score else 0
    return {
        "score": score,
        "max_score": max_score,
        "accuracy_percent": accuracy,
        "score_percent": score_percent,
        "passed": score_percent >= test.passing_cutoff_percent,
        "correct": correct,
        "incorrect": incorrect,
        "unanswered": unanswered,
        "topic_breakdown": [
            {
                "topic_slug": topic,
                "correct": stats["correct"],
                "incorrect": stats["incorrect"],
                "unanswered": stats["unanswered"],
                "accuracy_percent": round(
                    100 * stats["correct"] / (stats["correct"] + stats["incorrect"]), 2
                ) if stats["correct"] + stats["incorrect"] else 0,
                "avg_time_seconds": round(stats["time"] / stats["count"], 2) if stats["count"] else 0,
            }
            for topic, stats in sorted(by_topic.items())
        ],
        "answers": review_answers,
    }


def submit_attempt(db: Session, user: User, attempt_id: uuid.UUID) -> AttemptResultOut:
    attempt = _owned_attempt(db, user, attempt_id, lock=True)
    if attempt.status == "in_progress":
        test = db.get(PlacementTest, attempt.test_id)
        assert test is not None
        result = _score_attempt(db, attempt, test)
        attempt.status = "expired" if _as_utc(attempt.deadline_at) <= _now() else "submitted"
        attempt.submitted_at = _now()
        attempt.result_snapshot = result
        db.commit()
    if attempt.result_snapshot is None:
        raise HTTPException(status_code=409, detail="Attempt result is unavailable.")
    return AttemptResultOut(attempt_id=attempt.id, test_id=attempt.test_id, **attempt.result_snapshot)


def get_attempt(db: Session, user: User, attempt_id: uuid.UUID) -> AttemptOut:
    attempt = _owned_attempt(db, user, attempt_id)
    test = db.get(PlacementTest, attempt.test_id)
    assert test is not None
    return _attempt_out(db, attempt, test.title)


def get_attempt_review(db: Session, user: User, attempt_id: uuid.UUID) -> AttemptResultOut:
    attempt = _owned_attempt(db, user, attempt_id)
    if attempt.status == "in_progress" or attempt.result_snapshot is None:
        raise HTTPException(status_code=409, detail="Review is available after submission.")
    return AttemptResultOut(attempt_id=attempt.id, test_id=attempt.test_id, **attempt.result_snapshot)


async def generate_similar_practice(
    db: Session,
    user: User,
    payload: PracticeSimilarIn,
) -> list[PracticeQuestionOut]:
    attempt = _owned_attempt(db, user, payload.attempt_id)
    result = attempt.result_snapshot
    if attempt.status == "in_progress" or result is None:
        raise HTTPException(status_code=409, detail="Practice recommendations are available after submission.")
    topic_results = result.get("topic_breakdown", [])
    available_topics = {item["topic_slug"] for item in topic_results}
    if payload.topic_slugs:
        if any(topic not in available_topics for topic in payload.topic_slugs):
            raise HTTPException(status_code=422, detail="Practice topics must come from this submitted attempt.")
        selected_topics = payload.topic_slugs
    else:
        selected_topics = [
            item["topic_slug"]
            for item in sorted(topic_results, key=lambda item: (item["accuracy_percent"], -item["avg_time_seconds"]))
        ][:min(3, len(topic_results))]
    if not selected_topics:
        raise HTTPException(status_code=409, detail="No topic diagnostics are available for this attempt.")
    generated = await asyncio.gather(*(
        placement_generator.generate_question(
            prompt=f"Create a fresh placement practice question targeting the candidate's {topic.replace('-', ' ')} topic.",
            topic_slug=topic,
            subtopic=topic.replace("-", " ").title(),
            difficulty="medium",
        )
        for index in range(payload.question_count)
        for topic in [selected_topics[index % len(selected_topics)]]
    ))
    return [
        PracticeQuestionOut(
            topic_slug=question.topic_slug,
            subtopic=question.subtopic,
            question_type=question.question_type,
            stem=question.stem,
            options=question.options,
            correct_option_id=question.correct_option_id,
            shortcut_solution=question.shortcut_solution,
            concept_solution=question.concept_solution,
            estimated_seconds=question.estimated_seconds,
            difficulty=question.difficulty,
            stimulus=question.stimulus,
            latex=question.latex,
            code_language=question.code_language,
        )
        for question in generated
    ]


def student_analytics(db: Session, user: User) -> StudentAnalyticsOut:
    attempts = list(db.scalars(select(PlacementTestAttempt).where(
        PlacementTestAttempt.user_id == user.id,
        PlacementTestAttempt.result_snapshot.is_not(None),
    )))
    topic_totals: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"correct": 0, "incorrect": 0, "unanswered": 0, "time": 0, "count": 0}
    )
    scores = []
    for attempt in attempts:
        result = attempt.result_snapshot or {}
        scores.append(result.get("score_percent", 0))
        for item in result.get("topic_breakdown", []):
            stats = topic_totals[item["topic_slug"]]
            for key in ("correct", "incorrect", "unanswered"):
                stats[key] += item[key]
            count = item["correct"] + item["incorrect"] + item["unanswered"]
            stats["time"] += item["avg_time_seconds"] * count
            stats["count"] += count
    return StudentAnalyticsOut(
        attempts_completed=len(attempts),
        average_score_percent=round(sum(scores) / len(scores), 2) if scores else 0,
        topic_breakdown=[
            {
                "topic_slug": topic,
                "correct": stats["correct"],
                "incorrect": stats["incorrect"],
                "unanswered": stats["unanswered"],
                "accuracy_percent": round(
                    100 * stats["correct"] / (stats["correct"] + stats["incorrect"]), 2
                ) if stats["correct"] + stats["incorrect"] else 0,
                "avg_time_seconds": round(stats["time"] / stats["count"], 2) if stats["count"] else 0,
            }
            for topic, stats in sorted(topic_totals.items())
        ],
    )


def college_analytics(
    db: Session,
    user: User,
    requested_college_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="College administrator permissions are required.")
    college_id = _college_id(user, requested_college_id)
    if college_id is None:
        raise HTTPException(status_code=422, detail="A college_id is required for college analytics.")
    attempt_rows = db.execute(
        select(PlacementTestAttempt, User)
        .join(User, User.id == PlacementTestAttempt.user_id)
        .where(
            PlacementTestAttempt.result_snapshot.is_not(None),
            User.college_id == college_id,
        )
    )
    topic_stats: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"correct": 0, "incorrect": 0, "unanswered": 0, "time": 0, "count": 0}
    )
    cohort: dict[str, dict[str, float | int]] = defaultdict(lambda: {"attempts": 0, "score": 0})
    completed = 0
    scores = []
    for attempt, student in attempt_rows:
        result = attempt.result_snapshot or {}
        completed += 1
        score_percent = result.get("score_percent", 0)
        scores.append(score_percent)
        batch = db.get(Batch, student.batch_id) if student.batch_id else None
        cohort_key = f"{batch.name} · {batch.branch} · {batch.graduation_year}" if batch else "Unassigned"
        cohort[cohort_key]["attempts"] += 1
        cohort[cohort_key]["score"] += score_percent
        for item in result.get("topic_breakdown", []):
            stats = topic_stats[item["topic_slug"]]
            for key in ("correct", "incorrect", "unanswered"):
                stats[key] += item[key]
            count = item["correct"] + item["incorrect"] + item["unanswered"]
            stats["time"] += item["avg_time_seconds"] * count
            stats["count"] += count
    return {
        "college_id": college_id,
        "attempts_completed": completed,
        "average_score_percent": round(sum(scores) / len(scores), 2) if scores else 0,
        "topic_breakdown": [
            {
                "topic_slug": topic,
                "correct": stats["correct"],
                "incorrect": stats["incorrect"],
                "unanswered": stats["unanswered"],
                "accuracy_percent": round(
                    100 * stats["correct"] / (stats["correct"] + stats["incorrect"]), 2
                ) if stats["correct"] + stats["incorrect"] else 0,
                "avg_time_seconds": round(stats["time"] / stats["count"], 2) if stats["count"] else 0,
            }
            for topic, stats in sorted(topic_stats.items())
        ],
        "cohort_breakdown": [
            {
                "cohort": cohort_name,
                "attempts_completed": stats["attempts"],
                "average_score_percent": round(stats["score"] / stats["attempts"], 2) if stats["attempts"] else 0,
            }
            for cohort_name, stats in sorted(cohort.items())
        ],
    }


def create_college(db: Session, payload: CollegeCreateIn) -> CollegeOut:
    if db.scalar(select(College.id).where(College.slug == payload.slug)):
        raise HTTPException(status_code=409, detail="A college already uses this slug.")
    college = College(slug=payload.slug, name=payload.name)
    db.add(college)
    db.commit()
    db.refresh(college)
    return CollegeOut(id=college.id, slug=college.slug, name=college.name, status=college.status)


def create_batch(db: Session, user: User, payload: BatchCreateIn) -> BatchOut:
    _require_admin(user)
    college_id = _college_id(user, payload.college_id)
    if college_id is None:
        raise HTTPException(status_code=422, detail="Platform admin must specify a college when creating a batch.")
    batch = Batch(college_id=college_id, **payload.model_dump(exclude={"college_id"}))
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return BatchOut(id=batch.id, college_id=batch.college_id, **payload.model_dump(exclude={"college_id"}))


def list_batches(db: Session, user: User) -> list[BatchOut]:
    _require_admin(user)
    statement = select(Batch)
    if user.role != "platform_admin":
        statement = statement.where(Batch.college_id == user.college_id)
    return [
        BatchOut(
            id=batch.id,
            college_id=batch.college_id,
            name=batch.name,
            graduation_year=batch.graduation_year,
            branch=batch.branch,
            section=batch.section,
        )
        for batch in db.scalars(statement.order_by(Batch.graduation_year.desc(), Batch.name))
    ]


async def generate_test(db: Session, user: User, payload: GenerateTestIn) -> GenerateTestOut:
    _require_admin(user)
    college_id = _college_id(user, payload.college_id)
    if user.role != "platform_admin" and college_id is None:
        raise HTTPException(status_code=422, detail="A college is required for a generated test.")
    scope = "global" if user.role == "platform_admin" and college_id is None else "college"
    slugs = payload.topic_slugs or [_infer_topic_slug(payload.prompt)]
    generated_questions: list[PlacementQuestion] = []
    for index in range(payload.question_count):
        slug = slugs[index % len(slugs)]
        generated = await placement_generator.generate_question(
            prompt=payload.prompt,
            topic_slug=slug,
            subtopic=slug.replace("-", " ").title(),
            difficulty=payload.target_difficulty,
            company_tags=payload.company_tags,
        )
        if scope == "global":
            topic_college = None
        else:
            topic_college = college_id
        topic = _topic_for_write(db, slug=slug, college_id=topic_college, scope=scope)
        question = PlacementQuestion(
            college_id=college_id,
            topic_id=topic.id,
            created_by=user.id,
            scope=scope,
            status="draft",
            question_type=generated.question_type,
            subtopic=generated.subtopic,
            payload=generated.model_dump(
                mode="json",
                exclude={"question_type", "topic_slug", "subtopic", "source_type", "derivation", "derived_result"},
            ),
            difficulty=generated.difficulty,
            estimated_seconds=generated.estimated_seconds,
            company_tags=generated.company_tags,
            source_type=generated.source_type,
        )
        db.add(question)
        generated_questions.append(question)
    db.flush()
    test = PlacementTest(
        college_id=college_id,
        created_by=user.id,
        title=_title_from_prompt(payload.prompt),
        description=payload.prompt,
        scope=scope,
        duration_minutes=payload.duration_minutes,
        sections=[],
        status="draft",
    )
    db.add(test)
    db.flush()
    db.add_all(
        PlacementTestQuestion(
            test_id=test.id, question_id=question.id, position=index,
            section_name=slugs[index % len(slugs)].replace("-", " ").title(),
        )
        for index, question in enumerate(generated_questions)
    )
    db.commit()
    db.refresh(test)
    generated_out = []
    for question in generated_questions:
        db.refresh(question)
        topic = db.get(Topic, question.topic_id)
        assert topic is not None
        generated_out.append(_question_out(question, topic))
    return GenerateTestOut(test=_test_out(db, test), questions=generated_out)


def _infer_topic_slug(prompt: str) -> str:
    text = prompt.casefold()
    for words, slug in (
        (("percentage", "percent"), "percentages"),
        (("profit", "loss"), "profit-loss"),
        (("work",), "time-and-work"),
        (("speed", "distance", "travel"), "time-speed-distance"),
        (("ratio", "proportion"), "ratios"),
        (("compound interest",), "compound-interest"),
        (("interest",), "simple-interest"),
        (("data", "chart", "table", "caselet"), "data-interpretation"),
        (("verbal", "comprehension", "reading"), "verbal-comprehension"),
        (("logical", "pattern", "reasoning"), "logical-reasoning"),
        (("code", "pseudocode", "algorithm"), "pseudocode"),
    ):
        if any(word in text for word in words):
            return slug
    return "placement-aptitude"


def _title_from_prompt(prompt: str) -> str:
    words = re.sub(r"\s+", " ", prompt).strip().split()
    title = " ".join(words[:8]).strip(" .,:;")
    return (title or "AI-generated placement test")[:200]


def _parse_extracted_text(content: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"(?P<stem>.+?)\s*(?:\r?\n)\s*A[).]\s*(?P<a>.+?)\s*(?:\r?\n)\s*"
        r"B[).]\s*(?P<b>.+?)\s*(?:\r?\n)\s*C[).]\s*(?P<c>.+?)\s*(?:\r?\n)\s*"
        r"D[).]\s*(?P<d>.+?)\s*(?:\r?\n)\s*(?:Answer|Correct answer)\s*:\s*(?P<answer>[A-D])",
        flags=re.IGNORECASE | re.DOTALL,
    )
    output = []
    for match in pattern.finditer(content):
        stem = re.sub(r"^\s*(?:Q(?:uestion)?\s*\d*[.)\:]\s*)", "", match.group("stem").strip(), flags=re.IGNORECASE)
        option_texts = [match.group(letter.lower()).strip() for letter in "ABCD"]
        answer_index = "ABCD".index(match.group("answer").upper())
        options = [dict(id=f"option_{letter.lower()}", text=text) for letter, text in zip("ABCD", option_texts)]
        output.append({
            "scope": "college",
            "topic_slug": "imported-questions",
            "question_type": "mcq_single",
            "payload": {
                "stem": stem,
                "options": options,
                "correct_option_id": options[answer_index]["id"],
                "shortcut_solution": "Review the options and identify the correct answer.",
                "concept_solution": "This extracted item needs human review. Add a complete explanation before using it.",
                "estimated_seconds": 60,
                "difficulty": "medium",
                "company_tags": [],
            },
            "source_type": "imported",
        })
    return output


async def extract_questions(db: Session, user: User, payload: ExtractQuestionsIn) -> ExtractQuestionsOut:
    _require_admin(user)
    college_id = _college_id(user, payload.college_id)
    suffix = payload.filename.rsplit(".", 1)[-1].casefold()
    text = payload.content
    errors: list[ExtractionRowError] = []
    if suffix == "csv":
        try:
            rows = list(csv.DictReader(io.StringIO(text)))
        except csv.Error as error:
            raise HTTPException(status_code=422, detail=f"CSV could not be parsed: {error}") from error
        extracted = []
        if not rows:
            errors.append(ExtractionRowError(
                row_number=2,
                message="CSV contains a header but no question rows.",
            ))
        for row_number, row in enumerate(rows, start=2):
            try:
                extracted.append({
                    **row,
                    "payload": json.loads(row["payload"]),
                    "scope": "college",
                    "college_id": college_id,
                    "source_type": "imported",
                })
            except (KeyError, TypeError, json.JSONDecodeError) as error:
                errors.append(ExtractionRowError(
                    row_number=row_number,
                    message=f"Missing or invalid payload JSON: {error}",
                ))
    elif suffix in {"txt", "md"}:
        extracted = _parse_extracted_text(text)
        if not extracted:
            errors.append(ExtractionRowError(
                row_number=1,
                message="No questions matched the supported four-option answer format.",
            ))
    elif suffix in {"pdf", "docx"}:
        raise HTTPException(
            status_code=415,
            detail=f"{suffix.upper()} extraction needs server-side document parsing and is not enabled in this deployment.",
        )
    else:
        raise HTTPException(status_code=415, detail="Supported extraction formats are CSV and TXT.")
    result: list[QuestionOut] = []
    for row_number, row in enumerate(extracted, start=2 if suffix == "csv" else 1):
        row["college_id"] = college_id
        row["scope"] = "college"
        try:
            question_in = QuestionWriteIn.model_validate(row)
        except ValidationError as error:
            errors.append(ExtractionRowError(
                row_number=row_number,
                message=str(error.errors(include_url=False))[:2_000],
            ))
            continue
        question = _write_question(db, user, question_in)
        db.flush()
        topic = db.get(Topic, question.topic_id)
        assert topic is not None
        result.append(_question_out(question, topic))
    db.commit()
    return ExtractQuestionsOut(questions=result, errors=errors)


async def review_actions(db: Session, user: User, payload: ReviewActionsIn) -> dict[str, int]:
    _require_admin(user)
    updated = 0
    for item in payload.actions:
        question, _ = _editable_question(db, user, item.question_id)
        if question.status == "archived":
            raise HTTPException(status_code=409, detail="Archived questions cannot be reviewed or regenerated.")
        if item.action == "approve":
            question.status = "active"
        elif item.action == "discard":
            question.status = "archived"
        elif item.action == "edit_and_approve":
            replacement = item.replacement
            assert replacement is not None
            _write_question(db, user, replacement, status="active", question=question)
        elif item.action == "regenerate":
            topic = db.get(Topic, question.topic_id)
            assert topic is not None
            generated = await placement_generator.generate_question(
                prompt=question.payload["stem"],
                topic_slug=topic.slug,
                subtopic=question.subtopic,
                difficulty=question.difficulty,
                company_tags=question.company_tags,
            )
            question.payload = generated.model_dump(
                mode="json",
                exclude={"question_type", "topic_slug", "subtopic", "source_type", "derivation", "derived_result"},
            )
            question.question_type = generated.question_type
            question.source_type = generated.source_type
            question.updated_by = user.id
        updated += 1
    db.commit()
    return {"updated_count": updated}


def _public_test_question(snapshot: dict[str, Any]) -> dict[str, Any]:
    payload = snapshot["payload"]
    return {
        "position": snapshot["position"],
        "section_name": snapshot["section_name"],
        "question_id": snapshot["question_id"],
        "topic_slug": snapshot["topic_slug"],
        "subtopic": snapshot["subtopic"],
        "question_type": snapshot["question_type"],
        "stem": payload["stem"],
        "stimulus": payload.get("stimulus"),
        "latex": payload.get("latex"),
        "code_language": payload.get("code_language"),
        "options": payload["options"],
        "difficulty": snapshot["difficulty"],
        "estimated_seconds": snapshot["estimated_seconds"],
    }

