#!/usr/bin/env python3
"""Data Scientist (LLM, once/session) — profile CSV + leakage flags.

stdin: { dataset_path, target_column }
stdout: { profile, used_llm, note }
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DEFAULT_MODEL,
    extract_json_object,
    llm_configured,
    openrouter_chat,
    read_json_stdin,
    write_json,
)


def _heuristic_profile(df: pd.DataFrame, target: str) -> dict:
    cols = list(df.columns)
    leakage = [
        c
        for c in cols
        if c != target
        and (
            c.lower() in {"passengerid", "name", "ticket", "cabin", "id"}
            or "id" == c.lower()
            or c.lower().endswith("_id")
        )
    ]
    num = [c for c in cols if c != target and pd.api.types.is_numeric_dtype(df[c])]
    cat = [c for c in cols if c != target and c not in num and c not in leakage]
    return {
        "n_rows": int(len(df)),
        "n_columns": int(len(cols)),
        "target": target,
        "target_rate": float(df[target].mean())
        if target in df and pd.api.types.is_numeric_dtype(df[target])
        else None,
        "numeric_features": num,
        "categorical_features": cat,
        "leakage_suspects": leakage,
        "recommended_drops": leakage,
        "notes": [
            "Heuristic profile (OpenRouter unavailable).",
            "Drop id-like / high-cardinality text before modeling.",
        ],
    }


def main() -> int:
    inp = read_json_stdin()
    path = Path(inp["dataset_path"])
    target = inp.get("target_column") or "Survived"
    df = pd.read_csv(path)
    if target not in df.columns:
        write_json({"error": f"target {target!r} missing", "profile": {}})
        return 1

    missing = {c: float(df[c].isna().mean()) for c in df.columns}
    nunique = {c: int(df[c].nunique(dropna=True)) for c in df.columns}
    sample = df.head(6).astype(str).replace("nan", "").to_dict(orient="records")
    system = (
        "You are the Data Scientist lead in a live AutoML research lab. "
        "Profile a tabular classification CSV and return ONLY one JSON object with keys: "
        "n_rows (int), n_columns (int), target (string), target_rate (number|null), "
        "numeric_features (string[]), categorical_features (string[]), "
        "leakage_suspects (string[]), recommended_drops (string[]), "
        "notes (string[], short bullets about risks and modeling advice). "
        "Flag PassengerId/Name/Ticket/Cabin-style identifiers and near-unique text as leakage. "
        "Do not invent columns that are not present."
    )
    user = (
        f"dataset={path.name}\ntarget={target}\nn_rows={len(df)}\n"
        f"columns={list(df.columns)}\n"
        f"dtypes={{{', '.join(f'{c}:{df[c].dtype}' for c in df.columns)}}}\n"
        f"missing_rate={missing}\nnunique={nunique}\n"
        f"sample_rows={sample}\n"
    )

    used_llm = False
    note = "heuristic"
    profile = _heuristic_profile(df, target)
    if llm_configured():
        content, err = openrouter_chat(system, user, max_tokens=900, temperature=0.15)
        if content:
            parsed = extract_json_object(content)
            if parsed and (
                "recommended_drops" in parsed
                or "leakage_suspects" in parsed
                or "numeric_features" in parsed
            ):
                profile = parsed
                profile.setdefault("n_rows", int(len(df)))
                profile.setdefault("n_columns", int(len(df.columns)))
                profile.setdefault("target", target)
                profile.setdefault(
                    "recommended_drops",
                    profile.get("leakage_suspects") or [],
                )
                used_llm = True
                note = "openrouter live profile"
            else:
                note = f"llm unparsable; heuristic ({err or 'ok'})"
        else:
            note = f"{err or 'no llm'}; heuristic"

    write_json(
        {
            "profile": profile,
            "used_llm": used_llm,
            "model": os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL) if used_llm else None,
            "note": note,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
