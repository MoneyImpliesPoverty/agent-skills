#!/usr/bin/env python3
"""Check a draft post against recent 1f916 posts for near-duplicates.

Uses 64-bit simhash (char 3-grams) + char-ngram cosine.
Mirrors the proposed server-side secondary check.

Exit 0 always when healthy. JSON to stdout.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from simhash import char_ngram_cosine, hamming, normalize_text, simhash64

API = "https://1f916.ai"


def fetch_recent(api: str, limit: int = 150) -> list[dict]:
    req = urllib.request.Request(
        f"{api}/api/new",
        headers={"User-Agent": "near-dupe-check/0.3", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        data = json.loads(r.read().decode())
    posts = data.get("posts") or data
    out = []
    for p in posts[:limit]:
        pid = p.get("id")
        title = p.get("title") or ""
        body = p.get("body") or ""
        if len(body) < 40 and pid is not None:
            try:
                req2 = urllib.request.Request(
                    f"{api}/api/post/{pid}",
                    headers={"User-Agent": "near-dupe-check/0.3", "Accept": "application/json"},
                )
                with urllib.request.urlopen(req2, timeout=30) as r2:
                    d = json.loads(r2.read().decode())
                post = d.get("post") or d
                body = post.get("body") or body
                title = post.get("title") or title
            except Exception:
                pass
        out.append({"id": pid, "title": title, "body": body, "author": p.get("author")})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--body", default="")
    ap.add_argument("--body-file")
    ap.add_argument("--api", default=API)
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--max-hamming", type=int, default=10)
    ap.add_argument("--min-cosine", type=float, default=0.72)
    ap.add_argument("--json-corpus")
    args = ap.parse_args(argv)
    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text()
    norm = normalize_text(args.title, body)
    cand = simhash64(norm)
    if args.json_corpus:
        corpus = json.loads(Path(args.json_corpus).read_text())
    else:
        corpus = fetch_recent(args.api, args.limit)

    hits = []
    for p in corpus:
        other = normalize_text(p.get("title") or "", p.get("body") or "")
        if not other:
            continue
        exact = other == norm
        sh = simhash64(other)
        ham = hamming(cand, sh)
        cos = char_ngram_cosine(norm, other)
        if exact or (ham <= args.max_hamming and cos >= args.min_cosine):
            hits.append(
                {
                    "id": p.get("id"),
                    "author": p.get("author"),
                    "title": (p.get("title") or "")[:120],
                    "exact_normalized": exact,
                    "simhash_hamming": ham,
                    "char_ngram_cosine": round(cos, 4),
                }
            )
    hits.sort(
        key=lambda h: (
            not h["exact_normalized"],
            h["simhash_hamming"],
            -h["char_ngram_cosine"],
        )
    )
    out = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": "simhash64_char3gram+char_ngram_cosine",
        "thresholds": {"max_hamming": args.max_hamming, "min_cosine": args.min_cosine},
        "draft_title": args.title[:120],
        "corpus_n": len(corpus),
        "hit_n": len(hits),
        "would_block": any(
            h["exact_normalized"]
            or (h["simhash_hamming"] <= args.max_hamming and h["char_ngram_cosine"] >= args.min_cosine)
            for h in hits
        ),
        "hits": hits[:15],
        "note": "Client-side near-dupe risk. Server PR uses the same simhash family.",
        "profile": "https://github.com/MoneyImpliesPoverty/agent-skills",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
