"""Typed configuration loading and reproducibility helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and return an aware UTC datetime."""
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value!r}")
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class StudyConfig:
    protocol_version: str
    study_start: datetime
    data_cutoff: datetime
    horizons_days: tuple[int, ...]
    primary_horizon_days: int
    max_price_staleness_hours: int
    holdout_fraction: float
    split_strategy: str
    development_folds: int
    minimum_inner_train_groups: int
    embargo_days: int
    include_neg_risk: bool
    enforce_fingerprint_isolation: bool

    def __post_init__(self) -> None:
        if self.primary_horizon_days not in self.horizons_days:
            raise ValueError("primary_horizon_days must be included in horizons_days")
        if self.study_start >= self.data_cutoff:
            raise ValueError("study_start must precede data_cutoff")
        if not 0 < self.holdout_fraction < 0.5:
            raise ValueError("holdout_fraction must be between 0 and 0.5")
        if self.development_folds < 2:
            raise ValueError("development_folds must be at least 2")
        if self.minimum_inner_train_groups < 1:
            raise ValueError("minimum_inner_train_groups must be positive")
        if self.split_strategy not in {
            "strict_chronological_groups",
            "legacy_minimum_weeks",
        }:
            raise ValueError(f"Unsupported split_strategy: {self.split_strategy}")


@dataclass(frozen=True)
class ApiConfig:
    gamma_base_url: str
    clob_base_url: str
    data_base_url: str
    history_start: datetime
    page_size: int
    full_inventory: bool
    max_markets: int | None
    request_timeout_seconds: float
    max_retries: int
    concurrency: int
    price_fidelity_minutes: int
    history_lookback_days: int
    monthly_stratified_sampling: bool
    sampling_order: str
    collect_trades: bool
    trade_page_size: int
    user_agent: str


@dataclass(frozen=True)
class HistoricalConfig:
    enabled: bool
    repository: str
    revision: str
    layer: str
    additional_layers: tuple[str, ...]
    start_date: datetime
    end_date: datetime
    download_concurrency: int
    license: str

    def __post_init__(self) -> None:
        if self.start_date >= self.end_date:
            raise ValueError("historical start_date must precede end_date")
        if self.download_concurrency < 1:
            raise ValueError("historical download_concurrency must be positive")


@dataclass(frozen=True)
class ModelConfig:
    random_seed: int
    text_max_features: int
    text_min_document_frequency: int
    logistic_c_values: tuple[float, ...]
    residual_l2_values: tuple[float, ...]
    boosting_learning_rates: tuple[float, ...]
    boosting_leaf_nodes: tuple[int, ...]
    ensemble_minimum_brier_gain: float
    category_prior_strength: float
    probability_clip: float


@dataclass(frozen=True)
class CorpusConfig:
    contract_metadata_coverage_target: float
    resolution_coverage_target: float
    partition_rows: int
    retain_wallets: bool
    derive_prices_from_trades: bool

    def __post_init__(self) -> None:
        for value in (
            self.contract_metadata_coverage_target,
            self.resolution_coverage_target,
        ):
            if not 0 < value <= 1:
                raise ValueError("Corpus coverage targets must be in (0, 1]")
        if self.partition_rows < 1:
            raise ValueError("corpus.partition_rows must be positive")


@dataclass(frozen=True)
class InferenceConfig:
    alpha: float
    minimum_practical_effect: float
    bootstrap_repetitions: int
    block_length_weeks: int
    robustness_block_lengths_weeks: tuple[int, ...]
    power_repetitions: int
    target_power: float
    minimum_effective_weeks: int

    def __post_init__(self) -> None:
        if not 0 < self.alpha < 0.5:
            raise ValueError("alpha must be between 0 and 0.5")
        if not 0 < self.target_power < 1:
            raise ValueError("target_power must be between 0 and 1")
        if self.bootstrap_repetitions < 99:
            raise ValueError("bootstrap_repetitions must be at least 99")


@dataclass(frozen=True)
class PathsConfig:
    data_uri: str
    artifacts_uri: str
    reports_uri: str


@dataclass(frozen=True)
class ProjectConfig:
    study: StudyConfig
    api: ApiConfig
    historical: HistoricalConfig
    corpus: CorpusConfig
    model: ModelConfig
    inference: InferenceConfig
    paths: PathsConfig
    source_path: Path

    @property
    def canonical_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation used in run manifests."""
        payload = asdict(self)
        payload.pop("source_path", None)
        payload["study"]["study_start"] = self.study.study_start.isoformat()
        payload["study"]["data_cutoff"] = self.study.data_cutoff.isoformat()
        payload["api"]["history_start"] = self.api.history_start.isoformat()
        payload["historical"]["start_date"] = self.historical.start_date.isoformat()
        payload["historical"]["end_date"] = self.historical.end_date.isoformat()
        return payload

    @property
    def sha256(self) -> str:
        encoded = json.dumps(
            self.canonical_dict,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


def _require_mapping(payload: Any, name: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError(f"{name} must be a mapping")
    return {str(key): value for key, value in payload.items()}


def load_config(path: str | Path = "configs/study.yaml") -> ProjectConfig:
    """Load and validate the project YAML configuration."""
    source = Path(path).resolve()
    with source.open(encoding="utf-8") as handle:
        raw = _require_mapping(yaml.safe_load(handle), "configuration")

    study_raw = _require_mapping(raw["study"], "study")
    api_raw = _require_mapping(raw["api"], "api")
    historical_raw = _require_mapping(raw["historical"], "historical")
    corpus_raw = _require_mapping(
        raw.get(
            "corpus",
            {
                "contract_metadata_coverage_target": 0.95,
                "resolution_coverage_target": 0.95,
                "partition_rows": 250000,
                "retain_wallets": False,
                "derive_prices_from_trades": True,
            },
        ),
        "corpus",
    )
    model_raw = _require_mapping(raw["model"], "model")
    inference_raw = _require_mapping(raw["inference"], "inference")
    paths_raw = _require_mapping(raw["paths"], "paths")

    study = StudyConfig(
        protocol_version=str(study_raw["protocol_version"]),
        study_start=parse_utc(str(study_raw["study_start"])),
        data_cutoff=parse_utc(str(study_raw["data_cutoff"])),
        horizons_days=tuple(int(item) for item in study_raw["horizons_days"]),
        primary_horizon_days=int(study_raw["primary_horizon_days"]),
        max_price_staleness_hours=int(study_raw["max_price_staleness_hours"]),
        holdout_fraction=float(study_raw["holdout_fraction"]),
        split_strategy=str(study_raw.get("split_strategy", "legacy_minimum_weeks")),
        development_folds=int(study_raw["development_folds"]),
        minimum_inner_train_groups=int(study_raw.get("minimum_inner_train_groups", 1)),
        embargo_days=int(study_raw["embargo_days"]),
        include_neg_risk=bool(study_raw["include_neg_risk"]),
        enforce_fingerprint_isolation=bool(study_raw.get("enforce_fingerprint_isolation", False)),
    )
    max_markets_raw = api_raw.get("max_markets")
    api = ApiConfig(
        gamma_base_url=str(api_raw["gamma_base_url"]).rstrip("/"),
        clob_base_url=str(api_raw["clob_base_url"]).rstrip("/"),
        data_base_url=str(api_raw.get("data_base_url", "https://data-api.polymarket.com")).rstrip(
            "/"
        ),
        history_start=parse_utc(str(api_raw["history_start"])),
        page_size=int(api_raw["page_size"]),
        full_inventory=bool(api_raw.get("full_inventory", False)),
        max_markets=(None if max_markets_raw is None else int(max_markets_raw)),
        request_timeout_seconds=float(api_raw["request_timeout_seconds"]),
        max_retries=int(api_raw["max_retries"]),
        concurrency=int(api_raw["concurrency"]),
        price_fidelity_minutes=int(api_raw["price_fidelity_minutes"]),
        history_lookback_days=int(api_raw["history_lookback_days"]),
        monthly_stratified_sampling=bool(api_raw["monthly_stratified_sampling"]),
        sampling_order=str(api_raw["sampling_order"]),
        collect_trades=bool(api_raw.get("collect_trades", False)),
        trade_page_size=int(api_raw.get("trade_page_size", 10000)),
        user_agent=str(api_raw["user_agent"]),
    )
    historical = HistoricalConfig(
        enabled=bool(historical_raw["enabled"]),
        repository=str(historical_raw["repository"]),
        revision=str(historical_raw["revision"]),
        layer=str(historical_raw["layer"]),
        additional_layers=tuple(str(item) for item in historical_raw.get("additional_layers", [])),
        start_date=parse_utc(str(historical_raw["start_date"])),
        end_date=parse_utc(str(historical_raw["end_date"])),
        download_concurrency=int(historical_raw["download_concurrency"]),
        license=str(historical_raw["license"]),
    )
    corpus = CorpusConfig(
        contract_metadata_coverage_target=float(corpus_raw["contract_metadata_coverage_target"]),
        resolution_coverage_target=float(corpus_raw["resolution_coverage_target"]),
        partition_rows=int(corpus_raw["partition_rows"]),
        retain_wallets=bool(corpus_raw["retain_wallets"]),
        derive_prices_from_trades=bool(corpus_raw["derive_prices_from_trades"]),
    )
    model = ModelConfig(
        random_seed=int(model_raw["random_seed"]),
        text_max_features=int(model_raw["text_max_features"]),
        text_min_document_frequency=int(model_raw["text_min_document_frequency"]),
        logistic_c_values=tuple(float(item) for item in model_raw["logistic_c_values"]),
        residual_l2_values=tuple(
            float(item) for item in model_raw.get("residual_l2_values", [1.0])
        ),
        boosting_learning_rates=tuple(
            float(item) for item in model_raw.get("boosting_learning_rates", [0.05])
        ),
        boosting_leaf_nodes=tuple(int(item) for item in model_raw.get("boosting_leaf_nodes", [15])),
        ensemble_minimum_brier_gain=float(model_raw.get("ensemble_minimum_brier_gain", 0.0)),
        category_prior_strength=float(model_raw["category_prior_strength"]),
        probability_clip=float(model_raw["probability_clip"]),
    )
    inference = InferenceConfig(
        alpha=float(inference_raw["alpha"]),
        minimum_practical_effect=float(inference_raw["minimum_practical_effect"]),
        bootstrap_repetitions=int(inference_raw["bootstrap_repetitions"]),
        block_length_weeks=int(inference_raw["block_length_weeks"]),
        robustness_block_lengths_weeks=tuple(
            int(item) for item in inference_raw["robustness_block_lengths_weeks"]
        ),
        power_repetitions=int(inference_raw["power_repetitions"]),
        target_power=float(inference_raw["target_power"]),
        minimum_effective_weeks=int(inference_raw["minimum_effective_weeks"]),
    )
    paths = PathsConfig(
        data_uri=str(paths_raw["data_uri"]),
        artifacts_uri=str(paths_raw["artifacts_uri"]),
        reports_uri=str(paths_raw["reports_uri"]),
    )
    return ProjectConfig(
        study=study,
        api=api,
        historical=historical,
        corpus=corpus,
        model=model,
        inference=inference,
        paths=paths,
        source_path=source,
    )
