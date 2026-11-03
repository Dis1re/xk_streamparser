"""Show a claim, its quote and the transcript around the claim time.

Usage:
    python app/scripts/show_quote_context.py bonus_46 bonus_46-014 bonus_46-028
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
CLAIMS = APP_ROOT / "data" / "claims"
SESSIONS = APP_ROOT / "data" / "_sessions"


def parse_hms(value: str) -> int:
    parts = [int(x) for x in value.split(":")]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def main() -> int:
    sid, *claim_ids = sys.argv[1:]
    claims = {
        c["id"]: c
        for c in json.loads((CLAIMS / f"{sid}.json").read_text(encoding="utf-8"))
    }
    lines = (SESSIONS / sid / "transcript.txt").read_text(encoding="utf-8").splitlines()

    out = []
    for cid in claim_ids:
        claim = claims[cid]
        t = parse_hms(claim["time"])
        out.append(f"=== {cid} at {claim['time']} | {claim['section']}")
        out.append(f"CLAIM: {claim['claim']}")
        out.append(f"QUOTE: {claim['quote']}")
        out.append("--- transcript ---")
        for line in lines:
            if not line.startswith("["):
                continue
            try:
                lt = parse_hms(line[1:9])
            except ValueError:
                continue
            if t - 90 <= lt <= t + 150:
                out.append(line)
        out.append("")

    path = APP_ROOT / "data" / f"_ctx_{sid}.txt"
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"written {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
