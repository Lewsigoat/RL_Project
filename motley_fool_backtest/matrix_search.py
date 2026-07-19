"""Full filter matrix on the train window (first 70% of signals by date).

Builds the 5-D matrix long_only x min_conf x max_risk x allow_options x
thesis_only (2x4x3x2x2 = 96 cells), each cell holding train CAGR and Sharpe.
Reports the argmax-CAGR and argmax-Sharpe cells (with and without the
min-trade-count constraint) and evaluates both frozen winners on the test 30%.
"""
import itertools, json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from backtest import load_prices, load_signals, run
from tune_filters import GRID, MIN_TRAIN_TRADES, apply_filters, spy_return

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
DIMS = list(GRID)
STAT_KEYS = ("annualized", "sharpe", "total_return", "max_drawdown", "n_trades",
             "win_rate", "profit_factor")


def main():
    prices = load_prices()
    signals = load_signals()
    dates = sorted(s["date"] for s in signals)
    split_date = dates[int(len(dates) * 0.7)]
    train = [s for s in signals if s["date"] < split_date]
    test = [s for s in signals if s["date"] >= split_date]
    print(f"split {split_date}: train {len(train)}, test {len(test)}")

    rows = []
    combos = [dict(zip(GRID, v)) for v in itertools.product(*GRID.values())]
    for i, f in enumerate(combos):
        sigs = apply_filters(train, f)
        stats = None
        if sigs:
            _, _, stats = run(signals=sigs, prices_all=prices, write=False)
        rows.append({**f, **({k: stats[k] for k in STAT_KEYS} if stats else
                             {k: np.nan for k in STAT_KEYS})})
        if (i + 1) % 16 == 0:
            print(f"  {i + 1}/{len(combos)}")
    df = pd.DataFrame(rows).set_index(DIMS)
    df.to_csv(os.path.join(RESULTS, "train_matrix.csv"))

    def argmax(col, constrained):
        d = df[df.n_trades >= MIN_TRAIN_TRADES] if constrained else df
        d = d.dropna(subset=[col])
        best = d[col].idxmax()
        return dict(zip(DIMS, best)), d.loc[best]

    report = {"split_date": split_date, "dims": {k: list(map(str, v))
                                                 for k, v in GRID.items()}}
    winners = {}
    for col in ("annualized", "sharpe"):
        for constrained in (True, False):
            key = f"max_{'cagr' if col == 'annualized' else col}" + \
                  ("" if constrained else "_unconstrained")
            filt, row = argmax(col, constrained)
            report[key] = {"filters": filt,
                           "train": {k: row[k] for k in STAT_KEYS}}
            if constrained:
                winners[key] = filt
            print(key, filt, f"train {col}={row[col]:.3f}, n={row.n_trades:.0f}")

    # ---- frozen out-of-sample evaluation of both constrained winners
    for key, filt in winners.items():
        sigs = apply_filters(test, {**filt, "min_conf": float(filt["min_conf"]),
                                    "max_risk": float(filt["max_risk"])})
        ec, trades, stats = run(signals=sigs, prices_all=prices, write=False)
        report[key]["test"] = stats
        report[key]["spy_test_window"] = spy_return(prices, ec.index[0], ec.index[-1])

    with open(os.path.join(RESULTS, "matrix_search.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    # ---- heatmap panels: min_conf x max_risk, faceted by the boolean dims
    for col, fname in [("annualized", "matrix_cagr.png"), ("sharpe", "matrix_sharpe.png")]:
        bools = list(itertools.product(GRID["long_only"], GRID["allow_options"],
                                       GRID["thesis_only"]))
        fig, axes = plt.subplots(2, 4, figsize=(18, 7), sharex=True, sharey=True)
        vals = df[col].dropna()
        vmin, vmax = vals.min(), vals.max()
        for ax, (lo, ao, to) in zip(axes.flat, bools):
            sub = df.xs((lo, ao, to), level=("long_only", "allow_options",
                                             "thesis_only"))[col] \
                    .unstack("max_risk").sort_index()
            im = ax.imshow(sub.values, cmap="RdYlGn", vmin=vmin, vmax=vmax,
                           aspect="auto")
            ax.set_xticks(range(len(sub.columns)), [f"risk<={c:g}" for c in sub.columns])
            ax.set_yticks(range(len(sub.index)), [f"conf>={i:g}" for i in sub.index])
            ax.set_title(f"long_only={lo} options={ao} thesis={to}", fontsize=9)
            for (r, c), v in np.ndenumerate(sub.values):
                if np.isfinite(v):
                    ax.text(c, r, f"{v:.2f}", ha="center", va="center", fontsize=8)
        fig.suptitle(f"Train-window {'CAGR' if col == 'annualized' else 'Sharpe'} "
                     f"across the filter matrix (n<{MIN_TRAIN_TRADES} cells included)")
        fig.colorbar(im, ax=axes, shrink=0.8)
        fig.savefig(os.path.join(RESULTS, fname), dpi=110, bbox_inches="tight")
        plt.close(fig)
    print("wrote train_matrix.csv, matrix_search.json, matrix_cagr.png, matrix_sharpe.png")


if __name__ == "__main__":
    main()
