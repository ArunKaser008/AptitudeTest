from __future__ import annotations

import asyncio
import json
import logging
import random
import urllib.request
from typing import Any, Literal

from pydantic import Field, ValidationError

from app.core.config import get_settings
from app.placement_schemas import (
    Difficulty,
    PlacementQuestionPayload,
    QuestionOption,
    QuestionType,
)

logger = logging.getLogger(__name__)
QuestionSource = Literal["parametric", "ai_generated"]


class GeneratedPlacementQuestion(PlacementQuestionPayload):
    question_type: QuestionType
    topic_slug: str = Field(min_length=1, max_length=100)
    subtopic: str = Field(default="", max_length=150)
    source_type: QuestionSource
    derivation: list[str] = Field(default_factory=list, max_length=20)
    derived_result: float | None = None


def _topic_question_type(topic_slug: str, prompt: str) -> QuestionType:
    value = f"{topic_slug} {prompt}".casefold()
    if any(token in value for token in ("data", "interpret", "chart", "table", "caselet")):
        return "data_interpretation"
    if any(token in value for token in ("code", "pseudo", "program", "algorithm", "flowchart", "cs")):
        return "pseudocode"
    if any(token in value for token in ("verbal", "reading", "comprehension", "communication")):
        return "verbal"
    if any(token in value for token in ("logical", "reasoning", "pattern", "series")):
        return "logical_reasoning"
    return "mcq_single"


def _number_text(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _build_numeric_question(
    *,
    topic_slug: str,
    subtopic: str,
    difficulty: Difficulty,
    prompt: str,
    company_tags: list[str],
) -> GeneratedPlacementQuestion:
    rng = random.SystemRandom()
    topic = f"{topic_slug} {subtopic}".casefold()
    code = rng.randrange(100_000, 999_999)
    derivation: list[str]
    context = f"placement practice scenario {code}"
    if "percent" in topic:
        base, percent = rng.randrange(240, 1_201, 20), rng.choice([10, 12, 15, 20, 25, 30])
        answer = base * percent / 100
        stem = f"In {context}, a service desk resolves {base} tickets in a shift. {percent}% are flagged for follow-up. How many tickets are flagged?"
        derivation = [f"Convert {percent}% to {percent}/100.", f"Compute {base} × {percent}/100 = {_number_text(answer)}."]
        shortcut = f"Take {percent}% of {base}: {percent // 10}% is {base * percent // 1000}; scale to {_number_text(answer)}."
        solution = f"Percentage amount = base × rate / 100 = {base} × {percent} / 100 = {_number_text(answer)} tickets."
        label = "Percentage calculation"
    elif "profit" in topic or "loss" in topic:
        cost, percent = rng.randrange(300, 1_501, 25), rng.choice([10, 12, 15, 20, 25, 30])
        answer = cost * (100 + percent) / 100
        stem = f"A campus technology vendor buys a device for ₹{cost} and targets a {percent}% profit. What should the selling price be?"
        derivation = [f"Profit = {cost} × {percent}/100 = {_number_text(cost * percent / 100)}.", f"Selling price = {cost} + {_number_text(cost * percent / 100)} = {_number_text(answer)}."]
        shortcut = f"Multiply cost by (100 + profit%)/100: {cost} × {100 + percent}/100 = {_number_text(answer)}."
        solution = f"Profit is {percent}% of cost. Add ₹{_number_text(cost * percent / 100)} to ₹{cost}; selling price = ₹{_number_text(answer)}."
        label = "Profit and loss"
    elif "ratio" in topic or "proportion" in topic:
        a, b = rng.randrange(2, 8), rng.randrange(3, 10)
        total_units = a + b
        multiplier = rng.randrange(12, 60, 3)
        total = multiplier * total_units
        answer = multiplier * a
        stem = f"A project team splits {total} review tasks between two squads in the ratio {a}:{b}. How many tasks go to the first squad?"
        derivation = [f"Total ratio parts = {a} + {b} = {total_units}.", f"One part = {total}/{total_units} = {multiplier}; first squad gets {a} × {multiplier} = {answer}."]
        shortcut = f"First share = total × {a}/{total_units} = {answer} tasks."
        solution = f"Divide {total} tasks into {total_units} equal parts. The first squad receives {a} of those parts, or {answer} tasks."
        label = "Ratios"
    elif "work" in topic:
        hours_a, hours_b = rng.choice([(6, 12), (8, 8), (10, 15), (12, 18)])
        answer = round(hours_a * hours_b / (hours_a + hours_b), 2)
        stem = f"Two analysts can independently complete a data cleanup in {hours_a} and {hours_b} hours. How many hours will they take working together at constant rates?"
        derivation = [f"Combined rate = 1/{hours_a} + 1/{hours_b} = {(hours_a + hours_b)}/{hours_a * hours_b} jobs/hour.", f"Time = reciprocal rate = {_number_text(answer)} hours."]
        shortcut = f"For two workers use ab/(a+b): {hours_a} × {hours_b}/({hours_a}+{hours_b}) = {_number_text(answer)} hours."
        solution = f"Add rates, not times. Their combined rate is 1/{hours_a} + 1/{hours_b}; the reciprocal gives {_number_text(answer)} hours."
        label = "Time and work"
    elif "speed" in topic or "distance" in topic or "travel" in topic:
        speed = rng.randrange(30, 91, 5)
        hours = rng.randrange(2, 8)
        answer = speed * hours
        stem = f"A field engineer travels between two campus sites at an average {speed} km/h for {hours} hours. What distance is covered?"
        derivation = [f"Use distance = speed × time.", f"{speed} × {hours} = {answer} km."]
        shortcut = f"Multiply speed by time: {speed} × {hours} = {answer} km."
        solution = f"At a constant average speed, distance = {speed} km/h × {hours} h = {answer} km."
        label = "Time, speed and distance"
    elif "compound" in topic:
        principal, rate, years = rng.choice([(1_000, 10, 2), (2_000, 5, 2), (1_500, 20, 2), (1_000, 10, 3)])
        answer = round(principal * (1 + rate / 100) ** years, 2)
        stem = f"A student invests ₹{principal} in a placement fund that earns {rate}% annually, compounded yearly. What is its value after {years} years?"
        derivation = [f"Use A = P(1 + r/100)^t.", f"{principal} × (1 + {rate}/100)^{years} = {_number_text(answer)}."]
        shortcut = f"Apply the yearly growth factor {100 + rate}/100 for {years} years: value = ₹{_number_text(answer)}."
        solution = f"Compound growth is multiplicative: year-end value = ₹{principal} × {1 + rate / 100}^{years} = ₹{_number_text(answer)}."
        label = "Compound interest"
    elif "interest" in topic:
        principal, rate, years = rng.choice([(1_000, 8, 3), (2_500, 6, 2), (1_200, 10, 4), (3_000, 5, 3)])
        answer = principal * rate * years / 100
        stem = f"A student loan balance of ₹{principal} is charged simple interest at {rate}% per year for {years} years. How much interest accrues?"
        derivation = [f"Use simple interest = principal × rate × time / 100.", f"{principal} × {rate} × {years}/100 = {_number_text(answer)}."]
        shortcut = f"Simple interest = {principal} × {rate} × {years}/100 = ₹{_number_text(answer)}."
        solution = f"Substitute the principal, annual rate and time into SI = Prt/100 to get ₹{_number_text(answer)}."
        label = "Simple interest"
    else:
        return _build_llm_or_reasoning_question(topic_slug, subtopic, difficulty, prompt, company_tags, code)

    wrongs = list(dict.fromkeys([
        answer + max(1, round(answer * 0.1, 2)),
        max(0, answer - max(1, round(answer * 0.1, 2))),
        answer * 2,
    ]))
    while len(wrongs) < 3:
        wrongs.append(answer + len(wrongs) * 7 + 3)
    values = [answer, *wrongs[:3]]
    rng.shuffle(values)
    options = [QuestionOption(id=f"option_{chr(97 + index)}", text=_number_text(float(value))) for index, value in enumerate(values)]
    correct_id = options[values.index(answer)].id
    return GeneratedPlacementQuestion(
        question_type="mcq_single",
        topic_slug=topic_slug,
        subtopic=subtopic or label,
        source_type="parametric",
        stem=stem,
        options=options,
        correct_option_id=correct_id,
        shortcut_solution=shortcut,
        concept_solution=solution,
        estimated_seconds=75 if difficulty == "hard" else 60 if difficulty == "medium" else 45,
        difficulty=difficulty,
        company_tags=company_tags,
        derivation=derivation,
        derived_result=float(answer),
    )


def _build_llm_or_reasoning_question(
    topic_slug: str,
    subtopic: str,
    difficulty: Difficulty,
    prompt: str,
    company_tags: list[str],
    seed: int,
) -> GeneratedPlacementQuestion:
    topic = f"{topic_slug} {subtopic}".casefold()
    question_type = _topic_question_type(topic_slug, prompt)
    if question_type == "pseudocode":
        start = seed % 9 + 2
        value = sum(range(start, start + 5))
        stem = f"Review the pseudocode used in a placement screening round:\n\n total = 0\n for k from {start} to {start + 4}:\n     total = total + k\n\nWhat is the final value of total?"
        explanation = f"The loop adds every integer from {start} through {start + 4}: {value}."
        options_text = [str(value), str(value + 1), str(value - 1), str(value + 5)]
        shortcut = f"Pair the endpoints: five consecutive integers average {start + 2}; 5 × {start + 2} = {value}."
        solution = f"Iterate the loop values {', '.join(str(item) for item in range(start, start + 5))} and add them to total. The result is {value}."
    elif question_type == "verbal":
        change = seed % 8 + 3
        stem = f"A project team reduced its code review backlog by {change}% after introducing short daily triage meetings. Which conclusion is best supported by this information?"
        options_text = [
            "The meetings were followed by a smaller review backlog.",
            "Every code review was completed during the meetings.",
            "The team stopped reviewing code after the change.",
            "The backlog reduction proves individual performance increased.",
        ]
        value = 0
        shortcut = "Choose only the conclusion directly supported by the stated before-and-after relationship."
        solution = "The statement reports a lower backlog after the meetings. It does not say reviews happened during meetings or establish individual productivity."
    elif question_type == "data_interpretation":
        base, increase = 100 + seed % 400, seed % 25 + 10
        result = round(base * increase / 100)
        stem = f"A campus hiring dashboard shows {base} candidates in one cohort and a {increase}% increase in the next cohort. How many additional candidates joined?"
        options_text = [str(result), str(base + increase), str(base - increase), str(result + increase)]
        value = 0
        shortcut = f"Compute {increase}% of {base} to find the increase."
        solution = f"Additional candidates = {base} × {increase}/100 = {result}."
        question_type = "data_interpretation"
    else:
        start = seed % 15 + 3
        result = start + 12
        stem = f"A hiring assessment sequence is {start}, {start + 3}, {start + 6}, {start + 9}, … What is the next number?"
        options_text = [str(result), str(result + 2), str(result - 3), str(result * 2)]
        value = result
        shortcut = "The sequence increases by 3 each step."
        solution = f"Each term adds 3. The next term is {start + 9} + 3 = {result}."
    rng = random.SystemRandom()
    options = [QuestionOption(id=f"option_{chr(97 + index)}", text=text) for index, text in enumerate(options_text)]
    correct_text = str(value) if value else options_text[0]
    correct_id = next(option.id for option in options if option.text == correct_text)
    return GeneratedPlacementQuestion(
        question_type=question_type,
        topic_slug=topic_slug,
        subtopic=subtopic or topic_slug.replace("-", " ").title(),
        source_type="parametric",
        stem=stem,
        options=options,
        correct_option_id=correct_id,
        shortcut_solution=shortcut,
        concept_solution=solution,
        estimated_seconds=90 if difficulty == "hard" else 60 if difficulty == "medium" else 45,
        difficulty=difficulty,
        company_tags=company_tags,
    )


def _placement_question_output_schema(topic_slug: str, difficulty: Difficulty) -> dict[str, Any]:
    option_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "id": {"type": "string"},
            "text": {"type": "string"},
        },
        "required": ["id", "text"],
    }
    properties: dict[str, Any] = {
        "stem": {"type": "string"},
        "question_type": {
            "type": "string",
            "enum": ["mcq_single", "data_interpretation", "pseudocode", "logical_reasoning", "verbal"],
        },
        "topic_slug": {"type": "string", "enum": [topic_slug]},
        "subtopic": {"type": "string"},
        "source_type": {"type": "string", "enum": ["ai_generated"]},
        "difficulty": {"type": "string", "enum": [difficulty]},
        "estimated_seconds": {"type": "integer"},
        "options": {"type": "array", "items": option_schema},
        "correct_option_id": {"type": "string"},
        "shortcut_solution": {"type": "string"},
        "concept_solution": {"type": "string"},
        "company_tags": {"type": "array", "items": {"type": "string"}},
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def _llm_generate(prompt: str, topic_slug: str, difficulty: Difficulty) -> dict[str, Any]:
    settings = get_settings()
    body = {
        "model": settings.llm_model,
        "temperature": 0.6,
        "messages": [
            {"role": "system", "content": "Generate one original fresher placement aptitude question. Return only schema-valid JSON. Never copy a known test question. For quantitative topics, prefer deterministic numeric arithmetic; make the answer key exact."},
            {"role": "user", "content": f"Intent: {prompt}\nTopic slug: {topic_slug}\nDifficulty: {difficulty}"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "placement_question",
                "strict": True,
                "schema": _placement_question_output_schema(topic_slug, difficulty),
            },
        },
    }
    request = urllib.request.Request(
        settings.llm_base_url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=settings.llm_timeout_seconds) as response:
        result = json.loads(response.read())
    return json.loads(result["choices"][0]["message"]["content"])


async def generate_question(
    *,
    prompt: str,
    topic_slug: str,
    subtopic: str,
    difficulty: Difficulty,
    company_tags: list[str] | None = None,
) -> GeneratedPlacementQuestion:
    tags = company_tags or []
    numeric = any(token in f"{topic_slug} {subtopic}".casefold() for token in (
        "percent", "profit", "loss", "ratio", "work", "speed", "distance", "interest",
    ))
    if numeric:
        return _build_numeric_question(
            topic_slug=topic_slug,
            subtopic=subtopic,
            difficulty=difficulty,
            prompt=prompt,
            company_tags=tags,
        )
    if get_settings().llm_api_key:
        last_error: Exception | None = None
        for _ in range(get_settings().ai_generation_max_retries):
            try:
                body = await asyncio.to_thread(_llm_generate, prompt, topic_slug, difficulty)
                body["source_type"] = "ai_generated"
                body["topic_slug"] = topic_slug
                body["difficulty"] = difficulty
                return GeneratedPlacementQuestion.model_validate(body)
            except (OSError, KeyError, ValueError, ValidationError) as error:
                last_error = error
                logger.warning("Placement LLM response failed validation; retrying: %s", error)
        raise RuntimeError("The configured question provider did not return valid structured output.") from last_error
    seed = random.SystemRandom().randrange(1, 2**31)
    return _build_llm_or_reasoning_question(topic_slug, subtopic, difficulty, prompt, tags, seed)

