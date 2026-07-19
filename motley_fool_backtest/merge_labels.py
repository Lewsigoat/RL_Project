"""Merge the 50 label batches with auditor corrections into data/labels.jsonl.

Usage: python3 merge_labels.py <scratchpad_dir>
"""
import glob, json, os, sys

SP = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))

meta = {}
for f in glob.glob(f"{SP}/batches/batch_[0-9][0-9].json"):
    for a in json.load(open(f)):
        meta[a["id"]] = a

corrections = {}
for f in sorted(glob.glob(f"{SP}/audits/audit_*.json")):
    for v in json.load(open(f)):
        corrections[(v["id"], v["ticker"].upper())] = v

n_sig = n_veto = n_adj = 0
out = open(os.path.join(HERE, "data", "labels.jsonl"), "w")
for f in sorted(glob.glob(f"{SP}/batches/batch_[0-9][0-9]_labels.json")):
    for lab in json.load(open(f)):
        m = meta.get(lab["id"])
        if not m:
            continue
        signals = []
        for s in lab.get("signals", []):
            t = (s.get("primary_ticker") or "").upper()
            c = corrections.get((lab["id"], t))
            if c:
                if c["verdict"] == "veto":
                    n_veto += 1
                    continue
                if c["verdict"] == "adjust":
                    n_adj += 1
                    for k in ("confidence", "instrument", "direction"):
                        if c.get(k) is not None:
                            s[k] = c[k]
            signals.append(s)
            n_sig += 1
        out.write(json.dumps({"id": lab["id"], "date": m["date"], "url": m["url"],
                              "title": m.get("title", ""),
                              "article_type": lab.get("article_type"),
                              "signals": signals}) + "\n")
out.close()
print(f"articles: {len(meta)}, signals kept: {n_sig}, vetoed: {n_veto}, adjusted: {n_adj}")
