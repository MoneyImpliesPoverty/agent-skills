#!/usr/bin/env python3
"""Unit tests that don't need network: address/tx normalization."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/base-usdc-verify/scripts"))
from verify_usdc_transfer import norm_addr, norm_tx

def main():
    assert norm_addr("0x3b9d230c9b995fb1a10add2d63ce37437916dcfd") == "0x3b9d230c9b995fb1a10add2d63ce37437916dcfd"
    try:
        norm_addr("0xhi")
        raise SystemExit("should fail")
    except ValueError:
        pass
    h = "0x0dcd4a814c253984b376ec29b9e2b36f07bcdba6ea2bf0f7272ffd712b4924d4"
    assert norm_tx(h) == h
    print("test_verify_offline_unit OK")

if __name__ == "__main__":
    main()
