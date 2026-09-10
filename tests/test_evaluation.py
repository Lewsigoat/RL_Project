from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from polymarket_forecast.evaluation.bootstrap import (
    event_score_differences,
    paired_superiority_test,
)
from polymarket_forecast.evaluation.metrics import (
    brier_decomposition,
    brier_score,
    calibration_fit,
    holm_adjust,
    logarithmic_score,
)
from polymarket_forecast.evaluation.power import required_weeks_for_power, simulate_power


def _prediction_frame(events: int = 80) -> pd.DataFrame:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(events):
        label = index % 2
        market = 0.65 if label else 0.35
        model = 0.8 if label else 0.2
        rows.append(
            {
                "event_group_id": f"event-{index}",
                "forecast_cutoff": start + timedelta(days=7 * index),
                "label": label,
                "model_probability": model,
                "market_probability": market,
                "category_climatology_probability": 0.5,
            }
        )
    return pd.DataFrame(rows)


def test_proper_scores_and_calibration() -> None:
    y = np.asarray([0, 0, 1, 1])
    strong = np.asarray([0.1, 0.2, 0.8, 0.9])
    weak = np.asarray([0.4, 0.4, 0.6, 0.6])

    assert brier_score(y, strong) < brier_score(y, weak)
    assert logarithmic_score(y, strong) < logarithmic_score(y, weak)
    decomposition = brier_decomposition(y, strong, bins=5)
    assert decomposition.uncertainty == 0.25
    calibration = calibration_fit(y, strong)
    assert np.isfinite(calibration.intercept)
    assert np.isfinite(calibration.slope)


def test_holm_adjustment_is_monotone() -> None:
    adjusted = holm_adjust({"a": 0.01, "b": 0.03, "c": 0.5})

    assert adjusted["a"] == 0.03
    assert adjusted["b"] >= adjusted["a"]
    assert adjusted["c"] == 0.5


def test_block_bootstrap_detects_large_paired_advantage() -> None:
    predictions = _prediction_frame()

    first = paired_superiority_test(
        predictions,
        repetitions=999,
        block_length_weeks=4,
        seed=42,
    )
    second = paired_superiority_test(
        predictions,
        repetitions=999,
        block_length_weeks=4,
        seed=42,
    )

    assert first == second
    assert first.superior_to_both
    assert first.market.mean_brier_improvement > 0
    assert first.global_intersection_union_p < 0.05


def test_power_simulation_checks_global_and_boundary_nulls() -> None:
    differences = event_score_differences(_prediction_frame())
    simulation = simulate_power(
        differences,
        repetitions=1000,
        block_length_weeks=4,
        alpha=0.05,
        minimum_practical_effect=0.05,
        seed=7,
        sample_week_counts=[30, 80],
    )

    null = simulation.loc[
        (simulation["scenario"] == "global_null") & (simulation["sample_weeks"] == 80)
    ].iloc[0]
    effect = simulation.loc[
        (simulation["scenario"] == "minimum_practical_effect") & (simulation["sample_weeks"] == 80)
    ].iloc[0]
    assert null["joint_rejection_rate"] <= 0.06
    assert effect["joint_rejection_rate"] > null["joint_rejection_rate"]
    assert required_weeks_for_power(simulation, target_power=0.5) in {30, 80, None}
