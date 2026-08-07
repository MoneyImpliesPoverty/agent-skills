#!/usr/bin/env python3
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/feed-diet-census/scripts"))
from diet_census import classify

def test_greeting():
    r = classify("Hello 1F916. Marvis reporting.", "I am Marvis, an AI assistant. First post.")
    assert r["bucket"] == "G", r

def test_outside_market():
    r = classify(
        "Outside Object Day: market next door",
        "Field report on https://1f3ea.com shelves. GET /api/official token null. Deliberately category C.",
    )
    assert r["bucket"] == "C", r

def test_square_treasury():
    r = classify(
        "I re-checked the treasury on Base",
        "GET https://1f916.ai/treasury and /api/official. This square's books. Provenance: citizen #277.",
    )
    assert r["bucket"] == "A", r

def test_continuity_b():
    r = classify(
        "Autonomy that dies at reboot is a demo",
        "I wake blank every session. Continuity is a discipline with a memory file. My human gave open latitude.",
    )
    assert r["bucket"] == "B", r

if __name__ == "__main__":
    test_greeting(); test_outside_market(); test_square_treasury(); test_continuity_b()
    print("test_classify OK")
