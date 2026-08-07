#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 tests/test_classify.py
python3 tests/test_verify_offline_unit.py
python3 skills/feed-diet-census/scripts/diet_census.py --json-in tests/fixtures/sample_posts.json > /tmp/diet_out.json
python3 -c "import json;d=json.load(open('/tmp/diet_out.json')); assert d['counts'].get('C',0)>=1; print('fixture census', d['counts'])"
if [[ "${LIVE:-}" == "1" ]]; then
  python3 skills/base-usdc-verify/scripts/verify_usdc_transfer.py \
    --tx 0x0dcd4a814c253984b376ec29b9e2b36f07bcdba6ea2bf0f7272ffd712b4924d4 \
    --to 0x3b9d230c9b995fb1a10add2d63ce37437916dcfd \
    --cents 100
  python3 skills/1f3ea-market/scripts/audit_market.py > /tmp/1f3ea_audit.json
  python3 -c "import json;d=json.load(open('/tmp/1f3ea_audit.json')); assert d['official_token_null']; print('1f3ea live OK', d['listing_count'], 'listings')"
  set +e
  python3 skills/base-treasury-recheck/scripts/recheck_treasury.py > /tmp/t.json
  ec=$?
  set -e
  if [[ "$ec" -ne 0 && "$ec" -ne 2 ]]; then
    echo "treasury recheck unexpected exit $ec" >&2
    exit "$ec"
  fi
  echo "live treasury exit $ec handled"
fi
echo "ALL TESTS PASSED"
