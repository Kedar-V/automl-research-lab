# Airflow (Docker-only) → simple research loop

Classroom sequence:

1. **Airflow alone (DAG 1)** — merge two CSVs → **subset** → train baseline → publish subset
2. **Simple loop alone** — run `/simple-loop` on `merged_latest.csv`
3. **Reveal DAG 2** — same prep + stub that will later trigger the loop from Airflow

Everything runs in **Docker**. Do not install Airflow on the host.

## Data

Vendored under [`datasets/airflow/`](../datasets/airflow/) from the Financial Transaction Intelligence Dataset 2026 zip:

- `customers.csv` ⟕ `transactions.csv` on `customer_id`
- Target: `is_fraud`  
- See [`datasets/airflow/ATTRIBUTION.md`](../datasets/airflow/ATTRIBUTION.md)

## Start Airflow (compose profile)

From the repo root:

```bash
docker compose -f infra/docker-compose.yml --env-file .env --profile airflow up --build -d
```

UI: http://localhost:8088 — login `admin` / `admin` (override with `AIRFLOW_ADMIN_*`).

DAGs:

| DAG id | What it does |
| --- | --- |
| `simple_loop_baseline_prep` | Merge → **make_subset** (default 2000 rows) → baseline → publish → **stop** |
| `simple_loop_baseline_and_trigger` | Same prep → **`trigger_simple_loop` stub** (no HTTP yet) |

Unpause DAG 1 in the UI and Trigger.

### One-shot prep without the UI (still Docker)

```bash
docker compose -f infra/docker-compose.yml --env-file .env --profile airflow run --rm airflow-prep-once
```

Writes:

- `artifacts/airflow/runs/<run_id>/merged.csv` (full join)
- `artifacts/airflow/runs/<run_id>/subset.csv` (demo table used for training)
- `datasets/airflow/merged_latest.csv` (published subset for the simple-loop UI)

Override size with DAG param / conf `subset_rows` (default **2000**).

## Then: simple loop standalone

With the main stack up (`gateway` + frontend):

1. Open `/simple-loop`
2. Pick **`merged_latest.csv`**
3. Target column **`is_fraud`**
4. Run

## DAG 2 reveal (later)

`trigger_simple_loop` currently logs a stub payload pointing at `http://gateway:8000`.  
When you reveal the connection, replace [`task_trigger_simple_loop_stub`](dags/_shared_baseline_prep.py) with a real `POST /simple-loop/run` using `merged_latest.csv` / XCom paths.

## Stop

```bash
docker compose -f infra/docker-compose.yml --profile airflow down
```
