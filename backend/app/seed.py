from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Assessment, AssessmentConfigVersion, AssessmentSection

_BLUEPRINTS = (
    {
        "slug": "it-services-cognitive-quant-drive",
        "title": "IT Services Cognitive & Quant Drive",
        "description": "A timed fresher-placement simulation spanning applied numerical reasoning, data caselets, logic, workplace comprehension, and CS fundamentals.",
        "category": "company_mock",
        "target_role": "IT Services",
        "duration_seconds": 1_200,
        "topics": [
            "Quantitative Aptitude: applied percentages and ratios",
            "Quantitative Aptitude: numerical estimation",
            "Data Interpretation: product and recruitment caselets",
            "Logical Reasoning: abstract patterns and constraints",
            "Verbal Ability: workplace comprehension",
            "CS Fundamentals: pseudocode and data structures",
        ],
        "sections": [
            ("quantitative", "Applied Quantitative Reasoning", 3),
            ("data-interpretation", "Data Interpretation Caselets", 3),
            ("logical-reasoning", "Logical & Abstract Reasoning", 3),
            ("verbal", "Workplace Verbal Comprehension", 3),
            ("cs-fundamentals", "CS & Pseudocode Aptitude", 3),
        ],
    },
    {
        "slug": "product-sde-analytical-cs-aptitude",
        "title": "Product / SDE Analytical & CS Aptitude",
        "description": "A timed product-engineering readiness simulation with analytical reasoning, data interpretation, code tracing, and technical fundamentals.",
        "category": "aptitude",
        "target_role": "SDE / Product",
        "duration_seconds": 1_500,
        "topics": [
            "Quantitative Aptitude: applied probability and estimation",
            "Data Interpretation: engineering metrics caselets",
            "Logical Reasoning: algorithmic patterns",
            "Verbal Ability: technical workplace communication",
            "CS Fundamentals: pseudocode, complexity, and data structures",
        ],
        "sections": [
            ("quantitative", "Applied Numerical Reasoning", 3),
            ("data-interpretation", "Engineering Metrics Caselets", 3),
            ("logical-reasoning", "Logical & Algorithmic Patterns", 3),
            ("verbal", "Workplace Comprehension", 3),
            ("cs-fundamentals", "CS & Pseudocode Aptitude", 3),
        ],
    },
    {
        "slug": "data-consulting-caselet-round",
        "title": "Data & Consulting Caselet Round",
        "description": "A timed fresher simulation focused on interpreting business tables, quantitative trade-offs, structured logic, and concise workplace reasoning.",
        "category": "company_mock",
        "target_role": "Analytics",
        "duration_seconds": 1_500,
        "topics": [
            "Quantitative Aptitude: business arithmetic and percentages",
            "Data Interpretation: consulting and product caselets",
            "Logical Reasoning: structured inference",
            "Verbal Ability: business comprehension",
        ],
        "sections": [
            ("quantitative", "Business Numerical Reasoning", 4),
            ("data-interpretation", "Business & Product Caselets", 5),
            ("logical-reasoning", "Structured Logical Inference", 3),
            ("verbal", "Business Workplace Comprehension", 3),
        ],
    },
)


def seed_default_assessments(db: Session) -> None:
    for blueprint in _BLUEPRINTS:
        assessment = db.scalar(
            select(Assessment).where(Assessment.slug == blueprint["slug"])
        )
        if assessment is not None:
            continue
        assessment = Assessment(
            slug=blueprint["slug"],
            title=blueprint["title"],
            description=blueprint["description"],
            status="published",
            category=blueprint["category"],
            target_role=blueprint["target_role"],
            ai_generation_enabled=True,
            blueprint_topics=blueprint["topics"],
        )
        db.add(assessment)
        db.flush()
        config = AssessmentConfigVersion(
            assessment_id=assessment.id,
            version_number=1,
            status="published",
            duration_seconds=blueprint["duration_seconds"],
            show_explanations_after_submission=True,
            randomize_questions=True,
            randomize_options=True,
            scoring_policy={"minimum_score_zero": True},
        )
        db.add(config)
        db.flush()
        for position, (section_key, title, question_count) in enumerate(blueprint["sections"]):
            db.add(AssessmentSection(
                config_version_id=config.id,
                section_key=section_key,
                title=title,
                position=position,
                question_count=question_count,
                marks_per_question=1,
                negative_marks=0.25 if blueprint["category"] == "company_mock" else 0,
            ))
    db.commit()


def main() -> None:
    with SessionLocal() as db:
        seed_default_assessments(db)


if __name__ == "__main__":
    main()
