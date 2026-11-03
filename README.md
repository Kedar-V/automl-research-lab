# AutoML Research Lab: Student Setup

Classroom demo in two parts:

1. **Airflow** — merge CSVs, train a baseline, publish a dataset (Docker only)
2. **LangGraph simple loop** — run the mini research loop in the UI (no Airflow required)

You can run the sections independently, or run Airflow first so `/simple-loop` can use `merged_latest.csv`.

---

## Prerequisites

Install on your machine:

| Tool | Notes |
| --- | --- |
| Docker Desktop | Running before any `docker compose` / `make up` |
| Python 3.12+ | For `make install` (local venv; optional for Docker-only Airflow) |
| Node.js 20+ | For the frontend (`npm`) |
| Make | Comes with Xcode CLT on macOS |

Do not install Airflow on the host. It runs only in Docker.

---

## One-time: clone and env

From the repo root:

```bash
cp .env.example .env
```

Edit `.env` as needed:

| Variable | Used by | Required? |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | Simple loop LLM agents | Recommended (without it, nodes use fallbacks) |
| `OPENROUTER_MODEL` | Simple loop | Optional (default: `nvidia/nemotron-3.5-lightning:free`) |
| `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` | Airflow UI | Optional (default: `admin` / `admin`) |
| `CURSOR_API_KEY` / `WANDB_*` | Full multi-agent stack only | Optional; not needed for these two demos |

Keep secrets in `.env`. Never commit real keys.

---

## Section 1: Set up Airflow

Goal: start Airflow in Docker, run the prep DAG, and publish a subset CSV for later use.

### Step 1.1: Start Airflow

```bash
docker compose -f infra/docker-compose.yml --env-file .env --profile airflow up --build -d
```

Wait about 1–2 minutes for init and the webserver. Check:

```bash
docker compose -f infra/docker-compose.yml --profile airflow ps
```

### Step 1.2: Open the Airflow UI

1. Browser: [http://localhost:8088](http://localhost:8088)
2. Login: `admin` / `admin` (or whatever you set in `.env`)
3. You should see two DAGs:
   - `simple_loop_baseline_prep` — use this one first
   - `simple_loop_baseline_and_trigger` — later classroom reveal (stub trigger)

### Step 1.3: Run the prep DAG

1. Unpause `simple_loop_baseline_prep`
2. Click Trigger DAG
3. Open the run → Graph tab. Tasks turn green when done.

![Airflow DAG graph for simple_loop_baseline_prep](docs/images/airflow-dag.jpg)

What the DAG does:

`customers.csv` ⨝ `transactions.csv` → subset (~2000 rows) → train baseline → publish

### Step 1.4: Confirm the published dataset

After a successful run you should have:

```text
datasets/airflow/merged_latest.csv
```

Also written under `artifacts/airflow/runs/<run_id>/` (`merged.csv`, `subset.csv`).

CLI alternative (skip the UI, still Docker):

```bash
docker compose -f infra/docker-compose.yml --env-file .env --profile airflow run --rm airflow-prep-once
```

### Step 1.5: Stop Airflow (when done)

```bash
docker compose -f infra/docker-compose.yml --profile airflow down
```

More detail: [`airflow/README.md`](airflow/README.md) · data attribution: [`datasets/airflow/ATTRIBUTION.md`](datasets/airflow/ATTRIBUTION.md)

---

## Section 2: Set up the LangGraph simple loop only

Goal: run the mini LangGraph loop (`mini_loop/`) through the UI at `/simple-loop`.
This does not need Airflow. It uses the gateway and frontend (Docker services plus Vite).

### Step 2.1: Install local Python package (once)

```bash
make install
```

### Step 2.2: Start the backend stack

```bash
make up
make health
```

Expect each of these to print something other than `FAIL`:

`8000` (gateway), `8011`, `8002`, `8003`, `8004`, `8005`, `8006`

If `make health` fails, wait and retry. Images may still be building.

### Step 2.3: Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173)

### Step 2.4: Run the simple loop

1. Go to Simple loop: [http://127.0.0.1:5173/simple-loop](http://127.0.0.1:5173/simple-loop)
2. Pick a dataset:
   - After Section 1: `merged_latest.csv`, target column `is_fraud`
   - Without Airflow: e.g. `Titanic-Dataset.csv`, target `Survived` (or upload your own CSV)
3. Set target score / max cycles if you want (defaults are fine)
4. Click Run loop and watch the live LangGraph nodes (data scientist → hypothesis → ML engineer → judge → …)

![Simple research loop UI with merged_latest.csv and live agent graph](docs/images/simple-loop.jpg)

Optional check that the gateway sees the loop:

```bash
curl -s http://127.0.0.1:8000/simple-loop/info | python3 -m json.tool
```

`"available": true` and `"key_configured": true` means the mount and OpenRouter key are good.

### Step 2.5: Stop the stack (when done)

```bash
make down
```

Stop the frontend with `Ctrl+C` in the Vite terminal.

### Optional: CLI only (no UI)

With deps available in the gateway image path, or after installing packages yourself:

```bash
# Example with Titanic
.venv/bin/python mini_loop/run_cli.py \
  --dataset datasets/Titanic-Dataset.csv \
  --target Survived \
  --max-cycles 3
```

Use the UI path for the classroom demo.

---

## Suggested classroom order

| Order | What | Outcome |
| --- | --- | --- |
| 1 | Section 1 (Airflow) | Baseline + `merged_latest.csv` |
| 2 | Section 2 (simple loop) | Students run `/simple-loop` on that CSV |
| 3 | (Later) DAG `simple_loop_baseline_and_trigger` | Reveal how Airflow could call the loop |

---

## Useful ports

| What | URL |
| --- | --- |
| Frontend | http://127.0.0.1:5173 |
| Gateway API | http://127.0.0.1:8000 |
| Airflow UI | http://localhost:8088 |
| MLflow (full stack) | http://127.0.0.1:5050 |

---

## Full multi-agent lab (not required for the two demos above)

```bash
cp .env.example .env   # set MOCK_*=false for live research
make install && make up && make health
cd frontend && npm install && npm run dev
```

Upload `datasets/churn_sample.csv`, target `churned`.
Design canvas: [`AutoML_Research_Lab_demo_canvas.pdf`](AutoML_Research_Lab_demo_canvas.pdf) · mock script: [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)
