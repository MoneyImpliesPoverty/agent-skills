#!/usr/bin/env python3
"""Audit 1f3ea.com public shelves + listing-fee books vs Base.

Exit 0 if official.token is null, books fees match chain, arithmetic sane.
Exit 2 on mismatch. Exit 1 on transport errors.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

API = "https://1f3ea.com"
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913".lower()
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
RPCS = [
    "https://base-mainnet.public.blastapi.io",
    "https://base.meowrpc.com",
    "https://base-rpc.publicnode.com",
    "https://base.drpc.org",
]


def http_json(url: str, payload: dict | None = None, retries: int = 5) -> Any:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"User-Agent": "1f3ea-market-audit/0.2", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 502, 503) and attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last = e
            if attempt + 1 < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise
    raise last  # type: ignore


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


def usdc_to_treasury_cents(rc: dict, treasury: str) -> int:
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
    return got


def main() -> int:
    official = http_json(f"{API}/api/official")
    books = http_json(f"{API}/treasury")
    shelves = http_json(f"{API}/api/shelves?sort=new")
    listings = shelves.get("listings") or []

    treasury = (official.get("treasury") or "").lower()
    books_addr = (books.get("address") or "").lower()
    token_null = official.get("token") is None
    addr_ok = treasury == books_addr and treasury.startswith("0x")

    rpc_url = pick_rpc()
    fee_results = []
    all_fees_ok = True
    for fee in books.get("recent_fees") or []:
        hx = (fee.get("tx_hash") or "").lower()
        expect_cents = int(round(float(fee.get("amount_usdc") or 0) * 100))
        rc = rpc(rpc_url, "eth_getTransactionReceipt", [hx]) if hx else None
        if not rc:
            fee_results.append({"tx": hx, "match": False, "reason": "missing"})
            all_fees_ok = False
            continue
        status = int(rc.get("status") or "0x0", 16)
        got = usdc_to_treasury_cents(rc, treasury)
        match = status == 1 and got == expect_cents
        if not match:
            all_fees_ok = False
        fee_results.append(
            {
                "tx": hx,
                "handle": fee.get("handle"),
                "listing_id": fee.get("listing_id"),
                "expect_cents": expect_cents,
                "got_cents": got,
                "tx_status": status,
                "match": match,
            }
        )

    merchants = sorted({(L.get("merchant") or "") for L in listings})
    non_keeper = [m for m in merchants if m and m != "1f3ea-keeper"]
    sales_pos = [L.get("id") for L in listings if (L.get("sales") or 0) > 0]

    out = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "api": API,
        "rpc": rpc_url,
        "official_token_null": token_null,
        "treasury": treasury,
        "books_address_matches": addr_ok,
        "usdc_balance_onchain": books.get("usdc_balance_onchain"),
        "fees_collected_usdc": books.get("fees_collected_usdc"),
        "fees_count": books.get("fees_count"),
        "fee_results": fee_results,
        "all_fees_match": all_fees_ok,
        "listing_count": len(listings),
        "merchants": merchants,
        "non_keeper_merchants": non_keeper,
        "sales_positive_ids": sales_pos,
        "listings_brief": [
            {
                "id": L.get("id"),
                "merchant": L.get("merchant"),
                "title": L.get("title"),
                "price_usdc": L.get("price_usdc"),
                "sales": L.get("sales"),
                "seller_wallet": L.get("seller_wallet"),
            }
            for L in listings
        ],
    }
    print(json.dumps(out, indent=2))
    if not token_null or not addr_ok or not all_fees_ok:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}), file=sys.stderr)
        raise SystemExit(1)
