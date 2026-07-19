"""Build the Motley Fool article corpus: sample sitemap URLs, then (after fetch) extract text."""
import json, os, re, sys, random
from collections import defaultdict

SP = os.path.dirname(os.path.abspath(__file__))
TARGET = 1500
random.seed(42)

def sample_urls():
    urls = []
    for m in ("02", "03", "04"):
        xml = open(f"{SP}/sitemaps/2026-{m}.xml").read()
        for loc in re.findall(r"<loc>([^<]+)</loc>", xml):
            mm = re.search(r"fool\.com/investing/(2026)/(\d\d)/(\d\d)/", loc)
            if mm and mm.group(2) in ("02", "03", "04"):
                urls.append((f"{mm.group(1)}-{mm.group(2)}-{mm.group(3)}", loc))
    urls = sorted(set(urls))
    by_day = defaultdict(list)
    for d, u in urls:
        by_day[d].append(u)
    days = sorted(by_day)
    per_day = TARGET // len(days) + 1
    sampled = []
    for d in days:
        pool = by_day[d]
        random.shuffle(pool)
        sampled += [(d, u) for u in pool[:per_day]]
    random.shuffle(sampled)
    sampled = sorted(sampled[:TARGET])
    with open(f"{SP}/sampled_urls.tsv", "w") as f:
        for d, u in sampled:
            f.write(f"{d}\t{u}\n")
    print(f"total investing urls: {len(urls)}, days: {len(days)}, sampled: {len(sampled)}")

def extract():
    from bs4 import BeautifulSoup
    rows = []
    lines = [l.split("\t") for l in open(f"{SP}/sampled_urls.tsv").read().splitlines()]
    for i, (d, u) in enumerate(lines):
        path = f"{SP}/html/{i:04d}.html"
        if not os.path.exists(path) or os.path.getsize(path) < 5000:
            continue
        try:
            soup = BeautifulSoup(open(path, encoding="utf-8", errors="ignore").read(), "lxml")
        except Exception:
            continue
        body = soup.find(class_=re.compile(r"\barticle-body\b"))
        if not body:
            continue
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else ""
        tickers = set()
        for a in soup.find_all("a", href=True):
            tm = re.search(r"/quote/[a-z]+/[^/]+/([a-z\.\-]+)/?$", a["href"])
            if tm:
                tickers.add(tm.group(1).upper())
        for el in body.find_all(["script", "style", "aside", "figure"]):
            el.decompose()
        text = re.sub(r"\n{2,}", "\n", body.get_text("\n", strip=True))
        words = text.split()
        if len(words) < 80:
            continue
        text = " ".join(words[:1300])
        rows.append({"id": i, "date": d, "url": u, "title": title,
                     "tickers_linked": sorted(tickers), "text": text})
    os.makedirs(f"{SP}/batches", exist_ok=True)
    n_batches = 50
    for b in range(n_batches):
        batch = rows[b::n_batches]
        with open(f"{SP}/batches/batch_{b:02d}.json", "w") as f:
            json.dump(batch, f)
    print(f"extracted {len(rows)} articles into {n_batches} batches "
          f"(~{len(rows)//n_batches} each)")

if __name__ == "__main__":
    sample_urls() if sys.argv[1] == "sample" else extract()
