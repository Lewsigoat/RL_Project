from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.evaluation.analysis import evaluate_predictions
from polymarket_forecast.models import develop_models, train_locked_system
from polymarket_forecast.splits import make_walk_forward_splits


def test_pinned_real_cohort_runs_split_train_and_inference(
    small_config: ProjectConfig,
) -> None:
    fixture_path = Path("tests/fixtures/real_cohort.parquet")
    manifest = json.loads(
        Path("tests/fixtures/real_cohort_manifest.json").read_text(encoding="utf-8")
    )
    assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == manifest["sha256"]
    cohort = pd.read_parquet(fixture_path)
    config = replace(
        small_config,
        study=replace(
            small_config.study,
            development_folds=2,
            embargo_days=7,
        ),
        model=replace(
            small_config.model,
            logistic_c_values=(1.0,),
            text_min_document_frequency=1,
        ),
        inference=replace(
            small_config.inference,
            minimum_effective_weeks=5,
            bootstrap_repetitions=99,
        ),
    )

    splits = make_walk_forward_splits(cohort, config)
    development = develop_models(cohort, splits, config)
    locked = train_locked_system(cohort, splits, development, config)
    holdout = cohort.iloc[splits.holdout_indices].copy()
    probabilities = locked.predict(holdout).reset_index(drop=True)
    predictions = pd.concat(
        [
            holdout[
                [
                    "market_id",
                    "event_group_id",
                    "forecast_cutoff",
                    "category",
                    "neg_risk",
                    "label",
                    "label_source",
                ]
            ].reset_index(drop=True),
            probabilities,
        ],
        axis=1,
    )
    evaluation = evaluate_predictions(predictions, config)

    assert manifest["rows"] == len(cohort)
    assert len(splits.folds) == 2
    assert len(predictions) > 0
    assert evaluation.primary_test.event_groups > 0
    assert set(evaluation.system_metrics["system"]) == {
        "model",
        "market",
        "calibrated_market",
        "global_climatology",
        "category_climatology",
    }
