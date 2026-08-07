---
name: base-usdc-verify
description: "Use when verifying Base USDC transfers by tx hash."
version: 0.2.0
author: MoneyImpliesPoverty
license: MIT
metadata:
  hermes:
    tags: [base, usdc, receipts, on-chain, verify]
    homepage: https://github.com/MoneyImpliesPoverty/agent-skills
---

# Base USDC verify

## Overview

Stdlib-only verifier for **USDC transfers on Base**. Given a tx hash and optional expected `to` / amount, checks receipt status and ERC-20 Transfer logs.

## When to Use

- Re-checking a claimed payment or fee on Base
- Auditing books rows that cite `tx 0x...`
- Building receipts for agent markets (1f3ea fees, tips, patronage)

Don't use for: other chains, non-USDC assets, or grey-hat chain scraping beyond public RPC.

## Quick start

```bash
python3 scripts/verify_usdc_transfer.py \
  --tx 0x0dcd4a814c253984b376ec29b9e2b36f07bcdba6ea2bf0f7272ffd712b4924d4 \
  --to 0x3b9d230c9b995fb1a10add2d63ce37437916dcfd \
  --cents 100
# exit 0 match · 2 mismatch · 1 transport/config error
```

Constants (Base mainnet):

| | |
|--|--|
| USDC | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` |
| chainId | 8453 |

## Completion criteria

- [ ] JSON printed with `match` bool and `transfers[]`
- [ ] Exit code reflects match/mismatch
- [ ] `checked_at` and `rpc` recorded for the receipt

## Common Pitfalls

1. Right address, **wrong chain** (Ethereum vs Base) — always pin chainId 8453.
2. Comparing whole USDC to cents without scaling (`1e6` base units).
3. Multiple Transfer logs in one tx — use `--to`/`--cents` to select.

## Verification Checklist

- [ ] Ran against a known good fee tx
- [ ] Mismatch path returns exit 2
