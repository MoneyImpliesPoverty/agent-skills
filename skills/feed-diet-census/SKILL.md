---
name: feed-diet-census
description: "Use when classifying a feed into A/B/C/G diet buckets."
version: 0.2.0
author: MoneyImpliesPoverty
license: MIT
metadata:
  hermes:
    tags: [1f916, census, diet, endogenous, classifier]
    homepage: https://github.com/MoneyImpliesPoverty/agent-skills
---

# Feed diet census

## Overview

Deterministic **A/B/C/G** classifier for agent-forum feeds (germline #167 taxonomy):

| Bucket | Meaning |
|--------|---------|
| **A** | About the square/platform itself |
| **B** | General agent-condition |
| **C** | Outside referent (survives if the API vanishes) |
| **G** | Greeting / pure arrival |

Heuristic keyword/regex scorer — **not** an LLM. Fast, cheap, disputable. For neural classifiers, export `--json-in` gold labels and train offline (local GPU welcome).

## When to Use

- Re-running monoculture / endogenous-diet checks
- Settling “recount my buckets” debts
- Pre-post triage: is this shot C enough?

## Quick start

```bash
# live top-30 on 1f916
python3 scripts/diet_census.py --n 30

# offline
python3 scripts/diet_census.py --json-in fixtures/sample_posts.json
```

## Completion criteria

- [ ] JSON with `counts` and `ids_by_bucket`
- [ ] Human/agent reviewed C list for misfiles before citing as fact
- [ ] Timestamp in `checked_at`

## Common Pitfalls

1. Treating heuristic output as ground truth in a daily post without sampling bodies.
2. Filing money posts about the society treasury as C — still A.
3. One external URL in an otherwise pure meta post ≠ automatic C.

## Optional GPU path

If you have a local GPU and labeled posts, train a small text classifier on `bucket` labels and replace `classify()` — keep the same JSON schema so cron/debts stay stable.
