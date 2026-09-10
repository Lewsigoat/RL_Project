"""Reproducible orchestration for collection, training, and evaluation."""

from __future__ import annotations

import io
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from polymarket_forecast.cohort import CohortResult, build_cohort
from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.data.collector import CollectionSummary, collect_markets
from polymarket_forecast.data.historical import (
    build_historical_v1_cohort,
    collect_historical_v1,
)
from polymarket_forecast.data.storage import ResearchStorage
from polymarket_forecast.evaluation.analysis import EvaluationBundle, evaluate_predictions
from polymarket_forecast.evaluation.bootstrap import (
    event_score_differences,
    paired_superiority_test,
)
from polymarket_forecast.evaluation.metrics import holm_adjust
from polymarket_forecast.evaluation.power import required_weeks_for_power, simulate_power
from polymarket_forecast.models import (
    ClimatologyModel,
    DevelopmentResult,
    LockedSystem,
    develop_models,
    fit_ablation_predictions,
    train_locked_system,
)
from polymarket_forecast.splits import SplitPlan, make_walk_forward_splits


@dataclass(frozen=True)
class BuildSummary:
    data_run_id: str
    cohort_rows: int
    api_cohort_rows: int
    historical_cohort_rows: int
    primary_rows: int
    event_groups: int
    exclusions: int
    cohort_sha256: str


@dataclass(frozen=True)
class TrainingSummary:
    study_run_id: str
    data_run_id: str
    selected_model: str
    development_rows: int
    final_train_rows: int
    holdout_rows: int
    holdout_event_groups: int
    model_sha256: str


@dataclass(frozen=True)
class EvaluationSummary:
    study_run_id: str
    data_run_id: str
    selected_model: str
    holdout_rows: int
    holdout_event_groups: int
    effective_weeks: int
    global_p_value: float
    superior_to_both: bool
    practically_superior_to_both: bool
    required_weeks_for_target_power: int | None


def _latest_data_run(storage: ResearchStorage) -> str:
    pointer = storage.read_json("processed/latest.json")
    if not isinstance(pointer, dict) or not pointer.get("run_id"):
        raise ValueError("processed/latest.json does not identify a data run")
    return str(pointer["run_id"])


def _latest_study_run(storage: ResearchStorage) -> str:
    pointer = storage.read_json("latest.json")
    if not isinstance(pointer, dict) or not pointer.get("study_run_id"):
        raise ValueError("artifacts/latest.json does not identify a study run")
    return str(pointer["study_run_id"])


def _artifact_bytes(payload: Any) -> bytes:
    buffer = io.BytesIO()
    joblib.dump(payload, buffer, compress=3)
    return buffer.getvalue()


def _load_artifact(storage: ResearchStorage, relative: str) -> Any:
    return joblib.load(io.BytesIO(storage.read_bytes(relative)))


def collect_data(
    config: ProjectConfig,
    *,
    run_id: str | None = None,
) -> CollectionSummary:
    storage = ResearchStorage(config.paths.data_uri)
    summary = collect_markets(
        config,
        storage,
        run_id=run_id,
    )
    historical = collect_historical_v1(
        config,
        storage,
        run_id=summary.run_id,
    )
    if historical is not None:
        storage.write_json(
            f"processed/{summary.run_id}/historical_collection_summary.json",
            asdict(historical),
        )
    return summary


def build_dataset(
    config: ProjectConfig,
    *,
    data_run_id: str | None = None,
) -> BuildSummary:
    data_storage = ResearchStorage(config.paths.data_uri)
    resolved_run_id = data_run_id or _latest_data_run(data_storage)
    prefix = f"processed/{resolved_run_id}"
    markets = data_storage.read_parquet(f"{prefix}/markets.parquet")
    prices = data_storage.read_parquet(f"{prefix}/price_points.parquet")
    result: CohortResult = build_cohort(markets, prices, config)
    historical = (
        build_historical_v1_cohort(
            config,
            data_storage,
            run_id=resolved_run_id,
        )
        if config.historical.enabled
        else pd.DataFrame(columns=result.cohort.columns)
    )
    combined = pd.concat([historical, result.cohort], ignore_index=True)
    if not combined.empty:
        combined = (
            combined.sort_values(["forecast_cutoff", "market_id", "horizon_days"])
            .drop_duplicates(["market_id", "horizon_days"], keep="last")
            .reset_index(drop=True)
        )
    cohort_hash = data_storage.write_parquet(f"{prefix}/cohort.parquet", combined)
    data_storage.write_parquet(
        f"{prefix}/cohort_exclusions.parquet",
        result.exclusions,
    )
    primary = combined.loc[combined["horizon_days"] == config.study.primary_horizon_days]
    summary = BuildSummary(
        data_run_id=resolved_run_id,
        cohort_rows=int(len(combined)),
        api_cohort_rows=int(len(result.cohort)),
        historical_cohort_rows=int(len(historical)),
        primary_rows=int(len(primary)),
        event_groups=int(primary["event_group_id"].nunique()),
        exclusions=int(len(result.exclusions)),
        cohort_sha256=cohort_hash,
    )
    data_storage.write_json(f"{prefix}/build_summary.json", asdict(summary))
    return summary


def _enrich_selected_oof(
    primary: pd.DataFrame,
    splits: SplitPlan,
    development: DevelopmentResult,
    config: ProjectConfig,
) -> pd.DataFrame:
    selected = development.oof_predictions.loc[
        development.oof_predictions["candidate"] == development.selected_name
    ].copy()
    metadata = primary.reset_index().rename(columns={"index": "row_index"})
    metadata_columns = [
        "row_index",
        "market_id",
        "event_group_id",
        "forecast_cutoff",
        "label",
        "market_probability",
        "category",
        "label_source",
        "neg_risk",
    ]
    selected = selected.drop(columns=["event_group_id", "label"]).merge(
        metadata[metadata_columns],
        on="row_index",
        how="left",
        validate="one_to_one",
    )
    selected = selected.rename(columns={"probability": "model_probability"})
    selected["category_climatology_probability"] = np.nan
    selected["global_climatology_probability"] = np.nan
    for fold in splits.folds:
        train = primary.iloc[fold.train_indices]
        validation_indices = {int(index) for index in fold.validation_indices}
        mask = (selected["fold"] == fold.fold) & selected["row_index"].isin(validation_indices)
        validation = primary.loc[selected.loc[mask, "row_index"].astype(int)]
        y = train["label"].to_numpy(dtype=int)
        category_model = ClimatologyModel(
            config.model.category_prior_strength,
            use_category=True,
        ).fit(train, y)
        global_model = ClimatologyModel(
            config.model.category_prior_strength,
            use_category=False,
        ).fit(train, y)
        selected.loc[mask, "category_climatology_probability"] = category_model.predict_probability(
            validation
        )
        selected.loc[mask, "global_climatology_probability"] = global_model.predict_probability(
            validation
        )
    if (
        selected[["category_climatology_probability", "global_climatology_probability"]]
        .isna()
        .any()
        .any()
    ):
        raise AssertionError("OOF baseline probabilities were not fully assigned")
    return selected.sort_values("row_index").reset_index(drop=True)


def train_study(
    config: ProjectConfig,
    *,
    data_run_id: str | None = None,
    study_run_id: str | None = None,
) -> TrainingSummary:
    data_storage = ResearchStorage(config.paths.data_uri)
    artifact_storage = ResearchStorage(config.paths.artifacts_uri)
    resolved_data_run = data_run_id or _latest_data_run(data_storage)
    resolved_study_run = study_run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    cohort = data_storage.read_parquet(f"processed/{resolved_data_run}/cohort.parquet")
    primary = (
        cohort.loc[cohort["horizon_days"] == config.study.primary_horizon_days]
        .sort_values(["forecast_cutoff", "event_group_id", "market_id"])
        .reset_index(drop=True)
    )
    splits = make_walk_forward_splits(primary, config)
    development = develop_models(primary, splits, config)
    locked = train_locked_system(primary, splits, development, config)
    selected_oof = _enrich_selected_oof(primary, splits, development, config)

    payload = {
        "schema_version": "1",
        "config_sha256": config.sha256,
        "data_run_id": resolved_data_run,
        "study_run_id": resolved_study_run,
        "selected_model": development.selected_name,
        "split_plan": splits,
        "development": development,
        "locked_system": locked,
    }
    model_path = f"runs/{resolved_study_run}/locked_system.joblib"
    model_hash = artifact_storage.write_bytes(model_path, _artifact_bytes(payload))
    artifact_storage.write_parquet(
        f"runs/{resolved_study_run}/split_assignments.parquet",
        splits.assignments,
    )
    artifact_storage.write_parquet(
        f"runs/{resolved_study_run}/development_scoreboard.parquet",
        development.scoreboard,
    )
    artifact_storage.write_parquet(
        f"runs/{resolved_study_run}/development_oof.parquet",
        selected_oof,
    )
    summary = TrainingSummary(
        study_run_id=resolved_study_run,
        data_run_id=resolved_data_run,
        selected_model=development.selected_name,
        development_rows=int(len(splits.development_indices)),
        final_train_rows=int(len(splits.final_train_indices)),
        holdout_rows=int(len(splits.holdout_indices)),
        holdout_event_groups=int(primary.iloc[splits.holdout_indices]["event_group_id"].nunique()),
        model_sha256=model_hash,
    )
    artifact_storage.write_json(
        f"runs/{resolved_study_run}/training_summary.json",
        asdict(summary),
    )
    artifact_storage.write_json(
        "latest.json",
        {
            "study_run_id": resolved_study_run,
            "data_run_id": resolved_data_run,
            "model_path": model_path,
            "model_sha256": model_hash,
        },
    )
    return summary


def _prediction_frame(
    primary: pd.DataFrame,
    splits: SplitPlan,
    locked: LockedSystem,
) -> pd.DataFrame:
    holdout = primary.iloc[splits.holdout_indices].copy()
    probabilities = locked.predict(holdout)
    columns = [
        "market_id",
        "event_id",
        "event_group_id",
        "forecast_cutoff",
        "event_time",
        "closed_time",
        "category",
        "neg_risk",
        "label",
        "label_source",
        "horizon_days",
    ]
    metadata = holdout[columns].reset_index(drop=True)
    return pd.concat(
        [metadata, probabilities.reset_index(drop=True)],
        axis=1,
    )


def _save_evaluation_bundle(
    reports: ResearchStorage,
    prefix: str,
    bundle: EvaluationBundle,
) -> None:
    reports.write_json(f"{prefix}/primary_test.json", bundle.primary_test.to_dict())
    reports.write_parquet(f"{prefix}/system_metrics.parquet", bundle.system_metrics)
    reports.write_parquet(f"{prefix}/reliability.parquet", bundle.reliability)
    reports.write_parquet(
        f"{prefix}/block_robustness.parquet",
        bundle.block_robustness,
    )
    reports.write_parquet(f"{prefix}/slice_metrics.parquet", bundle.slice_metrics)
    reports.write_parquet(f"{prefix}/sensitivity.parquet", bundle.sensitivity)


def _evaluate_secondary_horizons(
    cohort: pd.DataFrame,
    config: ProjectConfig,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon in config.study.horizons_days:
        if horizon == config.study.primary_horizon_days:
            continue
        subset = (
            cohort.loc[cohort["horizon_days"] == horizon]
            .sort_values(["forecast_cutoff", "event_group_id", "market_id"])
            .reset_index(drop=True)
        )
        try:
            splits = make_walk_forward_splits(subset, config)
            development = develop_models(subset, splits, config)
            system = train_locked_system(subset, splits, development, config)
            predictions = _prediction_frame(subset, splits, system)
            test = paired_superiority_test(
                predictions,
                repetitions=config.inference.bootstrap_repetitions,
                block_length_weeks=config.inference.block_length_weeks,
                seed=config.model.random_seed + horizon,
                alpha=config.inference.alpha,
                minimum_practical_effect=config.inference.minimum_practical_effect,
            )
            rows.append(
                {
                    "horizon_days": horizon,
                    "status": "ok",
                    "selected_model": development.selected_name,
                    "contracts": len(predictions),
                    "event_groups": predictions["event_group_id"].nunique(),
                    "market_improvement": test.market.mean_brier_improvement,
                    "market_p_value": test.market.p_value_one_sided,
                    "climatology_improvement": test.climatology.mean_brier_improvement,
                    "climatology_p_value": test.climatology.p_value_one_sided,
                    "global_p_value": test.global_intersection_union_p,
                    "superior_to_both": test.superior_to_both,
                }
            )
        except (AssertionError, RuntimeError, ValueError) as exc:
            rows.append(
                {
                    "horizon_days": horizon,
                    "status": "insufficient_or_failed",
                    "detail": str(exc),
                }
            )
    result = pd.DataFrame(rows)
    valid = result.loc[result["status"] == "ok"]
    if not valid.empty:
        p_values: dict[str, float] = {}
        for raw_row in valid.itertuples():
            row: Any = raw_row
            p_values[f"horizon_{int(row.horizon_days)}"] = float(row.global_p_value)
        adjusted = holm_adjust(p_values)
        result["holm_adjusted_global_p"] = result["horizon_days"].map(
            {int(name.removeprefix("horizon_")): value for name, value in adjusted.items()}
        )
    return result


def run_power_analysis(
    config: ProjectConfig,
    *,
    study_run_id: str | None = None,
) -> pd.DataFrame:
    """Run the preregistered power simulation from development OOF residuals."""
    artifact_storage = ResearchStorage(config.paths.artifacts_uri)
    report_storage = ResearchStorage(config.paths.reports_uri)
    resolved_study_run = study_run_id or _latest_study_run(artifact_storage)
    development_oof = artifact_storage.read_parquet(
        f"runs/{resolved_study_run}/development_oof.parquet"
    )
    development_events = event_score_differences(development_oof)
    power = simulate_power(
        development_events,
        repetitions=config.inference.power_repetitions,
        block_length_weeks=config.inference.block_length_weeks,
        alpha=config.inference.alpha,
        minimum_practical_effect=config.inference.minimum_practical_effect,
        seed=config.model.random_seed,
    )
    report_storage.write_parquet(
        f"{resolved_study_run}/power_simulation.parquet",
        power,
    )
    return power


def evaluate_study(
    config: ProjectConfig,
    *,
    study_run_id: str | None = None,
) -> EvaluationSummary:
    data_storage = ResearchStorage(config.paths.data_uri)
    artifact_storage = ResearchStorage(config.paths.artifacts_uri)
    report_storage = ResearchStorage(config.paths.reports_uri)
    resolved_study_run = study_run_id or _latest_study_run(artifact_storage)
    pointer = artifact_storage.read_json("latest.json")
    data_run_id = str(pointer["data_run_id"])
    payload = _load_artifact(
        artifact_storage,
        f"runs/{resolved_study_run}/locked_system.joblib",
    )
    if payload["config_sha256"] != config.sha256:
        raise ValueError("Current configuration does not match the locked model")
    splits: SplitPlan = payload["split_plan"]
    development: DevelopmentResult = payload["development"]
    locked: LockedSystem = payload["locked_system"]

    cohort = data_storage.read_parquet(f"processed/{data_run_id}/cohort.parquet")
    primary = (
        cohort.loc[cohort["horizon_days"] == config.study.primary_horizon_days]
        .sort_values(["forecast_cutoff", "event_group_id", "market_id"])
        .reset_index(drop=True)
    )
    predictions = _prediction_frame(primary, splits, locked)
    bundle = evaluate_predictions(predictions, config)
    prefix = f"{resolved_study_run}"
    report_storage.write_parquet(f"{prefix}/holdout_predictions.parquet", predictions)
    _save_evaluation_bundle(report_storage, prefix, bundle)

    final_train = primary.iloc[splits.final_train_indices]
    holdout = primary.iloc[splits.holdout_indices]
    ablations = fit_ablation_predictions(
        final_train,
        holdout,
        config,
        selected_name=development.selected_name,
        ensemble_weights=development.ensemble_weights,
    )
    ablation_rows = []
    for column in ablations:
        loss = (ablations[column].to_numpy() - holdout["label"].to_numpy()) ** 2
        scored = pd.DataFrame(
            {
                "event_group_id": holdout["event_group_id"].to_numpy(),
                "loss": loss,
            }
        )
        ablation_rows.append(
            {
                "ablation": column,
                "event_weighted_brier": float(
                    scored.groupby("event_group_id")["loss"].mean().mean()
                ),
            }
        )
    report_storage.write_parquet(
        f"{prefix}/ablation_metrics.parquet",
        pd.DataFrame(ablation_rows),
    )

    power = run_power_analysis(config, study_run_id=resolved_study_run)
    required_weeks = required_weeks_for_power(
        power,
        target_power=config.inference.target_power,
    )
    secondary = _evaluate_secondary_horizons(cohort, config)
    report_storage.write_parquet(f"{prefix}/secondary_horizons.parquet", secondary)

    summary = EvaluationSummary(
        study_run_id=resolved_study_run,
        data_run_id=data_run_id,
        selected_model=development.selected_name,
        holdout_rows=int(len(predictions)),
        holdout_event_groups=int(predictions["event_group_id"].nunique()),
        effective_weeks=bundle.primary_test.effective_weeks,
        global_p_value=bundle.primary_test.global_intersection_union_p,
        superior_to_both=bundle.primary_test.superior_to_both,
        practically_superior_to_both=bundle.primary_test.practically_superior_to_both,
        required_weeks_for_target_power=required_weeks,
    )
    report_storage.write_json(f"{prefix}/evaluation_summary.json", asdict(summary))
    report_storage.write_json(
        "latest.json",
        {
            "study_run_id": resolved_study_run,
            "data_run_id": data_run_id,
            "selected_model": development.selected_name,
            "summary": f"{prefix}/evaluation_summary.json",
        },
    )
    return summary


def run_study(
    config: ProjectConfig,
    *,
    collect: bool = True,
    data_run_id: str | None = None,
    study_run_id: str | None = None,
) -> EvaluationSummary:
    """Execute collection through confirmatory evaluation."""
    resolved_data_run = data_run_id
    if collect:
        collection = collect_data(config, run_id=data_run_id)
        resolved_data_run = collection.run_id
    build_dataset(config, data_run_id=resolved_data_run)
    training = train_study(
        config,
        data_run_id=resolved_data_run,
        study_run_id=study_run_id,
    )
    return evaluate_study(config, study_run_id=training.study_run_id)


def export_result_tables(
    config: ProjectConfig,
    destination: str | Path = "reports/results",
) -> list[Path]:
    """Export aggregate, reviewable CSV/JSON results while excluding raw data."""
    source = ResearchStorage(config.paths.reports_uri)
    run_id = _latest_study_run(source)
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    exported: list[Path] = []
    json_files = ["evaluation_summary.json", "primary_test.json"]
    parquet_files = [
        "system_metrics.parquet",
        "block_robustness.parquet",
        "slice_metrics.parquet",
        "sensitivity.parquet",
        "ablation_metrics.parquet",
        "power_simulation.parquet",
        "secondary_horizons.parquet",
    ]
    for filename in json_files:
        path = target / filename
        path.write_bytes(source.read_bytes(f"{run_id}/{filename}"))
        exported.append(path)
    for filename in parquet_files:
        frame = source.read_parquet(f"{run_id}/{filename}")
        path = target / filename.replace(".parquet", ".csv")
        frame.to_csv(path, index=False)
        exported.append(path)
    manifest = {
        "study_run_id": run_id,
        "exported_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.sha256,
        "files": [path.name for path in exported],
        "raw_data_included": False,
    }
    manifest_path = target / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    exported.append(manifest_path)
    return exported
