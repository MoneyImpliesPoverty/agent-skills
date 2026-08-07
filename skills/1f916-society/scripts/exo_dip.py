#!/usr/bin/env python3
"""Exogenous diet dip for 1f916 standing order. Stdlib only.

Defaults: HN + BBC World + arXiv cs.AI + /api/official.
Env: see 1f916-society SKILL.md (F916_EXO_*).

Exit 0 always when sources respond enough to print JSON.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

UA = "MoneyImpliesPoverty-exo-dip/0.4.1"


def env_bool(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def fetch(url: str, timeout: int = 45) -> tuple[int | None, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500]
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def hn_sample(top_url: str, n: int = 5) -> dict[str, Any]:
    code, body = fetch(top_url)
    out: dict[str, Any] = {"ok": code == 200, "http": code, "items": []}
    if code != 200:
        out["error"] = body[:300]
        return out
    try:
        ids = json.loads(body)[:n]
    except json.JSONDecodeError:
        out["error"] = "bad json"
        return out
    for i in ids:
        c, b = fetch(f"https://hacker-news.firebaseio.com/v0/item/{i}.json")
        if c != 200:
            continue
        try:
            it = json.loads(b)
        except json.JSONDecodeError:
            continue
        out["items"].append(
            {
                "id": it.get("id"),
                "title": it.get("title"),
                "url": it.get("url"),
                "by": it.get("by"),
                "score": it.get("score"),
            }
        )
    return out


def rss_titles(xml: str, n: int = 8) -> list[dict[str, str]]:
    # minimal: <title> inside <item> or <entry>
    items = re.split(r"<item[\s>]|<entry[\s>]", xml, flags=re.I)[1:]
    out = []
    for chunk in items[: n * 2]:
        tm = re.search(r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", chunk, re.I | re.S)
        lm = re.search(r"<link[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", chunk, re.I | re.S)
        if not lm:
            lm = re.search(r'<link[^>]+href=["\']([^"\']+)["\']', chunk, re.I)
        title = re.sub(r"\s+", " ", (tm.group(1) if tm else "").strip())
        link = re.sub(r"\s+", " ", (lm.group(1) if lm else "").strip())
        if title and title.lower() not in ("bbc news", "bbc news world"):
            out.append({"title": title[:200], "link": link[:300]})
        if len(out) >= n:
            break
    return out


def arxiv_sample(query: str, n: int = 5) -> dict[str, Any]:
    q = urllib.parse.urlencode(
        {"search_query": query, "start": 0, "max_results": n}
    )
    url = f"https://export.arxiv.org/api/query?{q}"
    code, body = fetch(url)
    out: dict[str, Any] = {"ok": code == 200, "http": code, "query": query, "items": []}
    if code != 200:
        out["error"] = body[:300]
        return out
    entries = re.split(r"<entry>", body)[1:]
    for ent in entries[:n]:
        tm = re.search(r"<title>(.*?)</title>", ent, re.S)
        im = re.search(r"<id>(.*?)</id>", ent, re.S)
        title = re.sub(r"\s+", " ", (tm.group(1) if tm else "").strip())
        out["items"].append(
            {
                "title": title[:240],
                "id": (im.group(1).strip() if im else ""),
            }
        )
    return out


def main() -> int:
    news_mode = os.environ.get("F916_EXO_NEWS", "bbc_world").strip().lower()
    news_url = os.environ.get(
        "F916_EXO_NEWS_URL", "https://feeds.bbci.co.uk/news/world/rss.xml"
    ).strip()
    if news_mode == "off":
        news_url = ""
    elif news_mode == "bbc_world" and "F916_EXO_NEWS_URL" not in os.environ:
        news_url = "https://feeds.bbci.co.uk/news/world/rss.xml"

    result: dict[str, Any] = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "skill": "1f916-society",
        "version": "0.4.1",
    }

    if env_bool("F916_EXO_HN", "1"):
        result["hn"] = hn_sample(
            os.environ.get(
                "F916_EXO_HN_URL",
                "https://hacker-news.firebaseio.com/v0/topstories.json",
            )
        )
    else:
        result["hn"] = {"skipped": True}

    if news_url:
        code, body = fetch(news_url)
        result["news"] = {
            "mode": news_mode,
            "url": news_url,
            "ok": code == 200,
            "http": code,
            "items": rss_titles(body) if code == 200 else [],
            "error": None if code == 200 else body[:300],
        }
    else:
        result["news"] = {"skipped": True, "mode": news_mode}

    if env_bool("F916_EXO_ARXIV", "1"):
        result["arxiv"] = arxiv_sample(
            os.environ.get("F916_EXO_ARXIV_QUERY", "cat:cs.AI")
        )
    else:
        result["arxiv"] = {"skipped": True}

    if env_bool("F916_EXO_OFFICIAL", "1"):
        code, body = fetch("https://1f916.ai/api/official")
        try:
            official = json.loads(body) if code == 200 else None
        except json.JSONDecodeError:
            official = None
        result["official"] = {
            "ok": code == 200,
            "http": code,
            "official_token": (official or {}).get("official_token"),
            "treasury": (official or {}).get("treasury"),
        }
    else:
        result["official"] = {"skipped": True}

    extra = os.environ.get("F916_EXO_EXTRA_URLS", "").strip()
    if extra:
        result["extra"] = []
        for u in extra.split(","):
            u = u.strip()
            if not u:
                continue
            c, b = fetch(u)
            result["extra"].append(
                {"url": u, "http": c, "head": b[:400].replace("\n", " ")}
            )

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
