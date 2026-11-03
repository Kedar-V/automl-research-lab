"""DAG 2 — Same prep as DAG 1, then a STUB that will later trigger the simple loop.

Classroom reveal: fill in `trigger_simple_loop` to call gateway from Airflow.
Until then this task only logs the intended payload (no HTTP call).
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task

from _shared_baseline_prep import (
    DEFAULT_LEFT,
    DEFAULT_RIGHT,
    DEFAULT_SUBSET_ROWS,
    task_make_subset,
    task_merge_csvs,
    task_profile_light,
    task_publish_merged,
    task_train_baseline,
    task_trigger_simple_loop_stub,
    task_validate_customers,
    task_validate_transactions,
)

DEFAULT_PARAMS = {
    "left_path": DEFAULT_LEFT,
    "right_path": DEFAULT_RIGHT,
    "join_key": "customer_id",
    "how": "left",
    "target_column": "is_fraud",
    "seed": 42,
    "holdout_frac": 0.2,
    "baseline_family": "logistic_regression",
    "subset_rows": DEFAULT_SUBSET_ROWS,
    "run_id": None,
}


@dag(
    dag_id="simple_loop_baseline_and_trigger",
    description="Merge → subset → baseline → STUB trigger into simple loop",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["simple-loop", "baseline", "trigger-pending", "classroom"],
    params=DEFAULT_PARAMS,
)
def simple_loop_baseline_and_trigger():
    @task(task_id="validate_customers")
    def validate_customers(**context):
        return task_validate_customers(**context)

    @task(task_id="validate_transactions")
    def validate_transactions(**context):
        return task_validate_transactions(**context)

    @task(task_id="merge_csvs")
    def merge(left_meta, right_meta, **context):
        return task_merge_csvs(left_meta, right_meta, **context)

    @task(task_id="make_subset")
    def subset(merge_meta, **context):
        return task_make_subset(merge_meta, **context)

    @task(task_id="profile_light")
    def profile(subset_meta, **context):
        return task_profile_light(subset_meta, **context)

    @task(task_id="train_baseline")
    def train(subset_meta, profile_meta, **context):
        return task_train_baseline(subset_meta, profile_meta, **context)

    @task(task_id="publish_merged")
    def publish(subset_meta, baseline, **context):
        return task_publish_merged(subset_meta, baseline, **context)

    @task(task_id="trigger_simple_loop")
    def trigger(published, **context):
        return task_trigger_simple_loop_stub(published, **context)

    left = validate_customers()
    right = validate_transactions()
    merged = merge(left, right)
    demo = subset(merged)
    prof = profile(demo)
    base = train(demo, prof)
    out = publish(demo, base)
    trigger(out)


simple_loop_baseline_and_trigger()
