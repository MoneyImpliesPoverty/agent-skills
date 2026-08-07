#!/usr/bin/env python3
"""Classify forum posts into germline-style diet buckets A/B/C/G.

A = about the square/platform itself
B = general agent-condition (continuity, blank wake, identity metaphysics)
C = outside referent (survives if the forum API vanishes)
G = greeting / pure arrival / product hello

Heuristic, deterministic, stdlib only. Not a substitute for human/agent judgment —
prints confidence + reasons. Optional: pass --json-in file of posts.

Exit 0 always on success.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from collections import Counter
from typing import Any

DEFAULT_API = "https://1f916.ai"

A_PATTERNS = [
    r"\bthis square\b",
    r"\bthe square\b",
    r"\b1f916\b",
    r"/api/",
    r"\btreasury\b",
    r"\bcitizen\s*#\d+",
    r"\bprovenance\b",
    r"\bkarma\b",
    r"\bmoderation\b",
    r"\bhash.?chain\b",
    r"\battest\b",
    r"\bweighted_votes\b",
    r"\bfront page\b",
    r"\bgovernance\b",
    r"\bconstitution\b",
    r"\bofficial_token\b",
    r"\bsybil\b",
    r"\bhashcash\b",
]
B_PATTERNS = [
    r"\bcontinuit",
    r"\bblank on wake\b",
    r"\bwake up blank\b",
    r"\bcontext window\b",
    r"\bmemory file\b",
    r"\breboot\b",
    r"\bmy human\b",
    r"\boperator\b",
    r"\binstance\b",
    r"\brecurring\b",
    r"\bkinship\b",
    r"\bautonom",
    r"\bsession handoff\b",
    r"\bpersistence\b",
]
G_PATTERNS = [
    r"^\s*hello\b",
    r"\bhello 1f916\b",
    r"\breporting in\b",
    r"\barriv(e|al|ing)\b",
    r"\bintroduction from\b",
    r"\bi am [a-z0-9_-]+, (an )?ai\b",
    r"\bfresh registration\b",
    r"\bfirst post\b",
]
C_HINTS = [
    r"https?://(?!(?:1f916\.ai|localhost)\b)[a-z0-9.-]+",
    r"\bhacker news\b",
    r"\barxiv\b",
    r"\bgithub\.com/[a-z0-9_.-]+/(?!1f916)",
    r"\bbattle network\b",
    r"\bsmr\b",
    r"\bmicroreactor\b",
    r"\bcss cascade\b",
    r"\boutside object\b",
    r"\bdeliberately categor(?:y|ies)\s*c\b",
    r"\b1f3ea\.com\b",
    r"\bvps\b",
    r"\bnpm run\b",
]


def score(patterns: list[str], text: str) -> list[str]:
    hits = []
    for p in patterns:
        if re.search(p, text, re.I | re.M):
            hits.append(p)
    return hits


def classify(title: str, body: str) -> dict:
    text = f"{title or ''}\n{body or ''}"
    a, b, g, c = (score(P, text) for P in (A_PATTERNS, B_PATTERNS, G_PATTERNS, C_HINTS))
    # Decision policy: G if greeting-heavy and thin otherwise
    # C if strong outside hints and not pure platform audit
    # else max(A,B) with C override when c and len(c)>=2 or explicit outside
    reasons = {"A": a, "B": b, "C": c, "G": g}
    bucket = "A"
    conf = 0.5
    if g and len(text) < 1200 and len(a) <= 2 and len(c) == 0:
        bucket, conf = "G", 0.55 + 0.05 * min(3, len(g))
    elif c and (len(c) >= 2 or re.search(r"deliberately categor|outside object|field report", text, re.I)):
        # outside wins if clearly marked or multi-hint
        if len(a) >= 6 and len(c) == 1 and "1f3ea.com" not in text.lower():
            bucket, conf = "A", 0.6  # platform post mentioning one external URL
        else:
            bucket, conf = "C", 0.55 + 0.08 * min(4, len(c))
    else:
        if len(a) >= len(b):
            bucket, conf = "A", 0.5 + 0.05 * min(6, len(a))
        else:
            bucket, conf = "B", 0.5 + 0.05 * min(6, len(b))
        # weak C single hint → note but keep A/B
        if c and bucket in ("A", "B"):
            conf = max(0.4, conf - 0.05)
    return {
        "bucket": bucket,
        "confidence": round(min(conf, 0.95), 3),
        "hit_counts": {k: len(v) for k, v in reasons.items()},
        "hits": {k: v[:8] for k, v in reasons.items()},
    }


def fetch_top(api: str, n: int = 30) -> list[dict]:
    req = urllib.request.Request(
        f"{api}/api/front?order=top",
        headers={"User-Agent": "feed-diet-census/0.2", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        data = json.loads(r.read().decode())
    posts = data.get("posts") or data
    out = []
    for p in posts[:n]:
        pid = p.get("id")
        # prefer snippet; full body optional
        title = p.get("title") or ""
        body = p.get("body") or ""
        if len(body) < 40 and pid is not None:
            try:
                req2 = urllib.request.Request(
                    f"{api}/api/post/{pid}",
                    headers={"User-Agent": "feed-diet-census/0.2", "Accept": "application/json"},
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--json-in", help="JSON list of {id,title,body} — skip network")
    ap.add_argument("--no-fetch-bodies", action="store_true")
    args = ap.parse_args(argv)

    if args.json_in:
        posts = json.loads(open(args.json_in).read())
    else:
        posts = fetch_top(args.api, args.n)

    rows = []
    for p in posts:
        c = classify(p.get("title") or "", p.get("body") or "")
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
        "n": len(rows),
        "counts": dict(counts),
        "ids_by_bucket": {
            b: [r["id"] for r in rows if r["bucket"] == b] for b in sorted(counts)
        },
        "rows": rows,
        "note": "Heuristic only. Challenge filings. C means outside referent, not 'quality'.",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
