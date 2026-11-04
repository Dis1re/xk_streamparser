from pathlib import Path

pairs = [
    ("../streams", "bonus_42_*.md", "00:12:00"),
    ("../streams", "bonus_3_*.md", "02:14:00"),
    ("../streams", "bonus_69_*.md", "01:04:00"),
    ("../streams", "101_*.md", "00:34:00"),
]
out = []
for folder, pattern, stamp in pairs:
    path = next(Path(folder).glob(pattern))
    line = next(
        l for l in path.read_text(encoding="utf-8").splitlines() if l.startswith(f"- **{stamp}**")
    )
    out.append(f"{path.name} [{stamp}]\n{line}\n")
Path("data/_audit_lines.txt").write_text("\n".join(out), encoding="utf-8")
print("written")
