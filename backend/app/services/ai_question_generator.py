from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import Field, ValidationError, field_validator, model_validator

from app.core.config import Settings, get_settings
from app.schemas import CodeStimulus, PassageStimulus, StrictSchema, TableStimulus

logger = logging.getLogger(__name__)


class GeneratedOption(StrictSchema):
    id: Literal["opt_a", "opt_b", "opt_c", "opt_d"]
    text: str = Field(min_length=1, max_length=2_000)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Option text must not be blank.")
        return value.strip()


class GeneratedQuestion(StrictSchema):
    prompt: str = Field(min_length=10, max_length=20_000)
    topic: str = Field(min_length=1, max_length=150)
    difficulty: Literal["easy", "medium", "hard"]
    stimulus: PassageStimulus | TableStimulus | CodeStimulus | None = None
    options: list[GeneratedOption] = Field(min_length=4, max_length=4)
    correct_answer: dict[str, str]
    explanation: str = Field(min_length=12, max_length=20_000)
    derivation: list[str] = Field(default_factory=list, max_length=20)
    derived_result: float | None = None
    source_reference: Literal["ai_generated"] = "ai_generated"

    @field_validator("prompt", "topic", "explanation")
    @classmethod
    def non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text fields must not be blank.")
        return value.strip()

    @model_validator(mode="after")
    def validate_content(self) -> "GeneratedQuestion":
        ids = [option.id for option in self.options]
        texts = [option.text.casefold().strip() for option in self.options]
        if set(ids) != {"opt_a", "opt_b", "opt_c", "opt_d"}:
            raise ValueError("Exactly the four option IDs opt_a through opt_d are required.")
        if len(set(texts)) != 4:
            raise ValueError("Option texts must be distinct.")
        if set(self.correct_answer) != {"option_id"} or self.correct_answer["option_id"] not in ids:
            raise ValueError("correct_answer.option_id must reference one of the four options.")
        if not self.explanation.strip():
            raise ValueError("An explanation is required.")
        return self


@dataclass(frozen=True)
class GenerationRequest:
    section_title: str
    topics: tuple[str, ...]
    count: int
    difficulty: str
    scenario_seed: str
    previously_used_ids: tuple[str, ...] = ()
    recent_scenarios: tuple[str, ...] = ()


class LLMProvider(Protocol):
    async def generate(self, prompt: str, count: int) -> list[dict[str, object]]:
        ...


def _is_quantitative(request: GenerationRequest, question: GeneratedQuestion) -> bool:
    concepts = f"{request.section_title} {question.topic}".casefold()
    return any(token in concepts for token in ("quant", "numer", "data interpretation", "caselet", "arithmetic"))


def scenario_fingerprint(prompt: str, stimulus: object) -> str:
    payload = {"prompt": prompt.casefold().strip(), "stimulus": stimulus}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _numeric_values(text: str) -> list[Decimal]:
    candidates = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", text)
    values: list[Decimal] = []
    for candidate in candidates:
        try:
            values.append(Decimal(candidate.replace(",", "")))
        except Exception:
            continue
    return values


def _option_values(answer: int, candidates: list[int]) -> list[int]:
    values = [value for value in dict.fromkeys(candidates) if value != answer]
    offset = 1
    while len(values) < 3:
        candidate = answer + 10 * offset
        if candidate not in values:
            values.append(candidate)
        offset += 1
    return [answer, *values[:3]]


def validate_generated_question(
    payload: dict[str, object],
    request: GenerationRequest,
) -> GeneratedQuestion:
    question = GeneratedQuestion.model_validate(payload)
    if _is_quantitative(request, question):
        if (
            question.derived_result is None
            or not math.isfinite(question.derived_result)
            or len(question.derivation) < 2
            or any(not item.strip() for item in question.derivation)
        ):
            raise ValueError("Quantitative questions require a finite derived_result and step-by-step derivation.")
        correct_option = next(
            option for option in question.options if option.id == question.correct_answer["option_id"]
        )
        values = _numeric_values(correct_option.text)
        if not values or not any(
            abs(value - Decimal(str(question.derived_result))) <= Decimal("0.000001")
            for value in values
        ):
            raise ValueError("The correct option does not contain the derived numeric result.")
        derivation_text = " ".join(question.derivation)
        if not any(
            abs(value - Decimal(str(question.derived_result))) <= Decimal("0.000001")
            for value in _numeric_values(derivation_text)
        ):
            raise ValueError("The step-by-step derivation does not contain the stated result.")
    return question


def _fallback_question(request: GenerationRequest, index: int) -> dict[str, object]:
    digest = hashlib.sha256(f"{request.scenario_seed}:{index}".encode()).digest()
    first = 100 + int.from_bytes(digest[:2], "big") % 20 + index * 50
    second = 10 + int.from_bytes(digest[2:4], "big") % 20 + index * 30
    scenario_code = digest[:4].hex().upper()
    topic = request.topics[index % len(request.topics)] if request.topics else request.section_title
    section = request.section_title.casefold()
    if "verbal" in section or "comprehension" in topic.casefold():
        passage = (
            f"Team {chr(65 + digest[4] % 20)} piloted a new code-review checklist with "
            f"{first} engineers. Reviewers reduced avoidable rework by {second}% after "
            "collecting feedback and simplifying the checklist."
        )
        correct = "Collecting feedback helped the team refine a process before scaling it."
        return {
            "prompt": "Which conclusion is best supported by this workplace scenario?",
            "topic": topic,
            "difficulty": request.difficulty,
            "stimulus": {"kind": "passage", "title": f"Engineering team pilot {scenario_code}", "content": passage},
            "options": [
                {"id": "opt_a", "text": "Feedback helped refine a process before broader use."},
                {"id": "opt_b", "text": "The checklist eliminated the need for peer review."},
                {"id": "opt_c", "text": "The pilot measured individual engineer productivity."},
                {"id": "opt_d", "text": "The checklist should only be used by managers."},
            ],
            "correct_answer": {"option_id": "opt_a"},
            "explanation": correct + " The scenario explicitly links feedback to a simpler checklist and less rework.",
            "source_reference": "ai_generated",
        }
    if " cs " in f" {section} " or "technical" in section or (
        "pseudocode" in topic.casefold() and "data" not in section and "interpret" not in section
    ):
        output = index + 2
        answer = output * (output + 1) // 2
        option_values = _option_values(answer, [output, output * 2 + 1, output + 5])
        return {
            "prompt": "A code-review tool runs this pseudocode. What value is printed?",
            "topic": topic,
            "difficulty": request.difficulty,
            "stimulus": {
                "kind": "code",
                "title": f"Pseudocode run {scenario_code}",
                "language": "text",
                "content": f"total = 0\nfor i = 1 to {output}:\n    total = total + i\nprint(total)",
            },
            "options": [
                {"id": f"opt_{letter}", "text": str(value)}
                for letter, value in zip(("a", "b", "c", "d"), option_values)
            ],
            "correct_answer": {"option_id": "opt_a"},
            "explanation": f"The loop adds every integer from 1 through {output}. Summing that range gives n(n+1)/2 = {answer}.",
            "source_reference": "ai_generated",
        }
    if "logical" in section or "abstract" in section:
        step = 2 + second % 8
        third = first + step * 3
        answer = third + step * 4
        option_values = _option_values(answer, [answer + step, answer - step, answer + 2])
        return {
            "prompt": "A screening tool uses this abstract number pattern. Which value comes next?",
            "topic": topic,
            "difficulty": request.difficulty,
            "stimulus": {
                "kind": "code",
                "title": f"Sequence {scenario_code}",
                "language": "text",
                "content": f"{first}, {first + step}, {first + 2 * step}, {third}, ...",
            },
            "options": [
                {"id": f"opt_{letter}", "text": str(value)}
                for letter, value in zip(("a", "b", "c", "d"), option_values)
            ],
            "correct_answer": {"option_id": "opt_a"},
            "explanation": f"The sequence increases by {step} each time. The next value is {third} + {step} = {answer}.",
            "source_reference": "ai_generated",
        }
    if "data" in section or "interpret" in section or "caselet" in section:
        base = 100 * (1 + first % 10)
        increase = second
        result = base * increase // 100
        answer = base + result
        option_values = _option_values(answer, [answer + 5, answer - 5, base + increase])
        options = [
            {"id": f"opt_{letter}", "text": f"{value} units"}
            for letter, value in zip(("a", "b", "c", "d"), option_values)
        ]
        return {
            "prompt": f"In hiring sprint {scenario_code}, a product team recorded {base} active users in week 1. Active users increased by {increase}% in week 2. How many active users were recorded in week 2?",
            "topic": topic,
            "difficulty": request.difficulty,
            "stimulus": {
                "kind": "table",
                "title": f"Weekly product analytics {scenario_code}",
                "headers": ["Week", "Active users"],
                "rows": [["Week 1", base], ["Week 2", "Increase by stated percentage"]],
            },
            "options": options,
            "correct_answer": {"option_id": "opt_a"},
            "explanation": f"Increase = {base} × {increase}/100 = {result}. Add it to the base: {base} + {result} = {answer}.",
            "derivation": [
                f"Compute the increase: {base} × {increase} / 100 = {result}.",
                f"Add the increase to the initial value: {base} + {result} = {answer}.",
            ],
            "derived_result": answer,
            "source_reference": "ai_generated",
        }

    base = 100 * (1 + first % 10)
    percent = 5 + (second % 6) * 5
    increase = base * percent // 100
    answer = base + increase
    option_values = _option_values(answer, [answer + 4, answer - 4, base + percent])
    return {
        "prompt": f"In hiring sprint {scenario_code}, a campus platform receives {base} complete applications in the morning. By evening, complete applications have increased by {percent}%. How many complete applications are there now?",
        "topic": topic,
        "difficulty": request.difficulty,
        "options": [
            {"id": f"opt_{letter}", "text": f"{value} applications"}
            for letter, value in zip(("a", "b", "c", "d"), option_values)
        ],
        "correct_answer": {"option_id": "opt_a"},
        "explanation": f"Increase = {base} × {percent}/100 = {increase}. Add it to the starting count: {base} + {increase} = {answer}.",
        "derivation": [
            f"Calculate the percentage increase: {base} × {percent} / 100 = {increase}.",
            f"Add the increase: {base} + {increase} = {answer}.",
        ],
        "derived_result": answer,
        "source_reference": "ai_generated",
    }


class DeterministicFallbackProvider:
    def __init__(self, request: GenerationRequest):
        self.request = request

    async def generate(self, prompt: str, count: int) -> list[dict[str, object]]:
        del prompt
        return [_fallback_question(self.request, index) for index in range(count)]


class OpenAICompatibleProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate(self, prompt: str, count: int) -> list[dict[str, object]]:
        return await asyncio.wait_for(
            asyncio.to_thread(self._generate_sync, prompt, count),
            timeout=self.settings.llm_timeout_seconds,
        )

    def _generate_sync(self, prompt: str, count: int) -> list[dict[str, object]]:
        schema = {
            "name": "placement_questions",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["questions"],
                "properties": {
                    "questions": {
                        "type": "array",
                        "minItems": count,
                        "maxItems": count,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "prompt", "topic", "difficulty", "stimulus", "options",
                                "correct_answer", "explanation", "derivation", "derived_result",
                                "source_reference",
                            ],
                            "properties": {
                                "prompt": {"type": "string"},
                                "topic": {"type": "string"},
                                "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
                                "stimulus": {
                                    "anyOf": [
                                        {"type": "null"},
                                        {"type": "object"},
                                    ]
                                },
                                "options": {
                                    "type": "array",
                                    "minItems": 4,
                                    "maxItems": 4,
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": ["id", "text"],
                                        "properties": {
                                            "id": {"type": "string", "enum": ["opt_a", "opt_b", "opt_c", "opt_d"]},
                                            "text": {"type": "string"},
                                        },
                                    },
                                },
                                "correct_answer": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["option_id"],
                                    "properties": {
                                        "option_id": {"type": "string", "enum": ["opt_a", "opt_b", "opt_c", "opt_d"]},
                                    },
                                },
                                "explanation": {"type": "string"},
                                "derivation": {"type": "array", "items": {"type": "string"}},
                                "derived_result": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                                "source_reference": {"type": "string", "enum": ["ai_generated"]},
                            },
                        },
                    },
                },
            },
        }
        body = json.dumps({
            "model": self.settings.llm_model,
            "temperature": 0.8,
            "response_format": {"type": "json_schema", "json_schema": schema},
            "messages": [
                {"role": "system", "content": "Generate original, placement-relevant assessment questions. Follow the provided JSON schema exactly."},
                {"role": "user", "content": prompt},
            ],
        }).encode("utf-8")
        request = urllib.request.Request(
            self.settings.llm_base_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.settings.llm_timeout_seconds) as response:
            payload = json.loads(response.read())
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed["questions"]


def _build_prompt(request: GenerationRequest, count: int) -> str:
    topics = ", ".join(request.topics) if request.topics else request.section_title
    used = ", ".join(request.previously_used_ids[-100:]) or "none"
    scenarios = ", ".join(request.recent_scenarios[-50:]) or "none"
    return (
        f"Create exactly {count} fresh questions for section {request.section_title!r}; "
        f"topics: {topics}; difficulty: {request.difficulty}. Frame them around realistic campus "
        "or entry-level software hiring contexts. Vary scenarios, quantities, names, and the "
        "reasoning technique. Include exactly four distinct options with IDs opt_a, opt_b, opt_c, "
        "opt_d and a correct_answer option_id. Include a concise worked explanation. For quantitative, "
        "numerical reasoning, or data interpretation, include a step-by-step derivation with at least "
        "two steps and a derived_result matching the correct option numerically. Use a table, passage, "
        "or code stimulus where it improves the question. Use null stimulus otherwise. Set "
        "source_reference to ai_generated. Do not copy any prior candidate question IDs or scenarios. "
        f"Unique scenario seed: {request.scenario_seed}. Previously used question IDs: {used}. "
        f"Recent scenario fingerprints: {scenarios}."
    )


async def generate_questions(
    request: GenerationRequest,
    settings: Settings | None = None,
) -> list[GeneratedQuestion]:
    effective_settings = settings or get_settings()
    prompt = _build_prompt(request, request.count)
    provider: LLMProvider
    if effective_settings.llm_api_key:
        provider = OpenAICompatibleProvider(effective_settings)
    else:
        provider = None

    for attempt in range(effective_settings.ai_generation_max_retries):
        try:
            active_provider = provider or DeterministicFallbackProvider(GenerationRequest(
                section_title=request.section_title,
                topics=request.topics,
                count=request.count,
                difficulty=request.difficulty,
                scenario_seed=f"{request.scenario_seed}:{attempt}",
                previously_used_ids=request.previously_used_ids,
                recent_scenarios=request.recent_scenarios,
            ))
            payloads = await active_provider.generate(prompt, request.count)
            if len(payloads) != request.count:
                raise ValueError(f"Expected {request.count} questions but provider returned {len(payloads)}.")
            questions = [validate_generated_question(payload, request) for payload in payloads]
            scenario_fingerprints = [
                scenario_fingerprint(
                    item.prompt,
                    item.stimulus.model_dump(mode="json") if item.stimulus else None,
                )
                for item in questions
            ]
            if len(set(scenario_fingerprints)) != len(scenario_fingerprints):
                raise ValueError("Generated question prompts are not unique.")
            if set(scenario_fingerprints).intersection(request.recent_scenarios):
                raise ValueError("Generated question scenario repeats a recent candidate scenario.")
            return questions
        except (ValidationError, ValueError, KeyError, TypeError, IndexError, TimeoutError, OSError) as error:
            if attempt + 1 < effective_settings.ai_generation_max_retries:
                prompt = f"{prompt}\nRegenerate the entire batch. Validation failed: {error}"
            else:
                logger.warning("Question generation failed validation after retries: %s", error)
    raise RuntimeError("Question generation could not produce a validated question batch.")
