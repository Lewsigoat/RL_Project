# Walk-forward filter test (70% train / 30% test)

Signals split chronologically at **2026-04-02** (train 787, test 352).
Filters chosen on train only (objective: Sharpe, >= 40 trades), then frozen.

## Chosen filters

```json
{
  "long_only": true,
  "min_conf": 0.7,
  "max_risk": 7.0,
  "allow_options": false,
  "thesis_only": false
}
```

## Out-of-sample (test window)

| Metric | Filtered strategy | Unfiltered baseline | SPY |
|---|---|---|---|
| total_return | 0.0937 | 0.1548 | 0.128 |
| sharpe | 5.34 | 4.86 |  |
| max_drawdown | -0.0094 | -0.0171 |  |
| n_trades | 113 | 345 |  |
| win_rate | 0.646 | 0.536 |  |
| profit_factor | 6.22 | 3.51 |  |

## Top train combos (by Sharpe)

| long_only   |   min_conf |   max_risk | allow_options   | thesis_only   |   total_return |   sharpe |   max_drawdown |   n_trades |   win_rate |   profit_factor |
|:------------|-----------:|-----------:|:----------------|:--------------|---------------:|---------:|---------------:|-----------:|-----------:|----------------:|
| True        |        0.7 |          7 | False           | False         |         0.0154 |     0.32 |        -0.1056 |        256 |      0.328 |            1.14 |
| False       |        0.7 |          7 | False           | False         |         0.0152 |     0.32 |        -0.105  |        259 |      0.328 |            1.14 |
| False       |        0.6 |         10 | False           | False         |         0.0164 |     0.31 |        -0.1257 |        445 |      0.321 |            1.1  |
| True        |        0.6 |          7 | False           | False         |         0.0163 |     0.31 |        -0.1253 |        400 |      0.325 |            1.11 |
| True        |        0.7 |         10 | False           | False         |         0.0146 |     0.3  |        -0.109  |        265 |      0.328 |            1.13 |
| True        |        0.6 |         10 | False           | False         |         0.0159 |     0.3  |        -0.1325 |        421 |      0.323 |            1.1  |
| False       |        0.7 |         10 | False           | False         |         0.0138 |     0.29 |        -0.108  |        274 |      0.325 |            1.12 |
| False       |        0.6 |          7 | False           | False         |         0.0144 |     0.28 |        -0.1253 |        405 |      0.319 |            1.09 |
| True        |        0.6 |          7 | True            | False         |         0.0145 |     0.28 |        -0.1414 |        403 |      0.323 |            1.09 |
| True        |        0.7 |          7 | True            | False         |         0.0134 |     0.28 |        -0.1205 |        256 |      0.328 |            1.11 |