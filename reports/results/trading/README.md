# Excess-return diagnostic artifacts

Study run: `study-reproduction-20260910`
Data run: `real-20260910-v2`
Strategy: `edge_threshold_fractional_kelly`

These files are a post-hoc paper-trading diagnostic. They do not change the
preregistered Brier decision.

- `summary.json`: locked spec, unit and compounding books, bootstrap tests.
- `selection_scoreboard.csv`: OOF grid used to lock the edge threshold.
- `holdout_unit_trades.csv`: path-independent $1 book (primary economic test).
- `holdout_compound_trades.csv`: reserved-capital compounding fills.
- `holdout_equity.csv`: cash, reserved capital, and equity path.
- `holdout_event_returns.csv`: event-collapsed PnL for block inference.
- `cost_sensitivity.csv`: holdout unit-book results under alternate costs.
- `equity_curve.png`, `excess_pnl_histogram.png`, `cost_sensitivity.png`.

The written interpretation is in
[`../../excess_return_simulation.md`](../../excess_return_simulation.md).
