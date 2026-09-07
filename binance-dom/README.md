# Binance DOM

Live depth-of-market (order book) interpreter for any Binance spot ticker.
A small FastAPI backend pulls the book from Binance, runs it through a set of
pure-Python analytics, and streams the result to a single-page dashboard over a
WebSocket. The same analytics work from the CLI or a notebook.

## What it shows

| Metric | Meaning |
| --- | --- |
| Mid / spread (bps) | Best bid/ask midpoint and how wide the book is |
| Microprice + skew | Size-weighted mid; positive skew = price leaning up |
| Imbalance (top-N) | `(bid - ask) / (bid + ask)` over the top N levels, in [-1, 1] |
| Imbalance by distance | Same, but for everything resting within 5 / 10 / 25 / 50 / 100 bps of mid |
| Market-order slippage | Avg fill vs mid (bps) for 1K / 10K / 100K / 1M quote-currency market orders |
| Walls | Levels at least 4x the median size on their side |
| Cumulative depth chart | Classic stepped bid/ask liquidity curve |
| Imbalance history | Sparkline of top-N imbalance over the session |
| Read | Coarse label (`balanced`, `mild buy pressure`, ...) from imbalance + microprice skew |

## Run

```bash
cd binance-dom
pip install -r requirements.txt
python -m dom            # http://127.0.0.1:8000
```

Pick a quote asset, type or select a ticker, choose depth levels and hit
Connect. 5/10/20 levels use Binance's `@depth20@100ms` stream (live);
50+ levels poll the REST snapshot endpoint instead.

### CLI

```bash
python -m dom BTCUSDT --limit 100          # table
python -m dom ETHUSDT --limit 500 --json   # full analysis as JSON
```

### From Python

```python
from dom import OrderBook, analyze
import httpx

raw = httpx.get("https://data-api.binance.vision/api/v3/depth", params={"symbol": "BTCUSDT", "limit": 100}).json()
book = OrderBook.from_binance("BTCUSDT", raw)
a = analyze(book, top_n=5)
print(a.signal, a.imbalance_top, a.slippage["100000"])
```

## API

- `GET /api/symbols?quote=USDT&q=BTC` - tradable symbols (cached 10 min)
- `GET /api/depth?symbol=BTCUSDT&limit=100` - raw Binance snapshot
- `GET /api/analysis?symbol=BTCUSDT&limit=100&top_n=5` - snapshot + analytics
- `GET /api/ticker?symbol=BTCUSDT` - 24h stats
- `WS  /ws/{symbol}?levels=20&interval_ms=250&top_n=5` - streamed `{bids, asks, analysis}`

## Endpoints and geo-blocking

`api.binance.com` returns HTTP 451 in some regions. The client tries
`data-api.binance.vision` (Binance's public market-data mirror) first, then
falls back. Override the host list if needed:

```bash
BINANCE_REST_URLS=https://api.binance.us BINANCE_WS_URLS=wss://stream.binance.us:9443/ws python -m dom
```

## Tests

```bash
pytest
```
