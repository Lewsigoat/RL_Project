from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pandas as pd

from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.data.historical import build_historical_v1_cohort
from polymarket_forecast.data.storage import ResearchStorage


def test_historical_fills_build_a_past_only_cohort(
    small_config: ProjectConfig,
) -> None:
    config = replace(
        small_config,
        historical=replace(
            small_config.historical,
            enabled=True,
            revision="fixture-revision",
        ),
    )
    storage = ResearchStorage(config.paths.data_uri)
    root = storage.local_path("raw/polymarket_v1/fixture-revision/daily_aligned")
    root.mkdir(parents=True)
    event_time = datetime(2025, 6, 30, 12, tzinfo=UTC)
    rows = []
    for horizon in config.study.horizons_days:
        cutoff = event_time - timedelta(days=horizon)
        for hours_before, probability in [(120, 0.4), (24, 0.45), (1, 0.55)]:
            rows.append(
                {
                    "condition_id": "condition-1",
                    "market_slug": "will-example-event-happen",
                    "category_refined": "Politics",
                    "category": "Politics",
                    "winning_outcome_label": "Yes",
                    "resolution_status": "resolved",
                    "opens_at": event_time - timedelta(days=120),
                    "close_at": event_time,
                    "resolved_at": event_time + timedelta(hours=2),
                    "block_timestamp": int((cutoff - timedelta(hours=hours_before)).timestamp()),
                    "p_event": probability,
                }
            )
    pd.DataFrame(rows).to_parquet(root / "2025_06_01.parquet", index=False)

    cohort = build_historical_v1_cohort(
        config,
        storage,
        run_id="historical-fixture",
    )

    assert set(cohort["horizon_days"]) == {1, 7, 30}
    assert (cohort["price_timestamp"] <= cohort["forecast_cutoff"]).all()
    assert (cohort["price_age_hours"] == 1).all()
    assert set(cohort["label_source"]) == {"polymarket_v1_chain_aligned"}
