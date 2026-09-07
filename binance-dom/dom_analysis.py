"""Interpretation logic for Binance depth-of-market (order book) data.

All functions are pure and operate on plain sequences of (price, qty) tuples
so they are easy to unit-test and reuse outside the Streamlit app.
"""

from __future__ import annotations

import pandas as pd

from binance_client import OrderBook


def to_frame(levels: list[tuple[float, float]]) -> pd.DataFrame:
    df = pd.DataFrame(levels, columns=["price", "qty"])
    df["quote"] = df["price"] * df["qty"]  # size denominated in quote currency
    return df


def best_prices(book: OrderBook) -> tuple[float, float]:
    return book.bids[0][0], book.asks[0][0]


def spread_metrics(book: OrderBook) -> dict:
    bid, ask = best_prices(book)
    mid = (bid + ask) / 2
    spread = ask - bid
    return {
        "best_bid": bid,
        "best_ask": ask,
        "mid": mid,
        "spread": spread,
        "spread_bps": (spread / mid) * 1e4 if mid else 0.0,
    }


def depth_within_pct(book: OrderBook, pct: float) -> dict:
    """Quote-denominated depth within +/-pct% of the mid price, plus imbalance.

    Imbalance is (bid - ask) / (bid + ask): +1 means all bids, -1 all asks.
    """
    mid = spread_metrics(book)["mid"]
    lo, hi = mid * (1 - pct / 100), mid * (1 + pct / 100)
    bids = to_frame(book.bids)
    asks = to_frame(book.asks)
    bid_depth = bids.loc[bids["price"] >= lo, "quote"].sum()
    ask_depth = asks.loc[asks["price"] <= hi, "quote"].sum()
    total = bid_depth + ask_depth
    return {
        "band_pct": pct,
        "bid_depth_quote": float(bid_depth),
        "ask_depth_quote": float(ask_depth),
        "imbalance": float((bid_depth - ask_depth) / total) if total else 0.0,
    }


def top_n_imbalance(book: OrderBook, n: int = 10) -> float:
    """Imbalance across the top N levels on each side."""
    bids = to_frame(book.bids).head(n)["quote"].sum()
    asks = to_frame(book.asks).head(n)["quote"].sum()
    total = bids + asks
    return float((bids - asks) / total) if total else 0.0


def cumulative_depth(book: OrderBook, max_pct: float = 5.0, points: int = 60) -> pd.DataFrame:
    """Cumulative quote depth vs distance from mid, for both sides.

    Returns a long-form frame: side ('Bids'/'Asks'), pct_from_mid, cum_quote.
    """
    mid = spread_metrics(book)["mid"]
    rows = []
    for side, levels in (("Bids", book.bids), ("Asks", book.asks)):
        df = to_frame(levels)
        df["pct_from_mid"] = (df["price"] - mid).abs() / mid * 100
        df = df[df["pct_from_mid"] <= max_pct]
        df["cum_quote"] = df["quote"].cumsum()
        rows.append(df[["pct_from_mid", "cum_quote"]].assign(side=side))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def detect_walls(
    levels: list[tuple[float, float]], multiplier: float = 5.0, min_levels: int = 8
) -> pd.DataFrame:
    """Levels whose quote size exceeds multiplier x median level size."""
    df = to_frame(levels)
    if len(df) < min_levels:
        return df.iloc[0:0].assign(size_vs_median=pd.Series(dtype=float))
    median = df["quote"].median()
    walls = df[df["quote"] >= multiplier * median].copy()
    walls["size_vs_median"] = walls["quote"] / median
    return walls.sort_values("quote", ascending=False).reset_index(drop=True)


def estimate_market_order(
    levels: list[tuple[float, float]], quote_amount: float
) -> dict:
    """Walk the book to price a market order of `quote_amount` quote currency.

    Returns VWAP, slippage vs the best price, and how much of the order the
    visible book can fill.
    """
    df = to_frame(levels)
    best = df["price"].iloc[0]
    remaining = quote_amount
    cost_base = 0.0
    for price, qty in zip(df["price"], df["qty"]):
        level_quote = price * qty
        take = min(level_quote, remaining)
        cost_base += take / price
        remaining -= take
        if remaining <= 0:
            break
    filled = quote_amount - remaining
    vwap = filled / cost_base if cost_base else 0.0
    return {
        "requested_quote": quote_amount,
        "filled_quote": float(filled),
        "fill_pct": float(filled / quote_amount * 100) if quote_amount else 0.0,
        "vwap": float(vwap),
        "slippage_bps": float(abs(vwap - best) / best * 1e4) if best else 0.0,
        "fully_filled": bool(remaining <= 1e-9),
    }


def interpret(book: OrderBook, wall_multiplier: float = 5.0) -> list[str]:
    """Plain-English read of the book, shown as bullet points in the UI."""
    m = spread_metrics(book)
    out = [
        f"Spread is {m['spread']:.6g} ({m['spread_bps']:.2f} bps of mid) — "
        + ("tight, liquid top of book." if m["spread_bps"] < 2 else
           "moderate." if m["spread_bps"] < 10 else "wide; expect meaningful crossing cost.")
    ]
    for pct in (0.5, 2.0):
        d = depth_within_pct(book, pct)
        imb = d["imbalance"]
        direction = "bid-heavy (buyers stacking)" if imb > 0.1 else \
                    "ask-heavy (sellers stacking)" if imb < -0.1 else "balanced"
        out.append(
            f"Within ±{pct}% of mid: {direction} — imbalance {imb:+.2f}, "
            f"bids ${d['bid_depth_quote']:,.0f} vs asks ${d['ask_depth_quote']:,.0f}."
        )
    bid_walls = detect_walls(book.bids, wall_multiplier)
    ask_walls = detect_walls(book.asks, wall_multiplier)
    if not bid_walls.empty:
        w = bid_walls.iloc[0]
        out.append(f"Largest bid wall: ${w['quote']:,.0f} at {w['price']:,.6g} "
                   f"({w['size_vs_median']:.1f}× median level) — potential support.")
    if not ask_walls.empty:
        w = ask_walls.iloc[0]
        out.append(f"Largest ask wall: ${w['quote']:,.0f} at {w['price']:,.6g} "
                   f"({w['size_vs_median']:.1f}× median level) — potential resistance.")
    if bid_walls.empty and ask_walls.empty:
        out.append(f"No walls ≥ {wall_multiplier}× median level size detected.")
    return out
