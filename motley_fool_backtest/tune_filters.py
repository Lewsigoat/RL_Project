"""Walk-forward filter selection: choose signal filters on the first 70% of
signals (by publication date), evaluate the frozen winner on the last 30%.

The grid is pre-registered below — no peeking at test data during selection.
Selection objective: train Sharpe, requiring >= 40 train trades (small-sample
winners are noise). Outputs results/oos_test.json and results/oos_report.md.
"""
import itertools, json, os
import pandas as pd
from backtest import load_prices, load_signals, run, CAPITAL

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")

GRID = {
    "long_only": [False, True],
    "min_conf": [0.40, 0.50, 0.60, 0.70],
    "max_risk": [10, 7, 5],
    "allow_options": [True, False],
    "thesis_only": [False, True],   # forward_thesis + earnings_preview articles only
}
MIN_TRAIN_TRADES = 40
THESIS_TYPES = {"forward_thesis", "earnings_preview"}


def apply_filters(signals, f):
    out = []
    for s in signals:
        if f["long_only"] and s["direction"] != "bullish":
            continue
        if s["confidence"] < f["min_conf"]:
            continue
        if s["risk"] > f["max_risk"]:
            continue
        if f["thesis_only"] and s["article_type"] not in THESIS_TYPES:
            continue
        if not f["allow_options"] and s["instrument"] != "stock":
            s = {**s, "instrument": "stock"}
        out.append(s)
    return out


def spy_return(prices, start, end):
    c = prices["SPY"].loc[start:end, "close"]
    return round(c.iloc[-1] / c.iloc[0] - 1, 4)


def main():
    prices = load_prices()
    signals = load_signals()
    dates = sorted(s["date"] for s in signals)
    split_date = dates[int(len(dates) * 0.7)]
    train = [s for s in signals if s["date"] < split_date]
    test = [s for s in signals if s["date"] >= split_date]
    print(f"split at {split_date}: train {len(train)} signals "
          f"({dates[0]}..), test {len(test)} (..{dates[-1]})")

    rows = []
    combos = [dict(zip(GRID, v)) for v in itertools.product(*GRID.values())]
    for i, f in enumerate(combos):
        sigs = apply_filters(train, f)
        if not sigs:
            continue
        _, trades, stats = run(signals=sigs, prices_all=prices, write=False)
        if stats is None:
            continue
        rows.append({**f, **{k: stats[k] for k in
                             ("total_return", "sharpe", "max_drawdown", "n_trades",
                              "win_rate", "profit_factor")}})
        if (i + 1) % 16 == 0:
            print(f"  {i + 1}/{len(combos)} combos")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS, "train_grid.csv"), index=False)
    ok = df[df.n_trades >= MIN_TRAIN_TRADES].sort_values("sharpe", ascending=False)
    best = ok.iloc[0][list(GRID)].to_dict()
    best = {k: (bool(v) if isinstance(v, (bool,)) or str(v) in ("True", "False")
                else float(v)) for k, v in best.items()}
    print("chosen filters:", best)
    print("train stats:", ok.iloc[0][["total_return", "sharpe", "n_trades",
                                      "win_rate", "profit_factor"]].to_dict())

    # ---- frozen out-of-sample run
    test_sigs = apply_filters(test, best)
    ec, trades, stats = run(signals=test_sigs, prices_all=prices, write=False)
    base_ec, base_trades, base_stats = run(signals=test, prices_all=prices, write=False)
    spy_ret = spy_return(prices, ec.index[0], ec.index[-1])

    out = {
        "split_date": split_date,
        "chosen_filters": best,
        "train_row": ok.iloc[0].to_dict(),
        "test_filtered": stats,
        "test_unfiltered_baseline": base_stats,
        "spy_return_test_window": spy_ret,
    }
    with open(os.path.join(RESULTS, "oos_test.json"), "w") as fjson:
        json.dump(out, fjson, indent=2, default=str)
    ec.to_csv(os.path.join(RESULTS, "oos_equity_curve.csv"), header=["equity"])
    trades.drop(columns=["legs"]).to_csv(os.path.join(RESULTS, "oos_trades.csv"),
                                         index=False)

    lines = ["# Walk-forward filter test (70% train / 30% test)", "",
             f"Signals split chronologically at **{split_date}** "
             f"(train {len(train)}, test {len(test)}).",
             f"Filters chosen on train only (objective: Sharpe, "
             f">= {MIN_TRAIN_TRADES} trades), then frozen.", "",
             "## Chosen filters", "",
             "```json", json.dumps(best, indent=2), "```", "",
             "## Out-of-sample (test window)", "",
             "| Metric | Filtered strategy | Unfiltered baseline | SPY |", "|---|---|---|---|"]
    for k in ("total_return", "sharpe", "max_drawdown", "n_trades", "win_rate",
              "profit_factor"):
        lines.append(f"| {k} | {stats[k]} | {base_stats[k]} | "
                     f"{spy_ret if k == 'total_return' else ''} |")
    lines += ["", "## Top train combos (by Sharpe)", "",
              ok.head(10).to_markdown(index=False)]
    open(os.path.join(RESULTS, "oos_report.md"), "w").write("\n".join(lines))
    print(json.dumps({"test_filtered": stats, "test_baseline": base_stats,
                      "spy": spy_ret}, indent=2))


if __name__ == "__main__":
    main()
