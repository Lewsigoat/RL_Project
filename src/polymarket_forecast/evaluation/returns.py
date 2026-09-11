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


def weekly_equity_returns(equity: pd.DataFrame) -> pd.Series:
    if equity.empty or len(equity) < 3:
        return pd.Series(dtype=float)
    curve = equity.copy()
    curve["timestamp"] = pd.to_datetime(curve["timestamp"], utc=True)
    return (
        curve.set_index("timestamp")["equity"]
        .sort_index()
        .resample("W-SUN")
        .last()
        .dropna()
        .pct_change()
        .dropna()
    )


def weekly_trade_returns(
    trades: pd.DataFrame,
    *,
    pnl_column: str = "strategy_pnl",
) -> pd.Series:
    """Deployed-capital returns by resolution week. Risk-free rate is cash, 0."""
    if trades.empty:
        return pd.Series(dtype=float)
    working = trades.copy()
    time_column = "event_time" if "event_time" in working.columns else "forecast_cutoff"
    working[time_column] = pd.to_datetime(working[time_column], utc=True)
    working["week"] = working[time_column].dt.tz_localize(None).dt.to_period("W-SUN")
    weekly = working.groupby("week", as_index=False).agg(
        pnl=(pnl_column, "sum"),
        deployed=("cash_outlay", "sum"),
    )
    deployed = weekly["deployed"].to_numpy(dtype=float)
    pnl = weekly["pnl"].to_numpy(dtype=float)
    returns = np.divide(pnl, deployed, out=np.zeros(len(weekly), dtype=float), where=deployed > 0)
    return pd.Series(returns, dtype=float)


def sharpe_ratio(returns: pd.Series | np.ndarray, *, periods_per_year: int = 52) -> float:
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 2:
        return float("nan")
    volatility = float(values.std(ddof=1))
    if volatility < 1e-12:
        return float("nan")
    return float(values.mean() / volatility * np.sqrt(periods_per_year))


def sortino_ratio(returns: pd.Series | np.ndarray, *, periods_per_year: int = 52) -> float:
    values = np.asarray(returns, dtype=float)
    values = values[np.isfinite(values)]
    downside = values[values < 0]
    if len(values) < 2 or len(downside) < 1:
        return float("nan")
    downside_vol = float(downside.std(ddof=1))
    if downside_vol < 1e-12:
        return float("nan")
    return float(values.mean() / downside_vol * np.sqrt(periods_per_year))


def annualized_return(compound_return: float, weeks: float) -> float:
    if weeks < 1 or not np.isfinite(compound_return) or compound_return <= -1:
        return float("nan")
    return float((1.0 + compound_return) ** (52.0 / weeks) - 1.0)


def calmar_ratio(compound_return: float, drawdown: float, weeks: float) -> float:
    if not np.isfinite(compound_return) or not np.isfinite(drawdown) or drawdown >= 0:
        return float("nan")
    growth = annualized_return(compound_return, weeks)
    if not np.isfinite(growth):
        return float("nan")
    return float(growth / abs(drawdown))


def weekly_sharpe(equity: pd.DataFrame) -> float:
    return sharpe_ratio(weekly_equity_returns(equity))


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
    strategy_weeks = weekly_trade_returns(trades, pnl_column="strategy_pnl")
    excess_weeks = weekly_trade_returns(trades, pnl_column="excess_pnl")
    summary["weeks"] = int(len(strategy_weeks))
    summary["weekly_sharpe"] = sharpe_ratio(strategy_weeks)
    summary["weekly_sortino"] = sortino_ratio(strategy_weeks)
    summary["information_ratio"] = sharpe_ratio(excess_weeks)
    if equity is not None and not equity.empty and starting_bankroll is not None:
        final_equity = float(equity["equity"].iloc[-1])
        equity_weeks = weekly_equity_returns(equity)
        timestamps = pd.to_datetime(equity["timestamp"], utc=True)
        span_weeks = max(
            float((timestamps.max() - timestamps.min()) / pd.Timedelta(days=7)),
            1.0,
        )
        summary["starting_bankroll"] = starting_bankroll
        summary["final_equity"] = final_equity
        summary["compound_return"] = final_equity / starting_bankroll - 1.0
        summary["max_drawdown"] = max_drawdown(equity["equity"])
        summary["equity_weeks"] = int(len(equity_weeks))
        summary["calendar_weeks"] = span_weeks
        summary["weekly_sharpe"] = sharpe_ratio(equity_weeks)
        summary["weekly_sortino"] = sortino_ratio(equity_weeks)
        summary["annualized_return"] = annualized_return(
            summary["compound_return"],
            span_weeks,
        )
        summary["calmar"] = calmar_ratio(
            summary["compound_return"],
            summary["max_drawdown"],
            span_weeks,
        )
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


def fee_risk_table(
    predictions: pd.DataFrame,
    locked: StrategySpec,
    fees: tuple[float, ...],
) -> pd.DataFrame:
    """Locked-spread fee sweep with unit and compounding risk-adjusted returns."""
    rows: list[dict[str, Any]] = []
    for fee in fees:
        spec = replace(locked, taker_fee_rate=fee)
        signals = build_signals(predictions, spec)
        unit_trades = simulate_unit_book(signals, spec)
        compound_trades, equity = simulate_compounding_book(signals, spec)
        unit = summarize_book(unit_trades)
        compound = summarize_book(
            compound_trades,
            equity=equity,
            starting_bankroll=spec.starting_bankroll,
        )
        rows.append(
            {
                "half_spread": spec.half_spread,
                "taker_fee_rate": fee,
                "unit_trades": unit["trades"],
                "unit_weeks": unit["weeks"],
                "unit_return_on_deployed": unit["return_on_deployed"],
                "unit_weekly_sharpe": unit["weekly_sharpe"],
                "unit_weekly_sortino": unit["weekly_sortino"],
                "unit_information_ratio": unit["information_ratio"],
                "compound_trades": compound["trades"],
                "compound_return": compound.get("compound_return", float("nan")),
                "compound_annualized_return": compound.get("annualized_return", float("nan")),
                "compound_max_drawdown": compound.get("max_drawdown", float("nan")),
                "compound_weekly_sharpe": compound.get("weekly_sharpe", float("nan")),
                "compound_weekly_sortino": compound.get("weekly_sortino", float("nan")),
                "compound_calmar": compound.get("calmar", float("nan")),
            }
        )
    return pd.DataFrame(rows)
