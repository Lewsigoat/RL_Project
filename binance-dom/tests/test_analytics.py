import math

import pytest

from dom.analytics import (
    OrderBook,
    analyze,
    detect_walls,
    imbalance,
    market_order_fill,
    microprice,
    qty_within_bps,
    spread_bps,
)
from dom.client import snap_depth_limit, stream_url


def make_book(bids=None, asks=None):
    bids = bids or [["100.0", "2"], ["99.5", "1"], ["99.0", "1"], ["98.0", "1"], ["97.0", "1"]]
    asks = asks or [["100.5", "1"], ["101.0", "1"], ["101.5", "1"], ["102.0", "1"], ["103.0", "1"]]
    return OrderBook.from_binance("testusdt", {"lastUpdateId": 1, "bids": bids, "asks": asks})


def test_from_binance_sorts_and_drops_zero_qty():
    book = OrderBook.from_binance("x", {"bids": [["99", "1"], ["100", "0"], ["100.5", "3"]], "asks": [["102", "1"], ["101", "2"]]})
    assert book.symbol == "X"
    assert book.bids == [(100.5, 3.0), (99.0, 1.0)]
    assert book.asks == [(101.0, 2.0), (102.0, 1.0)]


def test_mid_spread_microprice():
    book = make_book()
    assert book.mid == 100.25
    assert spread_bps(book) == pytest.approx(0.5 / 100.25 * 1e4)
    # bid size 2 vs ask size 1 -> microprice leans towards the ask
    mp = microprice(book)
    assert mp == pytest.approx((100.5 * 2 + 100.0 * 1) / 3)
    assert mp > book.mid


def test_imbalance_bounds():
    assert imbalance(1, 1) == 0
    assert imbalance(3, 1) == 0.5
    assert imbalance(0, 5) == -1
    assert imbalance(0, 0) == 0


def test_qty_within_bps():
    book = make_book()
    # 100 bps of 100.25 = ~1.0025 -> bids at 100.0 and 99.5 qualify (dist .25, .75); 99.0 is 1.25 away
    qty, notional = qty_within_bps(book.bids, book.mid, 100, "bid")
    assert qty == 3
    assert notional == pytest.approx(100.0 * 2 + 99.5)


def test_market_order_fill_walks_book():
    book = make_book()
    fill = market_order_fill(book.asks, 150.0)  # 100.5*1 = 100.5, then 49.5 at 101
    assert fill["fully_filled"] == 1.0
    assert fill["worst_price"] == 101.0
    assert fill["filled_qty"] == pytest.approx(1 + 49.5 / 101.0)
    assert 100.5 < fill["avg_price"] < 101.0

    partial = market_order_fill(book.asks, 1e9)
    assert partial["fully_filled"] == 0.0
    assert partial["filled_qty"] == 5

    empty = market_order_fill([], 100)
    assert empty["avg_price"] is None


def test_detect_walls():
    bids = [(100.0, 1.0), (99.0, 1.0), (98.0, 1.0), (97.0, 10.0), (96.0, 1.0)]
    walls = detect_walls(bids, 100.5, "bid", ratio=4.0)
    assert len(walls) == 1
    assert walls[0].price == 97.0
    assert walls[0].ratio_to_median == 10.0
    assert walls[0].distance_bps == pytest.approx((100.5 - 97) / 100.5 * 1e4)
    assert detect_walls(bids[:3], 100.5, "bid") == []
    # dust book: 4x median but only a tiny share of the side -> not a wall
    dust = [(100.0, 0.001), (99.0, 0.001), (98.0, 0.005), (97.0, 100.0), (96.0, 0.001)]
    assert [w.price for w in detect_walls(dust, 100.5, "bid")] == [97.0]


def test_analyze_end_to_end():
    book = make_book()
    a = analyze(book, top_n=5)
    d = a.to_dict()
    assert d["symbol"] == "TESTUSDT"
    assert d["imbalance_top"] == pytest.approx(imbalance(6, 5))
    assert set(d["imbalance_bands"]) == {"5", "10", "25", "50", "100"}
    assert d["bid_depth_notional"] == pytest.approx(200 + 99.5 + 99 + 98 + 97)
    assert len(d["cumulative_bids"]) == 5
    assert d["cumulative_asks"][-1]["cum_qty"] == 5
    assert d["slippage"]["1000"]["buy_fully_filled"] == 0.0  # only ~508 notional on the ask side
    assert d["slippage"]["1000"]["buy_slippage_bps"] > 0
    assert d["signal"] in {"balanced", "mild buy pressure", "strong bid support / buy pressure", "mild sell pressure", "strong ask pressure / sell pressure"}
    assert all(not math.isnan(v) for v in d["imbalance_bands"].values())


def test_analyze_requires_both_sides():
    with pytest.raises(ValueError):
        analyze(OrderBook("X", bids=[(1.0, 1.0)], asks=[]))


def test_client_helpers():
    assert snap_depth_limit(7) == 10
    assert snap_depth_limit(100) == 100
    assert snap_depth_limit(99999) == 5000
    assert stream_url("BTCUSDT", levels=20, host="wss://h/ws") == "wss://h/ws/btcusdt@depth20@100ms"
    assert stream_url("ethusdt", levels=50, speed_ms=1000, host="wss://h/ws") == "wss://h/ws/ethusdt@depth20@1000ms"
