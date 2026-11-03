#!/usr/bin/env python3
"""ML Engineer (code + optional LLM repair) — validate, train, score.

stdin: {
  dataset_path, target_column, experiment_spec, holdout_frac?, seed?,
  repair_budget?
}
stdout: { execution_result, experiment_spec, repaired, used_llm_repair, note }
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    llm_configured,
    extract_json_object,
    openrouter_chat,
    read_json_stdin,
    write_json,
)


ALLOWED = {
    "logistic_regression",
    "random_forest",
    "hist_gradient_boosting",
}


def _validate(spec: dict) -> str | None:
    if not isinstance(spec, dict):
        return "spec must be object"
    if spec.get("model_family") not in ALLOWED:
        return f"model_family must be one of {sorted(ALLOWED)}"
    hp = spec.get("hyperparameters")
    if hp is not None and not isinstance(hp, dict):
        return "hyperparameters must be object"
    return None


def _repair_heuristic(spec: dict, error: str) -> dict:
    fixed = dict(spec)
    fixed["hyperparameters"] = dict(spec.get("hyperparameters") or {})
    fam = fixed.get("model_family")
    if fam not in ALLOWED:
        fixed["model_family"] = "random_forest"
    if fam == "logistic_regression":
        fixed["hyperparameters"] = {"C": 1.0, "max_iter": 400}
    elif fam == "hist_gradient_boosting":
        fixed["hyperparameters"] = {"learning_rate": 0.1, "max_iter": 100}
    else:
        fixed["model_family"] = "random_forest"
        fixed["hyperparameters"] = {"n_estimators": 100, "max_depth": 6}
    fixed["rationale"] = f"repaired after: {error[:120]}"
    return fixed


def _build_model(family: str, hp: dict):
    if family == "logistic_regression":
        return LogisticRegression(
            C=float(hp.get("C", 1.0)),
            max_iter=int(hp.get("max_iter", 300)),
        )
    if family == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            learning_rate=float(hp.get("learning_rate", 0.1)),
            max_iter=int(hp.get("max_iter", 100)),
        )
    return RandomForestClassifier(
        n_estimators=int(hp.get("n_estimators", 100)),
        max_depth=hp.get("max_depth", 6),
        random_state=42,
    )


def _run_once(df: pd.DataFrame, target: str, spec: dict, seed: int, holdout_frac: float) -> dict:
    y = df[target]
    drops = [c for c in (spec.get("drop_columns") or []) if c in df.columns and c != target]
    X = df.drop(columns=[target, *drops], errors="ignore")

    # Seal holdout first (never touch in loop scoring).
    X_tmp, X_hold, y_tmp, y_hold = train_test_split(
        X, y, test_size=holdout_frac, random_state=seed, stratify=y
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_tmp, y_tmp, test_size=0.25, random_state=seed, stratify=y_tmp
    )

    num_cols = [c for c in X_train.columns if pd.api.types.is_numeric_dtype(X_train[c])]
    cat_cols = [c for c in X_train.columns if c not in num_cols]
    pre = ColumnTransformer(
        [
            ("num", SimpleImputer(strategy="median"), num_cols),
            (
                "cat",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="most_frequent")),
                        ("oh", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                cat_cols,
            ),
        ]
    )
    family = str(spec["model_family"])
    model = _build_model(family, dict(spec.get("hyperparameters") or {}))
    pipe = Pipeline([("pre", pre), ("clf", model)])
    t0 = time.time()
    pipe.fit(X_train, y_train)
    pred = pipe.predict(X_val)
    duration = time.time() - t0
    return {
        "status": "succeeded",
        "experiment_id": spec.get("experiment_id"),
        "model_family": family,
        "hyperparameters": spec.get("hyperparameters") or {},
        "drop_columns": drops,
        "validation_metrics": {
            "f1": float(f1_score(y_val, pred, zero_division=0)),
            "accuracy": float(accuracy_score(y_val, pred)),
        },
        "duration_sec": round(duration, 3),
        "n_train": int(len(X_train)),
        "n_val": int(len(X_val)),
        "n_holdout": int(len(X_hold)),
        # Pass sealed holdout sizes only — not rows. Actual holdout eval is separate node.
        "holdout_seed": seed,
        "holdout_frac": holdout_frac,
    }


def main() -> int:
    inp = read_json_stdin()
    path = Path(inp["dataset_path"])
    target = inp.get("target_column") or "Survived"
    spec = dict(inp.get("experiment_spec") or {})
    seed = int(inp.get("seed") or 42)
    holdout_frac = float(inp.get("holdout_frac") or 0.2)
    repair_budget = int(inp.get("repair_budget") or 1)

    df = pd.read_csv(path)
    repaired = False
    used_llm_repair = False
    note = "ok"

    err = _validate(spec)
    attempts = 0
    while err and attempts < repair_budget:
        attempts += 1
        # Prefer live Nemotron repair when configured.
        repaired_this_round = False
        if llm_configured():
            system = (
                "You are the ML Engineer self-heal agent. "
                "Repair an invalid ExperimentSpec and return ONLY one JSON object with "
                "model_family in logistic_regression|random_forest|hist_gradient_boosting, "
                "hyperparameters (object), drop_columns (string[]), experiment_id, rationale. "
                "Fix the reported validation error while keeping the experiment useful."
            )
            user = f"error={err}\nspec={json.dumps(spec, default=str)}\n"
            content, _llm_err = openrouter_chat(system, user, max_tokens=700, temperature=0.2)
            if content:
                parsed = extract_json_object(content)
                if parsed and parsed.get("model_family"):
                    spec = parsed
                    used_llm_repair = True
                    repaired = True
                    repaired_this_round = True
                    note = f"nemotron repair after: {err}"
        if not repaired_this_round:
            spec = _repair_heuristic(spec, err)
            repaired = True
            note = f"heuristic repair after: {err}"
        err = _validate(spec)

    if err:
        write_json(
            {
                "execution_result": {
                    "status": "failed",
                    "error": err,
                    "validation_metrics": {},
                },
                "experiment_spec": spec,
                "repaired": repaired,
                "used_llm_repair": used_llm_repair,
                "note": note,
            }
        )
        return 1

    try:
        result = _run_once(df, target, spec, seed, holdout_frac)
    except Exception as exc:  # noqa: BLE001
        if repair_budget > 0 and not repaired:
            spec = _repair_heuristic(spec, str(exc))
            repaired = True
            note = f"heuristic repair after run error: {exc}"
            try:
                result = _run_once(df, target, spec, seed, holdout_frac)
            except Exception as exc2:  # noqa: BLE001
                write_json(
                    {
                        "execution_result": {
                            "status": "failed",
                            "error": str(exc2),
                            "validation_metrics": {},
                        },
                        "experiment_spec": spec,
                        "repaired": repaired,
                        "used_llm_repair": used_llm_repair,
                        "note": note,
                    }
                )
                return 1
        else:
            write_json(
                {
                    "execution_result": {
                        "status": "failed",
                        "error": str(exc),
                        "validation_metrics": {},
                    },
                    "experiment_spec": spec,
                    "repaired": repaired,
                    "used_llm_repair": used_llm_repair,
                    "note": note,
                }
            )
            return 1

    write_json(
        {
            "execution_result": result,
            "experiment_spec": spec,
            "repaired": repaired,
            "used_llm_repair": used_llm_repair,
            "note": note,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
