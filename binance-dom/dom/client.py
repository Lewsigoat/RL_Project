"""Thin Binance market-data client with endpoint fallback.

Binance geo-blocks ``api.binance.com`` in some regions (HTTP 451). The public
market-data mirror ``data-api.binance.vision`` serves the same read-only
endpoints, so we try a list of hosts in order. Override with the
``BINANCE_REST_URLS`` / ``BINANCE_WS_URLS`` environment variables
(comma-separated) to pin a specific host, e.g. ``https://api.binance.us``.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

DEFAULT_REST_URLS = (
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api1.binance.com",
)
DEFAULT_WS_URLS = (
    "wss://data-stream.binance.vision/ws",
    "wss://stream.binance.com:9443/ws",
)

VALID_DEPTH_LIMITS = (5, 10, 20, 50, 100, 500, 1000, 5000)
STREAM_DEPTH_LEVELS = (5, 10, 20)


def _env_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name)
    if not raw:
        return default
    return tuple(u.strip().rstrip("/") for u in raw.split(",") if u.strip())


def rest_urls() -> tuple[str, ...]:
    return _env_list("BINANCE_REST_URLS", DEFAULT_REST_URLS)


def ws_urls() -> tuple[str, ...]:
    return _env_list("BINANCE_WS_URLS", DEFAULT_WS_URLS)


def snap_depth_limit(limit: int) -> int:
    """Round up to the nearest limit Binance accepts."""
    for l in VALID_DEPTH_LIMITS:
        if limit <= l:
            return l
    return VALID_DEPTH_LIMITS[-1]


class BinanceError(RuntimeError):
    """Upstream unreachable or returned an unexpected error."""


class BadRequest(BinanceError):
    """Binance rejected the request (e.g. unknown symbol); retrying won't help."""


class BinanceClient:
    def __init__(self, timeout: float = 10.0, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "binance-dom/0.1"})
        self._preferred: str | None = None
        self._symbols_cache: tuple[float, list[dict[str, Any]]] | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        hosts = list(rest_urls())
        if self._preferred in hosts:
            hosts.remove(self._preferred)
            hosts.insert(0, self._preferred)
        last_err: Exception | None = None
        for host in hosts:
            try:
                r = await self._client.get(f"{host}{path}", params=params)
                if r.status_code == 451:
                    last_err = BinanceError(f"{host} unavailable in this region (451)")
                    continue
                if r.status_code == 400:
                    # Bad symbol etc. - no point retrying other hosts.
                    raise BadRequest(r.json().get("msg", r.text))
                r.raise_for_status()
                self._preferred = host
                return r.json()
            except BinanceError:
                raise
            except Exception as e:  # network / 5xx
                last_err = e
        raise BinanceError(f"all Binance hosts failed: {last_err}")

    async def depth(self, symbol: str, limit: int = 100) -> dict[str, Any]:
        return await self._get("/api/v3/depth", {"symbol": symbol.upper(), "limit": snap_depth_limit(limit)})

    async def symbols(self, quote: str | None = None, ttl: float = 600.0) -> list[dict[str, Any]]:
        """Trading symbols from exchangeInfo, cached for ``ttl`` seconds."""
        now = time.time()
        if self._symbols_cache is None or now - self._symbols_cache[0] > ttl:
            info = await self._get("/api/v3/exchangeInfo")
            syms = [
                {
                    "symbol": s["symbol"],
                    "base": s["baseAsset"],
                    "quote": s["quoteAsset"],
                    "tick_size": _tick_size(s),
                }
                for s in info.get("symbols", [])
                if s.get("status") == "TRADING" and s.get("isSpotTradingAllowed", True)
            ]
            syms.sort(key=lambda s: s["symbol"])
            self._symbols_cache = (now, syms)
        out = self._symbols_cache[1]
        if quote:
            out = [s for s in out if s["quote"] == quote.upper()]
        return out

    async def ticker_24h(self, symbol: str) -> dict[str, Any]:
        return await self._get("/api/v3/ticker/24hr", {"symbol": symbol.upper()})


def _tick_size(sym: dict[str, Any]) -> float | None:
    for f in sym.get("filters", []):
        if f.get("filterType") == "PRICE_FILTER":
            try:
                return float(f["tickSize"])
            except (KeyError, ValueError):
                return None
    return None


def stream_url(symbol: str, levels: int = 20, speed_ms: int = 100, host: str | None = None) -> str:
    levels = min(STREAM_DEPTH_LEVELS, key=lambda l: abs(l - levels))
    speed = "100ms" if speed_ms <= 100 else "1000ms"
    base = host or ws_urls()[0]
    return f"{base}/{symbol.lower()}@depth{levels}@{speed}"
