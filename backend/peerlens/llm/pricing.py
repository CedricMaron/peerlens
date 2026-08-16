"""Best-effort pricing for estimated cost.

Prices are USD per 1,000,000 tokens. This table is intentionally incomplete:
if a model is not listed, the estimated cost is ``None`` and the UI shows
"unknown" rather than a fabricated number. Users can override or extend the
table from Settings.
"""

from __future__ import annotations

# (input_per_mtok, output_per_mtok)
PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    # Anthropic
    "claude-opus-4": (15.00, 75.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-3-7-sonnet": (3.00, 15.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


def lookup(model: str, overrides: dict[str, list[float]] | None = None) -> tuple[float, float] | None:
    """Longest-prefix match so that dated model ids resolve to their family."""
    if not model:
        return None
    table: dict[str, tuple[float, float]] = dict(PRICING)
    for key, value in (overrides or {}).items():
        if isinstance(value, (list, tuple)) and len(value) == 2:
            table[key] = (float(value[0]), float(value[1]))

    best: tuple[float, float] | None = None
    best_len = -1
    for prefix, price in table.items():
        if model.startswith(prefix) and len(prefix) > best_len:
            best, best_len = price, len(prefix)
    return best


def estimate_cost(
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    overrides: dict | None = None,
    is_local: bool = False,
) -> float | None:
    """Return an estimated USD cost, or ``None`` when it cannot be known."""
    if is_local or provider == "ollama":
        return 0.0  # locally hosted: no per-token billing
    if input_tokens is None and output_tokens is None:
        return None
    price = lookup(model, overrides)
    if price is None:
        return None
    in_rate, out_rate = price
    return round(
        ((input_tokens or 0) / 1_000_000) * in_rate
        + ((output_tokens or 0) / 1_000_000) * out_rate,
        6,
    )
