# Excess-return simulation

This is a **post-hoc economic diagnostic**, not a replacement for the
preregistered Brier test. Strategy hyperparameters were locked on development
out-of-fold predictions. The holdout was already opened for forecast
evaluation, so the p-values below are descriptive inference on a reused
sample.

## Locked strategy

- Name: `edge_threshold_fractional_kelly`
- Study run: `study-reproduction-20260910`
- Data run: `real-20260910-v2`
- Forecast model: `ensemble`
- Minimum net edge: 0.05
- Kelly fraction: 0.25
- Maximum stake fraction: 0.02
- Half-spread: 0.01
- Taker fee on cash spent: 0.02
- Tradable ask range: [0.05, 0.95]

A signal fires when the model probability of the chosen side exceeds the
cost-adjusted ask by at least the locked edge. YES is bought at
`market + half-spread`; NO is bought at `1 - market + half-spread`. The
passive benchmark buys the market favorite on the same contracts with the
same cash stake.

## Holdout unit-stake book

Each signal risks a fixed 1.0 cash unit, including fees.
This book is path-independent and is the primary economic diagnostic.

- Trades: 329
- Event groups: 282
- Hit rate: 0.5805
- Long-YES share: 0.9088
- Total strategy PnL: 46.6504
- Total favorite PnL: -8.2679
- Total excess vs favorite: 54.9183
- Return on deployed capital: 0.1418

Development OOF lock (unit book, not the holdout): 40 trades,
return on deployed 0.2134, hit rate
0.2250. The lock is thin; Kelly and stake caps
do not change the unit-book score, so the smallest conservative size in
the winning edge bucket was kept.

Mean event strategy PnL vs cash: 0.1654,
one-sided p = 0.1532,
95% interval [-0.0652, 0.4828].

Mean event excess vs favorite: 0.1947,
one-sided p = 0.1036,
95% interval [-0.1028, 0.5095].

Superior to cash at alpha = 0.05: False.
Superior to the favorite at alpha = 0.05: False.

## Holdout compounding book

Starting bankroll 10000. Overlapping positions
reserve cash until resolution; new trades can spend only free cash.

- Trades filled: 238
- Final equity: 26961.0517
- Compound return: 1.6961
- Max drawdown: -0.1365
- Weekly Sharpe: 2.1724

The compounding path is an illustration, not the inferential test. Paper
Sharpe values ignore capacity, latency, and correlated fill risk.

## Cost sensitivity on the locked signals

Holdout unit-book return on deployed capital after changing costs. This
grid is diagnostic and was not used to pick the strategy.

| Half-spread | Taker fee | Trades | Return on deployed | Total PnL |
|---|---:|---:|---:|---:|
| 0.00 | 0.00 | 348 | 0.2936 | 102.1742 |
| 0.00 | 0.01 | 348 | 0.2808 | 97.7171 |
| 0.00 | 0.02 | 348 | 0.2682 | 93.3473 |
| 0.01 | 0.00 | 329 | 0.1646 | 54.1634 |
| 0.01 | 0.01 | 329 | 0.1531 | 50.3697 |
| 0.01 | 0.02 | 329 | 0.1418 | 46.6504 |
| 0.02 | 0.00 | 303 | 0.1412 | 42.7743 |
| 0.02 | 0.01 | 303 | 0.1299 | 39.3508 |
| 0.02 | 0.02 | 303 | 0.1188 | 35.9944 |
| 0.03 | 0.00 | 286 | 0.1286 | 36.7669 |
| 0.03 | 0.01 | 286 | 0.1174 | 33.5712 |
| 0.03 | 0.02 | 286 | 0.1064 | 30.4381 |

## Limits

Fills are assumed at the stale mid plus a constant half-spread. There is no
order book, latency, inventory, or withdrawal-risk model. A Brier edge does
not imply a net-of-cost trading edge. Cost-sensitivity tables belong next to
this report and should be read before any economic conclusion.
