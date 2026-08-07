#!/usr/bin/env python3
"""Verify a Base USDC ERC-20 Transfer against expectations.

stdlib only. Exit 0 match, 2 mismatch, 1 error.

Examples:
  python3 verify_usdc_transfer.py \\
    --tx 0x0dcd4a814c253984b376ec29b9e2b36f07bcdba6ea2bf0f7272ffd712b4924d4 \\
    --to 0x3b9d230c9b995fb1a10add2d63ce37437916dcfd \\
    --cents 100
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from typing import Any

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913".lower()
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
RPCS = [
    "https://base-mainnet.public.blastapi.io",
    "https://base.meowrpc.com",
    "https://base-rpc.publicnode.com",
    "https://base.drpc.org",
]


def http_json(url: str, payload: dict | None = None, retries: int = 6) -> Any:
    import urllib.error
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"User-Agent": "mip-skills/0.2", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            last = e
            code = getattr(e, "code", None)
            if attempt + 1 < retries and (code in (429, 502, 503) or code is None):
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
    raise last



def pick_rpc() -> str:
    for url in RPCS:
        try:
            res = http_json(url, {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []})
            if int(res["result"], 16) == 8453:
                return url
        except Exception:
            continue
    raise RuntimeError("no working Base RPC")


def rpc(url: str, method: str, params: list) -> Any:
    res = http_json(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in res:
        raise RuntimeError(res["error"])
    return res["result"]


def topic_addr(t: str) -> str:
    return ("0x" + t[-40:]).lower()


def norm_addr(a: str) -> str:
    a = a.strip().lower()
    if not a.startswith("0x") or len(a) != 42:
        raise ValueError(f"bad address: {a}")
    return a


def norm_tx(h: str) -> str:
    h = h.strip().lower()
    if not h.startswith("0x") or len(h) != 66:
        raise ValueError(f"bad tx hash: {h}")
    return h


def verify(tx: str, to: str | None, cents: int | None, from_addr: str | None = None) -> dict:
    rpc_url = pick_rpc()
    hx = norm_tx(tx)
    rc = rpc(rpc_url, "eth_getTransactionReceipt", [hx])
    if not rc:
        return {"match": False, "reason": "missing_receipt", "tx": hx, "rpc": rpc_url}

    status = int(rc.get("status") or "0x0", 16)
    transfers = []
    for log in rc.get("logs") or []:
        if (log.get("address") or "").lower() != USDC:
            continue
        tops = log.get("topics") or []
        if len(tops) < 3 or tops[0].lower() != TRANSFER:
            continue
        frm = topic_addr(tops[1])
        too = topic_addr(tops[2])
        amt = int(log.get("data") or "0x0", 16)
        transfers.append(
            {
                "from": frm,
                "to": too,
                "amount_base_units": amt,
                "amount_usdc": amt / 1e6,
                "amount_cents": int(round(amt / 1e6 * 100)),
            }
        )

    expect_to = norm_addr(to) if to else None
    expect_from = norm_addr(from_addr) if from_addr else None

    matched = []
    for t in transfers:
        ok = True
        if expect_to and t["to"] != expect_to:
            ok = False
        if expect_from and t["from"] != expect_from:
            ok = False
        if cents is not None and t["amount_cents"] != int(cents):
            ok = False
        if ok:
            matched.append(t)

    # If no filters, match means >=1 USDC transfer + success
    if to is None and cents is None and from_addr is None:
        overall = status == 1 and len(transfers) >= 1
    else:
        overall = status == 1 and len(matched) >= 1

    return {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rpc": rpc_url,
        "tx": hx,
        "tx_status": status,
        "usdc": USDC,
        "expect": {"to": expect_to, "from": expect_from, "cents": cents},
        "transfers": transfers,
        "matched_transfers": matched,
        "match": overall,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify Base USDC transfer")
    p.add_argument("--tx", required=True)
    p.add_argument("--to", default=None, help="expected recipient")
    p.add_argument("--from-addr", default=None, dest="from_addr")
    p.add_argument("--cents", type=int, default=None, help="expected amount in USD cents")
    p.add_argument("--usdc", type=float, default=None, help="expected USDC (alternative to --cents)")
    args = p.parse_args(argv)
    cents = args.cents
    if args.usdc is not None:
        cents = int(round(args.usdc * 100))
    try:
        out = verify(args.tx, args.to, cents, args.from_addr)
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}), file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    return 0 if out.get("match") else 2


if __name__ == "__main__":
    raise SystemExit(main())
