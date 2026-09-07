"""Order-book (depth of market) analytics.

Pure functions over a parsed :class:`OrderBook`. No I/O, so everything here is
easy to reuse from a notebook or unit test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Any, Iterable, Sequence

Level = tuple[float, float]  # (price, quantity)


@dataclass
class OrderBook:
    symbol: str
    bids: list[Level]  # sorted descending by price
    asks: list[Level]  # sorted ascending by price
    last_update_id: int | None = None
    timestamp_ms: int | None = None

    @classmethod
    def from_binance(cls, symbol: str, payload: dict[str, Any], timestamp_ms: int | None = None) -> "OrderBook":
        """Build from a Binance ``/api/v3/depth`` or ``@depthN`` stream payload."""
        bids = sorted(((float(p), float(q)) for p, q in payload.get("bids", [])), key=lambda l: -l[0])
        asks = sorted(((float(p), float(q)) for p, q in payload.get("asks", [])), key=lambda l: l[0])
        return cls(
            symbol=symbol.upper(),
            bids=[l for l in bids if l[1] > 0],
            asks=[l for l in asks if l[1] > 0],
            last_update_id=payload.get("lastUpdateId"),
            timestamp_ms=timestamp_ms,
        )

    @property
    def best_bid(self) -> Level | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Level | None:
        return self.asks[0] if self.asks else None

    @property
    def mid(self) -> float | None:
        if not self.bids or not self.asks:
            return None
        return (self.bids[0][0] + self.asks[0][0]) / 2


@dataclass
class Wall:
    side: str  # "bid" | "ask"
    price: float
    quantity: float
    notional: float
    ratio_to_median: float
    distance_bps: float


@dataclass
class DepthAnalysis:
    symbol: str
    mid: float
    spread: float
    spread_bps: float
    microprice: float
    microprice_skew_bps: float
    imbalance_top: float
    imbalance_bands: dict[str, float]
    bid_notional_bands: dict[str, float]
    ask_notional_bands: dict[str, float]
    bid_depth_qty: float
    ask_depth_qty: float
    bid_depth_notional: float
    ask_depth_notional: float
    slippage: dict[str, dict[str, float | None]]
    walls: list[Wall]
    levels: int
    signal: str
    cumulative_bids: list[dict[str, float]] = field(default_factory=list)
    cumulative_asks: list[dict[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "mid": self.mid,
            "spread": self.spread,
            "spread_bps": self.spread_bps,
            "microprice": self.microprice,
            "microprice_skew_bps": self.microprice_skew_bps,
            "imbalance_top": self.imbalance_top,
            "imbalance_bands": self.imbalance_bands,
            "bid_notional_bands": self.bid_notional_bands,
            "ask_notional_bands": self.ask_notional_bands,
            "bid_depth_qty": self.bid_depth_qty,
            "ask_depth_qty": self.ask_depth_qty,
            "bid_depth_notional": self.bid_depth_notional,
            "ask_depth_notional": self.ask_depth_notional,
            "slippage": self.slippage,
            "walls": [w.__dict__ for w in self.walls],
            "levels": self.levels,
            "signal": self.signal,
            "cumulative_bids": self.cumulative_bids,
            "cumulative_asks": self.cumulative_asks,
        }


# ---------------------------------------------------------------------------
# Primitive metrics
# ---------------------------------------------------------------------------


def spread_bps(book: OrderBook) -> float:
    mid = book.mid
    if mid is None or mid == 0:
        return 0.0
    return (book.asks[0][0] - book.bids[0][0]) / mid * 1e4


def microprice(book: OrderBook) -> float | None:
    """Size-weighted mid. Leans towards the side with *less* resting size,
    which is where price is statistically more likely to move."""
    if not book.bids or not book.asks:
        return None
    bp, bq = book.bids[0]
    ap, aq = book.asks[0]
    if bq + aq == 0:
        return (bp + ap) / 2
    return (ap * bq + bp * aq) / (bq + aq)


def imbalance(bid_qty: float, ask_qty: float) -> float:
    """(bid - ask) / (bid + ask) in [-1, 1]. Positive = more bids (buy pressure)."""
    total = bid_qty + ask_qty
    return 0.0 if total == 0 else (bid_qty - ask_qty) / total


def qty_within_bps(levels: Sequence[Level], mid: float, bps: float, side: str) -> tuple[float, float]:
    """Return (quantity, notional) resting within ``bps`` of ``mid`` on one side."""
    limit = mid * bps / 1e4
    qty = notional = 0.0
    for price, q in levels:
        dist = mid - price if side == "bid" else price - mid
        if dist > limit:
            break
        qty += q
        notional += q * price
    return qty, notional


def cumulative(levels: Iterable[Level]) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    cq = cn = 0.0
    for price, q in levels:
        cq += q
        cn += q * price
        out.append({"price": price, "qty": q, "cum_qty": cq, "cum_notional": cn})
    return out


def market_order_fill(levels: Sequence[Level], notional: float) -> dict[str, float | None]:
    """Walk the book as a market order of ``notional`` (quote currency) would.

    Returns avg fill price, worst price touched, base quantity filled and
    whether the book had enough depth. ``avg_price`` is ``None`` if nothing fills.
    """
    remaining = notional
    filled_qty = 0.0
    spent = 0.0
    worst = None
    for price, q in levels:
        if remaining <= 0:
            break
        take_notional = min(remaining, price * q)
        take_qty = take_notional / price
        filled_qty += take_qty
        spent += take_notional
        remaining -= take_notional
        worst = price
    avg = spent / filled_qty if filled_qty else None
    return {
        "avg_price": avg,
        "worst_price": worst,
        "filled_qty": filled_qty,
        "filled_notional": spent,
        "fully_filled": 1.0 if remaining <= 1e-9 else 0.0,
    }


def detect_walls(
    levels: Sequence[Level],
    mid: float,
    side: str,
    ratio: float = 4.0,
    min_levels: int = 5,
    min_share: float = 0.10,
) -> list[Wall]:
    """Flag levels whose size is ``ratio`` x the median size on that side *and*
    holds at least ``min_share`` of the visible size on that side. The share
    test stops dust-filled books (median ~0) from flagging everything."""
    if len(levels) < min_levels:
        return []
    med = median(q for _, q in levels)
    total = sum(q for _, q in levels)
    if med <= 0 or total <= 0:
        return []
    walls: list[Wall] = []
    for price, q in levels:
        r = q / med
        if r >= ratio and q / total >= min_share:
            dist = (mid - price if side == "bid" else price - mid) / mid * 1e4
            walls.append(Wall(side=side, price=price, quantity=q, notional=price * q, ratio_to_median=r, distance_bps=dist))
    walls.sort(key=lambda w: -w.notional)
    return walls


def classify(imb_top: float, imb_bands: dict[str, float], skew_bps: float) -> str:
    """Coarse, human-readable read of the book. Not trading advice."""
    near = imb_bands.get("10", imb_top)
    score = 0.5 * imb_top + 0.5 * near
    if score > 0.35 and skew_bps > 0:
        return "strong bid support / buy pressure"
    if score > 0.15:
        return "mild buy pressure"
    if score < -0.35 and skew_bps < 0:
        return "strong ask pressure / sell pressure"
    if score < -0.15:
        return "mild sell pressure"
    return "balanced"


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

DEFAULT_BANDS_BPS = (5.0, 10.0, 25.0, 50.0, 100.0)
DEFAULT_ORDER_SIZES = (1_000.0, 10_000.0, 100_000.0, 1_000_000.0)


def analyze(
    book: OrderBook,
    top_n: int = 5,
    bands_bps: Sequence[float] = DEFAULT_BANDS_BPS,
    order_sizes: Sequence[float] = DEFAULT_ORDER_SIZES,
    wall_ratio: float = 4.0,
    include_cumulative: bool = True,
) -> DepthAnalysis:
    if not book.bids or not book.asks:
        raise ValueError("order book must have at least one bid and one ask")

    mid = book.mid
    assert mid is not None
    spread = book.asks[0][0] - book.bids[0][0]
    mp = microprice(book) or mid
    skew_bps = (mp - mid) / mid * 1e4

    top_bid = sum(q for _, q in book.bids[:top_n])
    top_ask = sum(q for _, q in book.asks[:top_n])
    imb_top = imbalance(top_bid, top_ask)

    imb_bands: dict[str, float] = {}
    bid_bands: dict[str, float] = {}
    ask_bands: dict[str, float] = {}
    for b in bands_bps:
        bq, bn = qty_within_bps(book.bids, mid, b, "bid")
        aq, an = qty_within_bps(book.asks, mid, b, "ask")
        key = f"{b:g}"
        imb_bands[key] = imbalance(bq, aq)
        bid_bands[key] = bn
        ask_bands[key] = an

    bid_qty = sum(q for _, q in book.bids)
    ask_qty = sum(q for _, q in book.asks)
    bid_notional = sum(p * q for p, q in book.bids)
    ask_notional = sum(p * q for p, q in book.asks)

    slippage: dict[str, dict[str, float | None]] = {}
    for size in order_sizes:
        buy = market_order_fill(book.asks, size)
        sell = market_order_fill(book.bids, size)
        slippage[f"{size:g}"] = {
            "buy_avg_price": buy["avg_price"],
            "buy_slippage_bps": None if buy["avg_price"] is None else (buy["avg_price"] - mid) / mid * 1e4,
            "buy_fully_filled": buy["fully_filled"],
            "sell_avg_price": sell["avg_price"],
            "sell_slippage_bps": None if sell["avg_price"] is None else (mid - sell["avg_price"]) / mid * 1e4,
            "sell_fully_filled": sell["fully_filled"],
        }

    walls = detect_walls(book.bids, mid, "bid", wall_ratio) + detect_walls(book.asks, mid, "ask", wall_ratio)
    walls.sort(key=lambda w: -w.notional)

    return DepthAnalysis(
        symbol=book.symbol,
        mid=mid,
        spread=spread,
        spread_bps=spread / mid * 1e4,
        microprice=mp,
        microprice_skew_bps=skew_bps,
        imbalance_top=imb_top,
        imbalance_bands=imb_bands,
        bid_notional_bands=bid_bands,
        ask_notional_bands=ask_bands,
        bid_depth_qty=bid_qty,
        ask_depth_qty=ask_qty,
        bid_depth_notional=bid_notional,
        ask_depth_notional=ask_notional,
        slippage=slippage,
        walls=walls[:10],
        levels=max(len(book.bids), len(book.asks)),
        signal=classify(imb_top, imb_bands, skew_bps),
        cumulative_bids=cumulative(book.bids) if include_cumulative else [],
        cumulative_asks=cumulative(book.asks) if include_cumulative else [],
    )
