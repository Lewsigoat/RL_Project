# Motley Fool article-sentiment backtest

Backtests a "buy bullish articles / short bearish articles" strategy on Motley Fool
(fool.com) content, with LLM-labeled signals, confidence/risk-scaled position sizing,
optional ITM/OTM options, ATR trailing stops, and ratcheting profit takers.

## Pipeline

1. **Corpus** (`build_corpus.py`) — parsed fool.com monthly sitemaps for Feb–Apr 2026
   (10,882 `/investing/` articles), stratified-sampled 1,500 evenly across 89
   publication days, fetched and extracted 1,427 usable article texts (article body,
   title, linked tickers). Article text itself is not committed (copyright); the
   derived labels are.
2. **Labeling** — a team of 50 LLM agents (one per ~29-article batch) labeled every
   article: article type (recap vs forward thesis vs listicle...), and 0–3 signals per
   article. A signal exists only when a stock is the actual subject of a
   forward-looking authorial view — incidental ticker mentions and backward-looking
   recaps get no signal. Per signal: ticker, direction, confidence 0–1, risk 1–10,
   instrument (`stock`, `itm_call`, `otm_call`, `itm_put`, `otm_put`), strike hint
   (price levels quoted in the article), horizon. Result: 1,207 actionable signals on
   383 tickers.
3. **Audit** — 5 independent auditor agents re-read every high-impact signal
   (confidence ≥ 0.8 or an options instrument) against the source article and could
   veto or adjust it. Corrections are applied by `merge_labels.py` →
   `data/labels.jsonl`.
4. **Prices** (`fetch_prices.py`) — daily OHLCV per ticker from Nasdaq's public API
   (validated against IBKR closes), Sep 2025 → Jul 17 2026, in `data/prices/`.
5. **Backtest** (`backtest.py`) — see below. Outputs in `results/`
   (`report.md`, `stats.json`, `equity_curve.csv`, `trades.csv`, `summary.png`).
6. **Report** (`make_report.py`) — charts + markdown report.

## Strategy rules

- **Entry**: next trading day's open after publication. Duplicate same-day
  ticker+direction signals are merged (highest confidence wins).
- **Sizing**: notional = $1M × 2% × conf_weight × risk_weight, where conf_weight
  scales from 0.1→1.0 over confidence 0.3→1.0 and risk_weight = (11 − risk)/10.
  Options get 35% of the stock-equivalent notional as premium budget (leverage-aware).
  Signals below 0.40 confidence are not traded. Max gross exposure 150%.
- **Options**: modeled with Black-Scholes on 60-day realized vol (+5 pt IV markup,
  5% premium haircut per leg as spread cost) — no historical option quotes are
  available, so this is an approximation. Strike = article's price level when quoted
  (e.g. "if it holds $20" → $20 strike), else ±7% ITM/OTM. Expiry ≈ 1.5× horizon,
  45–120 days. Bearish theses use puts or short stock.
- **Trailing stop**: 2.5 × ATR(14) at entry, clipped to 8–18% (40% on option
  premium), trailed from the most favorable mark.
- **Profit taker (adaptive)**: initial threshold max(12%, 1.3 × trail) for stock,
  75% for options. On hit: take 1/3 off, re-arm one step higher, tighten the trail
  by 25% — so winners are partially banked and the rest rides with tighter risk.
  Position risk is also re-assessed weekly: if realized vol has doubled since entry,
  the trail tightens further.
- **Time stop**: the label's horizon (10–90 trading days); options exit at expiry.
- **Benchmark**: SPY over the same window.

## Walk-forward filter test (`tune_filters.py`)

Signals are split chronologically 70/30 (split date 2026-04-02). A pre-registered
grid of signal filters (long-only, min confidence, max risk, options on/off,
thesis-articles-only) is scored on the train window by Sharpe (min 40 trades),
frozen, and evaluated once on the test window. See `results/oos_report.md`.
Chosen filters: long-only, confidence ≥ 0.7, risk ≤ 7, stock-only. Out-of-sample:
+9.4% (Sharpe 5.3, max DD −0.9%, PF 6.2, 113 trades) vs unfiltered +15.5%
(Sharpe 4.9) and SPY +12.8% in the same window — note the test window landed in a
strong rebound, flattering all long exposure; the filters trade absolute return
for much better risk-adjusted numbers.

## Caveats

- 13.8% stratified sample of the period's articles, not the full firehose.
- Option P&L is model-derived (Black-Scholes on realized vol), not from traded
  option prices; real fills would differ, especially around earnings IV crush.
- Publication timestamps are date-granular; entry at next open avoids lookahead but
  may give up intraday drift.
- No borrow costs on shorts; no dividends; simple slippage assumptions.
- 8 tickers had no fetchable history and their signals were skipped: LC and SATS
  (renamed/delisted per Nasdaq) and 6 OTC ADRs (ADYEY, BYDDY, GTBIF, NTDOY,
  RHHBY, RNMBY).

## Reproduce

```bash
python3 build_corpus.py sample && python3 build_corpus.py   # corpus (needs scratchpad)
# ... run labeling/audit agents ...
python3 merge_labels.py <scratchpad>
python3 fetch_prices.py <scratchpad>/tickers.txt data/prices
python3 backtest.py
python3 make_report.py
```
