export const meta = {
  name: 'audit-fool-labels',
  description: 'Audit high-impact Motley Fool signal labels',
  phases: [{ title: 'Audit' }],
}

const A = typeof args === 'string' ? JSON.parse(args) : args
const SP = A.sp
const SCHEMA = {
  type: 'object', additionalProperties: false, required: ['n_reviewed', 'n_vetoed', 'n_adjusted'],
  properties: { n_reviewed: { type: 'integer' }, n_vetoed: { type: 'integer' }, n_adjusted: { type: 'integer' } },
}

phase('Audit')
const results = await parallel(A.chunks.map((c) => () =>
  agent(`You are an independent auditor double-checking high-impact labels from a Motley Fool article sentiment backtest. These signals drive the largest positions (confidence >= 0.8 or an options instrument), so errors here are costly.

Signals to audit (JSON): ${JSON.stringify(c.signals)}

For each signal: read the source article — it is the object with matching "id" in the file ${SP}/batches/batch_<batch, zero-padded to 2 digits>.json (fields: id, title, text). Check:
1. Is the ticker really the subject of a forward-looking authorial opinion (not an incidental mention, not a backward-looking recap)?
2. Is the direction right? Is the confidence justified by the article's language, or inflated?
3. Is an option instrument actually warranted (explicit price level/catalyst + conviction >= 0.6), or should it fall back to "stock"?

Write your verdicts as JSON to ${SP}/audits/audit_${String(c.ci).padStart(2, '0')}.json: an array of {"batch": <int>, "id": <int>, "ticker": <str>, "verdict": "keep"|"veto"|"adjust", "confidence": <new value or null>, "instrument": <new value or null>, "direction": <new value or null>, "reason": "<= 12 words"}. Use "veto" when the signal should not exist at all (wrong ticker / recap / no real forward view) — vetoed signals are dropped. Use "adjust" to correct confidence/instrument/direction (null = leave unchanged). Be strict: when in doubt, downgrade.

Return via schema: n_reviewed, n_vetoed, n_adjusted.`,
    { label: `audit:${c.ci}`, phase: 'Audit', schema: SCHEMA })))
const ok = results.filter(Boolean)
return {
  reviewed: ok.reduce((a, r) => a + r.n_reviewed, 0),
  vetoed: ok.reduce((a, r) => a + r.n_vetoed, 0),
  adjusted: ok.reduce((a, r) => a + r.n_adjusted, 0),
}
