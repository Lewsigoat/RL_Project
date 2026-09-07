"""One-shot terminal view of an order book: ``python -m dom BTCUSDT --limit 50``."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .analytics import DepthAnalysis, OrderBook, analyze
from .client import BinanceClient, BinanceError


def _fmt(x: float | None, nd: int = 2) -> str:
    return "-" if x is None else f"{x:,.{nd}f}"


def render(a: DepthAnalysis, book: OrderBook, ladder: int) -> str:
    lines = [
        f"{a.symbol}  mid {_fmt(a.mid, 4)}  spread {_fmt(a.spread, 4)} ({a.spread_bps:.3f} bps)",
        f"microprice {_fmt(a.microprice, 4)}  skew {a.microprice_skew_bps:+.2f} bps  ->  {a.signal.upper()}",
        "",
        f"imbalance top-N: {a.imbalance_top:+.3f}   " + "  ".join(f"{k}bps: {v:+.2f}" for k, v in a.imbalance_bands.items()),
        f"depth ({a.levels} lvls)  bids {_fmt(a.bid_depth_notional, 0)}  asks {_fmt(a.ask_depth_notional, 0)} (quote ccy)",
        "",
        "market-order slippage (bps):",
    ]
    for size, s in a.slippage.items():
        b = s["buy_slippage_bps"]
        se = s["sell_slippage_bps"]
        bflag = "" if s["buy_fully_filled"] else " (partial)"
        sflag = "" if s["sell_fully_filled"] else " (partial)"
        lines.append(f"  {float(size):>12,.0f}   buy {_fmt(b)}{bflag:<10} sell {_fmt(se)}{sflag}")
    if a.walls:
        lines += ["", "walls (>= ratio x median size):"]
        for w in a.walls[:6]:
            lines.append(f"  {w.side:<3} {w.price:>14,.4f}  qty {w.quantity:>12,.4f}  x{w.ratio_to_median:.1f}  {w.distance_bps:.1f} bps away")
    lines += ["", f"{'BID QTY':>14} {'BID':>14} | {'ASK':<14} {'ASK QTY':<14}"]
    for i in range(min(ladder, len(book.bids), len(book.asks))):
        bp, bq = book.bids[i]
        ap, aq = book.asks[i]
        lines.append(f"{bq:>14,.4f} {bp:>14,.4f} | {ap:<14,.4f} {aq:<14,.4f}")
    return "\n".join(lines)


async def _run(symbol: str, limit: int, top_n: int, as_json: bool, ladder: int) -> int:
    client = BinanceClient()
    try:
        raw = await client.depth(symbol, limit)
    except BinanceError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        await client.aclose()
    book = OrderBook.from_binance(symbol, raw)
    analysis = analyze(book, top_n=top_n, include_cumulative=as_json)
    if as_json:
        print(json.dumps(analysis.to_dict(), indent=2))
    else:
        print(render(analysis, book, ladder))
    return 0


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m dom", description="Analyse a Binance order book")
    p.add_argument("symbol", help="e.g. BTCUSDT")
    p.add_argument("--limit", type=int, default=100, help="depth levels to fetch (5..5000)")
    p.add_argument("--top-n", type=int, default=5, help="levels for top-of-book imbalance")
    p.add_argument("--ladder", type=int, default=10, help="rows of the ladder to print")
    p.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = p.parse_args(argv)
    sys.exit(asyncio.run(_run(args.symbol, args.limit, args.top_n, args.json, args.ladder)))


if __name__ == "__main__":
    main()
