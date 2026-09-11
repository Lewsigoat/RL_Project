"""Canonical records used by the data and modeling pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MarketRecord:
    """A normalized binary market with a verified outcome label."""

    market_id: str
    event_id: str
    condition_id: str
    question_id: str
    slug: str
    question: str
    description: str
    category: str
    yes_token_id: str
    no_token_id: str
    created_at: datetime
    event_time: datetime
    end_date: datetime
    closed_time: datetime
    source_updated_at: datetime | None
    label: int
    label_source: str
    neg_risk: bool
    final_volume: float | None
    final_liquidity: float | None
    raw_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PricePoint:
    """A sampled YES-token probability from the CLOB history endpoint."""

    market_id: str
    token_id: str
    timestamp: datetime
    price: float
    source: str = "clob_prices_history"

    def __post_init__(self) -> None:
        if not 0 <= self.price <= 1:
            raise ValueError(f"Price is outside [0, 1]: {self.price}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Exclusion:
    market_id: str
    reason: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ProvenanceRecord:
    """Immutable evidence for one source request or generated table."""

    artifact: str
    source_url: str
    retrieved_at: datetime
    sha256: str
    byte_count: int
    parameters_json: str
    status_code: int
    schema_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
