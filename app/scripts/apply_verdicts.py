"""Merge verifier verdicts into the claims file for a session.

Usage:
    python app/scripts/apply_verdicts.py 186
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
CLAIMS_DIR = APP_ROOT / "data" / "claims"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_verdicts.py <session_id>")
        return 2
    session_id = sys.argv[1]
    claims_path = CLAIMS_DIR / f"{session_id}.json"
    verdicts_path = CLAIMS_DIR / f"{session_id}_verdicts.json"
    claims = json.loads(claims_path.read_text(encoding="utf-8"))
    verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
    by_id = {v["id"]: v for v in verdicts}

    changed = 0
    for claim in claims:
        verdict = by_id.get(claim["id"])
        if not verdict:
            claim["verdict"] = "unchecked"
            continue
        claim["verdict"] = verdict["verdict"]
        claim["verdict_reason"] = verdict["reason"]
        if verdict["verdict"] == "corrected":
            if verdict.get("corrected_claim"):
                claim["claim"] = verdict["corrected_claim"]
            if verdict.get("corrected_scope"):
                claim["scope"] = verdict["corrected_scope"]
            if verdict.get("corrected_conditions"):
                claim["conditions"] = verdict["corrected_conditions"]
            changed += 1
        elif verdict["verdict"] == "rejected":
            claim["status"] = "rejected"
            changed += 1

    claims_path.write_text(
        json.dumps(claims, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(claims)} claims, updated {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
