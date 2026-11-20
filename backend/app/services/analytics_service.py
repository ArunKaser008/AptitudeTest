from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assessment, AssessmentAttempt, CandidateSession
from app.schemas import (
    AttemptResultOut,
    CandidatePerformanceOut,
    PerformanceTopicOut,
    PerformanceTrendOut,
    RecommendationListOut,
    RecommendationOut,
)


def _topic_counts(result: AttemptResultOut) -> dict[str, dict[str, float | int]]:
    aggregated: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"total": 0, "correct": 0, "incorrect": 0, "unanswered": 0, "time": 0.0}
    )
    if result.topics:
        for topic_result in result.topics:
            values = aggregated[topic_result.topic]
            count = topic_result.correct + topic_result.incorrect + topic_result.unanswered
            values["total"] += count
            values["correct"] += topic_result.correct
            values["incorrect"] += topic_result.incorrect
            values["unanswered"] += topic_result.unanswered
            values["time"] += topic_result.avg_time_seconds * count
        return aggregated

    for question in result.review:
        values = aggregated[question.topic]
        values["total"] += 1
        values["time"] += question.time_spent_seconds
        if question.is_correct is True:
            values["correct"] += 1
        elif question.is_correct is False:
            values["incorrect"] += 1
        else:
            values["unanswered"] += 1
    return aggregated


def get_candidate_performance(
    db: Session,
    candidate_session: CandidateSession,
) -> CandidatePerformanceOut:
    rows = db.execute(
        select(AssessmentAttempt, Assessment)
        .join(Assessment, Assessment.id == AssessmentAttempt.assessment_id)
        .where(
            AssessmentAttempt.candidate_session_id == candidate_session.id,
            AssessmentAttempt.status.in_(("submitted", "expired")),
            AssessmentAttempt.result_snapshot.is_not(None),
        )
        .order_by(AssessmentAttempt.submitted_at, AssessmentAttempt.created_at)
    )
    trend: list[PerformanceTrendOut] = []
    topic_totals: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"total": 0, "correct": 0, "incorrect": 0, "unanswered": 0, "time": 0.0}
    )
    completed_attempts = 0
    correct_count = 0
    attempted_count = 0
    question_count = 0
    elapsed_time = 0
    practice_time = 0
    earned_score = 0.0
    possible_score = 0.0
    for attempt, assessment in rows:
        if not attempt.result_snapshot:
            continue
        result = AttemptResultOut.model_validate(attempt.result_snapshot)
        completed_attempts += 1
        this_question_count = result.correct + result.incorrect + result.unanswered
        this_attempted_count = result.correct + result.incorrect
        question_count += this_question_count
        attempted_count += this_attempted_count
        correct_count += result.correct
        elapsed_time += sum(item.time_spent_seconds for item in result.review)
        earned_score += result.score
        possible_score += result.max_score
        if assessment.category == "practice":
            practice_time += result.elapsed_seconds
        submitted_at = attempt.submitted_at or attempt.updated_at
        trend.append(PerformanceTrendOut(
            attempt_id=attempt.id,
            assessment_slug=assessment.slug,
            assessment_title=result.assessment_title,
            category=assessment.category,
            submitted_at=submitted_at,
            score_percent=round(
                min(100, max(0, 100 * result.score / result.max_score))
                if result.max_score else 0,
                2,
            ),
            accuracy_percent=result.accuracy_percent if this_attempted_count else 0,
        ))
        for topic, totals in _topic_counts(result).items():
            for key, value in totals.items():
                topic_totals[topic][key] += value

    topics: list[PerformanceTopicOut] = []
    for topic, values in sorted(topic_totals.items()):
        total = int(values["total"])
        correct = int(values["correct"])
        incorrect = int(values["incorrect"])
        unanswered = int(values["unanswered"])
        answered = correct + incorrect
        topics.append(PerformanceTopicOut(
            topic=topic,
            total_questions=total,
            correct=correct,
            incorrect=incorrect,
            unanswered=unanswered,
            accuracy_percent=round(100 * correct / answered, 2) if answered else 0,
            avg_time_seconds=round(float(values["time"]) / total, 2) if total else 0,
        ))

    return CandidatePerformanceOut(
        completed_attempts=completed_attempts,
        readiness_score=round(100 * earned_score / possible_score, 2) if possible_score else 0,
        average_accuracy_percent=round(100 * correct_count / attempted_count, 2) if attempted_count else 0,
        average_time_seconds=round(elapsed_time / question_count, 2) if question_count else 0,
        practice_time_seconds=practice_time,
        trend=trend,
        topics=topics,
    )


def get_candidate_recommendations(
    db: Session,
    candidate_session: CandidateSession,
) -> RecommendationListOut:
    performance = get_candidate_performance(db, candidate_session)
    recommendations: list[RecommendationOut] = []
    for topic in sorted(
        (
            item for item in performance.topics
            if item.accuracy_percent < 60 and item.correct + item.incorrect > 0
        ),
        key=lambda item: (item.accuracy_percent, item.topic),
    ):
        recommendations.append(RecommendationOut(
            id=f"weak:{topic.topic}",
            kind="weak_topic",
            title=f"Strengthen {topic.topic}",
            description=f"Your recent accuracy is {topic.accuracy_percent}%. Practise this topic with a fresh timed question set.",
            topic=topic.topic,
            action_label="Practise topic",
            estimated_minutes=10,
        ))
    for topic in sorted(
        (item for item in performance.topics if item.avg_time_seconds > 75),
        key=lambda item: (-item.avg_time_seconds, item.topic),
    ):
        recommendations.append(RecommendationOut(
            id=f"speed:{topic.topic}",
            kind="time_management",
            title=f"Build speed in {topic.topic}",
            description=f"You average {round(topic.avg_time_seconds)} seconds per question. Practise a short set to improve pacing.",
            topic=topic.topic,
            action_label="Practise for speed",
            estimated_minutes=10,
        ))

    completed_slugs = {item.assessment_slug for item in performance.trend}
    completed_categories = {item.category for item in performance.trend}
    published = list(db.scalars(
        select(Assessment).where(Assessment.status == "published").order_by(Assessment.title)
    ))
    baseline = next((item for item in published if item.category == "aptitude"), None)
    if performance.completed_attempts == 0 and baseline is not None:
        recommendations.append(RecommendationOut(
            id=f"baseline:{baseline.slug}",
            kind="baseline",
            title="Establish your placement baseline",
            description="Start a verified timed assessment to see which skills to focus on next.",
            assessment_slug=baseline.slug,
            action_label="Take assessment",
            estimated_minutes=15,
        ))
    elif "aptitude" in completed_categories:
        company_mock = next(
            (
                item for item in published
                if item.category == "company_mock" and item.slug not in completed_slugs
            ),
            None,
        )
        if company_mock is not None:
            recommendations.append(RecommendationOut(
                id=f"progression:{company_mock.slug}",
                kind="progression",
                title=f"Progress to {company_mock.target_role or 'company-style'} practice",
                description="Try a role-focused mock to practise applying your aptitude skills under a hiring-style timer.",
                assessment_slug=company_mock.slug,
                action_label="Try company mock",
                estimated_minutes=15,
            ))
    return RecommendationListOut(count=len(recommendations), items=recommendations)
