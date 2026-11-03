#!/usr/bin/env python3
"""Hypothesis Generator (LLM) — one ExperimentSpec.

stdin: { profile, brief?, history? }
stdout: { experiment_spec, used_llm, note }
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

FAMILIES = (
    "logistic_regression",
    "random_forest",
    "hist_gradient_boosting",
)


def _heuristic_spec(profile: dict, history: list) -> dict:
    tried = {h.get("model_family") for h in history if isinstance(h, dict)}
    family = next((f for f in FAMILIES if f not in tried), "random_forest")
    n = len(history)
    if family == "logistic_regression":
        hp = {
            "C": [0.25, 0.5, 1.0, 2.0][n % 4],
            "max_iter": 500,
            "class_weight": "balanced",
        }
    elif family == "hist_gradient_boosting":
        hp = {
            "learning_rate": [0.05, 0.1, 0.15][n % 3],
            "max_iter": 80 + 20 * (n % 3),
            "class_weight": "balanced",
        }
    else:
        hp = {
            "n_estimators": 80 + 40 * (n % 4),
            "max_depth": [3, 5, 8, 12][n % 4],
            "class_weight": "balanced",
        }
    drops = list(profile.get("recommended_drops") or profile.get("leakage_suspects") or [])
    for leak in ("fraud_probability", "transaction_id", "customer_id", "merchant_id"):
        if leak not in drops:
            drops.append(leak)
    return {
        "experiment_id": f"exp-{n + 1}",
        "model_family": family,
        "hyperparameters": hp,
        "drop_columns": drops,
        "rationale": f"heuristic novelty pick #{n + 1}: {family} (balanced for rare positives)",
    }


def main() -> int:
    inp = read_json_stdin()
    profile = inp.get("profile") or {}
    brief = inp.get("brief") or {}
    history = inp.get("history") or brief.get("history") or []

    system = (
        "You are the Hypothesis Generator lead in a live AutoML research loop. "
        "Propose exactly ONE new tabular classification experiment. "
        "Return ONLY one JSON object with keys: experiment_id, model_family "
        "(must be logistic_regression|random_forest|hist_gradient_boosting), "
        "hyperparameters (object of numeric/string params), drop_columns (string[]), "
        "rationale (1-2 sentences citing the profile and prior lessons). "
        "Prefer models/hyperparameters not already tried in history. "
        "Respect recommended_drops / leakage_suspects from the profile. "
        "Never use fraud_probability as a feature. "
        "For imbalanced targets (e.g. is_fraud), set class_weight to balanced "
        "when the family supports it."
    )
    user = (
        f"profile={json.dumps(profile, default=str)}\n"
        f"brief={json.dumps(brief, default=str)}\n"
        f"recent_history={json.dumps(history[-5:], default=str)}\n"
        f"allowed_families={list(FAMILIES)}\n"
    )

    used_llm = False
    note = "heuristic"
    spec = _heuristic_spec(profile, history)
    if llm_configured():
        content, err = openrouter_chat(system, user, max_tokens=700, temperature=0.35)
        if content:
            parsed = extract_json_object(content)
            family = (parsed or {}).get("model_family")
            if parsed and family in FAMILIES:
                spec = parsed
                spec.setdefault("experiment_id", f"exp-{len(history) + 1}")
                spec.setdefault("hyperparameters", {})
                spec.setdefault(
                    "drop_columns",
                    profile.get("recommended_drops")
                    or profile.get("leakage_suspects")
                    or [],
                )
                used_llm = True
                note = "openrouter live hypothesis"
            else:
                note = f"llm unparsable; heuristic ({err or family or 'ok'})"
        else:
            note = f"{err or 'no llm'}; heuristic"

    write_json(
        {
            "experiment_spec": spec,
            "used_llm": used_llm,
            "model": os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL) if used_llm else None,
            "note": note,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
