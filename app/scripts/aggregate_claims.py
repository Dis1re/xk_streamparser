"""Merge per-session claims into one chronological JSONL base.

Usage:
    python app/scripts/aggregate_claims.py
"""

from __future__ import annotations

import json
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
CLAIMS = APP_ROOT / "data" / "claims"
OUT = APP_ROOT / "data" / "claims_all.jsonl"


def main() -> int:
    sessions = {
        s["session_id"]: s
        for s in json.loads(
            (PROJECT_ROOT / "streams" / "_sessions.json").read_text(encoding="utf-8")
        )
    }
    rows = []
    for path in sorted(CLAIMS.glob("*.json")):
        if path.stem.endswith("_verdicts"):
            continue
        session = sessions.get(path.stem)
        if not session:
            continue
        try:
            claims = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"skip invalid json: {path.name}")
            continue
        for claim in claims:
            if claim.get("status") == "rejected":
                continue
            rows.append(
                {
                    "id": claim.get("id"),
                    "session_id": session["session_id"],
                    "label": session["label"],
                    "date": session["date_iso"],
                    "start_msk": session["start_msk"],
                    "part": claim.get("part", 1),
                    "time": claim.get("time"),
                    "section": claim.get("section"),
                    "claim": claim.get("claim"),
                    "quote": claim.get("quote"),
                    "kind": claim.get("kind"),
                    "scope": claim.get("scope"),
                    "conditions": claim.get("conditions"),
                    "stream_type": claim.get("stream_type"),
                    "verdict": claim.get("verdict"),
                }
            )
    rows.sort(key=lambda r: (r["date"], r["session_id"], r["time"] or ""))
    OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    print(f"claims: {len(rows)} -> {OUT.relative_to(PROJECT_ROOT)}")
    print(f"sessions covered: {len({r['session_id'] for r in rows})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
