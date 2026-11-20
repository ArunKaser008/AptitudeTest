import asyncio

import pytest

from app.core.config import Settings
from app.services import ai_question_generator
from app.services.ai_question_generator import GenerationRequest, validate_generated_question


def test_fallback_generates_distinct_valid_placement_questions_without_api_key() -> None:
    request = GenerationRequest(
        section_title="Applied Quantitative Reasoning",
        topics=("Quantitative Aptitude: applied percentages",),
        count=3,
        difficulty="medium",
        scenario_seed="ci-test-seed",
    )

    questions = asyncio.run(ai_question_generator.generate_questions(
        request,
        Settings(llm_api_key=None),
    ))

    assert len(questions) == 3
    assert len({question.prompt for question in questions}) == 3
    assert all(question.source_reference == "ai_generated" for question in questions)
    assert all(len(question.options) == 4 for question in questions)
    assert all(len(question.derivation) >= 2 for question in questions)


def test_validation_rejects_bad_math_and_duplicate_options() -> None:
    request = GenerationRequest(
        section_title="Data Interpretation",
        topics=("Data Interpretation: product metrics",),
        count=1,
        difficulty="medium",
        scenario_seed="bad-answer-test",
    )
    payload = ai_question_generator._fallback_question(request, 0)
    payload["derived_result"] = float(payload["derived_result"]) + 1

    with pytest.raises(ValueError, match="correct option"):
        validate_generated_question(payload, request)

    duplicate = ai_question_generator._fallback_question(request, 0)
    options = duplicate["options"]
    options[-1]["text"] = options[0]["text"]
    with pytest.raises(ValueError, match="distinct"):
        validate_generated_question(duplicate, request)


def test_provider_validation_failure_retries_before_returning(monkeypatch: pytest.MonkeyPatch) -> None:
    request = GenerationRequest(
        section_title="Applied Quantitative Reasoning",
        topics=("Quantitative Aptitude: applied percentages",),
        count=1,
        difficulty="medium",
        scenario_seed="retry-test-seed",
    )
    valid = ai_question_generator._fallback_question(request, 0)
    invalid = {**valid, "options": valid["options"][:3]}

    class FakeProvider:
        calls = 0

        def __init__(self, settings: Settings):
            self.settings = settings

        async def generate(self, prompt: str, count: int) -> list[dict[str, object]]:
            del prompt, count
            self.calls += 1
            return [invalid if self.calls == 1 else valid]

    fake = FakeProvider(Settings(llm_api_key="test-key"))
    monkeypatch.setattr(ai_question_generator, "OpenAICompatibleProvider", lambda _: fake)
    result = asyncio.run(ai_question_generator.generate_questions(
        request,
        Settings(llm_api_key="test-key", ai_generation_max_retries=2),
    ))

    assert len(result) == 1
    assert fake.calls == 2
