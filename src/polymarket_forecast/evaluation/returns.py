"""Simulate paper-trading PnL and dependence-aware excess-return tests."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

from polymarket_forecast.evaluation.bootstrap import block_bootstrap_means
from polymarket_forecast.strategy import (
    StrategyConfig,
    StrategySpec,
    build_signals,
    cash_outlay,
    realized_pnl,
    shares_for_stake,
)

TRADE_COLUMNS = (
    "market_id",
    "event_group_id",
    "forecast_cutoff",
    "event_time",
    "side",
    "entry_ask",
    "favorite_side",
    "favorite_ask",
    "label",
    "edge",
    "stake",
    "shares",
    "cash_outlay",
    "strategy_pnl",
    "favorite_pnl",
    "excess_pnl",
    "return_on_stake",
    "book",
)


@dataclass(frozen=True)
class ReturnTest:
    metric: str
    mean: float
    p_value_one_sided: float
    lower_bound_one_sided_95: float
    confidence_interval_two_sided_95: tuple[float, float]
    superior_at_alpha: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_float(value: np.ndarray | float) -> float:
    return float(np.asarray(value, dtype=float).reshape(-1)[0])


def _finalize_trades(trades: pd.DataFrame, spec: StrategySpec, book: str) -> pd.DataFrame:
    if trades.empty:
        empty = pd.DataFrame(columns=list(TRADE_COLUMNS))
        empty["book"] = pd.Series(dtype=str)
        return empty
    working = trades.copy()
    working["shares"] = shares_for_stake(
        working["stake"],
        working["entry_ask"],
        spec.taker_fee_rate,
    )
    working["cash_outlay"] = cash_outlay(
        working["shares"],
        working["entry_ask"],
        spec.taker_fee_rate,
    )
    working["strategy_pnl"] = realized_pnl(
        working["side"],
        working["label"],
        working["shares"],
        working["entry_ask"],
        spec.taker_fee_rate,
    )
    favorite_shares = shares_for_stake(
        working["stake"],
        working["favorite_ask"],
        spec.taker_fee_rate,
    )
    working["favorite_pnl"] = realized_pnl(
        working["favorite_side"],
        working["label"],
        favorite_shares,
        working["favorite_ask"],
        spec.taker_fee_rate,
    )
    working["excess_pnl"] = working["strategy_pnl"] - working["favorite_pnl"]
    working["return_on_stake"] = np.divide(
        working["strategy_pnl"],
        working["cash_outlay"],
        out=np.zeros(len(working), dtype=float),
        where=working["cash_outlay"].to_numpy(dtype=float) > 0,
    )
    working["book"] = book
    return working.loc[:, list(TRADE_COLUMNS)].reset_index(drop=True)


def simulate_unit_book(signals: pd.DataFrame, spec: StrategySpec) -> pd.DataFrame:
    """Independent fixed-stake book used for selection and expected-value tests."""
    selected = signals.loc[signals["signal"]].copy()
    if selected.empty:
        return _finalize_trades(selected, spec, "unit")
    selected["stake"] = spec.unit_stake
    return _finalize_trades(selected, spec, "unit")


def simulate_compounding_book(
    signals: pd.DataFrame,
    spec: StrategySpec,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reserved-capital compounding book with no spending of locked cash."""
    working = signals.sort_values(["forecast_cutoff", "market_id", "event_group_id"]).reset_index(
        drop=True
    )
    events: list[tuple[pd.Timestamp, int, int]] = []
    for index in range(len(working)):
        row = working.iloc[index]
        if not bool(row["signal"]):
            continue
        cutoff = pd.Timestamp(row["forecast_cutoff"])
        resolve_at = pd.Timestamp(row["event_time"])
        events.append((cutoff, 1, index))
        events.append((resolve_at, 0, index))
    events.sort(key=lambda item: (item[0], item[1], item[2]))

    cash = float(spec.starting_bankroll)
    reserved = 0.0
    open_positions: dict[int, dict[str, float]] = {}
    accepted: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = [
        {
            "timestamp": (
                pd.Timestamp(working["forecast_cutoff"].min())
                if not working.empty
                else pd.Timestamp(0, tz="UTC")
            ),
            "cash": cash,
            "reserved": reserved,
            "equity": cash,
        }
    ]

    for timestamp, kind, index in events:
        row = working.iloc[index]
        if kind == 1:
            marked_equity = cash + reserved
            desired = min(float(marked_equity * row["stake_fraction"]), cash)
            if desired <= 0:
                continue
            shares = _as_float(
                shares_for_stake(desired, float(row["entry_ask"]), spec.taker_fee_rate)
            )
            outlay = _as_float(cash_outlay(shares, float(row["entry_ask"]), spec.taker_fee_rate))
            if outlay <= 0 or outlay > cash + 1e-9:
                continue
            cash -= outlay
            reserved += outlay
            open_positions[index] = {"stake": outlay, "shares": shares, "outlay": outlay}
            accepted.append(
                {
                    "market_id": row["market_id"],
                    "event_group_id": row["event_group_id"],
                    "forecast_cutoff": row["forecast_cutoff"],
                    "event_time": row["event_time"],
                    "side": int(row["side"]),
                    "entry_ask": float(row["entry_ask"]),
                    "favorite_side": int(row["favorite_side"]),
                    "favorite_ask": float(row["favorite_ask"]),
                    "label": int(row["label"]),
                    "edge": float(row["edge"]),
                    "stake": outlay,
                }
            )
        else:
            position = open_positions.pop(index, None)
            if position is None:
                continue
            payoff = (
                _as_float(
                    realized_pnl(
                        int(row["side"]),
                        int(row["label"]),
                        position["shares"],
                        float(row["entry_ask"]),
                        spec.taker_fee_rate,
                    )
                )
                + position["outlay"]
            )
            cash += payoff
            reserved -= position["outlay"]
        equity_rows.append(
            {
                "timestamp": timestamp,
                "cash": cash,
                "reserved": reserved,
                "equity": cash + reserved,
            }
        )

    trades = _finalize_trades(pd.DataFrame(accepted), spec, "compounding")
    equity_frame = pd.DataFrame(equity_rows).sort_values("timestamp").reset_index(drop=True)
    return trades, equity_frame


def event_return_table(trades: pd.DataFrame) -> pd.DataFrame:
    """Collapse contract PnL to one row per event group for block inference."""
    if trades.empty:
        return pd.DataFrame(
            columns=[
                "event_group_id",
                "forecast_cutoff",
                "strategy_pnl",
                "favorite_pnl",
                "excess_pnl",
                "trades",
                "cash_outlay",
                "week",
            ]
        )
    working = trades.copy()
    working["forecast_cutoff"] = pd.to_datetime(working["forecast_cutoff"], utc=True)
    event = (
        working.groupby("event_group_id", as_index=False)
        .agg(
            forecast_cutoff=("forecast_cutoff", "min"),
            strategy_pnl=("strategy_pnl", "sum"),
            favorite_pnl=("favorite_pnl", "sum"),
            excess_pnl=("excess_pnl", "sum"),
            trades=("strategy_pnl", "size"),
            cash_outlay=("cash_outlay", "sum"),
        )
        .sort_values(["forecast_cutoff", "event_group_id"])
        .reset_index(drop=True)
    )
    event["week"] = event["forecast_cutoff"].dt.tz_localize(None).dt.to_period("W-SUN").astype(str)
    return event


def mean_return_test(
    event_returns: pd.DataFrame,
    column: str,
    *,
    repetitions: int,
    block_length_weeks: int,
    seed: int,
    alpha: float,
) -> ReturnTest:
    """One-sided block-bootstrap test that the mean event return exceeds zero."""
    if event_returns.empty or event_returns["week"].nunique() < 2:
        return ReturnTest(
            metric=column,
            mean=float("nan"),
            p_value_one_sided=1.0,
            lower_bound_one_sided_95=float("nan"),
            confidence_interval_two_sided_95=(float("nan"), float("nan")),
            superior_at_alpha=False,
        )
    observed = float(event_returns[column].mean())
    centered = block_bootstrap_means(
        event_returns,
        [column],
        repetitions=repetitions,
        block_length_weeks=block_length_weeks,
        seed=seed,
        center=True,
    )
    uncentered = block_bootstrap_means(
        event_returns,
        [column],
        repetitions=repetitions,
        block_length_weeks=block_length_weeks,
        seed=seed + 1,
        center=False,
    )
    p_value = float((1 + int(np.count_nonzero(centered[:, 0] >= observed))) / (repetitions + 1))
    lower = float(np.quantile(uncentered[:, 0], alpha))
    interval = (
        float(np.quantile(uncentered[:, 0], alpha / 2)),
        float(np.quantile(uncentered[:, 0], 1 - alpha / 2)),
    )
    return ReturnTest(
        metric=column,
        mean=observed,
        p_value_one_sided=p_value,
        lower_bound_one_sided_95=lower,
        confidence_interval_two_sided_95=interval,
        superior_at_alpha=bool(p_value < alpha and lower > 0),
    )


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    peak = equity.cummax()
    drawdown = equity.to_numpy(dtype=float) / np.clip(peak.to_numpy(dtype=float), 1e-12, None) - 1.0
    return float(drawdown.min())


def weekly_sharpe(equity: pd.DataFrame) -> float:
    if equity.empty or len(equity) < 3:
        return float("nan")
    curve = equity.copy()
    curve["timestamp"] = pd.to_datetime(curve["timestamp"], utc=True)
    weekly = (
        curve.set_index("timestamp")["equity"]
        .sort_index()
        .resample("W-SUN")
        .last()
        .dropna()
        .pct_change()
        .dropna()
    )
    if len(weekly) < 2 or float(weekly.std(ddof=1)) == 0:
        return float("nan")
    return float(weekly.mean() / weekly.std(ddof=1) * np.sqrt(52))


def summarize_book(
    trades: pd.DataFrame,
    *,
    equity: pd.DataFrame | None = None,
    starting_bankroll: float | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "trades": int(len(trades)),
        "event_groups": int(trades["event_group_id"].nunique()) if not trades.empty else 0,
        "hit_rate": (
            float((trades["strategy_pnl"] > 0).mean()) if not trades.empty else float("nan")
        ),
        "total_strategy_pnl": float(trades["strategy_pnl"].sum()) if not trades.empty else 0.0,
        "total_favorite_pnl": float(trades["favorite_pnl"].sum()) if not trades.empty else 0.0,
        "total_excess_pnl": float(trades["excess_pnl"].sum()) if not trades.empty else 0.0,
        "mean_strategy_pnl": (
            float(trades["strategy_pnl"].mean()) if not trades.empty else float("nan")
        ),
        "mean_excess_pnl": (
            float(trades["excess_pnl"].mean()) if not trades.empty else float("nan")
        ),
        "deployed_capital": float(trades["cash_outlay"].sum()) if not trades.empty else 0.0,
        "return_on_deployed": float("nan"),
        "long_yes_share": float((trades["side"] > 0).mean()) if not trades.empty else float("nan"),
    }
    if summary["deployed_capital"] > 0:
        summary["return_on_deployed"] = (
            summary["total_strategy_pnl"] / summary["deployed_capital"]
        )
    if equity is not None and not equity.empty and starting_bankroll is not None:
        final_equity = float(equity["equity"].iloc[-1])
        summary["starting_bankroll"] = starting_bankroll
        summary["final_equity"] = final_equity
        summary["compound_return"] = final_equity / starting_bankroll - 1.0
        summary["max_drawdown"] = max_drawdown(equity["equity"])
        summary["weekly_sharpe"] = weekly_sharpe(equity)
    return summary


def select_strategy(
    development: pd.DataFrame,
    config: StrategyConfig,
) -> tuple[StrategySpec, pd.DataFrame]:
    """Lock hyperparameters on development OOF using the unit-stake book only."""
    rows: list[dict[str, Any]] = []
    best_spec = config.spec
    best_score = float("-inf")
    for spec in config.candidates():
        signals = build_signals(development, spec)
        trades = simulate_unit_book(signals, spec)
        events = event_return_table(trades)
        score = float("-inf")
        if len(trades) >= config.selection_minimum_trades and events["week"].nunique() >= 2:
            score = float(events["strategy_pnl"].mean())
        rows.append(
            {
                "min_edge": spec.min_edge,
                "kelly_fraction": spec.kelly_fraction,
                "max_stake_fraction": spec.max_stake_fraction,
                "trades": int(len(trades)),
                "event_groups": int(events["event_group_id"].nunique()) if not events.empty else 0,
                "weeks": int(events["week"].nunique()) if not events.empty else 0,
                "mean_event_pnl": score if np.isfinite(score) else float("nan"),
                "total_pnl": float(trades["strategy_pnl"].sum()) if not trades.empty else 0.0,
                "selected": False,
            }
        )
        if score > best_score:
            best_score = score
            best_spec = spec
    scoreboard = pd.DataFrame(rows)
    if best_score == float("-inf"):
        raise RuntimeError("No strategy candidate met the OOF trade and week minima")
    selected = (
        (scoreboard["min_edge"] == best_spec.min_edge)
        & (scoreboard["kelly_fraction"] == best_spec.kelly_fraction)
        & (scoreboard["max_stake_fraction"] == best_spec.max_stake_fraction)
    )
    scoreboard.loc[selected, "selected"] = True
    return best_spec, scoreboard


def cost_sensitivity_table(
    predictions: pd.DataFrame,
    locked: StrategySpec,
    config: StrategyConfig,
) -> pd.DataFrame:
    """Holdout robustness over documented cost assumptions. Not used for selection."""
    rows: list[dict[str, Any]] = []
    for half_spread in config.cost_half_spreads:
        for fee in config.cost_taker_fee_rates:
            spec = replace(locked, half_spread=half_spread, taker_fee_rate=fee)
            trades = simulate_unit_book(build_signals(predictions, spec), spec)
            summary = summarize_book(trades)
            rows.append(
                {
                    "half_spread": half_spread,
                    "taker_fee_rate": fee,
                    **summary,
                }
            )
    return pd.DataFrame(rows)
