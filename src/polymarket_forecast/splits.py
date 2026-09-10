"""Purged grouped walk-forward splits with label-availability checks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from polymarket_forecast.config import ProjectConfig


@dataclass(frozen=True)
class WalkForwardFold:
    fold: int
    train_indices: np.ndarray
    validation_indices: np.ndarray
    validation_start: pd.Timestamp
    label_available_before: pd.Timestamp


@dataclass(frozen=True)
class SplitPlan:
    folds: tuple[WalkForwardFold, ...]
    development_indices: np.ndarray
    final_train_indices: np.ndarray
    holdout_indices: np.ndarray
    holdout_start: pd.Timestamp
    assignments: pd.DataFrame


def make_walk_forward_splits(
    cohort: pd.DataFrame,
    config: ProjectConfig,
) -> SplitPlan:
    """Create event-grouped temporal development folds and a final holdout."""
    required = {"event_group_id", "forecast_cutoff", "closed_time"}
    missing = required.difference(cohort.columns)
    if missing:
        raise ValueError(f"Cohort is missing split columns: {sorted(missing)}")
    if cohort.empty:
        raise ValueError("Cannot split an empty cohort")

    working = cohort.reset_index(drop=True).copy()
    working["forecast_cutoff"] = pd.to_datetime(working["forecast_cutoff"], utc=True)
    working["closed_time"] = pd.to_datetime(working["closed_time"], utc=True)
    group_timing = (
        working.groupby("event_group_id", as_index=False)
        .agg(
            first_forecast_cutoff=("forecast_cutoff", "min"),
            final_resolution=("closed_time", "max"),
        )
        .sort_values(["first_forecast_cutoff", "event_group_id"])
        .reset_index(drop=True)
    )
    group_count = len(group_timing)
    minimum_groups = config.study.development_folds + 2
    if group_count < minimum_groups:
        raise ValueError(f"Need at least {minimum_groups} event groups, found {group_count}")

    holdout_count = max(1, math.ceil(group_count * config.study.holdout_fraction))
    fractional_start = pd.Timestamp(group_timing.iloc[-holdout_count]["first_forecast_cutoff"])
    descending = group_timing.sort_values("first_forecast_cutoff", ascending=False)
    observed_weeks: set[str] = set()
    effective_week_start = fractional_start
    for raw_row in descending.itertuples(index=False):
        row: Any = raw_row
        cutoff = pd.Timestamp(row.first_forecast_cutoff)
        observed_weeks.add(str(cutoff.tz_localize(None).to_period("W-SUN")))
        effective_week_start = cutoff
        if len(observed_weeks) >= config.inference.minimum_effective_weeks:
            break
    holdout_boundary = min(fractional_start, effective_week_start)
    holdout_groups = group_timing.loc[
        group_timing["first_forecast_cutoff"] >= holdout_boundary
    ].copy()
    development_groups = group_timing.loc[
        group_timing["first_forecast_cutoff"] < holdout_boundary
    ].copy()
    if len(development_groups) < config.study.development_folds + 1:
        raise ValueError("Development population is too small for requested folds")

    holdout_group_set = set(holdout_groups["event_group_id"].astype(str))
    development_group_set = set(development_groups["event_group_id"].astype(str))
    holdout_mask = working["event_group_id"].astype(str).isin(holdout_group_set)
    development_mask = working["event_group_id"].astype(str).isin(development_group_set)
    holdout_indices = np.flatnonzero(holdout_mask.to_numpy())
    development_indices = np.flatnonzero(development_mask.to_numpy())
    holdout_start = pd.Timestamp(working.loc[holdout_mask, "forecast_cutoff"].min())
    embargo = pd.Timedelta(days=config.study.embargo_days)

    chunks = np.array_split(
        development_groups["event_group_id"].astype(str).to_numpy(),
        config.study.development_folds + 1,
    )
    folds: list[WalkForwardFold] = []
    assignment_rows: list[dict[str, object]] = []
    for fold_number in range(1, config.study.development_folds + 1):
        validation_groups = set(chunks[fold_number].tolist())
        earlier_groups = set(np.concatenate(chunks[:fold_number]).tolist())
        validation_mask = working["event_group_id"].astype(str).isin(validation_groups)
        validation_start = pd.Timestamp(working.loc[validation_mask, "forecast_cutoff"].min())
        label_available_before = validation_start - embargo
        group_resolution = development_groups.set_index("event_group_id")["final_resolution"]
        eligible_train_groups = {
            group
            for group in earlier_groups
            if pd.Timestamp(group_resolution.loc[group]) < label_available_before
        }
        train_mask = working["event_group_id"].astype(str).isin(eligible_train_groups)
        train_indices = np.flatnonzero(train_mask.to_numpy())
        validation_indices = np.flatnonzero(validation_mask.to_numpy())
        if not len(train_indices) or not len(validation_indices):
            continue
        fold = WalkForwardFold(
            fold=fold_number,
            train_indices=train_indices,
            validation_indices=validation_indices,
            validation_start=validation_start,
            label_available_before=label_available_before,
        )
        folds.append(fold)
        assignment_rows.extend(
            {
                "row_index": int(index),
                "event_group_id": str(working.iloc[index]["event_group_id"]),
                "partition": "train",
                "fold": fold_number,
            }
            for index in train_indices
        )
        assignment_rows.extend(
            {
                "row_index": int(index),
                "event_group_id": str(working.iloc[index]["event_group_id"]),
                "partition": "validation",
                "fold": fold_number,
            }
            for index in validation_indices
        )
    if not folds:
        raise ValueError("No valid walk-forward fold remains after label embargo")

    final_label_cutoff = holdout_start - embargo
    final_train_groups = set(
        development_groups.loc[
            development_groups["final_resolution"] < final_label_cutoff,
            "event_group_id",
        ].astype(str)
    )
    final_train_mask = working["event_group_id"].astype(str).isin(final_train_groups)
    final_train_indices = np.flatnonzero(final_train_mask.to_numpy())
    if not len(final_train_indices):
        raise ValueError("No labels are available before the final holdout embargo")

    assignment_rows.extend(
        {
            "row_index": int(index),
            "event_group_id": str(working.iloc[index]["event_group_id"]),
            "partition": "final_train",
            "fold": 0,
        }
        for index in final_train_indices
    )
    assignment_rows.extend(
        {
            "row_index": int(index),
            "event_group_id": str(working.iloc[index]["event_group_id"]),
            "partition": "holdout",
            "fold": 0,
        }
        for index in holdout_indices
    )
    plan = SplitPlan(
        folds=tuple(folds),
        development_indices=development_indices,
        final_train_indices=final_train_indices,
        holdout_indices=holdout_indices,
        holdout_start=holdout_start,
        assignments=pd.DataFrame(assignment_rows),
    )
    audit_split_plan(working, plan, config)
    return plan


def audit_split_plan(
    cohort: pd.DataFrame,
    plan: SplitPlan,
    config: ProjectConfig,
) -> None:
    """Validate event isolation and past-label availability in every fold."""
    holdout_groups = set(cohort.iloc[plan.holdout_indices]["event_group_id"].astype(str))
    final_train_groups = set(cohort.iloc[plan.final_train_indices]["event_group_id"].astype(str))
    if holdout_groups.intersection(final_train_groups):
        raise AssertionError("An event group crosses final training and holdout")
    embargo = pd.Timedelta(days=config.study.embargo_days)
    for fold in plan.folds:
        train = cohort.iloc[fold.train_indices]
        validation = cohort.iloc[fold.validation_indices]
        train_groups = set(train["event_group_id"].astype(str))
        validation_groups = set(validation["event_group_id"].astype(str))
        if train_groups.intersection(validation_groups):
            raise AssertionError(f"An event group crosses fold {fold.fold}")
        validation_start = pd.Timestamp(validation["forecast_cutoff"].min())
        if (pd.to_datetime(train["closed_time"], utc=True) >= validation_start - embargo).any():
            raise AssertionError(f"Fold {fold.fold} contains unavailable training labels")
