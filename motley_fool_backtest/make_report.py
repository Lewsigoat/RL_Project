"""Generate charts + report.md from backtest results."""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "results")

ec = pd.read_csv(f"{R}/equity_curve.csv", index_col=0, parse_dates=True)["equity"]
trades = pd.read_csv(f"{R}/trades.csv", parse_dates=["entry_date", "exit_date"])
stats = json.load(open(f"{R}/stats.json"))
spy = pd.read_csv(os.path.join(HERE, "data", "prices", "SPY.csv"),
                  parse_dates=["date"]).set_index("date")["close"]
spy = spy.reindex(ec.index).ffill()

fig, axes = plt.subplots(2, 2, figsize=(14, 9))
ax = axes[0][0]
(ec / ec.iloc[0]).plot(ax=ax, label="Strategy", lw=1.8)
(spy / spy.iloc[0]).plot(ax=ax, label="SPY", lw=1.2, alpha=0.8)
ax.set_title("Equity curve vs SPY (normalized)"); ax.legend(); ax.grid(alpha=0.3)

ax = axes[0][1]
dd = ec / ec.cummax() - 1
dd.plot(ax=ax, color="crimson", lw=1.2)
ax.fill_between(dd.index, dd, 0, color="crimson", alpha=0.2)
ax.set_title("Drawdown"); ax.grid(alpha=0.3)

ax = axes[1][0]
b = trades.groupby(pd.cut(trades.confidence, [0.4, 0.5, 0.6, 0.7, 0.8, 1.0]),
                   observed=True).ret.mean()
b.plot.bar(ax=ax, color=["#c44" if v < 0 else "#2a7" for v in b])
ax.set_title("Avg trade return by confidence bucket")
ax.set_xticklabels([str(i) for i in b.index], rotation=30); ax.grid(alpha=0.3, axis="y")

ax = axes[1][1]
g = trades.groupby("instrument").pnl.sum().sort_values()
g.plot.barh(ax=ax, color=["#c44" if v < 0 else "#2a7" for v in g])
ax.set_title("Total P&L by instrument ($)"); ax.grid(alpha=0.3, axis="x")
fig.tight_layout()
fig.savefig(f"{R}/summary.png", dpi=110)

s = stats["stats"]
lines = ["# Motley Fool article-sentiment backtest — results", "",
         f"Cohort: articles published {trades.date.min()} to {trades.date.max()}; "
         f"simulation {s['start']} to {s['end']} on ${1_000_000:,} starting capital.", "",
         "| Metric | Value |", "|---|---|"]
for k, v in s.items():
    lines.append(f"| {k} | {v} |")
lines += ["", "![summary](summary.png)", ""]
for name, rows in stats["breakdowns"].items():
    lines += [f"## By {name}", "", "| " + " | ".join(rows[0].keys()) + " |",
              "|" + "---|" * len(rows[0])]
    for r in rows:
        lines.append("| " + " | ".join(str(x) for x in r.values()) + " |")
    lines.append("")
top = trades.nlargest(10, "pnl")[["ticker", "direction", "instrument", "entry_date",
                                  "exit_date", "pnl", "ret", "exit_reason"]]
bot = trades.nsmallest(10, "pnl")[["ticker", "direction", "instrument", "entry_date",
                                   "exit_date", "pnl", "ret", "exit_reason"]]
for title, df in [("Top 10 trades", top), ("Worst 10 trades", bot)]:
    lines += [f"## {title}", "", df.to_markdown(index=False), ""]
open(f"{R}/report.md", "w").write("\n".join(lines))
print("report written")
