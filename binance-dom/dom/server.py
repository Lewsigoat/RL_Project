"""FastAPI app: REST endpoints + a WebSocket that streams analysed depth.

Run with ``uvicorn dom.server:app --reload`` or ``python -m dom``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import websockets
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .analytics import OrderBook, analyze
from .client import BadRequest, BinanceClient, BinanceError, stream_url, ws_urls

log = logging.getLogger("dom")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = BinanceClient()
    try:
        yield
    finally:
        await app.state.client.aclose()


app = FastAPI(title="Binance DOM", version="0.1.0", lifespan=lifespan)


def _client() -> BinanceClient:
    return app.state.client


def _analysis_payload(symbol: str, raw: dict[str, Any], top_n: int, wall_ratio: float, source: str) -> dict[str, Any]:
    ts = int(time.time() * 1000)
    book = OrderBook.from_binance(symbol, raw, timestamp_ms=ts)
    analysis = analyze(book, top_n=top_n, wall_ratio=wall_ratio)
    return {
        "symbol": book.symbol,
        "ts": ts,
        "source": source,
        "last_update_id": book.last_update_id,
        "bids": book.bids,
        "asks": book.asks,
        "analysis": analysis.to_dict(),
    }


# ---------------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------------


@app.get("/api/symbols")
async def api_symbols(quote: str | None = None, q: str | None = None, limit: int = Query(500, le=5000)):
    try:
        syms = await _client().symbols(quote=quote)
    except BadRequest as e:
        raise HTTPException(400, str(e))
    except BinanceError as e:
        raise HTTPException(502, str(e))
    if q:
        needle = q.upper()
        syms = [s for s in syms if needle in s["symbol"]]
    return {"count": len(syms), "symbols": syms[:limit]}


@app.get("/api/depth")
async def api_depth(symbol: str, limit: int = Query(100, ge=1, le=5000)):
    try:
        return await _client().depth(symbol, limit)
    except BadRequest as e:
        raise HTTPException(400, str(e))
    except BinanceError as e:
        raise HTTPException(502, str(e))


@app.get("/api/analysis")
async def api_analysis(
    symbol: str,
    limit: int = Query(100, ge=5, le=5000),
    top_n: int = Query(5, ge=1, le=100),
    wall_ratio: float = Query(4.0, ge=1.0),
):
    try:
        raw = await _client().depth(symbol, limit)
        return _analysis_payload(symbol, raw, top_n, wall_ratio, source="rest")
    except BadRequest as e:
        raise HTTPException(400, str(e))
    except BinanceError as e:
        raise HTTPException(502, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/ticker")
async def api_ticker(symbol: str):
    try:
        return await _client().ticker_24h(symbol)
    except BadRequest as e:
        raise HTTPException(400, str(e))
    except BinanceError as e:
        raise HTTPException(502, str(e))


# ---------------------------------------------------------------------------
# WebSocket: live analysed depth
# ---------------------------------------------------------------------------


async def _binance_stream(symbol: str, levels: int, queue: asyncio.Queue[dict[str, Any]], stop: asyncio.Event) -> None:
    """Pump raw depth payloads from Binance into ``queue``. Tries each WS host;
    raises if none can be reached so the caller can fall back to polling."""
    last_err: Exception | None = None
    for host in ws_urls():
        url = stream_url(symbol, levels=levels, host=host)
        try:
            async with websockets.connect(url, open_timeout=8, ping_interval=20) as ws:
                log.info("connected to %s", url)
                while not stop.is_set():
                    msg = await asyncio.wait_for(ws.recv(), timeout=30)
                    payload = json.loads(msg)
                    if "bids" in payload:
                        # Drop stale frames if the consumer is slower than 100ms.
                        while not queue.empty():
                            queue.get_nowait()
                        queue.put_nowait(payload)
                return
        except asyncio.CancelledError:
            raise
        except Exception as e:  # connection refused / 451 / timeout
            last_err = e
            log.warning("stream %s failed: %s", url, e)
    raise ConnectionError(f"no Binance WS host reachable: {last_err}")


async def _rest_poller(symbol: str, levels: int, queue: asyncio.Queue[dict[str, Any]], stop: asyncio.Event, interval: float) -> None:
    while not stop.is_set():
        try:
            payload = await _client().depth(symbol, levels)
            while not queue.empty():
                queue.get_nowait()
            queue.put_nowait(payload)
        except BinanceError as e:
            queue.put_nowait({"error": str(e)})
        await asyncio.sleep(interval)


@app.websocket("/ws/{symbol}")
async def ws_depth(
    websocket: WebSocket,
    symbol: str,
    levels: int = Query(20, ge=5, le=1000),
    interval_ms: int = Query(250, ge=100, le=5000),
    top_n: int = Query(5, ge=1, le=100),
    wall_ratio: float = Query(4.0, ge=1.0),
):
    await websocket.accept()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    stop = asyncio.Event()
    source = "binance-ws" if levels <= 20 else "rest-poll"

    async def producer() -> None:
        nonlocal source
        if source == "binance-ws":
            try:
                await _binance_stream(symbol, levels, queue, stop)
                return
            except ConnectionError as e:
                log.warning("falling back to REST polling for %s: %s", symbol, e)
                source = "rest-poll"
                await websocket.send_json({"type": "info", "message": "live stream unavailable, polling REST"})
        await _rest_poller(symbol, levels, queue, stop, interval=max(interval_ms, 500) / 1000)

    producer_task = asyncio.create_task(producer())
    last_sent = 0.0
    try:
        while True:
            payload = await queue.get()
            if "error" in payload:
                await websocket.send_json({"type": "error", "message": payload["error"]})
                continue
            now = time.monotonic()
            if now - last_sent < interval_ms / 1000:
                continue
            last_sent = now
            try:
                out = _analysis_payload(symbol, payload, top_n, wall_ratio, source)
            except ValueError as e:
                await websocket.send_json({"type": "error", "message": str(e)})
                continue
            out["type"] = "depth"
            await websocket.send_json(out)
    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001
        log.exception("ws error for %s", symbol)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:  # noqa: BLE001
            pass
    finally:
        stop.set()
        producer_task.cancel()
        try:
            await producer_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
