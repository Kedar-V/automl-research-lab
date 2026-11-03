#!/usr/bin/env python3
"""Context builder (code) — brief for next hypothesis (drop repeats).

stdin: { profile, memory? }
stdout: { brief, note }
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_memory, read_json_stdin, write_json  # noqa: E402


def main() -> int:
    inp = read_json_stdin()
    profile = inp.get("profile") or {}
    mem = inp.get("memory") or load_memory()
    history = list(mem.get("history") or [])
    lessons = list(mem.get("lessons") or [])

    seen = set()
    deduped = []
    for h in reversed(history):
        key = (
            str(h.get("model_family")),
            str(sorted((h.get("hyperparameters") or {}).items())),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(h)
    deduped.reverse()

    brief = {
        "profile_notes": (profile.get("notes") or [])[:5],
        "recommended_drops": profile.get("recommended_drops") or [],
        "history": deduped[-5:],
        "findings": list(mem.get("findings") or [])[-5:],
        "lessons": lessons[-5:],
        "avoid": [
            {
                "model_family": h.get("model_family"),
                "hyperparameters": h.get("hyperparameters"),
            }
            for h in deduped
            if h.get("judge_action") in {"reject", "revise"} or h.get("status") == "failed"
        ][-8:],
    }
    write_json({"brief": brief, "note": f"brief from {len(history)} history rows"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
