from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from polymarket_forecast.evaluation.returns import (
    event_return_table,
    max_drawdown,
    mean_return_test,
    select_strategy,
    simulate_compounding_book,
    simulate_unit_book,
)
from polymarket_forecast.strategy import (
    StrategyConfig,
    StrategyGrid,
    StrategyInferenceConfig,
    StrategySpec,
    build_signals,
    kelly_fraction_of_wealth,
    load_strategy_config,
    realized_pnl,
    shares_for_stake,
)


def _spec(**overrides: object) -> StrategySpec:
    base = StrategySpec(
        min_edge=0.05,
        kelly_fraction=0.5,
        max_stake_fraction=0.05,
        half_spread=0.01,
        taker_fee_rate=0.02,
        price_clip=0.01,
        min_tradable_price=0.05,
        max_tradable_price=0.95,
        starting_bankroll=1000.0,
        unit_stake=1.0,
        assumed_horizon_days=7,
        probability_column="model_probability",
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def _scalar(value: object) -> float:
    return float(np.asarray(value, dtype=float).reshape(-1)[0])


def _predictions() -> pd.DataFrame:
    start = datetime(2024, 1, 7, tzinfo=UTC)
    rows = []
    for index in range(24):
        yes = index % 3 != 0
        rows.append(
            {
                "market_id": f"m-{index}",
                "event_group_id": f"e-{index}",
                "forecast_cutoff": start + timedelta(days=7 * index),
                "event_time": start + timedelta(days=7 * index + 7),
                "label": int(yes),
                "market_probability": 0.40 if yes else 0.60,
                "model_probability": 0.80 if yes else 0.20,
            }
        )
    return pd.DataFrame(rows)


def test_kelly_and_fee_inclusive_cash_accounting() -> None:
    assert abs(kelly_fraction_of_wealth(0.6, 0.4) - (1.0 / 3.0)) < 1e-12
    assert kelly_fraction_of_wealth(0.4, 0.4) == 0.0
    shares = _scalar(shares_for_stake(1.02, 0.5, 0.02))
    assert shares == 2.0
    assert _scalar(realized_pnl(1, 1, shares, 0.5, 0.02)) == 0.98
    assert _scalar(realized_pnl(1, 0, shares, 0.5, 0.02)) == -1.02
    assert _scalar(realized_pnl(-1, 0, shares, 0.5, 0.02)) == 0.98


def test_costs_and_threshold_suppress_trades() -> None:
    cheap = build_signals(_predictions(), _spec(half_spread=0.0, taker_fee_rate=0.0, min_edge=0.05))
    expensive = build_signals(
        _predictions(),
        _spec(half_spread=0.45, taker_fee_rate=0.10, min_edge=0.05),
    )
    assert int(cheap["signal"].sum()) > 0
    assert int(expensive["signal"].sum()) == 0


def test_unit_book_beats_favorite_when_model_is_correct() -> None:
    trades = simulate_unit_book(build_signals(_predictions(), _spec()), _spec())
    assert not trades.empty
    assert float(trades["strategy_pnl"].sum()) > float(trades["favorite_pnl"].sum())
    assert float(trades["excess_pnl"].sum()) > 0


def test_compounding_book_never_spends_reserved_cash() -> None:
    spec = _spec(starting_bankroll=10.0, max_stake_fraction=0.8, kelly_fraction=1.0)
    trades, equity = simulate_compounding_book(build_signals(_predictions(), spec), spec)
    assert not trades.empty
    assert bool((equity["reserved"] >= -1e-9).all())
    assert bool((equity["cash"] >= -1e-9).all())
    assert bool((equity["equity"] > 0).all())
    assert max_drawdown(equity["equity"]) <= 0


def test_select_strategy_does_not_see_holdout_rows() -> None:
    frame = _predictions()
    development = frame.iloc[:16].copy()
    config = StrategyConfig(
        name="test",
        spec=_spec(),
        grid=StrategyGrid(
            min_edge=(0.03, 0.20),
            kelly_fraction=(0.5,),
            max_stake_fraction=(0.05,),
        ),
        inference=StrategyInferenceConfig(
            bootstrap_repetitions=99,
            block_length_weeks=2,
            alpha=0.05,
            seed=7,
        ),
        selection_minimum_trades=4,
        cost_half_spreads=(0.01,),
        cost_taker_fee_rates=(0.02,),
        source_path=Path("configs/strategy.yaml"),
    )
    locked, scoreboard = select_strategy(development, config)
    assert locked.min_edge == 0.03
    assert int(scoreboard["selected"].sum()) == 1
    assert set(development["market_id"]).isdisjoint({f"m-{index}" for index in range(16, 24)})


def test_return_bootstrap_is_deterministic() -> None:
    trades = simulate_unit_book(build_signals(_predictions(), _spec()), _spec())
    events = event_return_table(trades)
    first = mean_return_test(
        events,
        "strategy_pnl",
        repetitions=199,
        block_length_weeks=2,
        seed=11,
        alpha=0.05,
    )
    second = mean_return_test(
        events,
        "strategy_pnl",
        repetitions=199,
        block_length_weeks=2,
        seed=11,
        alpha=0.05,
    )
    assert first == second
    assert first.mean > 0
    assert first.p_value_one_sided < 0.05


def test_strategy_yaml_loads() -> None:
    config = load_strategy_config("configs/strategy.yaml")
    assert config.name == "edge_threshold_fractional_kelly"
    assert len(config.candidates()) == 16
