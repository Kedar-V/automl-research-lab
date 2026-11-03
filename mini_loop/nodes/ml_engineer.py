#!/usr/bin/env python3
"""ML Engineer (code + LLM self-heal) — validate, train, score, repair via Nemotron.

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
    extract_json_object,
    llm_configured,
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
    err_l = error.lower()
    # Sparse / dense mismatch → switch off HGB or force RF with simpler cats.
    if "sparse" in err_l or "dense" in err_l:
        fixed["model_family"] = "random_forest"
        fixed["hyperparameters"] = {"n_estimators": 120, "max_depth": 8}
    elif fam not in ALLOWED:
        fixed["model_family"] = "random_forest"
        fixed["hyperparameters"] = {"n_estimators": 100, "max_depth": 6}
    elif fam == "logistic_regression":
        fixed["hyperparameters"] = {"C": 1.0, "max_iter": 400, "class_weight": "balanced"}
    elif fam == "hist_gradient_boosting":
        fixed["model_family"] = "random_forest"
        fixed["hyperparameters"] = {"n_estimators": 100, "max_depth": 6}
    else:
        fixed["model_family"] = "random_forest"
        fixed["hyperparameters"] = {"n_estimators": 100, "max_depth": 6}
    fixed["rationale"] = f"heuristic repaired after: {error[:120]}"
    return fixed


def _llm_repair(spec: dict, error: str, *, columns: list[str], target: str) -> tuple[dict | None, str | None]:
    """Ask Nemotron for a repaired ExperimentSpec. Returns (spec, err)."""
    if not llm_configured():
        return None, "OPENROUTER_API_KEY not set"
    system = (
        "You are the ML Engineer self-heal agent in a live AutoML loop. "
        "A train/validate attempt failed. Return ONLY one JSON ExperimentSpec with keys: "
        "experiment_id, model_family "
        "(logistic_regression|random_forest|hist_gradient_boosting), "
        "hyperparameters (object), drop_columns (string[] of existing columns to drop), "
        "rationale (1-2 sentences explaining the fix). "
        "Rules: "
        "- If the error mentions sparse/dense arrays, prefer random_forest or "
        "logistic_regression (hist_gradient_boosting cannot take sparse one-hot). "
        "- Drop id-like / high-cardinality text columns that cause explosion or leakage. "
        "- For severe class imbalance, set class_weight to balanced when the family supports it. "
        "- Keep drop_columns subset of provided columns (never include the target). "
        "- Change hyperparameters or family enough to actually address the error."
    )
    user = (
        f"error={error}\n"
        f"target={target}\n"
        f"columns={columns}\n"
        f"failed_spec={json.dumps(spec, default=str)}\n"
    )
    content, err = openrouter_chat(system, user, max_tokens=800, temperature=0.25)
    if not content:
        return None, err or "empty llm repair"
    parsed = extract_json_object(content)
    if not parsed or parsed.get("model_family") not in ALLOWED:
        return None, f"llm repair unparsable ({err or 'bad json'})"
    parsed.setdefault("experiment_id", spec.get("experiment_id"))
    parsed.setdefault("hyperparameters", {})
    drops = [c for c in (parsed.get("drop_columns") or []) if c in columns and c != target]
    parsed["drop_columns"] = drops
    return parsed, None


def _build_model(family: str, hp: dict):
    # Fraud-like targets are rare — default to balanced unless the spec overrides.
    cw = hp.get("class_weight", "balanced")
    if family == "logistic_regression":
        return LogisticRegression(
            C=float(hp.get("C", 1.0)),
            max_iter=int(hp.get("max_iter", 500)),
            class_weight=cw,
        )
    if family == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(
            learning_rate=float(hp.get("learning_rate", 0.1)),
            max_iter=int(hp.get("max_iter", 100)),
            class_weight=cw if cw in (None, "balanced") else None,
        )
    kw = {
        "n_estimators": int(hp.get("n_estimators", 100)),
        "max_depth": hp.get("max_depth", 6),
        "class_weight": cw,
        "random_state": 42,
    }
    if hp.get("min_samples_leaf") is not None:
        kw["min_samples_leaf"] = int(hp.get("min_samples_leaf"))
    return RandomForestClassifier(**kw)


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
    cat_cols = [
        c
        for c in X_train.columns
        if c not in num_cols and X_train[c].nunique(dropna=True) <= 40
    ]
    # Dense one-hot so hist_gradient_boosting (and mixed pipelines) never see sparse X.
    pre = ColumnTransformer(
        [
            ("num", SimpleImputer(strategy="median"), num_cols),
            (
                "cat",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="most_frequent")),
                        (
                            "oh",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                cat_cols,
            ),
        ],
        sparse_threshold=0.0,
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
            "f1": float(f1_score(y_val, pred, average="binary", zero_division=0))
            if y_val.nunique() <= 2
            else float(f1_score(y_val, pred, average="macro", zero_division=0)),
            "accuracy": float(accuracy_score(y_val, pred)),
        },
        "duration_sec": round(duration, 3),
        "n_train": int(len(X_train)),
        "n_val": int(len(X_val)),
        "n_holdout": int(len(X_hold)),
        "holdout_seed": seed,
        "holdout_frac": holdout_frac,
    }


def _apply_repair(
    spec: dict,
    error: str,
    *,
    columns: list[str],
    target: str,
) -> tuple[dict, bool, str]:
    """Prefer live Nemotron repair; fall back to heuristic only if LLM fails."""
    repaired_spec, llm_err = _llm_repair(spec, error, columns=columns, target=target)
    if repaired_spec is not None:
        v = _validate(repaired_spec)
        if v is None:
            return repaired_spec, True, f"openrouter repair after: {error}"
        # LLM returned invalid family/shape — try once more is overkill; fall through.
        llm_err = v
    fixed = _repair_heuristic(spec, error)
    note = f"heuristic repair after: {error}"
    if llm_err:
        note = f"heuristic repair after LLM miss ({llm_err}): {error}"
    return fixed, False, note


def main() -> int:
    inp = read_json_stdin()
    path = Path(inp["dataset_path"])
    target = inp.get("target_column") or "Survived"
    spec = dict(inp.get("experiment_spec") or {})
    seed = int(inp.get("seed") or 42)
    holdout_frac = float(inp.get("holdout_frac") or 0.2)
    repair_budget = int(inp.get("repair_budget") or 3)

    df = pd.read_csv(path)
    columns = list(df.columns)
    repaired = False
    used_llm_repair = False
    note = "ok"
    last_error: str | None = None

    # Spec validation repairs (count against budget).
    err = _validate(spec)
    attempts = 0
    while err and attempts < repair_budget:
        attempts += 1
        spec, used_llm, note = _apply_repair(spec, err, columns=columns, target=target)
        repaired = True
        used_llm_repair = used_llm_repair or used_llm
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

    result = None
    while True:
        try:
            result = _run_once(df, target, spec, seed, holdout_frac)
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if attempts >= repair_budget:
                write_json(
                    {
                        "execution_result": {
                            "status": "failed",
                            "error": last_error,
                            "validation_metrics": {},
                        },
                        "experiment_spec": spec,
                        "repaired": repaired,
                        "used_llm_repair": used_llm_repair,
                        "note": note if repaired else f"failed: {last_error}",
                    }
                )
                return 1
            attempts += 1
            spec, used_llm, note = _apply_repair(
                spec, last_error, columns=columns, target=target
            )
            repaired = True
            used_llm_repair = used_llm_repair or used_llm
            # Re-validate after repair before retrying run.
            v = _validate(spec)
            if v:
                spec, used_llm2, note = _apply_repair(spec, v, columns=columns, target=target)
                used_llm_repair = used_llm_repair or used_llm2

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
