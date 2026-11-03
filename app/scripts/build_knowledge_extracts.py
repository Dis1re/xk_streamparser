"""Build thematic extracts from stream notes for the knowledge base."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
NOTES = PROJECT_ROOT / "streams"
OUT = PROJECT_ROOT / "notes" / "_extracts"


def label_for(path: Path) -> str:
    name = path.stem
    m = re.match(r"bonus_(\d+)", name)
    if m:
        return f"({int(m.group(1))})"
    m = re.match(r"(\d+)_(\d+)_", name)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    m = re.match(r"(\d+)_", name)
    if m:
        return m.group(1)
    return name


SECTION_THEMES = {
    "design": [
        "геймдев", "геймдизайн", "ux", "механик", "левел", "обучен",
        "баланс", "визуал", "разбор", "tier", "dicewood", "roblox",
        "система", "результаты ludum", "рынок и жанры", "гейм дизайн",
        "геймдизайнер", "игровой баланс", "уровн", "нарратив",
    ],
    "dev": [
        "unity", "код", "архитект", "разработ", "инструмент", "технолог",
        "планирован", "нодов", "техническ", "роль разработчика",
        "производство", "прототип", "рефактор",
    ],
    "marketing": [
        "маркет", "steam", "itch", "вишлист", "tiktok", "next fest",
        "позиционирован", "монетизац", "цен", "промо", "трейлер",
        "обзор", "издател", "паблишер",
    ],
    "ai": ["ai", "ии", "нейросет", "chatgpt", "claude", "deepseek", "llm"],
    "business": [
        "деньги", "бизнес", "рынок", "индустр", "метрик", "налог",
        "виз", "монетизац", "зарплат", "доход",
    ],
    "london": ["лондон", "англ"],
    "books": ["книж", "ресурс"],
    "general": ["главное"],
    "quotes": ["цитат"],
}

DESIGN_PRIORITY = [
    (
        "design_ux",
        [
            "ux", "интерфейс", "обучен", "туториал", "онбординг", "читаем",
            "подсказк", "курсор", "кнопк", "хитбокс", "фидбек", "отклик",
            "телеграф", "аффорданс", "меню", "hud", "иконк", "текст",
        ],
    ),
    (
        "design_balance",
        [
            "баланс", "экономик", "сложност", "прогресс", "награ", "мета",
            "реликв", "луп", "цикл", "пейсинг", "темп", "контент",
            "фронтлоад", "гринд", "рандом", "шанс", "урон", "hp",
        ],
    ),
    (
        "design_level",
        [
            "левел", "уровень", "сеттинг", "нарратив", "истори", "квест",
            "туман", "карта", "лор", "атмосфер", "окружен",
        ],
    ),
    (
        "design_production",
        [
            "скоуп", "объем", "срок", "команд", "продюс", "рефактор",
            "прототип", "джем", "плейтест", "тест", "выгор", "релиз",
            "виз", "деньг", "бюджет", "издател", "маркет",
        ],
    ),
]

MARKETING_PRIORITY = [
    (
        "marketing_steam",
        [
            "steam", "вишлист", "страниц", "алгоритм", "обзор", "next fest",
            "фестивал", "тег", "капсул", "скриншот", "демо", "рейтинг",
            "конверси", "продаж", "цен",
        ],
    ),
]


def section_themes(section: str) -> list[str]:
    s = section.lower()
    hits = [theme for theme, words in SECTION_THEMES.items() if any(w in s for w in words)]
    if not hits:
        hits = ["other"]
    if "ai" in s and "ai" not in hits:
        hits.append("ai")
    return hits


def first_match(text: str, rules: list[tuple[str, list[str]]], default: str) -> str:
    s = text.lower()
    for name, words in rules:
        if any(w in s for w in words):
            return name
    return default


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    buckets: dict[str, list[str]] = defaultdict(list)
    sections: Counter[str] = Counter()
    notes_seen: set[str] = set()

    for path in sorted(NOTES.glob("*.md")):
        if path.name in ("README.md", "_template.md"):
            continue
        label = label_for(path)
        notes_seen.add(label)
        section = ""
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.startswith("## "):
                section = raw[3:].strip()
                sections[section] += 1
                continue
            line = raw.strip()
            if not line or section == "":
                continue
            if line.startswith("- "):
                bullet = line[2:].strip()
            elif re.match(r"^\d+\.\s+", line):
                bullet = re.sub(r"^\d+\.\s+", "", line).strip()
            else:
                continue
            if not bullet:
                continue
            ref = f"[{label}] {bullet}"
            for theme in section_themes(section):
                if theme == "design":
                    buckets[first_match(bullet, DESIGN_PRIORITY, "design_analysis")].append(f"- {ref}")
                elif theme == "marketing":
                    buckets[first_match(bullet, MARKETING_PRIORITY, "marketing_promo")].append(f"- {ref}")
                elif theme == "dev":
                    buckets["design_production"].append(f"- {ref}")
                elif theme == "books":
                    buckets["design_production"].append(f"- {ref}")
                elif theme == "quotes":
                    continue
                else:
                    buckets[theme].append(f"- {ref}")

    analysis = buckets.pop("design_analysis", [])
    if analysis:
        middle = len(analysis) // 2
        buckets["design_analysis_1"] = analysis[:middle]
        buckets["design_analysis_2"] = analysis[middle:]

    for theme, lines in sorted(buckets.items()):
        target = OUT / f"{theme}.md"
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{theme}: {len(lines)} bullets, {len(target.read_text(encoding='utf-8'))} chars")

    print(f"notes seen: {len(notes_seen)}")
    print("unclassified sections:")
    for section, count in sections.most_common():
        if section_themes(section) == ["other"]:
            print(f"  {count} x {section}")


if __name__ == "__main__":
    main()
