"""LLM orchestration: structured calls, JSON repair, and usage accounting.

Every call made through this module is recorded as an ``AIUsageEvent``,
including failures, so the Usage page reflects reality rather than intent.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from ..models import AIUsageEvent
from ..services import settings_service
from . import pricing
from .base import LLMError, LLMProvider, LLMResult, LLMUsage
from .providers import PROVIDERS

logger = logging.getLogger("peerlens.llm")

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def build_provider(db: Session) -> LLMProvider:
    config = settings_service.get_provider_config(db)
    if config is None:
        raise LLMError(
            "No AI provider configured. Open Settings -> AI Provider to connect "
            "OpenAI, Anthropic or a local Ollama model."
        )
    provider_cls = PROVIDERS.get(config.provider)
    if provider_cls is None:
        raise LLMError(f"Unknown AI provider: {config.provider}")
    return provider_cls(config)


def extract_json_object(text: str) -> dict:
    """Pull a JSON object out of a model response, tolerating stray prose."""
    if not text or not text.strip():
        raise ValueError("Empty model response.")
    candidate = text.strip()

    fenced = _FENCE.search(candidate)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = candidate.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in response: {candidate[:200]}")

    # Scan for the matching closing brace, ignoring braces inside strings.
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(candidate)):
        char = candidate[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                blob = candidate[start : index + 1]
                return json.loads(blob)
    raise ValueError("Unterminated JSON object in model response.")


def record_usage(
    db: Session,
    *,
    operation: str,
    provider: str,
    model: str,
    usage: LLMUsage,
    latency_ms: int | None,
    is_local: bool,
    paper_id: int | None = None,
    branch_id: int | None = None,
    success: bool = True,
    error: str | None = None,
) -> AIUsageEvent:
    overrides = settings_service.get_pricing_overrides(db)
    cost = pricing.estimate_cost(
        provider, model, usage.input_tokens, usage.output_tokens, overrides, is_local
    )
    event = AIUsageEvent(
        paper_id=paper_id,
        branch_id=branch_id,
        operation=operation,
        provider=provider,
        model=model,
        is_local=is_local,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cached_tokens=usage.cached_tokens,
        latency_ms=latency_ms,
        estimated_cost=cost,
        success=success,
        error=(error or None),
    )
    db.add(event)
    db.commit()
    return event


async def run_text(
    db: Session,
    *,
    operation: str,
    system: str,
    user: str,
    paper_id: int | None = None,
    branch_id: int | None = None,
    max_tokens: int = 8000,
    temperature: float = 0.2,
) -> LLMResult:
    """Free-text completion (used for manuscript prose)."""
    provider = build_provider(db)
    try:
        result = await provider.complete(
            system=system, user=user, json_mode=False,
            max_tokens=max_tokens, temperature=temperature,
        )
    except Exception as exc:  # noqa: BLE001 - recorded then re-raised
        record_usage(
            db, operation=operation, provider=provider.name, model=provider.model,
            usage=LLMUsage(), latency_ms=None, is_local=provider.is_local,
            paper_id=paper_id, branch_id=branch_id, success=False, error=str(exc)[:1000],
        )
        raise
    record_usage(
        db, operation=operation, provider=result.provider, model=result.model,
        usage=result.usage, latency_ms=result.latency_ms, is_local=result.is_local,
        paper_id=paper_id, branch_id=branch_id,
    )
    return result


async def run_structured(
    db: Session,
    *,
    operation: str,
    system: str,
    user: str,
    schema: type[T],
    paper_id: int | None = None,
    branch_id: int | None = None,
    max_tokens: int = 8000,
    temperature: float = 0.2,
) -> tuple[T, LLMResult]:
    """Completion validated against a Pydantic schema, with one repair attempt."""
    provider = build_provider(db)
    schema_text = json.dumps(schema.model_json_schema(), indent=2)
    system_with_schema = (
        f"{system}\n\n"
        "## Required output format\n"
        "Return a single JSON object conforming to this JSON Schema:\n"
        f"```json\n{schema_text}\n```\n"
        "Use only the fields defined by the schema. Leave arrays empty rather than "
        "inventing content to fill them."
    )

    attempts: list[str] = []
    last_error = ""
    current_user = user

    for attempt in range(2):
        try:
            result = await provider.complete(
                system=system_with_schema, user=current_user, json_mode=True,
                max_tokens=max_tokens, temperature=temperature,
            )
        except Exception as exc:  # noqa: BLE001 - recorded then re-raised
            record_usage(
                db, operation=operation, provider=provider.name, model=provider.model,
                usage=LLMUsage(), latency_ms=None, is_local=provider.is_local,
                paper_id=paper_id, branch_id=branch_id, success=False, error=str(exc)[:1000],
            )
            raise

        record_usage(
            db, operation=operation, provider=result.provider, model=result.model,
            usage=result.usage, latency_ms=result.latency_ms, is_local=result.is_local,
            paper_id=paper_id, branch_id=branch_id,
        )

        try:
            payload = extract_json_object(result.text)
            return schema.model_validate(payload), result
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            last_error = str(exc)[:1500]
            attempts.append(result.text[:2000])
            logger.warning(
                "Structured output validation failed for %s (attempt %s): %s",
                operation, attempt + 1, last_error,
            )
            current_user = (
                f"{user}\n\n---\n"
                "Your previous response could not be parsed against the required "
                f"schema.\n\nError:\n{last_error}\n\n"
                "Return corrected JSON only. Do not include any text outside the "
                "JSON object."
            )

    raise LLMError(
        f"The model did not return valid structured output for '{operation}' after "
        f"two attempts. Last error: {last_error}"
    )
