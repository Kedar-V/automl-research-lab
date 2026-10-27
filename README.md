# AutoML Research Lab

A teaching demo for master's data-science students: multi-agent AutoML with LangGraph, a sealed holdout, and microservices that talk only over HTTP and Redis Streams.

**Current stage: A1 — mock backend.** The gateway creates sessions and streams labeled sample fixture events over SSE (`mock: true`). Numbers are illustrative, not from trained models. Real experiments start in Phase C.

Design canvas: [`AutoML_Research_Lab_demo_canvas.pdf`](AutoML_Research_Lab_demo_canvas.pdf)

## Quick start

```bash
cp .env.example .env
make install          # creates .venv and installs contracts + pytest
make up               # docker compose build + start
make health           # curl each /healthz
make test             # contract + mock SSE tests
make demo-sse         # stream happy-path fixture (or SCENARIO=revise_loop)
make logs
make down
```

### Mock SSE scenarios

| Scenario | What you see |
| --- | --- |
| `happy` | Profile → experiment → accept → holdout → stop |
| `revise_loop` | Judge revises once, loop-back to Hypothesis Generator |
| `repair` | Invalid config → one Error repair → retry succeeds |
| `terminal_failure` | Repair exhausted → failed trial → supervisor skips |
| `budget_stop` | Stops at budget without hitting target score |
| `service_down` | Harness typed error → bounded retry → terminal failure |

```bash
# Manual curl
SID=$(curl -sf -X POST http://127.0.0.1:8000/sessions \
  -H 'Content-Type: application/json' \
  -d '{"target_column":"churned","scenario":"revise_loop"}' | jq -r .session_id)
curl -N "http://127.0.0.1:8000/sessions/$SID/events"
```

Pause / resume / reset: `POST /sessions/{id}/pause|resume|reset`.

### Local ports

| Service | Port |
| --- | --- |
| gateway | 8000 |
| orchestrator | 8011 (container still listens on 8001) |
| agent_service | 8002 |
| harness | 8003 |
| dataset_service | 8004 |
| memory_service | 8005 |
| tracking_service | 8006 |
| MLflow UI | 5050 (container still listens on 5000) |

`wandb-mcp` is not started by default. Use `docker compose -f infra/docker-compose.yml --profile wandb up` when you have `WANDB_API_KEY`.

## Build plan (stop after each stage)

- **A0**: contracts, skeletons, `/healthz`, contract tests, GitHub repo
- **A1** (this): mock backend SSE fixture scenarios
- **B1–B3**: React UI on the mock
- **C1–C7**: replace each mock with a real service
- **D1**: replay mode, failure demo, evaluation script

See [`docs/architecture.md`](docs/architecture.md) and [`docs/planned-features.md`](docs/planned-features.md).

## Hard rules (never break)

1. No model-written code is executed.
2. Sealed holdout is opened once, at the end, only via harness → dataset-service.
3. Services do not import each other's code or databases.
4. Mock data always carries `mock: true` and a visible UI banner (Phase B+).
