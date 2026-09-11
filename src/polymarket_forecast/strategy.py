"""Edge-threshold binary contract strategy and cash accounting.

The strategy buys YES when the model probability exceeds the cost-adjusted ask
and buys NO when the complement does. Stake is a capped fractional Kelly
fraction of current equity. This module does not claim live fill quality; it
prices entry at mid plus half-spread and a taker fee on cash spent.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

SIGNAL_COLUMNS = (
    "yes_ask",
    "no_ask",
    "edge_yes",
    "edge_no",
    "side",
    "entry_ask",
    "win_probability",
    "edge",
    "full_kelly",
    "stake_fraction",
    "signal",
    "favorite_side",
    "favorite_ask",
    "favorite_tradable",
)


@dataclass(frozen=True)
class StrategySpec:
    min_edge: float
    kelly_fraction: float
    max_stake_fraction: float
    half_spread: float
    taker_fee_rate: float
    price_clip: float
    min_tradable_price: float
    max_tradable_price: float
    starting_bankroll: float
    unit_stake: float
    assumed_horizon_days: int
    probability_column: str

    def __post_init__(self) -> None:
        if self.min_edge < 0:
            raise ValueError("min_edge must be non-negative")
        if not 0 < self.kelly_fraction <= 1:
            raise ValueError("kelly_fraction must be in (0, 1]")
        if not 0 < self.max_stake_fraction <= 1:
            raise ValueError("max_stake_fraction must be in (0, 1]")
        if self.half_spread < 0 or self.taker_fee_rate < 0:
            raise ValueError("trading costs must be non-negative")
        if not 0 < self.price_clip < 0.5:
            raise ValueError("price_clip must be in (0, 0.5)")
        if not 0 < self.min_tradable_price < self.max_tradable_price < 1:
            raise ValueError("tradable price bounds are invalid")
        if self.starting_bankroll <= 0 or self.unit_stake <= 0:
            raise ValueError("bankroll and unit_stake must be positive")
        if self.assumed_horizon_days < 1:
            raise ValueError("assumed_horizon_days must be positive")


@dataclass(frozen=True)
class StrategyGrid:
    min_edge: tuple[float, ...]
    kelly_fraction: tuple[float, ...]
    max_stake_fraction: tuple[float, ...]


@dataclass(frozen=True)
class StrategyInferenceConfig:
    bootstrap_repetitions: int
    block_length_weeks: int
    alpha: float
    seed: int


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    spec: StrategySpec
    grid: StrategyGrid
    inference: StrategyInferenceConfig
    selection_minimum_trades: int
    cost_half_spreads: tuple[float, ...]
    cost_taker_fee_rates: tuple[float, ...]
    source_path: Path

    def candidates(self) -> tuple[StrategySpec, ...]:
        specs = [
            replace(
                self.spec,
                min_edge=min_edge,
                kelly_fraction=kelly_fraction,
                max_stake_fraction=max_stake_fraction,
            )
            for min_edge in self.grid.min_edge
            for kelly_fraction in self.grid.kelly_fraction
            for max_stake_fraction in self.grid.max_stake_fraction
        ]
        return tuple(specs)


def _require_mapping(payload: Any, name: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError(f"{name} must be a mapping")
    return {str(key): value for key, value in payload.items()}


def load_strategy_config(path: str | Path = "configs/strategy.yaml") -> StrategyConfig:
    """Load the economic-simulation configuration."""
    source = Path(path).resolve()
    with source.open(encoding="utf-8") as handle:
        raw = _require_mapping(yaml.safe_load(handle), "strategy configuration")
    grid_raw = _require_mapping(raw["grid"], "grid")
    inference_raw = _require_mapping(raw["inference"], "inference")
    costs_raw = _require_mapping(raw.get("cost_sensitivity", {}), "cost_sensitivity")
    spec = StrategySpec(
        min_edge=float(grid_raw["min_edge"][0]),
        kelly_fraction=float(grid_raw["kelly_fraction"][0]),
        max_stake_fraction=float(grid_raw["max_stake_fraction"][0]),
        half_spread=float(raw["half_spread"]),
        taker_fee_rate=float(raw["taker_fee_rate"]),
        price_clip=float(raw["price_clip"]),
        min_tradable_price=float(raw["min_tradable_price"]),
        max_tradable_price=float(raw["max_tradable_price"]),
        starting_bankroll=float(raw["starting_bankroll"]),
        unit_stake=float(raw["unit_stake"]),
        assumed_horizon_days=int(raw["assumed_horizon_days"]),
        probability_column=str(raw.get("probability_column", "model_probability")),
    )
    return StrategyConfig(
        name=str(raw["name"]),
        spec=spec,
        grid=StrategyGrid(
            min_edge=tuple(float(item) for item in grid_raw["min_edge"]),
            kelly_fraction=tuple(float(item) for item in grid_raw["kelly_fraction"]),
            max_stake_fraction=tuple(float(item) for item in grid_raw["max_stake_fraction"]),
        ),
        inference=StrategyInferenceConfig(
            bootstrap_repetitions=int(inference_raw["bootstrap_repetitions"]),
            block_length_weeks=int(inference_raw["block_length_weeks"]),
            alpha=float(inference_raw["alpha"]),
            seed=int(inference_raw["seed"]),
        ),
        selection_minimum_trades=int(raw["selection_minimum_trades"]),
        cost_half_spreads=tuple(
            float(item) for item in costs_raw.get("half_spreads", [spec.half_spread])
        ),
        cost_taker_fee_rates=tuple(
            float(item) for item in costs_raw.get("taker_fee_rates", [spec.taker_fee_rate])
        ),
        source_path=source,
    )


def kelly_fraction_of_wealth(win_probability: float, entry_price: float) -> float:
    """Full-Kelly cash fraction for a binary contract bought at ``entry_price``.

    A stake ``s`` buys ``s / entry`` shares that pay 1 if the chosen side wins.
    The payout odds are ``(1 - entry) / entry``, so
    ``f* = (p - entry) / (1 - entry)``.
    """
    if not 0 < entry_price < 1:
        return 0.0
    edge = win_probability - entry_price
    if edge <= 0:
        return 0.0
    return float(edge / (1.0 - entry_price))


def clip_probability(value: Any, clip: float) -> np.ndarray:
    clipped = np.clip(np.asarray(value, dtype=float), clip, 1.0 - clip)
    return np.asarray(clipped, dtype=float)


def shares_for_stake(stake: Any, ask: Any, fee_rate: float) -> np.ndarray:
    """Convert cash, including the taker fee, into contract shares."""
    stake_array = np.asarray(stake, dtype=float)
    ask_array = np.asarray(ask, dtype=float)
    denominator = ask_array * (1.0 + fee_rate)
    shares = np.zeros_like(stake_array, dtype=float)
    valid = (stake_array > 0) & (denominator > 0)
    shares[valid] = stake_array[valid] / denominator[valid]
    return np.asarray(shares, dtype=float)


def cash_outlay(shares: Any, ask: Any, fee_rate: float) -> np.ndarray:
    return np.asarray(
        np.asarray(shares, dtype=float) * np.asarray(ask, dtype=float) * (1.0 + fee_rate),
        dtype=float,
    )


def realized_pnl(
    side: Any,
    label: Any,
    shares: Any,
    ask: Any,
    fee_rate: float,
) -> np.ndarray:
    """Profit after paying ask and the taker fee. ``side`` is +1 YES or -1 NO."""
    side_array = np.asarray(side, dtype=float)
    label_array = np.asarray(label, dtype=float)
    share_array = np.asarray(shares, dtype=float)
    won = np.where(side_array > 0, label_array >= 0.5, label_array < 0.5)
    payoff = share_array * won.astype(float)
    return np.asarray(payoff - cash_outlay(share_array, ask, fee_rate), dtype=float)


def build_signals(predictions: pd.DataFrame, spec: StrategySpec) -> pd.DataFrame:
    """Attach cost-adjusted edges, sides, and Kelly fractions to each contract."""
    required = {
        "market_id",
        "event_group_id",
        "forecast_cutoff",
        "label",
        "market_probability",
        spec.probability_column,
    }
    missing = required.difference(predictions.columns)
    if missing:
        raise ValueError(f"Predictions missing columns: {sorted(missing)}")

    frame = predictions.copy()
    frame["forecast_cutoff"] = pd.to_datetime(frame["forecast_cutoff"], utc=True)
    horizon = pd.Timedelta(days=spec.assumed_horizon_days)
    if "event_time" in frame.columns:
        frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True)
        missing_event = frame["event_time"].isna()
        if bool(missing_event.any()):
            frame.loc[missing_event, "event_time"] = (
                frame.loc[missing_event, "forecast_cutoff"] + horizon
            )
    else:
        frame["event_time"] = frame["forecast_cutoff"] + horizon

    p_model = frame[spec.probability_column].to_numpy(dtype=float)
    p_market = frame["market_probability"].to_numpy(dtype=float)
    ask_yes = clip_probability(p_market + spec.half_spread, spec.price_clip)
    ask_no = clip_probability(1.0 - p_market + spec.half_spread, spec.price_clip)
    edge_yes = p_model - ask_yes
    edge_no = (1.0 - p_model) - ask_no
    tradable_yes = (ask_yes >= spec.min_tradable_price) & (ask_yes <= spec.max_tradable_price)
    tradable_no = (ask_no >= spec.min_tradable_price) & (ask_no <= spec.max_tradable_price)
    take_yes = (edge_yes >= spec.min_edge) & (edge_yes >= edge_no) & tradable_yes
    take_no = (~take_yes) & (edge_no >= spec.min_edge) & tradable_no
    side = np.where(take_yes, 1, np.where(take_no, -1, 0)).astype(int)
    ask = np.where(side > 0, ask_yes, np.where(side < 0, ask_no, np.nan))
    win_probability = np.where(side > 0, p_model, np.where(side < 0, 1.0 - p_model, np.nan))
    edge = np.where(side > 0, edge_yes, np.where(side < 0, edge_no, np.nan))
    full_kelly = np.zeros(len(frame), dtype=float)
    traded = side != 0
    if bool(traded.any()):
        full_kelly[traded] = [
            kelly_fraction_of_wealth(float(probability), float(price))
            for probability, price in zip(win_probability[traded], ask[traded], strict=True)
        ]
    favorite_yes = p_market >= 0.5
    favorite_side = np.where(favorite_yes, 1, -1).astype(int)
    favorite_ask = np.where(favorite_yes, ask_yes, ask_no)
    favorite_tradable = np.where(favorite_yes, tradable_yes, tradable_no)

    frame["yes_ask"] = ask_yes
    frame["no_ask"] = ask_no
    frame["edge_yes"] = edge_yes
    frame["edge_no"] = edge_no
    frame["side"] = side
    frame["entry_ask"] = ask
    frame["win_probability"] = win_probability
    frame["edge"] = edge
    frame["full_kelly"] = full_kelly
    frame["stake_fraction"] = np.clip(
        spec.kelly_fraction * full_kelly,
        0.0,
        spec.max_stake_fraction,
    )
    frame["signal"] = traded
    frame["favorite_side"] = favorite_side
    frame["favorite_ask"] = favorite_ask
    frame["favorite_tradable"] = favorite_tradable
    return frame
