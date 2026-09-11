from __future__ import annotations

import numpy as np

from polymarket_forecast.cohort import build_cohort
from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.models import (
    develop_models,
    fit_ablation_predictions,
    train_locked_system,
)
from polymarket_forecast.splits import make_walk_forward_splits
from tests.factories import synthetic_source_frames


def test_candidate_development_locking_and_ablations(
    small_config: ProjectConfig,
) -> None:
    markets, prices = synthetic_source_frames(event_count=60, contracts_per_event=2)
    cohort = build_cohort(markets, prices, small_config).cohort
    primary = (
        cohort.loc[cohort["horizon_days"] == 7]
        .sort_values(["forecast_cutoff", "event_group_id", "market_id"])
        .reset_index(drop=True)
    )
    splits = make_walk_forward_splits(primary, small_config)

    development = develop_models(primary, splits, small_config)
    locked = train_locked_system(primary, splits, development, small_config)
    holdout = primary.iloc[splits.holdout_indices]
    predictions = locked.predict(holdout)
    ablations = fit_ablation_predictions(
        primary.iloc[splits.final_train_indices],
        holdout,
        small_config,
        selected_name=development.selected_name,
        ensemble_weights=development.ensemble_weights,
    )

    assert not development.scoreboard.empty
    assert development.selected_name in set(development.scoreboard["candidate"])
    assert len(predictions) == len(holdout)
    assert set(predictions.columns) == {
        "model_probability",
        "market_probability",
        "calibrated_market_probability",
        "global_climatology_probability",
        "category_climatology_probability",
    }
    assert np.isfinite(predictions.to_numpy()).all()
    assert ((predictions > 0) & (predictions < 1)).all().all()
    assert set(ablations) == {
        "market_only",
        "full_model",
        "without_text",
        "without_trajectory",
        "without_category",
        "without_time",
    }
