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
    development_folds: int
    embargo_days: int
    include_neg_risk: bool

    def __post_init__(self) -> None:
        if self.primary_horizon_days not in self.horizons_days:
            raise ValueError("primary_horizon_days must be included in horizons_days")
        if self.study_start >= self.data_cutoff:
            raise ValueError("study_start must precede data_cutoff")
        if not 0 < self.holdout_fraction < 0.5:
            raise ValueError("holdout_fraction must be between 0 and 0.5")
        if self.development_folds < 2:
            raise ValueError("development_folds must be at least 2")


@dataclass(frozen=True)
class ApiConfig:
    gamma_base_url: str
    clob_base_url: str
    page_size: int
    max_markets: int
    request_timeout_seconds: float
    max_retries: int
    concurrency: int
    price_fidelity_minutes: int
    history_lookback_days: int
    user_agent: str


@dataclass(frozen=True)
class ModelConfig:
    random_seed: int
    text_max_features: int
    text_min_document_frequency: int
    logistic_c_values: tuple[float, ...]
    category_prior_strength: float
    probability_clip: float


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
        development_folds=int(study_raw["development_folds"]),
        embargo_days=int(study_raw["embargo_days"]),
        include_neg_risk=bool(study_raw["include_neg_risk"]),
    )
    api = ApiConfig(
        gamma_base_url=str(api_raw["gamma_base_url"]).rstrip("/"),
        clob_base_url=str(api_raw["clob_base_url"]).rstrip("/"),
        page_size=int(api_raw["page_size"]),
        max_markets=int(api_raw["max_markets"]),
        request_timeout_seconds=float(api_raw["request_timeout_seconds"]),
        max_retries=int(api_raw["max_retries"]),
        concurrency=int(api_raw["concurrency"]),
        price_fidelity_minutes=int(api_raw["price_fidelity_minutes"]),
        history_lookback_days=int(api_raw["history_lookback_days"]),
        user_agent=str(api_raw["user_agent"]),
    )
    model = ModelConfig(
        random_seed=int(model_raw["random_seed"]),
        text_max_features=int(model_raw["text_max_features"]),
        text_min_document_frequency=int(model_raw["text_min_document_frequency"]),
        logistic_c_values=tuple(float(item) for item in model_raw["logistic_c_values"]),
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
        model=model,
        inference=inference,
        paths=paths,
        source_path=source,
    )
