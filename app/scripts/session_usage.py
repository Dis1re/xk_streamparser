"""Print token usage and tool activity for one subagent session.

Usage:
    python app/scripts/session_usage.py <session_id>
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

DB = Path(os.path.expanduser("~/.local/share/opencode/opencode.db"))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: session_usage.py <session_id>")
        return 2
    sid = sys.argv[1]
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    info = conn.execute(
        "select title, tokens_input, tokens_output, tokens_reasoning, "
        "tokens_cache_read, time_created, time_idle from session_v2 where id = ?",
        (sid,),
    ).fetchone()
    if not info:
        print(f"session not found: {sid}")
        return 1

    turns = 0
    tools: Counter[str] = Counter()
    for row in conn.execute(
        "select data from session_message where session_id = ? and type = 'assistant'",
        (sid,),
    ):
        turns += 1
        data = json.loads(row["data"])
        for part in data.get("content", []):
            if part.get("type") == "tool":
                tools[part.get("name")] += 1

    inp = info["tokens_input"] or 0
    cache = info["tokens_cache_read"] or 0
    out = info["tokens_output"] or 0
    reason = info["tokens_reasoning"] or 0
    total = inp + cache + out + reason
    wall = ((info["time_idle"] or 0) - (info["time_created"] or 0)) / 60000

    # DeepSeek V4.1 Flash, off-peak, USD per 1M tokens.
    cost = inp * 0.15 / 1e6 + cache * 0.003 / 1e6 + (out + reason) * 0.60 / 1e6

    print(f"session: {sid}")
    print(f"title: {info['title']}")
    print(f"turns: {turns}")
    print(f"tools: {dict(tools.most_common())}")
    print(f"input: {inp:,}")
    print(f"cache_read: {cache:,}")
    print(f"output: {out:,}")
    print(f"reasoning: {reason:,}")
    print(f"total_tokens: {total:,}")
    print(f"wall_min: {wall:.1f}")
    print(f"cost_usd_offpeak: {cost:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
