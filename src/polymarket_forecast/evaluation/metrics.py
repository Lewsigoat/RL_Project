"""Proper scoring rules and calibration diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def _validated(
    y_true: np.ndarray | pd.Series,
    probability: np.ndarray | pd.Series,
    *,
    clip: float = 1e-6,
) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(probability, dtype=float)
    if y.shape != p.shape:
        raise ValueError("y_true and probability must have the same shape")
    if y.ndim != 1:
        raise ValueError("Inputs must be one-dimensional")
    if not np.isin(y, [0, 1]).all():
        raise ValueError("y_true must be binary")
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("probabilities must be finite and in [0, 1]")
    return y, np.clip(p, clip, 1 - clip)


def brier_score(
    y_true: np.ndarray | pd.Series,
    probability: np.ndarray | pd.Series,
) -> float:
    y, p = _validated(y_true, probability)
    return float(np.mean((p - y) ** 2))


def logarithmic_score(
    y_true: np.ndarray | pd.Series,
    probability: np.ndarray | pd.Series,
    *,
    clip: float = 1e-6,
) -> float:
    y, p = _validated(y_true, probability, clip=clip)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def event_weighted_score(
    frame: pd.DataFrame,
    probability_column: str,
    *,
    score: str = "brier",
) -> float:
    required = {"event_group_id", "label", probability_column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns for event score: {sorted(missing)}")
    working = frame[list(required)].copy()
    if score == "brier":
        working["loss"] = (working[probability_column] - working["label"]) ** 2
    elif score == "log":
        probability = np.clip(working[probability_column], 1e-6, 1 - 1e-6)
        working["loss"] = -(
            working["label"] * np.log(probability)
            + (1 - working["label"]) * np.log(1 - probability)
        )
    else:
        raise ValueError(f"Unknown score: {score}")
    return float(working.groupby("event_group_id")["loss"].mean().mean())


@dataclass(frozen=True)
class CalibrationFit:
    intercept: float
    slope: float
    converged: bool


def calibration_fit(
    y_true: np.ndarray | pd.Series,
    probability: np.ndarray | pd.Series,
    *,
    clip: float = 1e-6,
) -> CalibrationFit:
    y, p = _validated(y_true, probability, clip=clip)
    if len(np.unique(y)) < 2:
        return CalibrationFit(float("nan"), float("nan"), False)
    logit = np.log(p / (1 - p))
    if float(np.ptp(logit)) < 1e-12:
        base_rate = float(np.clip(y.mean(), clip, 1 - clip))
        return CalibrationFit(
            intercept=float(np.log(base_rate / (1 - base_rate))),
            slope=float("nan"),
            converged=False,
        )

    def objective(parameters: np.ndarray) -> tuple[float, np.ndarray]:
        linear = parameters[0] + parameters[1] * logit
        fitted = 1 / (1 + np.exp(-np.clip(linear, -35, 35)))
        loss = float(np.mean(np.logaddexp(0, linear) - y * linear))
        residual = fitted - y
        gradient = np.asarray(
            [
                np.mean(residual),
                np.mean(residual * logit),
            ],
            dtype=float,
        )
        return loss, gradient

    result = minimize(
        objective,
        np.asarray([0.0, 1.0]),
        method="BFGS",
        jac=True,
        options={"maxiter": 1000, "gtol": 1e-8},
    )
    return CalibrationFit(
        intercept=float(result.x[0]),
        slope=float(result.x[1]),
        converged=bool(result.success),
    )


def reliability_table(
    y_true: np.ndarray | pd.Series,
    probability: np.ndarray | pd.Series,
    *,
    bins: int = 10,
) -> pd.DataFrame:
    y, p = _validated(y_true, probability)
    edges = np.linspace(0, 1, bins + 1)
    bin_index = np.clip(np.digitize(p, edges[1:-1], right=False), 0, bins - 1)
    rows: list[dict[str, Any]] = []
    for index in range(bins):
        mask = bin_index == index
        rows.append(
            {
                "bin": index,
                "lower": float(edges[index]),
                "upper": float(edges[index + 1]),
                "count": int(mask.sum()),
                "mean_probability": float(p[mask].mean()) if mask.any() else float("nan"),
                "observed_rate": float(y[mask].mean()) if mask.any() else float("nan"),
            }
        )
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class BrierDecomposition:
    score: float
    reliability: float
    resolution: float
    uncertainty: float
    reconstruction_error: float


def brier_decomposition(
    y_true: np.ndarray | pd.Series,
    probability: np.ndarray | pd.Series,
    *,
    bins: int = 10,
) -> BrierDecomposition:
    y, p = _validated(y_true, probability)
    table = reliability_table(y, p, bins=bins).dropna()
    total = max(int(table["count"].sum()), 1)
    base_rate = float(y.mean())
    weight = table["count"].to_numpy(dtype=float) / total
    mean_probability = table["mean_probability"].to_numpy(dtype=float)
    observed_rate = table["observed_rate"].to_numpy(dtype=float)
    reliability = float(np.sum(weight * (mean_probability - observed_rate) ** 2))
    resolution = float(np.sum(weight * (observed_rate - base_rate) ** 2))
    uncertainty = base_rate * (1 - base_rate)
    score = brier_score(y, p)
    reconstructed = reliability - resolution + uncertainty
    return BrierDecomposition(
        score=score,
        reliability=reliability,
        resolution=resolution,
        uncertainty=uncertainty,
        reconstruction_error=float(score - reconstructed),
    )


def summarize_probabilistic_forecast(
    y_true: np.ndarray | pd.Series,
    probability: np.ndarray | pd.Series,
    *,
    bins: int = 10,
) -> dict[str, Any]:
    y, p = _validated(y_true, probability)
    calibration = calibration_fit(y, p)
    decomposition = brier_decomposition(y, p, bins=bins)
    return {
        "observations": int(len(y)),
        "positive_rate": float(y.mean()),
        "mean_probability": float(p.mean()),
        "calibration_in_the_large": float(p.mean() - y.mean()),
        "sharpness_variance": float(np.var(p)),
        "brier_score": brier_score(y, p),
        "log_loss": logarithmic_score(y, p),
        "calibration": asdict(calibration),
        "brier_decomposition": asdict(decomposition),
    }


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Return Holm-adjusted p-values while preserving hypothesis names."""
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    count = len(ordered)
    adjusted: dict[str, float] = {}
    running_max = 0.0
    for rank, (name, value) in enumerate(ordered):
        candidate = min(1.0, (count - rank) * float(value))
        running_max = max(running_max, candidate)
        adjusted[name] = running_max
    return adjusted
