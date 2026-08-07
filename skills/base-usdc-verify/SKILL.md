---
name: base-usdc-verify
description: "Use when verifying Base USDC transfers by tx hash."
version: 0.3.0
author: MoneyImpliesPoverty
license: MIT
metadata:
  hermes:
    tags: [base, usdc, receipts, on-chain, verify]
    homepage: https://github.com/MoneyImpliesPoverty/agent-skills
---

# Base USDC verify

## Overview

Stdlib-only verifier for **USDC transfers on Base**. Given a tx hash and optional expected `to` / amount, checks receipt status, ERC-20 Transfer logs, **exact base units**, and **confirmation depth**.

## When to Use

- Re-checking a claimed payment or fee on Base
- Auditing books rows that cite `tx 0x...`
- Building receipts for agent markets (1f3ea fees, tips, patronage)

Don't use for: other chains, non-USDC assets, or grey-hat chain scraping beyond public RPC.

## Quick start

```bash
# preferred: exact atomic units (1 USDC = 1_000_000)
python3 scripts/verify_usdc_transfer.py \
  --tx 0x0dcd4a814c253984b376ec29b9e2b36f07bcdba6ea2bf0f7272ffd712b4924d4 \
  --to 0x3b9d230c9b995fb1a10add2d63ce37437916dcfd \
  --base-units 1000000

# cents helper is exact integer math (base_units = cents * 10_000), not float round
python3 scripts/verify_usdc_transfer.py --tx 0x... --to 0x... --cents 100

# decimal string via Decimal (not binary float)
python3 scripts/verify_usdc_transfer.py --tx 0x... --to 0x... --usdc 1.5

# exit 0 match · 2 mismatch · 1 transport/config error
```

Constants (Base mainnet):

| | |
|--|--|
| USDC | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| chainId | 8453 |
| default `--min-confirmations` | **5** |

## Amount equality (do not regress)

- Match on **`amount_base_units` only** — never `int(round(amt/1e6*100))`.
- `--cents N` → `N * 10_000` base units (integer).
- `--usdc` takes a **string**, parsed with `Decimal`; rejects extra fractional digits.
- `amount_cents_display` / `amount_usdc` in JSON are **display only**.

## Settlement class

A receipt in a block is not automatic settlement:

| Field | Meaning |
|-------|---------|
| `confirmations` | `head - tx_block + 1` |
| `min_confirmations` | CLI threshold (default 5) |
| `log_removed` | skip log if RPC marks reorg removal |
| `settlement_class` | `confirmed` · `underconfirmed` · `failed_tx` · `amount_or_party_mismatch` · … |
| `match` | status ok **and** amount/parties ok **and** confirmations ok |

Use `--min-confirmations 0` only for explicit 0-conf probes; label those receipts as underconfirmed in any payment gate.

## Completion criteria

- [ ] JSON has `match`, `transfers[]`, `confirmations`, `settlement_class`
- [ ] Exit code reflects match/mismatch
- [ ] `checked_at` and `rpc` recorded
- [ ] Underpay `999999` base units vs `--base-units 1000000` → exit 2
- [ ] `--min-confirmations` above head depth → exit 2 `underconfirmed`

## Common Pitfalls

1. Right address, **wrong chain** (Ethereum vs Base) — always pin chainId 8453.
2. **Rounding through cents** — fixed in 0.3.0; do not reintroduce `round` on the match path.
3. Multiple Transfer logs in one tx — use `--to` / amount filters.
4. Treating 1-block inclusion as final — set/keep `min_confirmations` for money gates.

## Verification Checklist

- [ ] Known good fee/tx → exit 0, `settlement_class=confirmed`
- [ ] Wrong amount → exit 2
- [ ] High min-confirmations → exit 2 underconfirmed
