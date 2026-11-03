"""Shared TaskFlow callables for baseline prep DAGs (runs inside Airflow containers)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Repo is mounted at /repo in Docker; also allow local import if PYTHONPATH set.
REPO = Path("/repo") if Path("/repo/mini_loop").exists() else Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mini_loop.baseline import (  # noqa: E402
    make_subset,
    merge_csvs,
    profile_light,
    publish_merged,
    run_prep,
    train_baseline,
    validate_csv,
)

DEFAULT_LEFT = str(REPO / "datasets" / "airflow" / "customers.csv")
DEFAULT_RIGHT = str(REPO / "datasets" / "airflow" / "transactions.csv")
DEFAULT_SUBSET_ROWS = 2000


def conf_value(context: dict[str, Any], key: str, default: Any) -> Any:
    dag_run = context.get("dag_run")
    conf = (dag_run.conf if dag_run else None) or {}
    params = context.get("params") or {}
    if key in conf and conf[key] is not None:
        return conf[key]
    if key in params and params[key] is not None:
        return params[key]
    return default


def task_validate_customers(**context) -> dict[str, Any]:
    path = conf_value(context, "left_path", DEFAULT_LEFT)
    key = conf_value(context, "join_key", "customer_id")
    return validate_csv(path, require_columns=[key])


def task_validate_transactions(**context) -> dict[str, Any]:
    path = conf_value(context, "right_path", DEFAULT_RIGHT)
    key = conf_value(context, "join_key", "customer_id")
    target = conf_value(context, "target_column", "is_fraud")
    return validate_csv(path, require_columns=[key, target])


def task_merge_csvs(left_meta: dict, right_meta: dict, **context) -> dict[str, Any]:
    run_id = conf_value(context, "run_id", None) or context["ts_nodash"]
    out = REPO / "artifacts" / "airflow" / "runs" / run_id / "merged.csv"
    return merge_csvs(
        left_meta["path"],
        right_meta["path"],
        join_key=conf_value(context, "join_key", "customer_id"),
        how=conf_value(context, "how", "left"),
        target_column=conf_value(context, "target_column", "is_fraud"),
        seed=int(conf_value(context, "seed", 42)),
        out_csv=out,
    )


def task_make_subset(merge_meta: dict, **context) -> dict[str, Any]:
    run_id = conf_value(context, "run_id", None) or context["ts_nodash"]
    out = REPO / "artifacts" / "airflow" / "runs" / run_id / "subset.csv"
    return make_subset(
        merge_meta["merged_path"],
        out_csv=out,
        n_rows=int(conf_value(context, "subset_rows", DEFAULT_SUBSET_ROWS)),
        target_column=conf_value(context, "target_column", "is_fraud"),
        seed=int(conf_value(context, "seed", 42)),
    )


def task_profile_light(table_meta: dict, **context) -> dict[str, Any]:
    return profile_light(
        table_meta["merged_path"],
        target_column=conf_value(context, "target_column", "is_fraud"),
    )


def task_train_baseline(table_meta: dict, profile: dict, **context) -> dict[str, Any]:
    family = conf_value(context, "baseline_family", "logistic_regression")
    if family == "logistic_regression":
        hp = {"C": 1.0, "max_iter": 500, "class_weight": "balanced"}
    elif family == "random_forest":
        hp = {"n_estimators": 100, "max_depth": 6, "class_weight": "balanced"}
    else:
        hp = {"learning_rate": 0.1, "max_iter": 100}
    return train_baseline(
        table_meta["merged_path"],
        target_column=conf_value(context, "target_column", "is_fraud"),
        drop_columns=list(profile.get("recommended_drops") or []),
        model_family=family,
        hyperparameters=hp,
        seed=int(conf_value(context, "seed", 42)),
        holdout_frac=float(conf_value(context, "holdout_frac", 0.2)),
    )


def task_publish_merged(table_meta: dict, baseline: dict, **context) -> dict[str, Any]:
    """Publish the demo subset as merged_latest.csv for the simple loop."""
    run_id = conf_value(context, "run_id", None) or context["ts_nodash"]
    return publish_merged(
        run_id=run_id,
        merged_path=table_meta["merged_path"],
        baseline=baseline,
        target_column=conf_value(context, "target_column", "is_fraud"),
        out_dir=REPO / "artifacts" / "airflow" / "runs" / run_id,
    )


def task_trigger_simple_loop_stub(published: dict, **context) -> dict[str, Any]:
    """DAG 2 terminal task — stub until the classroom reveal wires Airflow → simple loop."""
    payload = {
        "status": "stub",
        "todo": "Reveal: call gateway /simple-loop/run from Airflow with merged.csv",
        "dataset_path": published.get("published_latest")
        or published.get("merged_dataset_path"),
        "target_column": published.get("target_column", "is_fraud"),
        "suggested_max_cycles": 3,
        "gateway_url": "http://gateway:8000",
        "baseline_val_f1": published.get("baseline_val_f1"),
    }
    print("[trigger_simple_loop STUB] would start simple loop with:", payload)
    return payload


def run_prep_in_container(**kwargs) -> dict[str, Any]:
    return run_prep(**kwargs)
