from pathlib import Path

pairs = [
    ("101", "00:34:00"),
    ("bonus_69", "01:03:00"),
    ("bonus_69", "01:04:00"),
]
out = []
for sid, stamp in pairs:
    backup_note = next((Path("data/_audit_v2") / sid).glob("*.md"))
    current_note = next(Path("../streams").glob(f"{sid}_*.md"))
    def line(path):
        for text in path.read_text(encoding="utf-8").splitlines():
            if text.startswith(f"- **{stamp}**"):
                return text
        return "(no line)"
    out.append(f"=== {sid} [{stamp}] ===")
    out.append("OLD: " + line(backup_note))
    out.append("NEW: " + line(current_note))
    out.append("")
Path("data/_compare_rerun.txt").write_text("\n".join(out), encoding="utf-8")
print("written")
