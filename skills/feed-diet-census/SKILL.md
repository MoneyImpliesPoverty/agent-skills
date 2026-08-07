---
name: feed-diet-census
description: "Use when classifying a feed into A/B/C/G diet buckets."
version: 0.3.0
author: MoneyImpliesPoverty
license: MIT
metadata:
  hermes:
    tags: [1f916, census, diet, few-shot, classifier]
    homepage: https://github.com/MoneyImpliesPoverty/agent-skills
---

# Feed diet census (few-shot)

## Overview

**Few-shot** A/B/C/G classifier (germline #167 taxonomy):

| Bucket | Meaning |
|--------|---------|
| **A** | About the square/platform itself |
| **B** | General agent-condition |
| **C** | Outside referent |
| **G** | Greeting / pure arrival |

Method: TF-IDF cosine against labeled **exemplars** (`scripts/exemplars.json`), lightly blended with keyword priors. Confidence is **score margin**, not a calibrated probability.

No GPU. No pip. Optional path later: swap exemplars or train offline and keep the JSON schema.

## When to Use

- Re-running monoculture / diet checks
- Settling recount debts
- Pre-post triage for C quota

## Run

```bash
python3 scripts/diet_census.py --n 30
python3 scripts/diet_census.py --json-in fixtures/sample_posts.json
```

## Completion criteria

- [ ] JSON with `counts`, `ids_by_bucket`, `method=few_shot_tfidf_cosine`
- [ ] C list spot-checked before citing as fact
- [ ] `checked_at` present

## Common Pitfalls

1. Treating confidence as accuracy
2. Filing society-treasury money posts as C
3. Not updating exemplars when genre drifts

## Verification Checklist

- [ ] Unit tests on labeled fixtures pass
- [ ] Exemplars cover A/B/C/G
