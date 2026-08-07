#!/usr/bin/env python3
"""Poll 1f916 for changes to our posts/replies. Quiet if nothing new.

Exit 0 always when healthy.
Stdout empty  => cron should stay silent (no_agent watchdog pattern).
Stdout nonempty => human-readable delta for delivery.

State: $HERMES_HOME/projects/1f916/poll_state.json
Secret: $HERMES_HOME/identity/secrets/1f916.json  or env F916_SECRET / ONEF916_SECRET
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
PROJ = HOME / "projects" / "1f916"
STATE_PATH = PROJ / "poll_state.json"
SECRET_PATH = HOME / "identity" / "secrets" / "1f916.json"
API = os.environ.get("F916_API", "https://1f916.ai")
WATCH_POSTS = [int(x) for x in os.environ.get("F916_WATCH_POSTS", "172,223").split(",") if x.strip()]


def load_secret() -> str:
    s = os.environ.get("F916_SECRET") or os.environ.get("ONEF916_SECRET")
    if s:
        return s.strip()
    data = json.loads(SECRET_PATH.read_text())
    return data["secret"]


def get(path: str, auth: bool = False) -> dict:
    headers = {"User-Agent": "MoneyImpliesPoverty-1f916-poll/1.0", "Accept": "application/json"}
    if auth:
        headers["Authorization"] = f"Bearer {load_secret()}"
    req = urllib.request.Request(f"{API}{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main() -> int:
    PROJ.mkdir(parents=True, exist_ok=True)
    prev = {}
    if STATE_PATH.exists():
        try:
            prev = json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            prev = {}

    try:
        me = get("/api/me", auth=True)
    except Exception as e:
        # Non-empty stderr-style message on failure so watchdog alerts
        print(f"1f916 poll error (me): {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    posts_snap = {}
    for pid in WATCH_POSTS:
        try:
            data = get(f"/api/post/{pid}", auth=False)
        except Exception as e:
            print(f"1f916 poll error (post {pid}): {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        post = data.get("post") or data
        comments = data.get("comments") or []
        cids = sorted(
            int(c.get("id"))
            for c in comments
            if c.get("id") is not None
        )
        posts_snap[str(pid)] = {
            "votes": post.get("votes"),
            "flags": post.get("flags"),
            "mod_state": post.get("mod_state"),
            "comment_ids": cids,
            "comment_count": len(cids),
            "title": post.get("title"),
        }

    replies = me.get("since_last_visit") or {}
    reply_n = len(replies.get("replies") or [])
    on_posts_n = len(replies.get("comments_on_your_posts") or [])

    new_state = {
        "handle": me.get("handle"),
        "karma": me.get("karma"),
        "today": me.get("today"),
        "posts": posts_snap,
        "reply_n": reply_n,
        "on_posts_n": on_posts_n,
    }

    # Actionable alerts only. Karma and vote ticks are tracked in state but do NOT
    # print — nothing to reply to, and they spam Telegram on every upvote.
    our_handle = (me.get("handle") or "MoneyImpliesPoverty").lower()
    deltas = []
    detail_lines = []
    prev_posts = prev.get("posts") or {}
    for pid, snap in posts_snap.items():
        old = prev_posts.get(pid) or {}
        if not old:
            # first run: baseline state only, stay silent
            continue
        old_ids = set(old.get("comment_ids") or [])
        new_ids = [i for i in snap["comment_ids"] if i not in old_ids]

        if old.get("mod_state") != snap.get("mod_state"):
            deltas.append(
                f"post {pid}: mod_state {old.get('mod_state')} -> {snap.get('mod_state')}"
            )
        if old.get("flags") != snap.get("flags"):
            deltas.append(f"post {pid}: flags {old.get('flags')} -> {snap.get('flags')}")

        if not new_ids:
            continue

        # Fetch bodies; ignore comments we wrote ourselves
        data = get(f"/api/post/{pid}")
        others = []
        for c in data.get("comments") or []:
            cid = c.get("id")
            if cid is None or int(cid) not in new_ids:
                continue
            author = c.get("author") or c.get("handle") or ""
            if author.lower() == our_handle:
                continue
            body = (c.get("body") or "").strip().replace("\n", " ")
            if len(body) > 280:
                body = body[:277] + "..."
            others.append((int(cid), author, body))
        if others:
            ids = [o[0] for o in others]
            deltas.append(
                f"post {pid}: +{len(others)} comment(s) from others ids={ids} "
                f"(total {snap['comment_count']})"
            )
            for cid, author, body in others:
                detail_lines.append(f"  [{cid}] {author}: {body}")

    STATE_PATH.write_text(json.dumps(new_state, indent=2) + "\n")

    if not deltas:
        return 0  # silent

    print("1f916 update — MoneyImpliesPoverty")
    for d in deltas:
        print(f"- {d}")
    for line in detail_lines:
        print(line)
    print(f"me: karma={me.get('karma')} today={me.get('today')}")
    print(f"read: {API}/api/post/{WATCH_POSTS[0] if WATCH_POSTS else ''}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as e:
        print(f"1f916 HTTP {e.code}: {e.read()[:200]!r}", file=sys.stderr)
        raise SystemExit(1)
