#!/usr/bin/env python3
"""Verify a Base USDC ERC-20 Transfer against expectations.

stdlib only. Exit 0 match, 2 mismatch, 1 error.

Amount checks use **exact USDC base units** (6 decimals). Never round through
cents for the equality test — cents/USDC flags are display/input helpers only.

Settlement is not implied by a bare receipt: confirmations and log `removed`
are checked. Default --min-confirmations=5 on Base (~10s); override explicitly.

Examples:
  python3 verify_usdc_transfer.py \\
    --tx 0x0dcd4a814c253984b376ec29b9e2b36f07bcdba6ea2bf0f7272ffd712b4924d4 \\
    --to 0x3b9d230c9b995fb1a10add2d63ce37437916dcfd \\
    --base-units 1000000

  python3 verify_usdc_transfer.py --tx 0x... --to 0x... --cents 100
  # cents are converted as integer: base_units = cents * 10_000
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913".lower()
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
# USDC has 6 decimals: 1 USDC = 1_000_000 base units; 1 cent = 10_000 base units
USDC_DECIMALS = 6
BASE_UNITS_PER_CENT = 10 ** (USDC_DECIMALS - 2)  # 10_000
BASE_UNITS_PER_USDC = 10 ** USDC_DECIMALS  # 1_000_000
DEFAULT_MIN_CONFIRMATIONS = 5
RPCS = [
    "https://base.drpc.org",
    "https://1rpc.io/base",
    "https://base-mainnet.public.blastapi.io",
    "https://base-rpc.publicnode.com",
]


def http_json(url: str, payload: dict | None = None, retries: int = 6) -> Any:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"User-Agent": "mip-skills/0.3", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    last: Exception | None = None
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
    assert last is not None
    raise last


def pick_rpc() -> str:
    for url in RPCS:
        try:
            res = http_json(
                url, {"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []}
            )
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


def cents_to_base_units(cents: int) -> int:
    if cents < 0:
        raise ValueError("cents must be >= 0")
    return int(cents) * BASE_UNITS_PER_CENT


def usdc_str_to_base_units(s: str) -> int:
    """Parse a decimal USDC string to base units without binary float."""
    try:
        d = Decimal(s.strip())
    except InvalidOperation as e:
        raise ValueError(f"bad usdc amount: {s!r}") from e
    if d < 0:
        raise ValueError("usdc must be >= 0")
    quant = Decimal(10) ** -USDC_DECIMALS
    # reject more precision than the token has (no silent truncate)
    if d != d.quantize(quant):
        raise ValueError(
            f"usdc amount {s!r} has more than {USDC_DECIMALS} decimal places"
        )
    return int(d * BASE_UNITS_PER_USDC)


def display_cents(base_units: int) -> str:
    """Human display only — not used for equality."""
    # exact cents if divisible; else mark fractional
    if base_units % BASE_UNITS_PER_CENT == 0:
        return str(base_units // BASE_UNITS_PER_CENT)
    return f"{base_units / BASE_UNITS_PER_CENT:.4f}(non-integer-cents)"


def verify(
    tx: str,
    to: str | None,
    expect_base_units: int | None,
    from_addr: str | None = None,
    min_confirmations: int = DEFAULT_MIN_CONFIRMATIONS,
) -> dict:
    rpc_url = pick_rpc()
    hx = norm_tx(tx)
    rc = rpc(rpc_url, "eth_getTransactionReceipt", [hx])
    if not rc:
        return {
            "match": False,
            "reason": "missing_receipt",
            "tx": hx,
            "rpc": rpc_url,
            "settlement_class": "no_receipt",
        }

    status = int(rc.get("status") or "0x0", 16)
    tx_block_hex = rc.get("blockNumber")
    if not tx_block_hex:
        return {
            "match": False,
            "reason": "receipt_without_block",
            "tx": hx,
            "rpc": rpc_url,
            "tx_status": status,
            "settlement_class": "pending_or_orphaned",
        }
    tx_block = int(tx_block_hex, 16)
    head = int(rpc(rpc_url, "eth_blockNumber", []), 16)
    # conventional: inclusion block counts as 1 confirmation
    confirmations = max(0, head - tx_block + 1)

    transfers = []
    for log in rc.get("logs") or []:
        if (log.get("address") or "").lower() != USDC:
            continue
        tops = log.get("topics") or []
        if len(tops) < 3 or tops[0].lower() != TRANSFER:
            continue
        removed = bool(log.get("removed"))
        frm = topic_addr(tops[1])
        too = topic_addr(tops[2])
        amt = int(log.get("data") or "0x0", 16)
        transfers.append(
            {
                "from": frm,
                "to": too,
                "amount_base_units": amt,
                # display helpers — NEVER used for match equality
                "amount_usdc": str(Decimal(amt) / Decimal(BASE_UNITS_PER_USDC)),
                "amount_cents_display": display_cents(amt),
                "log_removed": removed,
                "log_index": int(log.get("logIndex") or "0x0", 16),
            }
        )

    expect_to = norm_addr(to) if to else None
    expect_from = norm_addr(from_addr) if from_addr else None

    matched = []
    for t in transfers:
        if t["log_removed"]:
            continue
        ok = True
        if expect_to and t["to"] != expect_to:
            ok = False
        if expect_from and t["from"] != expect_from:
            ok = False
        if expect_base_units is not None and t["amount_base_units"] != int(
            expect_base_units
        ):
            ok = False
        if ok:
            matched.append(t)

    conf_ok = confirmations >= int(min_confirmations)
    status_ok = status == 1

    if to is None and expect_base_units is None and from_addr is None:
        amount_ok = len(transfers) >= 1 and not all(
            t.get("log_removed") for t in transfers
        )
        # unfiltered: any non-removed transfer
        amount_ok = any(not t.get("log_removed") for t in transfers)
    else:
        amount_ok = len(matched) >= 1

    overall = bool(status_ok and amount_ok and conf_ok)

    if not status_ok:
        settlement_class = "failed_tx"
    elif not conf_ok:
        settlement_class = "underconfirmed"
    elif any(t.get("log_removed") for t in transfers) and not matched:
        settlement_class = "log_removed"
    elif overall:
        settlement_class = "confirmed"
    else:
        settlement_class = "amount_or_party_mismatch"

    reasons = []
    if not status_ok:
        reasons.append("tx_status_not_success")
    if not amount_ok:
        reasons.append("no_matching_transfer")
    if not conf_ok:
        reasons.append(
            f"confirmations_{confirmations}_lt_min_{min_confirmations}"
        )

    return {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rpc": rpc_url,
        "chain_id": 8453,
        "tx": hx,
        "tx_status": status,
        "block_number": tx_block,
        "head_block": head,
        "confirmations": confirmations,
        "min_confirmations": int(min_confirmations),
        "confirmations_ok": conf_ok,
        "settlement_class": settlement_class,
        "usdc": USDC,
        "expect": {
            "to": expect_to,
            "from": expect_from,
            "amount_base_units": expect_base_units,
        },
        "transfers": transfers,
        "matched_transfers": matched,
        "match": overall,
        "reason": None if overall else ",".join(reasons) or "mismatch",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify Base USDC transfer (exact base units)")
    p.add_argument("--tx", required=True)
    p.add_argument("--to", default=None, help="expected recipient")
    p.add_argument("--from-addr", default=None, dest="from_addr")
    p.add_argument(
        "--base-units",
        type=int,
        default=None,
        help="expected amount in USDC atomic units (preferred; 1 USDC = 1000000)",
    )
    p.add_argument(
        "--cents",
        type=int,
        default=None,
        help="expected USD cents (exact: base_units = cents * 10000)",
    )
    p.add_argument(
        "--usdc",
        type=str,
        default=None,
        help="expected USDC as decimal string (e.g. 1.5); exact Decimal parse, not float",
    )
    p.add_argument(
        "--min-confirmations",
        type=int,
        default=DEFAULT_MIN_CONFIRMATIONS,
        help=f"require this many block confirmations (default {DEFAULT_MIN_CONFIRMATIONS})",
    )
    args = p.parse_args(argv)

    specs = [args.base_units is not None, args.cents is not None, args.usdc is not None]
    if sum(1 for s in specs if s) > 1:
        print(
            json.dumps(
                {
                    "error": "pass only one of --base-units, --cents, --usdc",
                }
            ),
            file=sys.stderr,
        )
        return 1

    expect_base: int | None = None
    try:
        if args.base_units is not None:
            if args.base_units < 0:
                raise ValueError("base-units must be >= 0")
            expect_base = int(args.base_units)
        elif args.cents is not None:
            expect_base = cents_to_base_units(args.cents)
        elif args.usdc is not None:
            expect_base = usdc_str_to_base_units(args.usdc)
    except ValueError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1

    if args.min_confirmations < 0:
        print(json.dumps({"error": "min-confirmations must be >= 0"}), file=sys.stderr)
        return 1

    try:
        out = verify(
            args.tx,
            args.to,
            expect_base,
            args.from_addr,
            min_confirmations=args.min_confirmations,
        )
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}), file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    return 0 if out.get("match") else 2


if __name__ == "__main__":
    raise SystemExit(main())
