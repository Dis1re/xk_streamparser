"""Verify citations in notes/*.md against the verified claims base.

Usage:
    python app/scripts/check_knowledge.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
NOTES = APP_ROOT.parent / "notes"
CLAIMS = APP_ROOT / "data" / "claims_all.jsonl"

CITE_RE = re.compile(
    r"\[(\d{4}-\d{2}-\d{2})\s*·\s*([^\]]+?)\s+(\d{1,2}):(\d{2}):(\d{2})\]"
)


def parse_hms(h: str, m: str, s: str) -> int:
    return int(h) * 3600 + int(m) * 60 + int(s)


def norm_label(value: str) -> str:
    value = value.replace("(", "").replace(")", "").strip()
    return value.split(" P")[0].strip()


def main() -> int:
    index: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    for line in CLAIMS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        h, m, s = (int(x) for x in row["time"].split(":"))
        key = (row["date"], norm_label(row["label"]), int(row.get("part") or 1))
        index[key].append(h * 3600 + m * 60 + s)

    missing = []
    total = 0
    for path in sorted(NOTES.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for match in CITE_RE.finditer(text):
            total += 1
            date, label_raw, h, m, s = match.groups()
            label = norm_label(label_raw)
            part_match = re.search(r"\bP(\d+)\b", label_raw)
            part = int(part_match.group(1)) if part_match else None
            seconds = parse_hms(h, m, s)

            candidates = []
            parts = [part] if part else [1, 2, 3, 4]
            for p in parts:
                candidates.extend(index.get((date, label, p), []))
            if not any(abs(value - seconds) <= 60 for value in candidates):
                missing.append((path.name, match.group(0), len(candidates)))

    print(f"citations checked: {total}, not found: {len(missing)}")
    for name, cite, count in missing:
        print(f"  {name}: {cite}  (claims at that label/date: {count})")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
