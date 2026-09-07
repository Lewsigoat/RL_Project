# Binance DOM Interpreter

A Streamlit app that pulls live **depth-of-market (order book)** data from the
Binance public API for any ticker you choose and interprets it: spread,
imbalance, depth chart, buy/sell walls, and market-order slippage estimates.

## Features

- **Ticker choice** — searchable dropdown of every trading spot symbol,
  sorted by 24h quote volume, filterable by quote asset (USDT, FDUSD, USDC,
  BTC, ETH, ...).
- **Order book ladder** — bids/asks side by side with visual depth bars and
  cumulative size.
- **Depth chart** — cumulative quote depth vs distance from mid price.
- **Interpretation panel** — plain-English read of spread, ±0.5%/±2% depth
  imbalance, and the largest walls (potential support/resistance).
- **Walls detection** — levels whose size exceeds a configurable multiple of
  the median level size.
- **Market impact estimator** — walks the book to compute VWAP and slippage
  for a hypothetical market buy/sell of a given quote size.
- **Auto-refresh** — optional live polling every 2–60 s.
- **Endpoint selector** — defaults to `data-api.binance.vision` (Binance.com
  market data, no key needed, works where `api.binance.com` is geo-blocked);
  Binance.US also available.

## Quick start

```bash
cd binance-dom
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501.

## Project layout

| File | Purpose |
| --- | --- |
| `binance_client.py` | REST client for Binance public market data (no API key needed) |
| `dom_analysis.py` | Pure interpretation functions: spread, imbalance, walls, slippage |
| `app.py` | Streamlit UI |

## Notes

- All endpoints used are public market data; no Binance account or API key is
  required.
- The book snapshot is REST-based (`GET /api/v3/depth`), so it reflects the
  moment of the fetch. Enable auto-refresh for a near-live view.
- This is an analytics tool, not financial advice.
