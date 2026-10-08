"""List prices per million tokens (USD), for cost estimates in logs and the interface.

Prices change: these were read from OpenAI's model pages on 2026-10-08. A model that is not
listed gets no estimate rather than a wrong one.
"""

from __future__ import annotations

TOKENS_PER_PRICE_UNIT = 1_000_000
PRICES_PER_MILLION: dict[str, tuple[float, float]] = {
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-4.1-mini": (0.40, 1.60),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Cost of one call; dated model names (``gpt-5.4-mini-2026-03-17``) use their family."""
    family = next(
        (
            name
            for name in sorted(PRICES_PER_MILLION, key=len, reverse=True)
            if model.startswith(name)
        ),
        None,
    )
    if family is None:
        return None
    input_price, output_price = PRICES_PER_MILLION[family]
    return (input_tokens * input_price + output_tokens * output_price) / TOKENS_PER_PRICE_UNIT
