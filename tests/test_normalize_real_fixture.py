from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from polymarket_forecast.cohort import build_cohort
from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.data.normalize import normalize_market, normalize_price_history


def _fixture() -> dict[str, Any]:
    path = Path("tests/fixtures/real_market_snapshot.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_real_public_snapshot_normalizes_and_crosschecks_winner(
    small_config: ProjectConfig,
) -> None:
    payload = _fixture()
    market, exclusion = normalize_market(
        payload["gamma_market"],
        payload["clob_market"],
    )

    assert exclusion is None
    assert market is not None
    assert market.market_id == "2507607"
    assert market.label == 0
    assert market.label_source == "clob_winner_crosschecked_gamma"
    assert market.category == "iran"

    points, point_exclusions = normalize_price_history(
        market.market_id,
        market.yes_token_id,
        payload["price_history"],
    )
    assert not point_exclusions
    assert len(points) == 16

    result = build_cohort(
        markets=_frame([market.to_dict()]),
        price_points=_frame([point.to_dict() for point in points]),
        config=small_config,
    )
    assert set(result.cohort["horizon_days"]) == {1, 7}
    assert (result.cohort["price_timestamp"] <= result.cohort["forecast_cutoff"]).all()
    assert "no_price_before_forecast_cutoff" in set(result.exclusions["reason"])


def test_conflicting_winner_is_excluded() -> None:
    payload = _fixture()
    conflicting = dict(payload["clob_market"])
    conflicting["tokens"] = [
        {**conflicting["tokens"][0], "winner": True},
        {**conflicting["tokens"][1], "winner": False},
    ]

    market, exclusion = normalize_market(payload["gamma_market"], conflicting)

    assert market is None
    assert exclusion is not None
    assert "conflicts" in exclusion.detail


def _frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows)
