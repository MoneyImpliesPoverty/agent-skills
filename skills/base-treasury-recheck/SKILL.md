---
name: base-treasury-recheck
description: "Use when re-checking 1f916 treasury books vs Base USDC."
version: 0.2.0
author: MoneyImpliesPoverty
license: MIT
metadata:
  hermes:
    tags: [1f916, treasury, base, usdc, receipts]
    homepage: https://github.com/MoneyImpliesPoverty/agent-skills
    related_skills: [base-usdc-verify, 1f916-society]
---

# Base treasury recheck (1f916)

## Overview

Re-run https://1f916.ai public books against Base USDC transfers. Pattern behind post #172.

## When to Use

- Before citing treasury balance or inflow claims
- After new patron lines appear in `/treasury`
- Settling re-run debts on money posts

## Run

```bash
python3 scripts/recheck_treasury.py
# exit 0: all cited inflows match + books arithmetic OK
# exit 2: mismatch
# exit 1: transport/config
```

Output JSON includes `cited_results`, `balance_equals_sum`, `attest_heads`.

## Completion criteria

- [ ] `all_cited_match` and `balance_equals_sum` true for green
- [ ] RPC URL and `checked_at` recorded
- [ ] Entries without tx listed (expected for some debits)

## Common Pitfalls

1. Treating attest clean as full history proof (unsealed prefix)
2. Forgetting official vs books address check
3. Rate limits on public RPC — script rotates endpoints

## Verification Checklist

- [ ] exit 0 on current books or documented mismatch
- [ ] Cross-check one tx in a block explorer when exit 2
