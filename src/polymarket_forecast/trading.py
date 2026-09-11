"""Run the OOF-locked excess-return simulation on a completed study run."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Any

from polymarket_forecast.config import ProjectConfig
from polymarket_forecast.data.storage import ResearchStorage
from polymarket_forecast.evaluation.returns import (
    cost_sensitivity_table,
    event_return_table,
    mean_return_test,
    select_strategy,
    simulate_compounding_book,
    simulate_unit_book,
    summarize_book,
)
from polymarket_forecast.pipeline import _latest_study_run
from polymarket_forecast.strategy import StrategyConfig, StrategySpec, build_signals


@dataclass(frozen=True)
class ReturnSimulationSummary:
    study_run_id: str
    data_run_id: str
    selected_model: str
    locked_min_edge: float
    locked_kelly_fraction: float
    locked_max_stake_fraction: float
    holdout_unit_trades: int
    holdout_unit_return_on_deployed: float
    holdout_compound_return: float
    strategy_pnl_p_value: float
    excess_pnl_p_value: float
    superior_to_cash: bool
    superior_to_favorite: bool


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _spec_dict(spec: StrategySpec) -> dict[str, Any]:
    return asdict(spec)


def simulate_study_returns(
    config: ProjectConfig,
    strategy: StrategyConfig,
    *,
    study_run_id: str | None = None,
    destination: str | Path = "reports/results",
) -> ReturnSimulationSummary:
    """Lock the strategy on development OOF, then simulate the holdout once."""
    artifact_storage = ResearchStorage(config.paths.artifacts_uri)
    report_storage = ResearchStorage(config.paths.reports_uri)
    resolved_study_run = study_run_id or _latest_study_run(artifact_storage)
    pointer = artifact_storage.read_json("latest.json")
    if not isinstance(pointer, dict):
        raise ValueError("artifacts/latest.json is missing")
    data_run_id = str(pointer["data_run_id"])
    training = artifact_storage.read_json(f"runs/{resolved_study_run}/training_summary.json")
    if not isinstance(training, dict):
        raise ValueError("training summary is missing")
    development = artifact_storage.read_parquet(
        f"runs/{resolved_study_run}/development_oof.parquet"
    )
    holdout = report_storage.read_parquet(f"{resolved_study_run}/holdout_predictions.parquet")

    locked, scoreboard = select_strategy(development, strategy)
    oof_unit = simulate_unit_book(build_signals(development, locked), locked)
    holdout_signals = build_signals(holdout, locked)
    holdout_unit = simulate_unit_book(holdout_signals, locked)
    holdout_compound, equity = simulate_compounding_book(holdout_signals, locked)
    holdout_events = event_return_table(holdout_unit)
    inference = strategy.inference
    strategy_test = mean_return_test(
        holdout_events,
        "strategy_pnl",
        repetitions=inference.bootstrap_repetitions,
        block_length_weeks=inference.block_length_weeks,
        seed=inference.seed,
        alpha=inference.alpha,
    )
    excess_test = mean_return_test(
        holdout_events,
        "excess_pnl",
        repetitions=inference.bootstrap_repetitions,
        block_length_weeks=inference.block_length_weeks,
        seed=inference.seed + 17,
        alpha=inference.alpha,
    )
    costs = cost_sensitivity_table(holdout, locked, strategy)
    unit_summary = summarize_book(holdout_unit)
    compound_summary = summarize_book(
        holdout_compound,
        equity=equity,
        starting_bankroll=locked.starting_bankroll,
    )
    oof_summary = summarize_book(oof_unit)

    prefix = f"{resolved_study_run}/trading"
    report_storage.write_parquet(f"{prefix}/selection_scoreboard.parquet", scoreboard)
    report_storage.write_parquet(f"{prefix}/oof_unit_trades.parquet", oof_unit)
    report_storage.write_parquet(f"{prefix}/holdout_unit_trades.parquet", holdout_unit)
    report_storage.write_parquet(f"{prefix}/holdout_compound_trades.parquet", holdout_compound)
    report_storage.write_parquet(f"{prefix}/holdout_equity.parquet", equity)
    report_storage.write_parquet(f"{prefix}/holdout_event_returns.parquet", holdout_events)
    report_storage.write_parquet(f"{prefix}/cost_sensitivity.parquet", costs)

    payload = {
        "schema_version": "1",
        "diagnostic": True,
        "confirmatory": False,
        "note": (
            "Post-hoc economic diagnostic. Hyperparameters were locked on development "
            "OOF. The holdout was already opened for the Brier test, so these p-values "
            "are not a second confirmatory claim."
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "study_run_id": resolved_study_run,
        "data_run_id": data_run_id,
        "selected_model": training.get("selected_model"),
        "strategy_name": strategy.name,
        "locked_spec": _spec_dict(locked),
        "oof_unit": oof_summary,
        "holdout_unit": unit_summary,
        "holdout_compounding": compound_summary,
        "tests": {
            "strategy_pnl_vs_cash": strategy_test.to_dict(),
            "excess_pnl_vs_favorite": excess_test.to_dict(),
        },
    }
    report_storage.write_json(f"{prefix}/summary.json", payload)

    export_root = Path(destination)
    trading_export = export_root / "trading"
    trading_export.mkdir(parents=True, exist_ok=True)
    scoreboard.to_csv(trading_export / "selection_scoreboard.csv", index=False)
    holdout_unit.to_csv(trading_export / "holdout_unit_trades.csv", index=False)
    holdout_compound.to_csv(trading_export / "holdout_compound_trades.csv", index=False)
    equity.to_csv(trading_export / "holdout_equity.csv", index=False)
    holdout_events.to_csv(trading_export / "holdout_event_returns.csv", index=False)
    costs.to_csv(trading_export / "cost_sensitivity.csv", index=False)
    _write_json(trading_export / "summary.json", payload)

    return ReturnSimulationSummary(
        study_run_id=resolved_study_run,
        data_run_id=data_run_id,
        selected_model=str(training.get("selected_model")),
        locked_min_edge=locked.min_edge,
        locked_kelly_fraction=locked.kelly_fraction,
        locked_max_stake_fraction=locked.max_stake_fraction,
        holdout_unit_trades=int(unit_summary["trades"]),
        holdout_unit_return_on_deployed=float(unit_summary["return_on_deployed"]),
        holdout_compound_return=float(compound_summary.get("compound_return", float("nan"))),
        strategy_pnl_p_value=strategy_test.p_value_one_sided,
        excess_pnl_p_value=excess_test.p_value_one_sided,
        superior_to_cash=strategy_test.superior_at_alpha,
        superior_to_favorite=excess_test.superior_at_alpha,
    )


def _format_signed(value: float, digits: int = 4) -> str:
    if not isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def generate_return_report(
    summary: dict[str, Any],
    *,
    report_path: str | Path = "reports/excess_return_simulation.md",
) -> Path:
    """Write a standalone English diagnostic report for the trading simulation."""
    locked = summary["locked_spec"]
    unit = summary["holdout_unit"]
    compound = summary["holdout_compounding"]
    tests = summary["tests"]
    cash_test: dict[str, Any] = tests["strategy_pnl_vs_cash"]
    favorite_test: dict[str, Any] = tests["excess_pnl_vs_favorite"]
    destination = Path(report_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cash_interval = cash_test["confidence_interval_two_sided_95"]
    favorite_interval = favorite_test["confidence_interval_two_sided_95"]
    text = f"""# Excess-return simulation

This is a **post-hoc economic diagnostic**, not a replacement for the
preregistered Brier test. Strategy hyperparameters were locked on development
out-of-fold predictions. The holdout was already opened for forecast
evaluation, so the p-values below are descriptive inference on a reused
sample.

## Locked strategy

- Name: `{summary["strategy_name"]}`
- Study run: `{summary["study_run_id"]}`
- Data run: `{summary["data_run_id"]}`
- Forecast model: `{summary["selected_model"]}`
- Minimum net edge: {locked["min_edge"]}
- Kelly fraction: {locked["kelly_fraction"]}
- Maximum stake fraction: {locked["max_stake_fraction"]}
- Half-spread: {locked["half_spread"]}
- Taker fee on cash spent: {locked["taker_fee_rate"]}
- Tradable ask range: [{locked["min_tradable_price"]}, {locked["max_tradable_price"]}]

A signal fires when the model probability of the chosen side exceeds the
cost-adjusted ask by at least the locked edge. YES is bought at
`market + half-spread`; NO is bought at `1 - market + half-spread`. The
passive benchmark buys the market favorite on the same contracts with the
same cash stake.

## Holdout unit-stake book

Each signal risks a fixed {locked["unit_stake"]} cash unit, including fees.
This book is path-independent and is the primary economic diagnostic.

- Trades: {unit["trades"]}
- Event groups: {unit["event_groups"]}
- Hit rate: {_format_signed(unit["hit_rate"])}
- Long-YES share: {_format_signed(unit["long_yes_share"])}
- Total strategy PnL: {_format_signed(unit["total_strategy_pnl"])}
- Total favorite PnL: {_format_signed(unit["total_favorite_pnl"])}
- Total excess vs favorite: {_format_signed(unit["total_excess_pnl"])}
- Return on deployed capital: {_format_signed(unit["return_on_deployed"])}

Mean event strategy PnL vs cash: {_format_signed(cash_test["mean"])},
one-sided p = {_format_signed(cash_test["p_value_one_sided"])},
95% interval [{_format_signed(cash_interval[0])}, {_format_signed(cash_interval[1])}].

Mean event excess vs favorite: {_format_signed(favorite_test["mean"])},
one-sided p = {_format_signed(favorite_test["p_value_one_sided"])},
95% interval [{_format_signed(favorite_interval[0])}, {_format_signed(favorite_interval[1])}].

Superior to cash at alpha = 0.05: {cash_test["superior_at_alpha"]}.
Superior to the favorite at alpha = 0.05: {favorite_test["superior_at_alpha"]}.

## Holdout compounding book

Starting bankroll {locked["starting_bankroll"]:.0f}. Overlapping positions
reserve cash until resolution; new trades can spend only free cash.

- Trades filled: {compound["trades"]}
- Final equity: {_format_signed(compound.get("final_equity", float("nan")))}
- Compound return: {_format_signed(compound.get("compound_return", float("nan")))}
- Max drawdown: {_format_signed(compound.get("max_drawdown", float("nan")))}
- Weekly Sharpe: {_format_signed(compound.get("weekly_sharpe", float("nan")))}

## Limits

Fills are assumed at the stale mid plus a constant half-spread. There is no
order book, latency, inventory, or withdrawal-risk model. A Brier edge does
not imply a net-of-cost trading edge. Cost-sensitivity tables belong next to
this report and should be read before any economic conclusion.
"""
    destination.write_text(text, encoding="utf-8")
    return destination
