#!/usr/bin/env python3
"""Final holdout evaluation (code) — sealed split opened once at the end.

stdin: { dataset_path, target_column, best_spec, seed?, holdout_frac? }
stdout: { holdout_metrics, note }
"""

from __future__ import annotations

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
from _common import read_json_stdin, write_json  # noqa: E402


def _model(family: str, hp: dict):
    if family == "logistic_regression":
        return LogisticRegression(C=float(hp.get("C", 1.0)), max_iter=int(hp.get("max_iter", 300)))
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


def main() -> int:
    inp = read_json_stdin()
    path = Path(inp["dataset_path"])
    target = inp.get("target_column") or "Survived"
    spec = inp.get("best_spec") or {}
    seed = int(inp.get("seed") or 42)
    holdout_frac = float(inp.get("holdout_frac") or 0.2)

    df = pd.read_csv(path)
    y = df[target]
    drops = [c for c in (spec.get("drop_columns") or []) if c in df.columns and c != target]
    X = df.drop(columns=[target, *drops], errors="ignore")
    X_tmp, X_hold, y_tmp, y_hold = train_test_split(
        X, y, test_size=holdout_frac, random_state=seed, stratify=y
    )

    num_cols = [c for c in X_tmp.columns if pd.api.types.is_numeric_dtype(X_tmp[c])]
    cat_cols = [c for c in X_tmp.columns if c not in num_cols]
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
    family = str(spec.get("model_family") or "random_forest")
    pipe = Pipeline([("pre", pre), ("clf", _model(family, dict(spec.get("hyperparameters") or {})))])
    t0 = time.time()
    pipe.fit(X_tmp, y_tmp)
    pred = pipe.predict(X_hold)
    write_json(
        {
            "holdout_metrics": {
                "f1": float(f1_score(y_hold, pred, zero_division=0)),
                "accuracy": float(accuracy_score(y_hold, pred)),
                "n_holdout": int(len(X_hold)),
                "duration_sec": round(time.time() - t0, 3),
            },
            "note": "sealed holdout opened once",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
