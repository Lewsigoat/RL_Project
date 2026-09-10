from __future__ import annotations

import pandas as pd
import pytest

from polymarket_forecast.cohort import audit_cohort, build_cohort
from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.splits import make_walk_forward_splits
from tests.factories import synthetic_source_frames


def test_cohort_uses_only_fresh_past_prices(small_config: ProjectConfig) -> None:
    markets, prices = synthetic_source_frames(event_count=12, contracts_per_event=2)

    result = build_cohort(markets, prices, small_config)

    assert len(result.cohort) == 12 * 2 * 3
    assert result.exclusions.empty
    assert (result.cohort["price_timestamp"] <= result.cohort["forecast_cutoff"]).all()
    assert (result.cohort["forecast_cutoff"] < result.cohort["closed_time"]).all()
    assert not {"final_volume", "final_liquidity"}.intersection(result.cohort.columns)


def test_cohort_audit_rejects_future_price(small_config: ProjectConfig) -> None:
    markets, prices = synthetic_source_frames(event_count=4)
    cohort = build_cohort(markets, prices, small_config).cohort
    cohort.loc[0, "price_timestamp"] = cohort.loc[0, "forecast_cutoff"] + pd.Timedelta(minutes=1)

    with pytest.raises(AssertionError, match="after the forecast cutoff"):
        audit_cohort(cohort, small_config)


def test_walk_forward_split_keeps_events_isolated_and_labels_past(
    small_config: ProjectConfig,
) -> None:
    markets, prices = synthetic_source_frames(event_count=60, contracts_per_event=2)
    cohort = build_cohort(markets, prices, small_config).cohort
    primary = (
        cohort.loc[cohort["horizon_days"] == 7]
        .sort_values(["forecast_cutoff", "event_group_id", "market_id"])
        .reset_index(drop=True)
    )

    plan = make_walk_forward_splits(primary, small_config)

    assert len(plan.folds) == small_config.study.development_folds
    holdout_groups = set(primary.iloc[plan.holdout_indices]["event_group_id"])
    train_groups = set(primary.iloc[plan.final_train_indices]["event_group_id"])
    assert holdout_groups.isdisjoint(train_groups)
    for fold in plan.folds:
        train = primary.iloc[fold.train_indices]
        validation = primary.iloc[fold.validation_indices]
        assert set(train["event_group_id"]).isdisjoint(validation["event_group_id"])
        assert train["closed_time"].max() < validation["forecast_cutoff"].min() - pd.Timedelta(
            days=small_config.study.embargo_days
        )
