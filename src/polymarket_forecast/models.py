"""Baselines, candidate forecasters, model locking, and ablations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.base import BaseEstimator
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.splits import SplitPlan

NUMERIC_FEATURES = [
    "market_probability",
    "market_logit",
    "price_age_hours",
    "price_return_24h",
    "price_return_7d",
    "price_mean_7d",
    "price_std_7d",
    "price_min_7d",
    "price_max_7d",
    "history_points_7d",
    "contract_age_days",
    "time_to_event_days",
    "question_length",
    "description_length",
]
TRAJECTORY_FEATURES = [
    "price_age_hours",
    "price_return_24h",
    "price_return_7d",
    "price_mean_7d",
    "price_std_7d",
    "price_min_7d",
    "price_max_7d",
    "history_points_7d",
]
TIME_FEATURES = ["contract_age_days", "time_to_event_days"]
CATEGORICAL_FEATURES = ["category", "neg_risk"]


class ProbabilityModel(Protocol):
    def fit(self, frame: pd.DataFrame, y: np.ndarray) -> ProbabilityModel: ...

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray: ...


class ConstantModel:
    def __init__(self, probability: float) -> None:
        self.probability = float(probability)

    def fit(self, frame: pd.DataFrame, y: np.ndarray) -> ConstantModel:
        del frame, y
        return self

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        probability = np.full(len(frame), self.probability)
        return np.column_stack([1 - probability, probability])


class SklearnFrameModel:
    def __init__(self, estimator: BaseEstimator) -> None:
        self.estimator = estimator

    def fit(self, frame: pd.DataFrame, y: np.ndarray) -> SklearnFrameModel:
        self.estimator.fit(frame, y)
        return self

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        result = self.estimator.predict_proba(frame)
        return np.asarray(result, dtype=float)


class ClimatologyModel:
    """Past-only global or category-shrunk YES rates."""

    def __init__(self, prior_strength: float, use_category: bool = True) -> None:
        self.prior_strength = prior_strength
        self.use_category = use_category
        self.global_rate = 0.5
        self.category_rates: dict[str, float] = {}

    def fit(self, frame: pd.DataFrame, y: np.ndarray) -> ClimatologyModel:
        positives = float(y.sum())
        self.global_rate = (positives + 1) / (len(y) + 2)
        self.category_rates = {}
        if self.use_category:
            training = pd.DataFrame(
                {
                    "category": frame["category"].fillna("unknown").astype(str).to_numpy(),
                    "label": y,
                }
            )
            grouped = training.groupby("category")["label"].agg(["sum", "count"])
            for category, row in grouped.iterrows():
                numerator = float(row["sum"]) + self.prior_strength * self.global_rate
                denominator = float(row["count"]) + self.prior_strength
                self.category_rates[str(category)] = numerator / denominator
        return self

    def predict_probability(self, frame: pd.DataFrame) -> np.ndarray:
        if not self.use_category:
            return np.full(len(frame), self.global_rate)
        categories = frame["category"].fillna("unknown").astype(str)
        return categories.map(self.category_rates).fillna(self.global_rate).to_numpy(dtype=float)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        probability = self.predict_probability(frame)
        return np.column_stack([1 - probability, probability])


class MarketCalibrator:
    """Logistic recalibration of the matched-time market probability."""

    def __init__(self, probability_clip: float, c_value: float = 1.0) -> None:
        self.probability_clip = probability_clip
        self.c_value = c_value
        self.model: LogisticRegression | ConstantModel | None = None

    def _design(self, frame: pd.DataFrame) -> pd.DataFrame:
        probability = np.clip(
            frame["market_probability"].to_numpy(dtype=float),
            self.probability_clip,
            1 - self.probability_clip,
        )
        return pd.DataFrame({"market_logit": np.log(probability / (1 - probability))})

    def fit(self, frame: pd.DataFrame, y: np.ndarray) -> MarketCalibrator:
        if len(np.unique(y)) < 2:
            self.model = ConstantModel((float(y.sum()) + 1) / (len(y) + 2))
        else:
            estimator = LogisticRegression(C=self.c_value, max_iter=2000)
            estimator.fit(self._design(frame), y)
            self.model = estimator
        return self

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("MarketCalibrator must be fitted before prediction")
        if isinstance(self.model, ConstantModel):
            return self.model.predict_proba(frame)
        return np.asarray(self.model.predict_proba(self._design(frame)), dtype=float)


class MarketResidualModel:
    """Regularized logistic correction with the market logit as a fixed offset."""

    def __init__(
        self,
        numeric_features: list[str],
        categorical_features: list[str],
        *,
        l2: float,
        probability_clip: float,
    ) -> None:
        self.numeric_features = numeric_features
        self.categorical_features = categorical_features
        self.l2 = l2
        self.probability_clip = probability_clip
        self.transformer: ColumnTransformer | None = None
        self.parameters: np.ndarray | None = None

    def _offset(self, frame: pd.DataFrame) -> np.ndarray:
        probability = np.clip(
            frame["market_probability"].to_numpy(dtype=float),
            self.probability_clip,
            1 - self.probability_clip,
        )
        return np.asarray(np.log(probability / (1 - probability)), dtype=float)

    def fit(self, frame: pd.DataFrame, y: np.ndarray) -> MarketResidualModel:
        transformer = _structured_transformer(
            [feature for feature in self.numeric_features if feature != "market_logit"],
            self.categorical_features,
            dense=True,
        )
        design = np.asarray(transformer.fit_transform(frame), dtype=float)
        offset = self._offset(frame)

        def objective(parameters: np.ndarray) -> tuple[float, np.ndarray]:
            intercept = parameters[0]
            coefficients = parameters[1:]
            linear = offset + intercept + design @ coefficients
            probability = 1 / (1 + np.exp(-np.clip(linear, -35, 35)))
            loss_value = float(
                np.mean(np.logaddexp(0, linear) - y * linear)
                + 0.5 * self.l2 * coefficients @ coefficients / max(len(y), 1)
            )
            residual = probability - y
            gradient = np.concatenate(
                [
                    [float(np.mean(residual))],
                    design.T @ residual / max(len(y), 1) + self.l2 * coefficients / max(len(y), 1),
                ]
            )
            return loss_value, gradient

        initial = np.zeros(design.shape[1] + 1)
        result = minimize(
            objective,
            initial,
            method="L-BFGS-B",
            jac=True,
            options={"maxiter": 1000, "ftol": 1e-10},
        )
        if not result.success:
            raise RuntimeError(f"Residual model optimization failed: {result.message}")
        self.transformer = transformer
        self.parameters = np.asarray(result.x, dtype=float)
        return self

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        if self.transformer is None or self.parameters is None:
            raise RuntimeError("MarketResidualModel must be fitted before prediction")
        design = np.asarray(self.transformer.transform(frame), dtype=float)
        linear = self._offset(frame) + self.parameters[0] + design @ self.parameters[1:]
        probability = 1 / (1 + np.exp(-np.clip(linear, -35, 35)))
        return np.column_stack([1 - probability, probability])


@dataclass(frozen=True)
class CandidateDefinition:
    name: str
    family: str
    factory: Callable[[], ProbabilityModel]


@dataclass(frozen=True)
class DevelopmentResult:
    selected_name: str
    scoreboard: pd.DataFrame
    oof_predictions: pd.DataFrame
    ensemble_weights: dict[str, float]


@dataclass
class LockedSystem:
    selected_name: str
    models: dict[str, ProbabilityModel]
    weights: dict[str, float]
    global_climatology: ClimatologyModel
    category_climatology: ClimatologyModel
    market_calibrator: MarketCalibrator
    probability_clip: float

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        candidate_probabilities = {
            name: _positive_probability(model, frame, self.probability_clip)
            for name, model in self.models.items()
        }
        if self.selected_name == "ensemble":
            model_probability = sum(
                self.weights[name] * candidate_probabilities[name] for name in self.weights
            )
        else:
            model_probability = candidate_probabilities[self.selected_name]
        return pd.DataFrame(
            {
                "model_probability": model_probability,
                "market_probability": np.clip(
                    frame["market_probability"].to_numpy(dtype=float),
                    self.probability_clip,
                    1 - self.probability_clip,
                ),
                "calibrated_market_probability": _positive_probability(
                    self.market_calibrator,
                    frame,
                    self.probability_clip,
                ),
                "global_climatology_probability": self.global_climatology.predict_probability(
                    frame
                ),
                "category_climatology_probability": (
                    self.category_climatology.predict_probability(frame)
                ),
            },
            index=frame.index,
        )


def _structured_transformer(
    numeric_features: list[str],
    categorical_features: list[str],
    *,
    dense: bool,
) -> ColumnTransformer:
    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            (
                "onehot",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=not dense,
                ),
            ),
        ]
    )
    transformers: list[tuple[str, Any, Any]] = []
    if numeric_features:
        transformers.append(("numeric", numeric, numeric_features))
    if categorical_features:
        transformers.append(("categorical", categorical, categorical_features))
    return ColumnTransformer(transformers, sparse_threshold=0 if dense else 0.3)


def _features(
    *,
    include_trajectory: bool = True,
    include_category: bool = True,
    include_time: bool = True,
) -> tuple[list[str], list[str]]:
    numeric = list(NUMERIC_FEATURES)
    if not include_trajectory:
        numeric = [feature for feature in numeric if feature not in TRAJECTORY_FEATURES]
    if not include_time:
        numeric = [feature for feature in numeric if feature not in TIME_FEATURES]
    categorical = list(CATEGORICAL_FEATURES) if include_category else []
    return numeric, categorical


def candidate_definitions(
    config: ProjectConfig,
    *,
    include_text: bool = True,
    include_trajectory: bool = True,
    include_category: bool = True,
    include_time: bool = True,
) -> list[CandidateDefinition]:
    numeric, categorical = _features(
        include_trajectory=include_trajectory,
        include_category=include_category,
        include_time=include_time,
    )
    candidates: list[CandidateDefinition] = []
    for c_value in config.model.logistic_c_values:

        def make_text(c: float = c_value) -> ProbabilityModel:
            transformers: list[tuple[str, Any, Any]] = [
                (
                    "structured",
                    _structured_transformer(numeric, categorical, dense=False),
                    numeric + categorical,
                )
            ]
            if include_text:
                transformers.append(
                    (
                        "text",
                        TfidfVectorizer(
                            max_features=config.model.text_max_features,
                            min_df=config.model.text_min_document_frequency,
                            ngram_range=(1, 2),
                            strip_accents="unicode",
                        ),
                        "text",
                    )
                )
            preprocessor = ColumnTransformer(transformers)
            estimator = Pipeline(
                [
                    ("features", preprocessor),
                    (
                        "model",
                        LogisticRegression(
                            C=c,
                            max_iter=3000,
                            solver="liblinear",
                            random_state=config.model.random_seed,
                        ),
                    ),
                ]
            )
            return SklearnFrameModel(estimator)

        candidates.append(
            CandidateDefinition(
                name=f"text_logistic_c{c_value:g}",
                family="text_logistic",
                factory=make_text,
            )
        )

        def make_residual(c: float = c_value) -> ProbabilityModel:
            return MarketResidualModel(
                numeric,
                categorical,
                l2=1 / c,
                probability_clip=config.model.probability_clip,
            )

        candidates.append(
            CandidateDefinition(
                name=f"market_residual_c{c_value:g}",
                family="market_residual",
                factory=make_residual,
            )
        )

    def make_boosting() -> ProbabilityModel:
        estimator = Pipeline(
            [
                ("features", _structured_transformer(numeric, categorical, dense=True)),
                (
                    "model",
                    HistGradientBoostingClassifier(
                        learning_rate=0.05,
                        max_iter=250,
                        max_leaf_nodes=15,
                        l2_regularization=1.0,
                        random_state=config.model.random_seed,
                    ),
                ),
            ]
        )
        return SklearnFrameModel(estimator)

    candidates.append(
        CandidateDefinition(
            name="structured_boosting",
            family="structured_boosting",
            factory=make_boosting,
        )
    )
    return candidates


def _event_weighted_brier(
    frame: pd.DataFrame,
    probability: np.ndarray,
) -> float:
    scored = pd.DataFrame(
        {
            "event_group_id": frame["event_group_id"].astype(str).to_numpy(),
            "loss": (probability - frame["label"].to_numpy(dtype=float)) ** 2,
        }
    )
    return float(scored.groupby("event_group_id")["loss"].mean().mean())


def _positive_probability(
    model: ProbabilityModel,
    frame: pd.DataFrame,
    clip: float,
) -> np.ndarray:
    probability = np.asarray(model.predict_proba(frame), dtype=float)[:, 1]
    return np.asarray(np.clip(probability, clip, 1 - clip), dtype=float)


def _fit_candidate(
    definition: CandidateDefinition,
    train: pd.DataFrame,
) -> ProbabilityModel:
    y = train["label"].to_numpy(dtype=int)
    if len(np.unique(y)) < 2:
        return ConstantModel((float(y.sum()) + 1) / (len(y) + 2))
    return definition.factory().fit(train, y)


def develop_models(
    cohort: pd.DataFrame,
    splits: SplitPlan,
    config: ProjectConfig,
) -> DevelopmentResult:
    """Cross-fit all candidates and lock one system using development data only."""
    definitions = candidate_definitions(config)
    prediction_rows: list[dict[str, Any]] = []
    for definition in definitions:
        for fold in splits.folds:
            train = cohort.iloc[fold.train_indices]
            validation = cohort.iloc[fold.validation_indices]
            model = _fit_candidate(definition, train)
            probability = _positive_probability(
                model,
                validation,
                config.model.probability_clip,
            )
            prediction_rows.extend(
                {
                    "candidate": definition.name,
                    "family": definition.family,
                    "fold": fold.fold,
                    "row_index": int(index),
                    "event_group_id": str(validation.loc[index, "event_group_id"]),
                    "label": int(validation.loc[index, "label"]),
                    "probability": float(value),
                }
                for index, value in zip(validation.index, probability, strict=True)
            )
    oof = pd.DataFrame(prediction_rows)
    if oof.empty:
        raise ValueError("No out-of-fold predictions were produced")
    scores: list[dict[str, Any]] = []
    for (candidate, family), group in oof.groupby(["candidate", "family"]):
        loss = (group["probability"] - group["label"]) ** 2
        event_brier = group.assign(loss=loss).groupby("event_group_id")["loss"].mean().mean()
        scores.append(
            {
                "candidate": candidate,
                "family": family,
                "event_weighted_brier": float(event_brier),
                "log_loss": float(
                    log_loss(
                        group["label"],
                        group["probability"],
                        labels=[0, 1],
                    )
                ),
                "observations": int(len(group)),
                "event_groups": int(group["event_group_id"].nunique()),
            }
        )
    scoreboard = pd.DataFrame(scores).sort_values(["event_weighted_brier", "candidate"])

    best_by_family = (
        scoreboard.sort_values("event_weighted_brier")
        .drop_duplicates("family")
        .set_index("family")["candidate"]
        .to_dict()
    )
    component_names = sorted(str(value) for value in best_by_family.values())
    component_scores = scoreboard.set_index("candidate").loc[
        component_names, "event_weighted_brier"
    ]
    inverse = 1 / np.maximum(component_scores.to_numpy(dtype=float), 1e-9)
    weights = {
        name: float(weight)
        for name, weight in zip(component_names, inverse / inverse.sum(), strict=True)
    }
    pivot = oof.loc[oof["candidate"].isin(component_names)].pivot_table(
        index=["row_index", "event_group_id", "label", "fold"],
        columns="candidate",
        values="probability",
    )
    pivot = pivot.dropna(subset=component_names).reset_index()
    if not pivot.empty:
        ensemble_probability = sum(pivot[name] * weights[name] for name in component_names)
        ensemble_loss = (ensemble_probability - pivot["label"]) ** 2
        ensemble_brier = float(
            pivot.assign(loss=ensemble_loss).groupby("event_group_id")["loss"].mean().mean()
        )
        ensemble_row = pd.DataFrame(
            [
                {
                    "candidate": "ensemble",
                    "family": "ensemble",
                    "event_weighted_brier": ensemble_brier,
                    "log_loss": float(
                        log_loss(pivot["label"], ensemble_probability, labels=[0, 1])
                    ),
                    "observations": int(len(pivot)),
                    "event_groups": int(pivot["event_group_id"].nunique()),
                }
            ]
        )
        scoreboard = pd.concat([scoreboard, ensemble_row], ignore_index=True).sort_values(
            ["event_weighted_brier", "candidate"]
        )
        oof = pd.concat(
            [
                oof,
                pd.DataFrame(
                    {
                        "candidate": "ensemble",
                        "family": "ensemble",
                        "fold": pivot["fold"],
                        "row_index": pivot["row_index"],
                        "event_group_id": pivot["event_group_id"],
                        "label": pivot["label"],
                        "probability": ensemble_probability,
                    }
                ),
            ],
            ignore_index=True,
        )
    selected_name = str(scoreboard.iloc[0]["candidate"])
    return DevelopmentResult(
        selected_name=selected_name,
        scoreboard=scoreboard.reset_index(drop=True),
        oof_predictions=oof,
        ensemble_weights=weights,
    )


def train_locked_system(
    cohort: pd.DataFrame,
    splits: SplitPlan,
    development: DevelopmentResult,
    config: ProjectConfig,
) -> LockedSystem:
    train = cohort.iloc[splits.final_train_indices]
    definitions = {item.name: item for item in candidate_definitions(config)}
    if development.selected_name == "ensemble":
        required = sorted(development.ensemble_weights)
    else:
        required = [development.selected_name]
    models = {name: _fit_candidate(definitions[name], train) for name in required}
    y = train["label"].to_numpy(dtype=int)
    global_climatology = ClimatologyModel(
        config.model.category_prior_strength,
        use_category=False,
    ).fit(train, y)
    category_climatology = ClimatologyModel(
        config.model.category_prior_strength,
        use_category=True,
    ).fit(train, y)
    market_calibrator = MarketCalibrator(config.model.probability_clip).fit(train, y)
    return LockedSystem(
        selected_name=development.selected_name,
        models=models,
        weights=development.ensemble_weights,
        global_climatology=global_climatology,
        category_climatology=category_climatology,
        market_calibrator=market_calibrator,
        probability_clip=config.model.probability_clip,
    )


def fit_ablation_predictions(
    train: pd.DataFrame,
    test: pd.DataFrame,
    config: ProjectConfig,
) -> pd.DataFrame:
    """Fit preregistered ablations with one fixed residual specification."""
    settings = {
        "full_residual": {},
        "without_text": {"include_text": False},
        "without_trajectory": {"include_trajectory": False},
        "without_category": {"include_category": False},
        "without_time": {"include_time": False},
    }
    output: dict[str, np.ndarray] = {
        "market_only": test["market_probability"].to_numpy(dtype=float)
    }
    for name, options in settings.items():
        definitions = candidate_definitions(config, **options)
        residuals = [item for item in definitions if item.family == "market_residual"]
        definition = min(
            residuals,
            key=lambda item: abs(float(item.name.rsplit("c", maxsplit=1)[-1]) - 1.0),
        )
        model = _fit_candidate(definition, train)
        output[name] = _positive_probability(model, test, config.model.probability_clip)
    return pd.DataFrame(output, index=test.index)
