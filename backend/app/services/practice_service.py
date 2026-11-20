from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assessment, QuestionVersion
from app.schemas import PracticeTopicOut


def list_topics(db: Session) -> list[PracticeTopicOut]:
    totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"easy": 0, "medium": 0, "hard": 0}
    )
    rows = db.execute(
        select(QuestionVersion.topic, QuestionVersion.difficulty)
        .where(
            QuestionVersion.status == "published",
            QuestionVersion.verified_at.is_not(None),
        )
    )
    for topic, difficulty in rows:
        totals[topic][difficulty] += 1
    blueprints = db.scalars(
        select(Assessment.blueprint_topics).where(Assessment.status == "published")
    )
    for blueprint_topics in blueprints:
        for topic in blueprint_topics or []:
            totals.setdefault(topic, {"easy": 0, "medium": 0, "hard": 0})
    return [
        PracticeTopicOut(
            topic=topic,
            easy_count=counts["easy"],
            medium_count=counts["medium"],
            hard_count=counts["hard"],
            total_count=sum(counts.values()),
        )
        for topic, counts in sorted(totals.items())
    ]
