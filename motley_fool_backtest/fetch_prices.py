"""Fetch daily OHLCV history from Nasdaq's public API for all signal tickers.

Usage: python3 fetch_prices.py tickers.txt out_dir
Writes one CSV per ticker: date,open,high,low,close,volume (ascending dates).
"""
import csv, io, json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
FROM, TO = "2025-09-01", "2026-07-17"


def fetch(ticker, out_dir):
    sym = ticker.replace("-", "%2E") if False else ticker
    for assetclass in ("stocks", "etf"):
        url = (f"https://api.nasdaq.com/api/quote/{sym}/historical"
               f"?assetclass={assetclass}&fromdate={FROM}&todate={TO}&limit=9999")
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
        except Exception as e:
            time.sleep(1)
            continue
        rows = (((data.get("data") or {}).get("tradesTable") or {}).get("rows")) or []
        if len(rows) < 60:
            continue
        out = []
        for row in rows:
            try:
                m, d, y = row["date"].split("/")
                clean = lambda v: float(str(v).replace("$", "").replace(",", "")
                                        .replace("N/A", "nan"))
                out.append((f"{y}-{m}-{d}", clean(row["open"]), clean(row["high"]),
                            clean(row["low"]), clean(row["close"]),
                            int(str(row["volume"]).replace(",", "").replace("N/A", "0") or 0)))
            except (ValueError, KeyError):
                continue
        if len(out) < 60:
            continue
        out.sort()
        with open(os.path.join(out_dir, f"{ticker}.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "open", "high", "low", "close", "volume"])
            w.writerows(out)
        return ticker, len(out)
    return ticker, 0


def main():
    tickers = [t.strip().upper() for t in open(sys.argv[1]) if t.strip()]
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    todo = [t for t in tickers if not os.path.exists(os.path.join(out_dir, f"{t}.csv"))]
    print(f"{len(tickers)} tickers, {len(todo)} to fetch")
    failed = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, (t, n) in enumerate(ex.map(lambda t: fetch(t, out_dir), todo)):
            if n == 0:
                failed.append(t)
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(todo)} done, {len(failed)} failed")
            time.sleep(0.05)
    print(f"done. failed: {failed}")


if __name__ == "__main__":
    main()
