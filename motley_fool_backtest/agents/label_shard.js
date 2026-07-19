export const meta = {
  name: 'label-fool-shard',
  description: 'Label a shard of Motley Fool article batches',
  phases: [{ title: 'Label' }],
}

const A = typeof args === 'string' ? JSON.parse(args) : args
const SP = A.sp
const SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['batch', 'n_articles', 'n_signals'],
  properties: {
    batch: { type: 'integer' }, n_articles: { type: 'integer' }, n_signals: { type: 'integer' },
  },
}

const labelPrompt = (b) => {
  const bb = String(b).padStart(2, '0')
  return `You are one of 50 analysts labeling Motley Fool articles for a sentiment backtest (buy bullish, sell/short bearish). Precision matters more than recall: mislabeled tickers or fake "signals" from backward-looking news recaps poison the backtest.

Read the JSON file ${SP}/batches/batch_${bb}.json — an array of articles, each with fields id, date, url, title, tickers_linked, text.

For EACH article produce a label object:
- article_type: one of "recap" (backward-looking, e.g. "why X stock popped/dropped today/this week"), "forward_thesis", "listicle", "earnings_preview", "income_dividend", "macro_index", "educational_other".
- signals: array of 0-3 signal objects. A signal exists ONLY for a stock that is the actual subject of a forward-looking opinion by the author. Articles mention many tickers (peers, comparisons, index funds) — do NOT create signals for incidental mentions. Pure recaps, educational pieces, and macro musings usually have ZERO signals. Listicles ("3 stocks to buy now") get one signal per genuinely recommended stock, max 3 (pick the 3 with strongest conviction).
Each signal object:
  - primary_ticker: the US-listed ticker symbol as written in the text (e.g. "NVTS"). If the discussed listing is not a plain US-listed stock/ADR (foreign-only listing, crypto, private co), skip the signal.
  - relevant: true only if the author expresses an actionable forward-looking view on THIS stock.
  - direction: "bullish" | "bearish" | "neutral". Hedged both-ways pieces => "neutral".
  - confidence: 0-1. How strong and unambiguous the author's conviction is. Explicit "screaming buy" ~0.85-0.95; standard positive thesis ~0.6-0.75; hedged/cautious ~0.4-0.55; balanced "on one hand..." => below 0.4.
  - risk_score: 1-10 risk of the stock+thesis. 1-3 megacap/steady compounder; 4-6 typical growth; 7-8 speculative growth, heavy valuation stretch or single-catalyst; 9-10 binary/moonshot (biotech readouts, meme, pre-revenue).
  - instrument: "stock" | "itm_call" | "otm_call" | "itm_put" | "otm_put". Default "stock". Recommend an option only when the risk profile in the article justifies it: an explicit price level or catalyst (e.g. "if X holds above $20 it's solid" => "itm_call" with strike_hint 20); very high conviction + high expected upside and the reader accepts total-loss risk => "otm_call"; strong bearish thesis => "itm_put" (or "otm_put" if crash-style). Options need confidence >= 0.6.
  - strike_hint: a numeric per-share price level explicitly discussed in the article (support level, "maintain above $X", price target useful as strike), else null.
  - horizon_days: 10-90, the holding period the thesis implies (earnings catalyst ~20-40; secular thesis 60-90).
  - rationale: <= 15 words.

Write the complete labels as JSON to the file ${SP}/batches/batch_${bb}_labels.json using the Write tool — format: array of {"id": <int>, "url": <str>, "article_type": <str>, "signals": [<signal objects with all fields above>]}. Every article id from the input file must appear exactly once.

Then return via the structured output schema: batch=${b}, n_articles, n_signals (total signals with relevant=true and direction != "neutral").`
}

phase('Label')
const results = await parallel(A.batches.map((b) => () =>
  agent(labelPrompt(b), { label: `label:batch${String(b).padStart(2, '0')}`, phase: 'Label', schema: SCHEMA })))
const ok = results.filter(Boolean)
return { done: ok.map(r => r.batch), articles: ok.reduce((a, r) => a + r.n_articles, 0), signals: ok.reduce((a, r) => a + r.n_signals, 0) }
