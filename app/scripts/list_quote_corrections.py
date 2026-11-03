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
out = []
for claim in claims:
    verdict = verdicts.get(claim["id"])
    if not verdict or verdict["verdict"] == "confirmed":
        continue
    if claim["section"] != "Цитаты":
        continue
    out.append(
        f"id: {claim['id']}\ntime: {claim['time']}\n"
        f"verdict: {verdict['verdict']}\n"
        f"new: {verdict['corrected_claim']}\n"
        f"quote: {verdict['quote']}\n"
    )
Path(f"data/_quotes_{sid}.md").write_text("\n".join(out), encoding="utf-8")
print(f"quote corrections: {len(out)}")
