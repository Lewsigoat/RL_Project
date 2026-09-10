"""Event- and calendar-block-aware paired forecast comparisons."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BaselineTest:
    baseline: str
    mean_brier_improvement: float
    brier_skill_score: float
    p_value_one_sided: float
    lower_bound_one_sided_95: float
    confidence_interval_two_sided_95: tuple[float, float]
    superior_at_alpha: bool
    practically_relevant: bool


@dataclass(frozen=True)
class SuperiorityResult:
    alpha: float
    minimum_practical_effect: float
    repetitions: int
    block_length_weeks: int
    event_groups: int
    effective_weeks: int
    market: BaselineTest
    climatology: BaselineTest
    global_intersection_union_p: float
    superior_to_both: bool
    practically_superior_to_both: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def event_score_differences(
    predictions: pd.DataFrame,
    *,
    climatology_column: str = "category_climatology_probability",
) -> pd.DataFrame:
    """Collapse paired contract losses to one row per underlying event."""
    required = {
        "event_group_id",
        "forecast_cutoff",
        "label",
        "model_probability",
        "market_probability",
        climatology_column,
    }
    missing = required.difference(predictions.columns)
    if missing:
        raise ValueError(f"Predictions missing columns: {sorted(missing)}")
    working = predictions.copy()
    working["forecast_cutoff"] = pd.to_datetime(working["forecast_cutoff"], utc=True)
    y = working["label"].to_numpy(dtype=float)
    working["model_loss"] = (working["model_probability"].to_numpy(dtype=float) - y) ** 2
    working["market_loss"] = (working["market_probability"].to_numpy(dtype=float) - y) ** 2
    working["climatology_loss"] = (working[climatology_column].to_numpy(dtype=float) - y) ** 2
    working["market_improvement"] = working["market_loss"] - working["model_loss"]
    working["climatology_improvement"] = working["climatology_loss"] - working["model_loss"]
    event = (
        working.groupby("event_group_id", as_index=False)
        .agg(
            forecast_cutoff=("forecast_cutoff", "min"),
            model_loss=("model_loss", "mean"),
            market_loss=("market_loss", "mean"),
            climatology_loss=("climatology_loss", "mean"),
            market_improvement=("market_improvement", "mean"),
            climatology_improvement=("climatology_improvement", "mean"),
            contracts=("label", "size"),
        )
        .sort_values(["forecast_cutoff", "event_group_id"])
        .reset_index(drop=True)
    )
    event["week"] = event["forecast_cutoff"].dt.tz_localize(None).dt.to_period("W-SUN").astype(str)
    return event


def _draw_week_blocks(
    weeks: np.ndarray,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    count = len(weeks)
    length = min(block_length, count)
    blocks_needed = math.ceil(count / length)
    maximum_start = count - length
    starts = rng.integers(0, maximum_start + 1, size=blocks_needed)
    sampled = np.concatenate([weeks[start : start + length] for start in starts])
    return sampled[:count]


def block_bootstrap_means(
    event_differences: pd.DataFrame,
    columns: list[str],
    *,
    repetitions: int,
    block_length_weeks: int,
    seed: int,
    center: bool,
) -> np.ndarray:
    """Resample consecutive week blocks and retain all events in each week."""
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    missing = {"week", *columns}.difference(event_differences.columns)
    if missing:
        raise ValueError(f"Event differences missing columns: {sorted(missing)}")
    unique_weeks = np.asarray(sorted(event_differences["week"].astype(str).unique()))
    if len(unique_weeks) < 2:
        raise ValueError("At least two forecast weeks are required for block inference")
    values = event_differences[columns].to_numpy(dtype=float)
    if center:
        values = values - values.mean(axis=0, keepdims=True)
    week_values = {
        week: values[event_differences["week"].astype(str).to_numpy() == week]
        for week in unique_weeks
    }
    rng = np.random.default_rng(seed)
    means = np.empty((repetitions, len(columns)), dtype=float)
    for repetition in range(repetitions):
        sampled_weeks = _draw_week_blocks(unique_weeks, block_length_weeks, rng)
        sample = np.concatenate([week_values[str(week)] for week in sampled_weeks])
        means[repetition] = sample.mean(axis=0)
    return means


def _test_one_baseline(
    *,
    baseline: str,
    column_index: int,
    event: pd.DataFrame,
    observed: np.ndarray,
    centered_draws: np.ndarray,
    uncentered_draws: np.ndarray,
    repetitions: int,
    alpha: float,
    minimum_practical_effect: float,
) -> BaselineTest:
    p_value = float(
        (1 + np.count_nonzero(centered_draws[:, column_index] >= observed[column_index]))
        / (repetitions + 1)
    )
    lower = float(np.quantile(uncentered_draws[:, column_index], alpha))
    two_sided = (
        float(np.quantile(uncentered_draws[:, column_index], alpha / 2)),
        float(np.quantile(uncentered_draws[:, column_index], 1 - alpha / 2)),
    )
    baseline_loss_column = "market_loss" if baseline == "market" else "climatology_loss"
    baseline_loss = float(event[baseline_loss_column].mean())
    model_loss = float(event["model_loss"].mean())
    skill = 1 - model_loss / baseline_loss if baseline_loss > 0 else float("nan")
    return BaselineTest(
        baseline=baseline,
        mean_brier_improvement=float(observed[column_index]),
        brier_skill_score=float(skill),
        p_value_one_sided=p_value,
        lower_bound_one_sided_95=lower,
        confidence_interval_two_sided_95=two_sided,
        superior_at_alpha=bool(p_value < alpha and lower > 0),
        practically_relevant=bool(lower > minimum_practical_effect),
    )


def paired_superiority_test(
    predictions: pd.DataFrame,
    *,
    repetitions: int,
    block_length_weeks: int,
    seed: int,
    alpha: float = 0.05,
    minimum_practical_effect: float = 0.005,
    climatology_column: str = "category_climatology_probability",
) -> SuperiorityResult:
    """Run the preregistered intersection-union superiority test."""
    event = event_score_differences(
        predictions,
        climatology_column=climatology_column,
    )
    columns = ["market_improvement", "climatology_improvement"]
    observed = event[columns].mean().to_numpy(dtype=float)
    centered = block_bootstrap_means(
        event,
        columns,
        repetitions=repetitions,
        block_length_weeks=block_length_weeks,
        seed=seed,
        center=True,
    )
    uncentered = block_bootstrap_means(
        event,
        columns,
        repetitions=repetitions,
        block_length_weeks=block_length_weeks,
        seed=seed,
        center=False,
    )
    market = _test_one_baseline(
        baseline="market",
        column_index=0,
        event=event,
        observed=observed,
        centered_draws=centered,
        uncentered_draws=uncentered,
        repetitions=repetitions,
        alpha=alpha,
        minimum_practical_effect=minimum_practical_effect,
    )
    climatology = _test_one_baseline(
        baseline="climatology",
        column_index=1,
        event=event,
        observed=observed,
        centered_draws=centered,
        uncentered_draws=uncentered,
        repetitions=repetitions,
        alpha=alpha,
        minimum_practical_effect=minimum_practical_effect,
    )
    global_p = max(market.p_value_one_sided, climatology.p_value_one_sided)
    return SuperiorityResult(
        alpha=alpha,
        minimum_practical_effect=minimum_practical_effect,
        repetitions=repetitions,
        block_length_weeks=block_length_weeks,
        event_groups=int(event["event_group_id"].nunique()),
        effective_weeks=int(event["week"].nunique()),
        market=market,
        climatology=climatology,
        global_intersection_union_p=global_p,
        superior_to_both=bool(market.superior_at_alpha and climatology.superior_at_alpha),
        practically_superior_to_both=bool(
            market.practically_relevant and climatology.practically_relevant
        ),
    )


def block_length_robustness(
    predictions: pd.DataFrame,
    *,
    block_lengths: tuple[int, ...],
    repetitions: int,
    seed: int,
    alpha: float,
    minimum_practical_effect: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for block_length in block_lengths:
        result = paired_superiority_test(
            predictions,
            repetitions=repetitions,
            block_length_weeks=block_length,
            seed=seed,
            alpha=alpha,
            minimum_practical_effect=minimum_practical_effect,
        )
        rows.append(
            {
                "block_length_weeks": block_length,
                "market_improvement": result.market.mean_brier_improvement,
                "market_p_value": result.market.p_value_one_sided,
                "climatology_improvement": result.climatology.mean_brier_improvement,
                "climatology_p_value": result.climatology.p_value_one_sided,
                "global_p_value": result.global_intersection_union_p,
                "superior_to_both": result.superior_to_both,
            }
        )
    return pd.DataFrame(rows)
