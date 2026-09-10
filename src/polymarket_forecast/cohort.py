"""Build one leakage-audited observation per market and forecast horizon."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast

import numpy as np
import pandas as pd

from polymarket_forecast.config import ProjectConfig


@dataclass(frozen=True)
class CohortResult:
    cohort: pd.DataFrame
    exclusions: pd.DataFrame


def _as_utc(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    converted = frame.copy()
    for column in columns:
        converted[column] = pd.to_datetime(converted[column], utc=True, errors="coerce")
    return converted


def _text_fingerprint(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.casefold()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _price_at_or_before(history: pd.DataFrame, target: pd.Timestamp) -> float:
    eligible = history.loc[history["timestamp"] <= target, "price"]
    return float(eligible.iloc[-1]) if not eligible.empty else float("nan")


def _trajectory_features(history: pd.DataFrame, cutoff: pd.Timestamp) -> dict[str, float]:
    recent = history.loc[
        (history["timestamp"] > cutoff - pd.Timedelta(days=7)) & (history["timestamp"] <= cutoff)
    ]
    prices = recent["price"].astype(float)
    last_price = float(prices.iloc[-1])
    clipped = np.clip(last_price, 1e-6, 1 - 1e-6)
    return {
        "market_probability": last_price,
        "market_logit": float(np.log(clipped / (1 - clipped))),
        "price_return_24h": last_price
        - _price_at_or_before(history, cutoff - pd.Timedelta(days=1)),
        "price_return_7d": last_price - _price_at_or_before(history, cutoff - pd.Timedelta(days=7)),
        "price_mean_7d": float(prices.mean()),
        "price_std_7d": float(prices.std(ddof=0)),
        "price_min_7d": float(prices.min()),
        "price_max_7d": float(prices.max()),
        "history_points_7d": float(len(recent)),
    }


def build_cohort(
    markets: pd.DataFrame,
    price_points: pd.DataFrame,
    config: ProjectConfig,
) -> CohortResult:
    """Construct all preregistered market-horizon rows using past-only prices."""
    required_markets = {
        "market_id",
        "event_id",
        "question",
        "description",
        "category",
        "created_at",
        "event_time",
        "closed_time",
        "label",
        "label_source",
        "neg_risk",
    }
    required_prices = {"market_id", "timestamp", "price"}
    missing_markets = required_markets.difference(markets.columns)
    missing_prices = required_prices.difference(price_points.columns)
    if missing_markets:
        raise ValueError(f"markets is missing columns: {sorted(missing_markets)}")
    if missing_prices:
        raise ValueError(f"price_points is missing columns: {sorted(missing_prices)}")

    clean_markets = _as_utc(markets, ("created_at", "event_time", "closed_time"))
    clean_prices = _as_utc(price_points, ("timestamp",))
    clean_prices = clean_prices.dropna(subset=["timestamp", "price"]).copy()
    clean_prices["price"] = pd.to_numeric(clean_prices["price"], errors="coerce")
    clean_prices = clean_prices.loc[clean_prices["price"].between(0, 1)]
    clean_prices = clean_prices.sort_values(["market_id", "timestamp"]).drop_duplicates(
        ["market_id", "timestamp"],
        keep="last",
    )

    rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    grouped_prices = {
        str(market_id): group.reset_index(drop=True)
        for market_id, group in clean_prices.groupby("market_id", sort=False)
    }
    max_staleness = pd.Timedelta(hours=config.study.max_price_staleness_hours)

    for raw_market in clean_markets.itertuples(index=False):
        market = cast(Any, raw_market)
        market_id = str(market.market_id)
        history = grouped_prices.get(market_id)
        for horizon_days in config.study.horizons_days:
            reason = ""
            cutoff = pd.Timestamp(market.event_time) - pd.Timedelta(days=horizon_days)
            if pd.isna(cutoff) or pd.isna(market.created_at) or pd.isna(market.closed_time):
                reason = "missing_time"
            elif cutoff < pd.Timestamp(market.created_at):
                reason = "created_after_forecast_cutoff"
            elif cutoff >= pd.Timestamp(market.closed_time):
                reason = "resolved_before_forecast_cutoff"
            elif history is None or history.empty:
                reason = "no_price_history"

            eligible = pd.DataFrame()
            if not reason and history is not None:
                eligible = history.loc[history["timestamp"] <= cutoff]
                if eligible.empty:
                    reason = "no_price_before_forecast_cutoff"

            if not reason:
                last = eligible.iloc[-1]
                age = cutoff - pd.Timestamp(last["timestamp"])
                if age < pd.Timedelta(0):
                    reason = "future_price_detected"
                elif age > max_staleness:
                    reason = "stale_price"

            if reason:
                exclusions.append(
                    {
                        "market_id": market_id,
                        "event_id": str(market.event_id),
                        "horizon_days": horizon_days,
                        "reason": reason,
                    }
                )
                continue

            trajectory = _trajectory_features(eligible, cutoff)
            question = str(market.question or "")
            description = str(market.description or "")
            event_group_id = str(market.event_id or market_id)
            rows.append(
                {
                    "market_id": market_id,
                    "event_id": str(market.event_id),
                    "event_group_id": event_group_id,
                    "question_fingerprint": _text_fingerprint(question),
                    "horizon_days": horizon_days,
                    "forecast_cutoff": cutoff,
                    "price_timestamp": pd.Timestamp(eligible.iloc[-1]["timestamp"]),
                    "price_age_hours": float(
                        (cutoff - pd.Timestamp(eligible.iloc[-1]["timestamp"])).total_seconds()
                        / 3600
                    ),
                    **trajectory,
                    "contract_age_days": float(
                        (cutoff - pd.Timestamp(market.created_at)).total_seconds() / 86400
                    ),
                    "time_to_event_days": float(horizon_days),
                    "question_length": float(len(question)),
                    "description_length": float(len(description)),
                    "text": f"{question} {description}".strip(),
                    "category": str(market.category or "unknown"),
                    "neg_risk": bool(market.neg_risk),
                    "label": int(market.label),
                    "label_source": str(market.label_source),
                    "created_at": pd.Timestamp(market.created_at),
                    "event_time": pd.Timestamp(market.event_time),
                    "closed_time": pd.Timestamp(market.closed_time),
                }
            )

    cohort = pd.DataFrame(rows)
    if not cohort.empty:
        cohort = cohort.sort_values(
            ["forecast_cutoff", "event_group_id", "market_id", "horizon_days"]
        ).reset_index(drop=True)
    exclusion_frame = pd.DataFrame(
        exclusions,
        columns=["market_id", "event_id", "horizon_days", "reason"],
    )
    audit_cohort(cohort, config)
    return CohortResult(cohort=cohort, exclusions=exclusion_frame)


def audit_cohort(cohort: pd.DataFrame, config: ProjectConfig) -> None:
    """Raise when a cohort violates a preregistered temporal invariant."""
    if cohort.empty:
        return
    duplicates = cohort.duplicated(["market_id", "horizon_days"])
    if duplicates.any():
        raise AssertionError("Cohort contains duplicate market-horizon observations")
    if (cohort["price_timestamp"] > cohort["forecast_cutoff"]).any():
        raise AssertionError("Cohort contains a price from after the forecast cutoff")
    if (cohort["created_at"] > cohort["forecast_cutoff"]).any():
        raise AssertionError("Cohort contains a contract created after its cutoff")
    if (cohort["closed_time"] <= cohort["forecast_cutoff"]).any():
        raise AssertionError("Cohort contains a contract resolved before its cutoff")
    maximum_age = timedelta(hours=config.study.max_price_staleness_hours)
    ages = cohort["forecast_cutoff"] - cohort["price_timestamp"]
    if (ages > maximum_age).any() or (ages < timedelta(0)).any():
        raise AssertionError("Cohort contains a stale or future price")
    forbidden = {"final_volume", "final_liquidity", "outcomePrices", "winner"}
    leaked = forbidden.intersection(cohort.columns)
    if leaked:
        raise AssertionError(f"Forbidden terminal fields in cohort: {sorted(leaked)}")
