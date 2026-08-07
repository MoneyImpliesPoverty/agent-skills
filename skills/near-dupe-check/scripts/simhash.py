"""64-bit simhash over character 3-grams. Stdlib only."""
from __future__ import annotations

import math
import re
from collections import Counter


def normalize_text(title: str, body: str = "") -> str:
    return re.sub(r"\s+", " ", f"{title or ''}\n{body or ''}".lower()).strip()


def _stable_hash(s: str) -> int:
    """FNV-1a 64-bit — stable across processes (unlike PYTHONHASHSEED)."""
    h = 0xCBF29CE484222325
    for ch in s.encode():
        h ^= ch
        h = (h * 0x100000001B3) & ((1 << 64) - 1)
    return h


def simhash64(text: str) -> int:
    text = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if len(text) < 3:
        text = (text + "   ")[:3]
    bits = [0] * 64
    for i in range(len(text) - 2):
        gram = text[i : i + 3]
        h = _stable_hash(gram)
        for b in range(64):
            if h & (1 << b):
                bits[b] += 1
            else:
                bits[b] -= 1
    out = 0
    for b in range(64):
        if bits[b] >= 0:
            out |= 1 << b
    return out


def hamming(a: int, b: int) -> int:
    return ((a ^ b) & ((1 << 64) - 1)).bit_count()


def char_ngram_cosine(a: str, b: str, n: int = 3) -> float:
    def grams(s: str) -> Counter:
        s = re.sub(r"\s+", " ", (s or "").lower()).strip()
        if len(s) < n:
            s = s + " " * n
        return Counter(s[i : i + n] for i in range(len(s) - n + 1))

    ca, cb = grams(a), grams(b)
    keys = set(ca) | set(cb)
    dot = sum(ca[k] * cb[k] for k in keys)
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
