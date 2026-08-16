"""Provider plumbing: JSON extraction, reasoning stripping, pricing honesty."""

from __future__ import annotations

import pytest

from peerlens.llm import pricing
from peerlens.llm.base import strip_reasoning
from peerlens.llm.client import extract_json_object


def test_plain_json():
    assert extract_json_object('{"status": "ready"}') == {"status": "ready"}


def test_fenced_json():
    text = 'Here you go:\n```json\n{"status": "ready"}\n```\nHope that helps.'
    assert extract_json_object(text) == {"status": "ready"}


def test_json_with_surrounding_prose():
    text = 'Sure.\n{"a": 1, "b": {"c": 2}}\nLet me know if you need more.'
    assert extract_json_object(text) == {"a": 1, "b": {"c": 2}}


def test_braces_inside_strings_do_not_confuse_the_scanner():
    text = '{"issue": "the set {a, b} was unbalanced", "n": 2}'
    assert extract_json_object(text)["n"] == 2


def test_escaped_quotes_are_handled():
    text = r'{"issue": "he said \"significant\" without a test"}'
    assert "significant" in extract_json_object(text)["issue"]


def test_empty_response_is_rejected():
    with pytest.raises(ValueError):
        extract_json_object("   ")


def test_non_json_is_rejected():
    with pytest.raises(ValueError):
        extract_json_object("I cannot answer that.")


def test_reasoning_blocks_are_stripped():
    """Internal monologue from local reasoning models must never reach the UI."""
    text = "<think>Let me consider the options...</think>\nThe answer is 4."
    assert strip_reasoning(text) == "The answer is 4."


def test_unterminated_reasoning_block_is_truncated():
    assert strip_reasoning("Answer first.<think>then rambling") == "Answer first."


def test_text_without_reasoning_is_untouched():
    assert strip_reasoning("A plain answer.") == "A plain answer."


def test_pricing_uses_longest_prefix_match():
    assert pricing.lookup("gpt-4o-mini-2024-07-18") == (0.15, 0.60)
    assert pricing.lookup("gpt-4o-2024-11-20") == (2.50, 10.00)


def test_unknown_model_has_unknown_cost():
    """Never fabricate pricing for a model we do not have a rate for."""
    assert pricing.lookup("some-new-model-v9") is None
    assert pricing.estimate_cost("openai", "some-new-model-v9", 1000, 500) is None


def test_local_models_cost_nothing():
    assert pricing.estimate_cost("ollama", "llama3.1:8b", 5000, 2000, is_local=True) == 0.0


def test_missing_token_counts_give_unknown_cost():
    assert pricing.estimate_cost("openai", "gpt-4o", None, None) is None


def test_cost_is_computed_from_reported_tokens():
    cost = pricing.estimate_cost("openai", "gpt-4o", 1_000_000, 1_000_000)
    assert cost == pytest.approx(12.50)


def test_pricing_overrides_are_respected():
    cost = pricing.estimate_cost(
        "openai", "custom-model", 1_000_000, 0, overrides={"custom-model": [1.0, 2.0]}
    )
    assert cost == pytest.approx(1.0)
