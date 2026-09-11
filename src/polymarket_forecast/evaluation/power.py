"""Deterministic block-resampling power and type-I error simulation."""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd


def _sample_mean_vectors(
    event_differences: pd.DataFrame,
    *,
    columns: list[str],
    sample_weeks: int,
    block_length_weeks: int,
    repetitions: int,
    seed: int,
) -> np.ndarray:
    weeks = np.asarray(sorted(event_differences["week"].astype(str).unique()))
    if len(weeks) < 2:
        raise ValueError("Power simulation requires at least two observed weeks")
    centered = event_differences.copy()
    centered[columns] = centered[columns] - centered[columns].mean()
    values_by_week = {
        week: centered.loc[centered["week"].astype(str) == week, columns].to_numpy(dtype=float)
        for week in weeks
    }
    block_length = min(block_length_weeks, len(weeks))
    blocks_needed = math.ceil(sample_weeks / block_length)
    rng = np.random.default_rng(seed)
    draws = np.empty((repetitions, len(columns)), dtype=float)
    for repetition in range(repetitions):
        starts = rng.integers(0, len(weeks), size=blocks_needed)
        sampled_weeks: list[str] = []
        for start in starts:
            sampled_weeks.extend(
                str(weeks[(start + offset) % len(weeks)]) for offset in range(block_length)
            )
        selected = sampled_weeks[:sample_weeks]
        sample = np.concatenate([values_by_week[week] for week in selected])
        draws[repetition] = sample.mean(axis=0)
    return draws


def simulate_power(
    event_differences: pd.DataFrame,
    *,
    repetitions: int,
    block_length_weeks: int,
    alpha: float,
    minimum_practical_effect: float,
    seed: int,
    sample_week_counts: Iterable[int] | None = None,
) -> pd.DataFrame:
    """Estimate conjunctive rejection probability under fixed effect shifts.

    The centered empirical block distribution supplies the null critical
    values. Each scenario adds a known mean effect and applies the same
    intersection-union rule as the confirmatory test.
    """
    required = {"week", "market_improvement", "climatology_improvement"}
    missing = required.difference(event_differences.columns)
    if missing:
        raise ValueError(f"Power input missing columns: {sorted(missing)}")
    observed_weeks = int(event_differences["week"].nunique())
    if sample_week_counts is None:
        sample_week_counts = sorted({30, 52, 78, 104, max(observed_weeks, 2)})
    scenarios = [
        ("global_null", 0.0, 0.0),
        ("boundary_market_null", 0.0, minimum_practical_effect),
        ("boundary_climatology_null", minimum_practical_effect, 0.0),
        ("half_mpe", minimum_practical_effect / 2, minimum_practical_effect / 2),
        ("minimum_practical_effect", minimum_practical_effect, minimum_practical_effect),
        ("double_mpe", 2 * minimum_practical_effect, 2 * minimum_practical_effect),
    ]
    columns = ["market_improvement", "climatology_improvement"]
    rows: list[dict[str, float | int | str | bool]] = []
    for week_count in sample_week_counts:
        if week_count < 2:
            continue
        null_draws = _sample_mean_vectors(
            event_differences,
            columns=columns,
            sample_weeks=int(week_count),
            block_length_weeks=block_length_weeks,
            repetitions=repetitions,
            seed=seed + int(week_count),
        )
        critical = np.quantile(null_draws, 1 - alpha, axis=0)
        for scenario, effect_market, effect_climatology in scenarios:
            shifted = null_draws + np.asarray([effect_market, effect_climatology])
            market_reject = shifted[:, 0] > critical[0]
            climatology_reject = shifted[:, 1] > critical[1]
            rows.append(
                {
                    "scenario": scenario,
                    "sample_weeks": int(week_count),
                    "effect_market": effect_market,
                    "effect_climatology": effect_climatology,
                    "market_rejection_rate": float(market_reject.mean()),
                    "climatology_rejection_rate": float(climatology_reject.mean()),
                    "joint_rejection_rate": float(
                        np.logical_and(market_reject, climatology_reject).mean()
                    ),
                    "extrapolates_observed_weeks": bool(week_count > observed_weeks),
                    "observed_weeks": observed_weeks,
                }
            )
    return pd.DataFrame(rows)


def required_weeks_for_power(
    simulation: pd.DataFrame,
    *,
    target_power: float,
) -> int | None:
    eligible = simulation.loc[
        (simulation["scenario"] == "minimum_practical_effect")
        & (simulation["joint_rejection_rate"] >= target_power)
    ].sort_values("sample_weeks")
    if eligible.empty:
        return None
    return int(eligible.iloc[0]["sample_weeks"])
