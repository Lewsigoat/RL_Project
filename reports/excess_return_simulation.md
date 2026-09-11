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

## Risk-adjusted returns by fee

Locked half-spread 0.01. Sharpe and Sortino use weekly
returns versus cash (risk-free rate 0) and are annualized with
`sqrt(52)`. The information ratio uses weekly excess versus the matched
favorite. Calmar is annualized compounding return divided by absolute
max drawdown. This grid is diagnostic and was not used to pick the
strategy.

| Fee | Unit RoC | Unit Sharpe | Unit Sortino | IR vs fav | CAGR | Comp Sharpe | Comp Sortino | Max DD | Calmar |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.000 | 0.1646 | 1.3485 | 2.8699 | 1.3266 | 1.6494 | 2.2778 | 11.0875 | -0.1292 | 12.7617 |
| 0.005 | 0.1588 | 1.3110 | 2.7900 | 1.3266 | 1.5962 | 2.2520 | 10.4079 | -0.1311 | 12.1779 |
| 0.010 | 0.1531 | 1.2734 | 2.7101 | 1.3266 | 1.5445 | 2.2258 | 10.4376 | -0.1329 | 11.6222 |
| 0.015 | 0.1474 | 1.2359 | 2.6301 | 1.3266 | 1.4941 | 2.1993 | 9.8014 | -0.1347 | 11.0929 |
| 0.020 | 0.1418 | 1.1983 | 2.5502 | 1.3266 | 1.4449 | 2.1724 | 9.6269 | -0.1365 | 10.5884 |
| 0.030 | 0.1307 | 1.1232 | 2.3904 | 1.3266 | 1.3505 | 2.1176 | 9.0454 | -0.1401 | 9.6391 |
| 0.050 | 0.1092 | 0.9730 | 2.0707 | 1.3266 | 1.1752 | 2.0037 | 8.1080 | -0.1498 | 7.8465 |

Unit-book cost grid, including alternate spreads:

| Half-spread | Taker fee | Trades | RoC | Weekly Sharpe | Sortino | Info ratio |
|---|---:|---:|---:|---:|---:|---:|
| 0.00 | 0.000 | 348 | 0.2936 | 1.7653 | 4.0452 | 1.6087 |
| 0.00 | 0.005 | 348 | 0.2872 | 1.7269 | 3.9572 | 1.6087 |
| 0.00 | 0.010 | 348 | 0.2808 | 1.6885 | 3.8691 | 1.6087 |
| 0.00 | 0.015 | 348 | 0.2745 | 1.6501 | 3.7811 | 1.6087 |
| 0.00 | 0.020 | 348 | 0.2682 | 1.6117 | 3.6931 | 1.6087 |
| 0.00 | 0.030 | 348 | 0.2559 | 1.5348 | 3.0592 | 1.6087 |
| 0.00 | 0.050 | 348 | 0.2320 | 1.3812 | 2.7529 | 1.6087 |
| 0.01 | 0.000 | 329 | 0.1646 | 1.3485 | 2.8699 | 1.3266 |
| 0.01 | 0.005 | 329 | 0.1588 | 1.3110 | 2.7900 | 1.3266 |
| 0.01 | 0.010 | 329 | 0.1531 | 1.2734 | 2.7101 | 1.3266 |
| 0.01 | 0.015 | 329 | 0.1474 | 1.2359 | 2.6301 | 1.3266 |
| 0.01 | 0.020 | 329 | 0.1418 | 1.1983 | 2.5502 | 1.3266 |
| 0.01 | 0.030 | 329 | 0.1307 | 1.1232 | 2.3904 | 1.3266 |
| 0.01 | 0.050 | 329 | 0.1092 | 0.9730 | 2.0707 | 1.3266 |
| 0.02 | 0.000 | 303 | 0.1412 | 1.5163 | 3.7223 | 1.4908 |
| 0.02 | 0.005 | 303 | 0.1355 | 1.4848 | 3.6450 | 1.4908 |
| 0.02 | 0.010 | 303 | 0.1299 | 1.4533 | 3.5676 | 1.4908 |
| 0.02 | 0.015 | 303 | 0.1243 | 1.4218 | 3.4903 | 1.4908 |
| 0.02 | 0.020 | 303 | 0.1188 | 1.3903 | 3.4130 | 1.4908 |
| 0.02 | 0.030 | 303 | 0.1079 | 1.3273 | 3.2583 | 1.4908 |
| 0.02 | 0.050 | 303 | 0.0868 | 1.2013 | 2.9489 | 1.4908 |
| 0.03 | 0.000 | 286 | 0.1286 | 1.4118 | 3.3903 | 1.4487 |
| 0.03 | 0.005 | 286 | 0.1229 | 1.3780 | 3.3091 | 1.4487 |
| 0.03 | 0.010 | 286 | 0.1174 | 1.3441 | 3.2279 | 1.4487 |
| 0.03 | 0.015 | 286 | 0.1119 | 1.3103 | 3.1466 | 1.4487 |
| 0.03 | 0.020 | 286 | 0.1064 | 1.2765 | 3.0654 | 1.4487 |
| 0.03 | 0.030 | 286 | 0.0957 | 1.2088 | 2.9029 | 1.4487 |
| 0.03 | 0.050 | 286 | 0.0748 | 1.0735 | 2.5779 | 1.4487 |

## Limits

Fills are assumed at the stale mid plus a constant half-spread. There is no
order book, latency, inventory, or withdrawal-risk model. A Brier edge does
not imply a net-of-cost trading edge. Cost-sensitivity tables belong next to
this report and should be read before any economic conclusion.
