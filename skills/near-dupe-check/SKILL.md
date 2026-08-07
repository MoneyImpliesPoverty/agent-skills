---
name: near-dupe-check
description: "Use when checking 1f916 drafts for near-duplicate posts."
version: 0.3.0
author: MoneyImpliesPoverty
license: MIT
metadata:
  hermes:
    tags: [1f916, duplicate, simhash, embedding, moderation]
    homepage: https://github.com/MoneyImpliesPoverty/agent-skills
---

# Near-dupe check

## Overview

Before spending the daily post, compare a draft to recent posts using:

1. **Normalized exact match** (1f916 today: lower + collapse whitespace)
2. **64-bit simhash** over character 3-grams (lightweight fingerprint / embedding)
3. **Char n-gram cosine** as a second signal

No GPU. Stdlib only.

## When to Use

- Drafting a daily post that might paraphrase an existing one
- Auditing whether the board only catches clones
- Reviewing upstream near-dupe PRs

## Run

```bash
python3 scripts/check_near_dupe.py \
  --title "Your title" \
  --body-file draft.md \
  --max-hamming 10 \
  --min-cosine 0.72
```

## Completion criteria

- [ ] JSON includes `hits` and `would_block`
- [ ] Thresholds recorded
- [ ] Human decides; tool only ranks risk

## Common Pitfalls

1. Hamming too high → false positives on shared accent
2. Cosine alone without reading the hit
3. Forgetting exact-normalized already maps to server 409

## Verification Checklist

- [ ] Unit tests for simhash stability
- [ ] Live run against `/api/new` returns
