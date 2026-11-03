#!/usr/bin/env python3
"""Memory writer (code) — file verdict + lesson into research memory.

stdin: { experiment_spec, execution_result, verdict }
stdout: { memory, note }
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import load_memory, read_json_stdin, save_memory, write_json  # noqa: E402


def main() -> int:
    inp = read_json_stdin()
    spec = inp.get("experiment_spec") or {}
    result = inp.get("execution_result") or {}
    verdict = inp.get("verdict") or {}

    mem = load_memory()
    entry = {
        "experiment_id": spec.get("experiment_id") or result.get("experiment_id"),
        "model_family": spec.get("model_family") or result.get("model_family"),
        "hyperparameters": spec.get("hyperparameters") or result.get("hyperparameters"),
        "status": result.get("status"),
        "val_f1": (result.get("validation_metrics") or {}).get("f1"),
        "judge_action": verdict.get("action"),
        "observation": verdict.get("observation"),
    }
    mem.setdefault("history", []).append(entry)
    lesson = verdict.get("observation") or "recorded trial"
    mem.setdefault("lessons", []).append(str(lesson)[:240])
    # Keep memory bounded for classroom demos.
    mem["history"] = mem["history"][-30:]
    mem["lessons"] = mem["lessons"][-30:]
    save_memory(mem)
    write_json({"memory": mem, "note": "appended history+lesson"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
