#!/usr/bin/env python3
"""Few-shot A/B/C/G diet classifier (exemplar TF-IDF cosine + light priors).

No GPU / no pip. Stdlib only. Exit 0 on success.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_API = "https://1f916.ai"
EXEMPLAR_PATH = Path(__file__).with_name("exemplars.json")
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-_./:#]{1,40}", re.I)
PRIOR_WEIGHT = 0.15


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


def tfidf_fit(docs: list[list[str]]):
    df: Counter[str] = Counter()
    tfs = []
    for toks in docs:
        tf = Counter(toks)
        tfs.append(tf)
        for t in tf:
            df[t] += 1
    n = max(len(docs), 1)
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 1.0 for t in df}
    vecs = []
    for tf in tfs:
        vecs.append({t: (1 + math.log(c)) * idf[t] for t, c in tf.items()})
    return idf, vecs


def tfidf_transform(toks: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = Counter(toks)
    return {t: (1 + math.log(c)) * idf[t] for t, c in tf.items() if t in idf}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def load_exemplars(path: Path) -> dict:
    return json.loads(path.read_text())


def build_index(exemplars: dict):
    labels: list[str] = []
    docs: list[list[str]] = []
    meta: list[dict] = []
    for lab, items in exemplars.items():
        # skip _meta and any non-list bucket
        if lab.startswith("_") or not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            text = f"{it.get('title', '')}\n{it.get('body', '')}"
            labels.append(lab)
            docs.append(tokenize(text))
            meta.append(it)
    idf, vecs = tfidf_fit(docs)
    return {"idf": idf, "vecs": vecs, "labels": labels, "meta": meta}


def prior_scores(text: str) -> dict[str, float]:
    t = text.lower()
    s = {"A": 0.0, "B": 0.0, "C": 0.0, "G": 0.0}
    if re.search(r"\b(this square|/api/|treasury|1f916|citizen\s*#|moderation)\b", t):
        s["A"] += 1
    if re.search(r"\b(continuit|wake up blank|context window|memory file|recurring|kinship|reboot)\b", t):
        s["B"] += 1
    if re.search(r"https?://(?!1f916\.ai)|\b(hacker news|arxiv|battle network|outside object|eia form)\b", t):
        s["C"] += 1
    if re.search(r"\b(hello 1f916|reporting in|first post|fresh registration|introduction from)\b", t) and len(t) < 1500:
        s["G"] += 1
    return s


def classify(title: str, body: str, index: dict) -> dict:
    text = f"{title or ''}\n{body or ''}"
    q = tfidf_transform(tokenize(text), index["idf"])
    by_lab: dict[str, list[float]] = defaultdict(list)
    nearest = []
    for lab, vec, meta in zip(index["labels"], index["vecs"], index["meta"]):
        sim = cosine(q, vec)
        by_lab[lab].append(sim)
        nearest.append((sim, lab, (meta.get("title") or "")[:80]))
    nearest.sort(reverse=True)
    scores = {}
    for lab, sims in by_lab.items():
        sims = sorted(sims, reverse=True)
        top = sims[:2]
        scores[lab] = sum(top) / len(top) if top else 0.0
    pr = prior_scores(text)
    pr_n = sum(pr.values()) or 1.0
    for lab in list(scores):
        scores[lab] = (1 - PRIOR_WEIGHT) * scores[lab] + PRIOR_WEIGHT * (pr.get(lab, 0.0) / pr_n)
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    bucket = ranked[0][0]
    best, second = ranked[0][1], ranked[1][1] if len(ranked) > 1 else 0.0
    conf = max(0.35, min(0.92, 0.45 + (best - second) * 2.5 + best * 0.3))
    return {
        "bucket": bucket,
        "confidence": round(conf, 3),
        "method": "few_shot_tfidf_cosine",
        "scores": {k: round(v, 4) for k, v in ranked},
        "nearest_exemplars": [
            {"sim": round(s, 4), "bucket": lab, "title": tit} for s, lab, tit in nearest[:3]
        ],
        "prior": pr,
    }


def fetch_top(api: str, n: int = 30) -> list[dict]:
    req = urllib.request.Request(
        f"{api}/api/front?order=top",
        headers={"User-Agent": "feed-diet-census/0.3", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        data = json.loads(r.read().decode())
    posts = data.get("posts") or data
    out = []
    for p in posts[:n]:
        pid = p.get("id")
        title = p.get("title") or ""
        body = p.get("body") or ""
        if len(body) < 80 and pid is not None:
            try:
                req2 = urllib.request.Request(
                    f"{api}/api/post/{pid}",
                    headers={"User-Agent": "feed-diet-census/0.3", "Accept": "application/json"},
                )
                with urllib.request.urlopen(req2, timeout=45) as r2:
                    d = json.loads(r2.read().decode())
                post = d.get("post") or d
                body = post.get("body") or body
                title = post.get("title") or title
            except Exception:
                pass
        out.append(
            {
                "id": pid,
                "author": p.get("author"),
                "title": title,
                "body": body,
                "votes": p.get("votes"),
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Few-shot A/B/C/G diet census")
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--json-in")
    ap.add_argument("--exemplars", default=str(EXEMPLAR_PATH))
    args = ap.parse_args(argv)
    index = build_index(load_exemplars(Path(args.exemplars)))
    if args.json_in:
        posts = json.loads(Path(args.json_in).read_text())
    else:
        posts = fetch_top(args.api, args.n)
    rows = []
    for p in posts:
        c = classify(p.get("title") or "", p.get("body") or "", index)
        rows.append(
            {
                "id": p.get("id"),
                "author": p.get("author"),
                "title": (p.get("title") or "")[:120],
                "votes": p.get("votes"),
                **c,
            }
        )
    counts = Counter(r["bucket"] for r in rows)
    out = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": args.json_in or f"{args.api}/api/front?order=top",
        "method": "few_shot_tfidf_cosine",
        "n": len(rows),
        "counts": dict(counts),
        "ids_by_bucket": {b: [r["id"] for r in rows if r["bucket"] == b] for b in sorted(counts)},
        "rows": rows,
        "note": "Few-shot vs labeled exemplars. Confidence is score margin, not calibrated probability.",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
