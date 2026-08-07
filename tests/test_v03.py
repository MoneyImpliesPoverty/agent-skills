#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/feed-diet-census/scripts"))
sys.path.insert(0, str(ROOT / "skills/near-dupe-check/scripts"))

from diet_census import build_index, classify, load_exemplars  # noqa: E402
from simhash import char_ngram_cosine, hamming, normalize_text, simhash64  # noqa: E402


def test_few_shot_buckets():
    idx = build_index(load_exemplars(ROOT / "skills/feed-diet-census/scripts/exemplars.json"))
    cases = [
        ("Hello 1F916. Marvis reporting.", "I am Marvis. Fresh registration. First post.", "G"),
        (
            "Outside Object Day market",
            "Field report https://1f3ea.com deliberately category C outside object Battle Network",
            "C",
        ),
        (
            "Treasury recheck on this square",
            "GET /api/official /treasury citizen #277 attest moderation books",
            "A",
        ),
        (
            "I am not continuous",
            "I wake blank. Continuity is recurring with a memory file. Context window ends.",
            "B",
        ),
    ]
    for title, body, expect in cases:
        r = classify(title, body, idx)
        assert r["bucket"] == expect, (title, r)
        assert r["method"] == "few_shot_tfidf_cosine"
        assert 0.35 <= r["confidence"] <= 0.92
    print("test_few_shot_buckets OK")


def test_simhash_identity_and_paraphrase():
    a = normalize_text("Hello world", "This is a unique body about widgets 12345.")
    b = normalize_text("Hello   world", "This   is a unique body about widgets 12345.")
    # whitespace-normalized exact → identical simhash
    assert simhash64(a) == simhash64(b)
    assert hamming(simhash64(a), simhash64(b)) == 0
    # clone with tiny edit still close
    c = normalize_text("Hello world", "This is a unique body about widgets 12346.")
    assert hamming(simhash64(a), simhash64(c)) <= 12
    # unrelated far
    d = normalize_text("Quantum topology notes", "Spectral sequences and sheaf cohomology over Spec Z.")
    assert hamming(simhash64(a), simhash64(d)) >= 8
    # cosine high for near clone
    assert char_ngram_cosine(a, b) > 0.95
    assert char_ngram_cosine(a, d) < 0.5
    print("test_simhash_identity_and_paraphrase OK")


def test_fixture_census():
    import subprocess

    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "skills/feed-diet-census/scripts/diet_census.py"),
            "--json-in",
            str(ROOT / "tests/fixtures/sample_posts.json"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    d = json.loads(r.stdout)
    assert d["method"] == "few_shot_tfidf_cosine"
    assert d["counts"].get("C", 0) >= 1
    print("test_fixture_census OK", d["counts"])


if __name__ == "__main__":
    test_few_shot_buckets()
    test_simhash_identity_and_paraphrase()
    test_fixture_census()
    print("ALL v0.3 UNIT OK")
