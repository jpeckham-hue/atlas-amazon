"""Model pricing used for *estimated* semantic cost.

The defaults are Anthropic first-party API list prices, as published in the
Claude API reference cached on 2026-09-25 (USD per million tokens). Prices
change: pass your own `PricingTable` to override, and treat every cost
figure as an estimate. A model missing from the table has unknown cost, and
a configured cost limit then refuses to call it (fail safe).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

PRICING_AS_OF = "2026-09-25"
# The API may report a dated snapshot ID (for example "claude-haiku-4-5-20251001")
# for a request made with the alias; both have the same price.
_SNAPSHOT_SUFFIX = re.compile(r"-\d{8}$")


@dataclass(frozen=True, slots=True)
class ModelPrice:
    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float = 0.0
    cache_write_per_mtok: float = 0.0  # 5-minute cache writes

    def cost(
        self, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0
    ) -> float:
        return (
            input_tokens * self.input_per_mtok
            + output_tokens * self.output_per_mtok
            + cache_read * self.cache_read_per_mtok
            + cache_write * self.cache_write_per_mtok
        ) / 1_000_000


DEFAULT_PRICES: Mapping[str, ModelPrice] = MappingProxyType(
    {
        "claude-opus-5-5": ModelPrice(4.00, 20.00, 0.20, 5.00),
        "claude-sonnet-5-5": ModelPrice(2.00, 10.00, 0.20, 2.50),
        "claude-haiku-4-5": ModelPrice(1.00, 5.00, 0.10, 1.25),
    }
)


@dataclass(frozen=True, slots=True)
class PricingTable:
    prices: Mapping[str, ModelPrice] = field(default_factory=lambda: DEFAULT_PRICES)
    as_of: str = PRICING_AS_OF

    def get(self, model: str) -> ModelPrice | None:
        price = self.prices.get(model)
        if price is None:
            price = self.prices.get(_SNAPSHOT_SUFFIX.sub("", model))
        return price
