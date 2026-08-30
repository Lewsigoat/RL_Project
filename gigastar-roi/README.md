# GigaStar Gold-tier ROI study

What one **Gold CRT** — the smallest ticket available — in every GigaStar channel drop
cost, and what it has paid back. Valued **30 August 2026** (distributions through
June 2026 revenue).

## Headline

| | |
|---|---|
| Funded drops (buyable) | 39 of 45 filed |
| Invested (1 Gold CRT each) | $3,156.00 |
| Distributions received to date | $464.80 |
| Capital returned | **14.73%** |
| Median drop | 10.80% |
| Drops ≥24 months old | 32.3% returned, ≈12.6%/yr |

These are perpetual revenue-share units — principal is never repaid, so 14.73% is
progress toward payback, not profit.

## Method

1. **Universe** — SEC EDGAR full-text search for GigaStar `Channel Drop` issuers with a
   Form C (45), cross-checked against the platform's own `offerCount` of 45.
2. **Lowest tier** — each Form C defines a Gold CRT as 1 revenue-sharing unit
   (Platinum 4, Diamond 16) and states every tier has the same economic value per
   dollar invested, so the Gold tier is both the cheapest ticket and rate-equivalent.
3. **Return per unit** — distributions are strictly pro-rata per unit and tier pricing is
   linear, so a drop's return per Gold CRT is `aggregateNetDistributionAll / aggregateCost`.
   This reproduces GigaStar's own published per-unit figures exactly on 10 of the 11
   drops where it publishes them (`Let's Talk Money 3` is the lone 2x outlier, likely the
   March 2026 restatement into standardised Gold units).

## Files

| File | Contents |
|---|---|
| `analyze_roi.py` | Joins the three source datasets and computes per-drop and basket ROI |
| `gigastar_roi.csv` / `.json` | Per-drop results: ticket price, paid per CRT, ROI, months held |
| `offerRois.json` | Source: `mgw.gigastar.io/public/portfolio/analytics/offerRois` |
| `offer_previews.json` | Source: `mgw.gigastar.io/public/portfolio/offer_previews` (symbol join) |
| `offerings_meta.json` | Source: WealthBlock offering records — Gold prices, open/close dates |
| `report.html` | Rendered report |

Run with `python3 analyze_roi.py` from this directory.

## Caveats

- Order fees ($5/order + $3 ACH) are excluded; 39 orders would add ~$312 and cut the
  basket return to ~13.4%.
- Per-drop distributions sum to $1,448,236 against the platform's headline $1,478,489
  — a 2% gap consistent with the two endpoints refreshing on different schedules.
- Past distributions do not predict future ones. Not investment advice.
