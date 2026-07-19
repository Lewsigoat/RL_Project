"""Backtest of Motley Fool article sentiment, Feb-Apr 2026 cohort.

Strategy
--------
- LLM-labeled articles (see data/labels.jsonl): each actionable signal carries a
  primary ticker, direction, confidence (0-1), risk score (1-10), an instrument
  recommendation (stock / ITM or OTM call / ITM or OTM put), an optional strike
  hint taken from price levels quoted in the article, and a holding horizon.
- Entry at next trading day's open after publication.
- Position size scales with confidence and inversely with risk.
- Options are modeled with Black-Scholes on 60-day realized vol (no historical
  option quotes are available); a spread/markup haircut is charged on both legs.
- Exits: ATR-scaled trailing stop, ratcheting profit taker (partial exits that
  re-arm at higher levels, re-assessed daily), horizon/time stop, option expiry.
"""
import json, math, os
from collections import defaultdict
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PRICES_DIR = os.path.join(HERE, "data", "prices")
LABELS = os.path.join(HERE, "data", "labels.jsonl")
RESULTS = os.path.join(HERE, "results")

CAPITAL = 1_000_000.0
MAX_GROSS = 1.5          # max gross exposure as fraction of equity
BASE_WEIGHT = 0.02       # max notional weight of a single full-confidence stock trade
OPT_BUDGET_FRAC = 0.35   # option premium budget vs stock-equivalent notional
MIN_CONFIDENCE = 0.40
RISK_FREE = 0.04
SPREAD_HAIRCUT = 0.05    # 5% of premium each way for options, 10bps for stock
STOCK_SLIPPAGE = 0.001
END_DATE = None          # set from price data


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(S, K, T, sigma, r, kind):
    """Black-Scholes European option price; returns intrinsic at T<=0."""
    if T <= 0:
        return max(0.0, S - K) if kind == "call" else max(0.0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if kind == "call":
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)


def load_prices():
    prices = {}
    for f in os.listdir(PRICES_DIR):
        if not f.endswith(".csv"):
            continue
        t = f[:-4]
        df = pd.read_csv(os.path.join(PRICES_DIR, f), parse_dates=["date"])
        df = df.drop_duplicates("date").set_index("date").sort_index()
        if len(df) < 60:
            continue
        # ATR(14) and 60d realized vol, shifted so entry-day values are known
        tr = np.maximum(df.high - df.low,
                        np.maximum((df.high - df.close.shift()).abs(),
                                   (df.low - df.close.shift()).abs()))
        df["atr"] = tr.rolling(14).mean()
        df["rvol"] = df.close.pct_change().rolling(60).std() * math.sqrt(252)
        prices[t] = df
    return prices


def load_signals():
    signals = []
    with open(LABELS) as f:
        for line in f:
            art = json.loads(line)
            for s in art.get("signals", []):
                if not s.get("relevant") or s.get("direction") not in ("bullish", "bearish"):
                    continue
                if (s.get("confidence") or 0) < MIN_CONFIDENCE:
                    continue
                t = (s.get("primary_ticker") or "").upper().replace(".", "-")
                if not t:
                    continue
                signals.append({
                    "date": art["date"], "url": art["url"], "title": art.get("title", ""),
                    "ticker": t, "direction": s["direction"],
                    "confidence": float(s["confidence"]),
                    "risk": float(s.get("risk_score") or 5),
                    "instrument": s.get("instrument") or "stock",
                    "strike_hint": s.get("strike_hint"),
                    "horizon": int(min(max(s.get("horizon_days") or 40, 10), 90)),
                })
    # merge duplicates per instrument expression: keep highest confidence
    best = {}
    for s in signals:
        k = (s["ticker"], s["date"], s["direction"], s["instrument"])
        if k not in best or s["confidence"] > best[k]["confidence"]:
            best[k] = s
    return sorted(best.values(), key=lambda s: s["date"])


class Position:
    def __init__(self, sig, entry_date, entry_px, qty, opt=None, trail_pct=0.12, pt=0.15):
        self.sig = sig
        self.entry_date = entry_date
        self.entry_px = entry_px          # per-share stock px or per-share option premium
        self.qty = qty                    # shares (negative = short) or option contracts*100
        self.opt = opt                    # dict(kind, K, expiry, sigma) or None
        self.trail_pct = trail_pct
        self.pt = pt                      # current profit-taker threshold (return on entry px)
        self.pt_step = pt
        self.peak = entry_px if qty > 0 else entry_px  # peak favorable mark
        self.realized = 0.0
        self.days = 0
        self.log = []

    def mark(self, row, date):
        if self.opt:
            T = max((self.opt["expiry"] - date).days, 0) / 365.0
            return bs_price(row.close, self.opt["K"], T, self.opt["sigma"], RISK_FREE,
                            self.opt["kind"])
        return row.close


def run():
    prices = load_prices()
    signals = load_signals()
    spy = prices.pop("SPY")
    all_days = spy.index
    global END_DATE
    END_DATE = all_days[-1]

    sig_by_day = defaultdict(list)
    for s in signals:
        d = pd.Timestamp(s["date"])
        nxt = all_days[all_days > d]
        if len(nxt) == 0:
            continue
        sig_by_day[nxt[0]].append(s)

    # simulate only from the first entry day: earlier months would dilute the stats
    first_entry = min(sig_by_day)
    all_days = all_days[all_days >= first_entry]

    cash = CAPITAL
    open_pos, closed = [], []
    equity_curve = []

    def equity(date):
        tot = cash
        for p in open_pos:
            df = prices[p.sig["ticker"]]
            if date in df.index:
                tot += p.qty * p.mark(df.loc[date], date)
            else:
                tot += p.qty * p.entry_px
        return tot

    def gross(date):
        g = 0.0
        for p in open_pos:
            df = prices[p.sig["ticker"]]
            row = df.loc[date] if date in df.index else None
            px = p.mark(row, date) if row is not None else p.entry_px
            if p.opt:
                g += abs(p.qty) * px
            else:
                g += abs(p.qty) * px
        return g

    def close_part(p, date, px, frac, reason):
        sold = p.qty * frac
        cost = abs(sold) * px * (SPREAD_HAIRCUT if p.opt else STOCK_SLIPPAGE)
        nonlocal cash
        cash += sold * px - cost
        p.realized += sold * (px - p.entry_px) - cost
        p.qty -= sold
        p.log.append((str(date.date()), reason, round(px, 4), round(frac, 2)))
        if abs(p.qty) < 1e-9:
            r = p.realized / (abs(p.entry_qty) * p.entry_px)
            closed.append({**{k: p.sig[k] for k in
                              ("ticker", "date", "direction", "confidence", "risk",
                               "instrument", "url", "title")},
                           "entry_date": str(p.entry_date.date()),
                           "exit_date": str(date.date()), "days_held": p.days,
                           "entry_px": round(p.entry_px, 4), "exit_px": round(px, 4),
                           "pnl": round(p.realized, 2), "ret": round(r, 4),
                           "exit_reason": reason, "legs": p.log})
            return True
        return False

    for date in all_days:
        # ---- manage open positions
        for p in list(open_pos):
            t = p.sig["ticker"]
            df = prices[t]
            if date not in df.index:
                continue
            row = df.loc[date]
            p.days += 1
            px = p.mark(row, date)
            long = p.qty > 0
            fav = px if long else -px
            if fav > (p.peak if long else -p.peak) * (1 if long else 1):
                pass
            # track most favorable mark
            if (long and px > p.peak) or (not long and px < p.peak):
                p.peak = px

            # option expiry
            if p.opt and date >= p.opt["expiry"]:
                if close_part(p, date, px, 1.0, "expiry"):
                    open_pos.remove(p)
                continue

            # trailing stop off the peak favorable mark
            stop_hit = (long and px <= p.peak * (1 - p.trail_pct)) or \
                       (not long and px >= p.peak * (1 + p.trail_pct))
            if stop_hit:
                if close_part(p, date, px, 1.0, "trailing_stop"):
                    open_pos.remove(p)
                continue

            # ratcheting profit taker: take a third off, re-arm higher, tighten trail
            ret = (px / p.entry_px - 1) * (1 if long else -1)
            if ret >= p.pt:
                if close_part(p, date, px, 1 / 3, f"profit_take@{p.pt:.0%}"):
                    open_pos.remove(p)
                    continue
                p.pt += p.pt_step
                p.trail_pct *= 0.75
            # weekly re-assessment: if realized vol doubled since entry, tighten
            elif p.days % 5 == 0 and not p.opt:
                rv = row.rvol
                if rv and p.entry_rvol and rv > 2 * p.entry_rvol:
                    p.trail_pct = max(p.trail_pct * 0.8, 0.05)
                    p.log.append((str(date.date()), "tighten_trail", round(p.trail_pct, 3), 0))

            # time stop
            if p.days >= p.sig["horizon"]:
                if close_part(p, date, px, 1.0, "time_stop"):
                    open_pos.remove(p)

        # ---- entries
        eq = equity(date)
        # when the gross-exposure cap binds, highest-conviction signals enter first
        for s in sorted(sig_by_day.get(date, []), key=lambda x: -x["confidence"]):
            t = s["ticker"]
            if t not in prices or date not in prices[t].index:
                continue
            df = prices[t]
            row = df.loc[date]
            if not np.isfinite(row.open) or row.open <= 0:
                continue
            if gross(date) > MAX_GROSS * eq:
                continue
            atr, rvol = row.atr, row.rvol
            if not np.isfinite(atr) or not np.isfinite(rvol):
                atr, rvol = row.open * 0.03, 0.45
            conf_w = min(max((s["confidence"] - 0.3) / 0.7, 0.1), 1.0)
            risk_w = (11 - s["risk"]) / 10.0
            notional = CAPITAL * BASE_WEIGHT * conf_w * risk_w
            trail = min(max(2.5 * atr / row.open, 0.08), 0.18)
            pt0 = max(0.12, 1.3 * trail)
            long_dir = s["direction"] == "bullish"
            inst = s["instrument"]

            if inst in ("itm_call", "otm_call", "itm_put", "otm_put"):
                kind = "call" if inst.endswith("call") else "put"
                # bearish thesis with a call rec (or vice versa) -> fall back to thesis side
                if (kind == "call") != long_dir:
                    kind = "call" if long_dir else "put"
                itm = inst.startswith("itm")
                S = row.open
                if s["strike_hint"] and 0.75 * S <= s["strike_hint"] <= 1.25 * S:
                    K = float(s["strike_hint"])
                else:
                    off = -0.07 if itm else 0.07
                    K = S * (1 + off) if kind == "call" else S * (1 - off)
                sigma = max(rvol, 0.15) + 0.05
                exp_days = min(max(int(s["horizon"] * 1.5), 45), 120)
                expiry = date + pd.Timedelta(days=exp_days)
                prem = bs_price(S, K, exp_days / 365.0, sigma, RISK_FREE, kind)
                if prem < 0.05:
                    continue
                budget = notional * OPT_BUDGET_FRAC
                qty = max(round(budget / (prem * 100)) * 100, 100)
                cost = qty * prem * (1 + SPREAD_HAIRCUT)
                if cost > CAPITAL * 0.02:
                    continue
                cash -= cost
                p = Position(s, date, prem * (1 + SPREAD_HAIRCUT), qty,
                             opt={"kind": kind, "K": K, "expiry": expiry, "sigma": sigma},
                             trail_pct=0.40, pt=0.75)
            else:
                qty = notional / row.open
                qty = qty if long_dir else -qty
                fill = row.open * (1 + STOCK_SLIPPAGE * (1 if long_dir else -1))
                cash -= qty * fill
                p = Position(s, date, fill, qty, trail_pct=trail, pt=pt0)
            p.entry_qty = p.qty
            p.entry_rvol = rvol
            p.peak = p.entry_px
            open_pos.append(p)

        equity_curve.append((date, equity(date)))

    # force-close whatever is still open at end of data
    for p in list(open_pos):
        df = prices[p.sig["ticker"]]
        last = df.index[df.index <= END_DATE][-1]
        close_part(p, last, p.mark(df.loc[last], last), 1.0, "end_of_data")
        open_pos.remove(p)

    ec = pd.Series(dict(equity_curve)).sort_index()
    trades = pd.DataFrame(closed)
    os.makedirs(RESULTS, exist_ok=True)
    ec.to_csv(os.path.join(RESULTS, "equity_curve.csv"), header=["equity"])
    trades.drop(columns=["legs"]).to_csv(os.path.join(RESULTS, "trades.csv"), index=False)

    # ---- stats
    rets = ec.pct_change().dropna()
    span = (ec.index[-1] - ec.index[0]).days / 365.25
    spy_w = spy.loc[ec.index[0]:ec.index[-1], "close"]
    stats = {
        "start": str(ec.index[0].date()), "end": str(ec.index[-1].date()),
        "final_equity": round(ec.iloc[-1], 0),
        "total_return": round(ec.iloc[-1] / CAPITAL - 1, 4),
        "annualized": round((ec.iloc[-1] / CAPITAL) ** (1 / span) - 1, 4),
        "sharpe": round(rets.mean() / rets.std() * math.sqrt(252), 2) if rets.std() else None,
        "max_drawdown": round((ec / ec.cummax() - 1).min(), 4),
        "spy_return_same_period": round(spy_w.iloc[-1] / spy_w.iloc[0] - 1, 4),
        "n_trades": len(trades),
        "win_rate": round((trades.pnl > 0).mean(), 3),
        "avg_win": round(trades[trades.pnl > 0].pnl.mean(), 0),
        "avg_loss": round(trades[trades.pnl <= 0].pnl.mean(), 0),
        "profit_factor": round(trades[trades.pnl > 0].pnl.sum()
                               / -trades[trades.pnl <= 0].pnl.sum(), 2),
    }
    by = {}
    for col, buck in [("direction", None), ("instrument", None),
                      ("confidence", pd.cut(trades.confidence, [0.4, 0.6, 0.8, 1.0])),
                      ("risk", pd.cut(trades.risk, [0, 3, 6, 10]))]:
        g = trades.groupby(buck if buck is not None else col, observed=True)
        by[col] = g.agg(n=("pnl", "size"), total_pnl=("pnl", "sum"),
                        win_rate=("pnl", lambda x: round((x > 0).mean(), 3)),
                        avg_ret=("ret", "mean")).round(3).reset_index().astype(str) \
                   .to_dict("records")
    with open(os.path.join(RESULTS, "stats.json"), "w") as f:
        json.dump({"stats": stats, "breakdowns": by}, f, indent=2, default=str)
    print(json.dumps(stats, indent=2))
    return ec, trades


if __name__ == "__main__":
    run()
