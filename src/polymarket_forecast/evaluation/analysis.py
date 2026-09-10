"""Assemble confirmatory and preregistered robustness analyses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.evaluation.bootstrap import (
    SuperiorityResult,
    block_length_robustness,
    paired_superiority_test,
)
from polymarket_forecast.evaluation.metrics import (
    event_weighted_score,
    reliability_table,
    summarize_probabilistic_forecast,
)


@dataclass(frozen=True)
class EvaluationBundle:
    primary_test: SuperiorityResult
    system_metrics: pd.DataFrame
    reliability: pd.DataFrame
    block_robustness: pd.DataFrame
    slice_metrics: pd.DataFrame
    sensitivity: pd.DataFrame


SYSTEM_COLUMNS = {
    "model": "model_probability",
    "market": "market_probability",
    "calibrated_market": "calibrated_market_probability",
    "global_climatology": "global_climatology_probability",
    "category_climatology": "category_climatology_probability",
}


def _system_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for system, column in SYSTEM_COLUMNS.items():
        summary = summarize_probabilistic_forecast(
            predictions["label"],
            predictions[column],
        )
        rows.append(
            {
                "system": system,
                "event_weighted_brier": event_weighted_score(predictions, column),
                "event_weighted_log_loss": event_weighted_score(
                    predictions,
                    column,
                    score="log",
                ),
                **{
                    key: value
                    for key, value in summary.items()
                    if key not in {"calibration", "brier_decomposition"}
                },
                "calibration_intercept": summary["calibration"]["intercept"],
                "calibration_slope": summary["calibration"]["slope"],
                "calibration_converged": summary["calibration"]["converged"],
                "brier_reliability": summary["brier_decomposition"]["reliability"],
                "brier_resolution": summary["brier_decomposition"]["resolution"],
                "brier_uncertainty": summary["brier_decomposition"]["uncertainty"],
            }
        )
    return pd.DataFrame(rows).sort_values("event_weighted_brier")


def _reliability(predictions: pd.DataFrame) -> pd.DataFrame:
    tables: list[pd.DataFrame] = []
    for system, column in SYSTEM_COLUMNS.items():
        table = reliability_table(predictions["label"], predictions[column])
        table.insert(0, "system", system)
        tables.append(table)
    return pd.concat(tables, ignore_index=True)


def _slice_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for category, group in predictions.groupby("category"):
        if group["event_group_id"].nunique() < 3:
            continue
        rows.append(
            {
                "slice": f"category:{category}",
                "contracts": int(len(group)),
                "event_groups": int(group["event_group_id"].nunique()),
                "model_brier": event_weighted_score(group, "model_probability"),
                "market_brier": event_weighted_score(group, "market_probability"),
                "climatology_brier": event_weighted_score(
                    group,
                    "category_climatology_probability",
                ),
            }
        )
    for label_source, group in predictions.groupby("label_source"):
        rows.append(
            {
                "slice": f"label_source:{label_source}",
                "contracts": int(len(group)),
                "event_groups": int(group["event_group_id"].nunique()),
                "model_brier": event_weighted_score(group, "model_probability"),
                "market_brier": event_weighted_score(group, "market_probability"),
                "climatology_brier": event_weighted_score(
                    group,
                    "category_climatology_probability",
                ),
            }
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        result["model_minus_market_brier"] = result["model_brier"] - result["market_brier"]
    return result


def _contract_weighted_sensitivity(predictions: pd.DataFrame) -> dict[str, Any]:
    y = predictions["label"].to_numpy(dtype=float)
    model_loss = (predictions["model_probability"].to_numpy(dtype=float) - y) ** 2
    market_loss = (predictions["market_probability"].to_numpy(dtype=float) - y) ** 2
    climate_loss = (predictions["category_climatology_probability"].to_numpy(dtype=float) - y) ** 2
    return {
        "analysis": "contract_weighted",
        "contracts": int(len(predictions)),
        "event_groups": int(predictions["event_group_id"].nunique()),
        "market_improvement": float(np.mean(market_loss - model_loss)),
        "climatology_improvement": float(np.mean(climate_loss - model_loss)),
    }


def _testable_sensitivity(
    name: str,
    frame: pd.DataFrame,
    config: ProjectConfig,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "analysis": name,
        "contracts": int(len(frame)),
        "event_groups": int(frame["event_group_id"].nunique()),
        "effective_weeks": int(
            pd.to_datetime(frame["forecast_cutoff"], utc=True)
            .dt.tz_localize(None)
            .dt.to_period("W-SUN")
            .nunique()
        ),
    }
    if base["event_groups"] < 4 or base["effective_weeks"] < 2:
        return {**base, "status": "insufficient_data"}
    test = paired_superiority_test(
        frame,
        repetitions=config.inference.bootstrap_repetitions,
        block_length_weeks=config.inference.block_length_weeks,
        seed=config.model.random_seed,
        alpha=config.inference.alpha,
        minimum_practical_effect=config.inference.minimum_practical_effect,
    )
    return {
        **base,
        "status": "ok",
        "market_improvement": test.market.mean_brier_improvement,
        "market_p_value": test.market.p_value_one_sided,
        "climatology_improvement": test.climatology.mean_brier_improvement,
        "climatology_p_value": test.climatology.p_value_one_sided,
        "global_p_value": test.global_intersection_union_p,
        "superior_to_both": test.superior_to_both,
    }


def evaluate_predictions(
    predictions: pd.DataFrame,
    config: ProjectConfig,
) -> EvaluationBundle:
    """Evaluate one locked model on one untouched horizon cohort."""
    primary = paired_superiority_test(
        predictions,
        repetitions=config.inference.bootstrap_repetitions,
        block_length_weeks=config.inference.block_length_weeks,
        seed=config.model.random_seed,
        alpha=config.inference.alpha,
        minimum_practical_effect=config.inference.minimum_practical_effect,
    )
    blocks = block_length_robustness(
        predictions,
        block_lengths=config.inference.robustness_block_lengths_weeks,
        repetitions=config.inference.bootstrap_repetitions,
        seed=config.model.random_seed,
        alpha=config.inference.alpha,
        minimum_practical_effect=config.inference.minimum_practical_effect,
    )
    largest_event = (
        predictions.groupby("event_group_id").size().sort_values(ascending=False).index[0]
    )
    sensitivity_rows = [
        _contract_weighted_sensitivity(predictions),
        _testable_sensitivity(
            "clob_winner_labels_only",
            predictions.loc[predictions["label_source"] == "clob_winner_crosschecked_gamma"],
            config,
        ),
        _testable_sensitivity(
            "exclude_neg_risk",
            predictions.loc[~predictions["neg_risk"].astype(bool)],
            config,
        ),
        _testable_sensitivity(
            "remove_largest_event",
            predictions.loc[predictions["event_group_id"] != largest_event],
            config,
        ),
    ]
    return EvaluationBundle(
        primary_test=primary,
        system_metrics=_system_metrics(predictions),
        reliability=_reliability(predictions),
        block_robustness=blocks,
        slice_metrics=_slice_metrics(predictions),
        sensitivity=pd.DataFrame(sensitivity_rows),
    )
