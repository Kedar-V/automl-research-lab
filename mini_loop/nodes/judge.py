#!/usr/bin/env python3
"""Judge (LLM) — verdict from validation evidence.

stdin: { execution_result, experiment_spec, target_score?, brief? }
stdout: { verdict, used_llm, note }
verdict: { action: accept|revise|reject, observation, next_action }
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DEFAULT_MODEL,
    extract_json_object,
    llm_configured,
    openrouter_chat,
    read_json_stdin,
    write_json,
)


def _heuristic(result: dict, target_score: float) -> dict:
    status = result.get("status")
    f1 = float((result.get("validation_metrics") or {}).get("f1") or 0)
    if status != "succeeded":
        return {
            "action": "revise",
            "observation": f"run failed: {result.get('error')}",
            "next_action": "propose next experiment",
        }
    if f1 >= target_score:
        return {
            "action": "accept",
            "observation": f"val f1 {f1:.3f} meets target {target_score:.2f}",
            "next_action": "finalize",
        }
    return {
        "action": "revise",
        "observation": f"val f1 {f1:.3f} below target {target_score:.2f}",
        "next_action": "propose next experiment",
    }


def main() -> int:
    inp = read_json_stdin()
    result = inp.get("execution_result") or {}
    spec = inp.get("experiment_spec") or {}
    brief = inp.get("brief") or {}
    target_score = float(inp.get("target_score") or 0.8)

    system = (
        "You are the Judge lead in a live AutoML research loop. "
        "Decide from VALIDATION evidence only — never invent holdout scores. "
        "Return ONLY one JSON object with keys: "
        "action (accept|revise|reject), observation (1-2 sentences with the val F1), "
        "next_action (short instruction for the next agent). "
        "accept only if validation F1 meets or exceeds target_score; "
        "revise when under target but recoverable; reject for hopeless/broken runs."
    )
    user = (
        f"target_score={target_score}\n"
        f"spec={json.dumps(spec, default=str)}\n"
        f"result={json.dumps(result, default=str)}\n"
        f"brief={json.dumps(brief, default=str)}\n"
    )

    used_llm = False
    note = "heuristic"
    verdict = _heuristic(result, target_score)
    if llm_configured():
        content, err = openrouter_chat(system, user, max_tokens=500, temperature=0.1)
        if content:
            parsed = extract_json_object(content)
            if parsed and parsed.get("action") in {"accept", "revise", "reject"}:
                verdict = {
                    "action": parsed["action"],
                    "observation": parsed.get("observation")
                    or verdict.get("observation"),
                    "next_action": parsed.get("next_action")
                    or verdict.get("next_action"),
                }
                used_llm = True
                note = "openrouter live verdict"
            else:
                note = f"llm unparsable; heuristic ({err or 'ok'})"
        else:
            note = f"{err or 'no llm'}; heuristic"

    write_json(
        {
            "verdict": verdict,
            "used_llm": used_llm,
            "model": os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL) if used_llm else None,
            "note": note,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
