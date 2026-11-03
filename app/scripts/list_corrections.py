import json
import sys
from pathlib import Path

sid = sys.argv[1]
claims = json.loads(Path(f"data/claims/{sid}.json").read_text(encoding="utf-8"))
verdicts = {
    v["id"]: v
    for v in json.loads(
        Path(f"data/claims/{sid}_verdicts.json").read_text(encoding="utf-8")
    )
}
for claim in claims:
    verdict = verdicts.get(claim["id"])
    if verdict and verdict["verdict"] == "corrected":
        print(f"{claim['id']} | {claim['section']} | {claim['time']}")
        print("  now:", claim["claim"])
        print("  new:", verdict["corrected_claim"])
        print("  quote:", verdict["quote"])
        print()
