# Student copy guide — Airflow baseline prep

Paste into [`student_baseline_prep.py`](student_baseline_prep.py) **one task at a time**.  
Filled reference (same code, working): [`simple_loop_baseline_prep.py`](simple_loop_baseline_prep.py).

Skeleton already defines paths (`CUSTOMERS`, `TRANSACTIONS`, `RUNS`, `PUBLISH`, `TARGET`, …) and imports.  
Replace each `raise NotImplementedError(...)` stub with the body below (keep the `@task` + `def` lines that are already there, or paste the whole `@task` block).

In-app copy buttons: `/guide` → Airflow tab.

Until you uncomment the **wiring** block at the bottom, the Airflow Graph tab stays empty.

---

## Step 1 — `validate_customers`

```python
@task
def validate_customers():
    """Check the customers CSV exists and has the join key."""
    if not CUSTOMERS.is_file():
        raise FileNotFoundError(CUSTOMERS)
    # nrows=0 → headers only (fast)
    cols = list(pd.read_csv(CUSTOMERS, nrows=0).columns)
    if JOIN_KEY not in cols:
        raise ValueError(f"missing {JOIN_KEY}")
    # Returned dict becomes XCom → next task's left_meta
    return {"path": str(CUSTOMERS)}
```

---

## Step 2 — `validate_transactions`

```python
@task
def validate_transactions():
    """Check the transactions CSV exists and has join key + target label."""
    if not TRANSACTIONS.is_file():
        raise FileNotFoundError(TRANSACTIONS)
    cols = list(pd.read_csv(TRANSACTIONS, nrows=0).columns)
    for need in (JOIN_KEY, TARGET):
        if need not in cols:
            raise ValueError(f"missing {need}")
    return {"path": str(TRANSACTIONS)}
```

---

## Step 3 — `merge_csvs`

```python
@task
def merge_csvs(left_meta: dict, right_meta: dict, **context):
    """Join transactions ⟕ customers. One output row per transaction."""
    run_id = context["ts_nodash"]  # e.g. 20261104T145012
    out = RUNS / run_id / "merged.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    left = pd.read_csv(left_meta["path"])
    right = pd.read_csv(right_meta["path"])
    # fact table on the left of the merge → keep one row per transaction
    merged = right.merge(left, on=JOIN_KEY, how="left", suffixes=("", "_customer"))
    merged.to_csv(out, index=False)
    return {"merged_path": str(out), "n_merged": len(merged)}
```

---

## Step 4 — `make_subset`

```python
@task
def make_subset(merge_meta: dict, **context):
    """Downsample so baseline + the later simple-loop demo stay fast in class."""
    run_id = context["ts_nodash"]
    out = RUNS / run_id / "subset.csv"
    df = pd.read_csv(merge_meta["merged_path"])
    n = min(SUBSET_ROWS, len(df))
    subset = df.sample(n=n, random_state=42) if n < len(df) else df
    subset.to_csv(out, index=False)
    # Keep key name merged_path so later tasks stay uniform
    return {"merged_path": str(out), "n_subset": len(subset)}
```

---

## Step 5 — `profile_light`

```python
@task
def profile_light(subset_meta: dict):
    """List columns that look leaky / id-like so training can drop them."""
    df = pd.read_csv(subset_meta["merged_path"])
    drops = [
        c
        for c in df.columns
        if c != TARGET
        and (c.endswith("_id") or c in {"timestamp", "fraud_probability", "fraud_history"})
    ]
    return {"recommended_drops": drops, "n_rows": len(df)}
```

---

## Step 6 — `train_baseline`

```python
@task
def train_baseline(subset_meta: dict, profile_meta: dict):
    """Tiny numeric-only LogisticRegression — a classroom A-baseline, not production ML."""
    df = pd.read_csv(subset_meta["merged_path"])
    drops = list(profile_meta.get("recommended_drops") or [])
    y = df[TARGET]
    X = (
        df.drop(columns=[TARGET, *drops], errors="ignore")
        .select_dtypes("number")
        .fillna(0)
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y if y.nunique() > 1 else None,
    )
    clf = LogisticRegression(max_iter=500, class_weight="balanced")
    clf.fit(X_train, y_train)
    f1 = float(f1_score(y_val, clf.predict(X_val), zero_division=0))
    return {"f1": f1, "n_train": len(X_train), "n_val": len(X_val)}
```

---

## Step 7 — `publish_merged`

```python
@task
def publish_merged(subset_meta: dict, baseline: dict):
    """Copy the subset to a stable path the simple-loop UI can pick up."""
    PUBLISH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(subset_meta["merged_path"], PUBLISH)
    return {
        "published_latest": str(PUBLISH),
        "merged_dataset_path": subset_meta["merged_path"],
        "baseline_val_f1": baseline["f1"],
        "target_column": TARGET,
    }
```

---

## Step 8 — Wiring (fills the Graph tab)

Uncomment / replace the wiring block at the bottom of `student_baseline_prep.py`:

```python
left = validate_customers()
right = validate_transactions()
merged = merge_csvs(left, right)  # waits for BOTH validates
demo = make_subset(merged)
prof = profile_light(demo)
base = train_baseline(demo, prof)  # needs subset path + drop list
publish_merged(demo, base)
```

## Step 9 — Run (terminal, from repo root)

Airflow profile already up (`docker compose … --profile airflow up -d`).

```bash
# Unpause
docker compose -f infra/docker-compose.yml --env-file .env --profile airflow exec airflow-scheduler \
  airflow dags unpause student_baseline_prep

# Trigger
docker compose -f infra/docker-compose.yml --env-file .env --profile airflow exec airflow-scheduler \
  airflow dags trigger student_baseline_prep

# Wait / confirm success (re-run until you see a success row)
docker compose -f infra/docker-compose.yml --env-file .env --profile airflow exec airflow-scheduler \
  airflow dags list-runs -d student_baseline_prep --state success --limit 5

# Host: published CSV + run folder
ls -la datasets/airflow/merged_latest.csv
ls -la artifacts/airflow/runs/
ls -la artifacts/airflow/runs/$(ls -t artifacts/airflow/runs | head -1)/
```

Or in the UI: http://localhost:8088 → unpause `student_baseline_prep` → Trigger → Graph all green.

Published file: `datasets/airflow/merged_latest.csv` (for `/simple-loop` or `/student-loop`).
