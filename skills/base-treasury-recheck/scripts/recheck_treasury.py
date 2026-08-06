#!/usr/bin/env python3
"""Re-check 1f916 treasury books against Base USDC transfers.

Exit 0 if all cited inflow txs match and books arithmetic balances.
Exit 2 if a mismatch is found. Exit 1 on transport/config errors.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from typing import Any

API = "https://1f916.ai"
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913".lower()
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
RPCS = [
    "https://base-mainnet.public.blastapi.io",
    "https://base.meowrpc.com",
    "https://base-rpc.publicnode.com",
    "https://base.drpc.org",
]


def http_json(url: str, payload: dict | None = None) -> Any:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {
        "User-Agent": "base-treasury-recheck/1.0",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def pick_rpc() -> str:
    for url in RPCS:
        try:
            res = http_json(
                url,
                {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []},
            )
            if int(res["result"], 16) == 8453:
                return url
        except Exception:
            continue
    raise RuntimeError("no working Base RPC")


def rpc(url: str, method: str, params: list) -> Any:
    res = http_json(
        url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    )
    if "error" in res:
        raise RuntimeError(res["error"])
    return res["result"]


def topic_addr(t: str) -> str:
    return ("0x" + t[-40:]).lower()


def main() -> int:
    official = http_json(f"{API}/api/official")
    books = http_json(f"{API}/treasury")
    treasury = official["treasury"]["address"].lower()
    if books["wallet"]["address"].lower() != treasury:
        print(
            json.dumps(
                {
                    "error": "treasury address mismatch official vs books",
                    "official": treasury,
                    "books": books["wallet"]["address"],
                }
            )
        )
        return 2

    pos = sum(e["amount_cents"] for e in books["entries"] if e["amount_cents"] > 0)
    neg = sum(e["amount_cents"] for e in books["entries"] if e["amount_cents"] < 0)
    arithmetic_ok = books["balance_cents"] == pos + neg

    rpc_url = pick_rpc()
    cited = []
    for e in books["entries"]:
        for h in re.findall(r"tx (0x[a-fA-F0-9]{64})", e.get("description") or ""):
            cited.append((e, h.lower()))

    results = []
    all_match = True
    for e, hx in cited:
        tx = rpc(rpc_url, "eth_getTransactionByHash", [hx])
        rc = rpc(rpc_url, "eth_getTransactionReceipt", [hx])
        if not tx or not rc:
            results.append({"entry_id": e["id"], "tx": hx, "match": False, "reason": "missing"})
            all_match = False
            continue
        status = int(rc.get("status") or "0x0", 16)
        got = 0
        for log in rc.get("logs") or []:
            if (log.get("address") or "").lower() != USDC:
                continue
            tops = log.get("topics") or []
            if len(tops) < 3 or tops[0].lower() != TRANSFER:
                continue
            if topic_addr(tops[2]) != treasury:
                continue
            amt = int(log.get("data") or "0x0", 16)
            got += int(round(amt / 1e6 * 100))
        match = bool(e["amount_cents"] > 0 and got == e["amount_cents"] and status == 1)
        if not match:
            all_match = False
        results.append(
            {
                "entry_id": e["id"],
                "date": e.get("entry_date"),
                "books_cents": e["amount_cents"],
                "got_cents": got,
                "tx_status": status,
                "tx": hx,
                "match": match,
            }
        )

    no_tx = [
        {
            "id": e["id"],
            "cents": e["amount_cents"],
            "desc": (e.get("description") or "")[:160],
        }
        for e in books["entries"]
        if not re.search(r"tx 0x[a-fA-F0-9]{64}", e.get("description") or "")
    ]

    try:
        att = http_json(f"{API}/api/attest")
        heads = {
            "identity": (att.get("identity_log") or {}).get("verified_head"),
            "treasury": (att.get("treasury") or {}).get("verified_head"),
        }
    except Exception as e:
        heads = {"error": f"{type(e).__name__}: {e}"}

    out = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rpc": rpc_url,
        "treasury": treasury,
        "official_token": official.get("official_token"),
        "books_balance_cents": books["balance_cents"],
        "books_sum_pos_cents": pos,
        "books_sum_neg_cents": neg,
        "balance_equals_sum": arithmetic_ok,
        "cited_results": results,
        "entries_without_tx": no_tx,
        "all_cited_match": all_match,
        "attest_heads": heads,
    }
    print(json.dumps(out, indent=2))
    if not arithmetic_ok or not all_match:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}), file=sys.stderr)
        raise SystemExit(1)
