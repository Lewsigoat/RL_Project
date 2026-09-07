"""Thin client for Binance public market-data REST endpoints.

No API key is required for any endpoint used here. The default base URL is
Binance's market-data-only host (data-api.binance.vision), which serves the
full Binance.com order book and is reachable from regions where
api.binance.com returns HTTP 451.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

BASE_URLS = {
    "Binance.com market data (data-api.binance.vision)": "https://data-api.binance.vision",
    "Binance.US (api.binance.us)": "https://api.binance.us",
    "Binance.com (api.binance.com)": "https://api.binance.com",
}

DEFAULT_BASE_URL = BASE_URLS["Binance.com market data (data-api.binance.vision)"]

DEPTH_LIMITS = [5, 10, 20, 50, 100, 500, 1000, 5000]


class BinanceAPIError(RuntimeError):
    """Raised when the Binance API returns a non-200 response."""


@dataclass
class OrderBook:
    symbol: str
    last_update_id: int
    bids: list[tuple[float, float]]  # (price, qty) descending by price
    asks: list[tuple[float, float]]  # (price, qty) ascending by price
    fetched_at: float


class BinanceClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "binance-dom-interpreter/1.0"})

    def _get(self, path: str, params: dict | None = None):
        url = f"{self.base_url}{path}"
        resp = self._session.get(url, params=params, timeout=self.timeout)
        if resp.status_code != 200:
            raise BinanceAPIError(f"GET {url} -> HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def ping(self) -> bool:
        self._get("/api/v3/ping")
        return True

    def get_symbols(self, quote_assets: tuple[str, ...] = ("USDT",)) -> list[str]:
        """All TRADING spot symbols for the given quote assets, sorted."""
        info = self._get("/api/v3/exchangeInfo")
        symbols = [
            s["symbol"]
            for s in info["symbols"]
            if s["status"] == "TRADING" and s["quoteAsset"] in quote_assets
        ]
        return sorted(symbols)

    def get_24h_tickers(self, quote_assets: tuple[str, ...] = ("USDT",)) -> list[dict]:
        """24h ticker stats for every symbol, filtered by quote asset."""
        data = self._get("/api/v3/ticker/24hr")
        return [t for t in data if any(t["symbol"].endswith(q) for q in quote_assets)]

    def get_price(self, symbol: str) -> float:
        data = self._get("/api/v3/ticker/price", {"symbol": symbol})
        return float(data["price"])

    def get_order_book(self, symbol: str, limit: int = 100) -> OrderBook:
        if limit not in DEPTH_LIMITS:
            raise ValueError(f"limit must be one of {DEPTH_LIMITS}")
        data = self._get("/api/v3/depth", {"symbol": symbol, "limit": limit})
        return OrderBook(
            symbol=symbol,
            last_update_id=data["lastUpdateId"],
            bids=[(float(p), float(q)) for p, q in data["bids"]],
            asks=[(float(p), float(q)) for p, q in data["asks"]],
            fetched_at=time.time(),
        )
