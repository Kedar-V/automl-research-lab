# AutoML Research Lab

A teaching demo for master's data-science students: multi-agent AutoML with LangGraph, a sealed holdout, and microservices that talk only over HTTP and Redis Streams.

**Current stage: A0 — contracts and service skeletons.** Placeholder routes return `501`. No real experiments yet. Mock event streaming arrives in Stage A1.

Design canvas: [`AutoML_Research_Lab_demo_canvas.pdf`](AutoML_Research_Lab_demo_canvas.pdf)

## Quick start (Stage A0)

```bash
cp .env.example .env
make install          # creates .venv and installs contracts + pytest
make up               # docker compose build + start
make health           # curl each /healthz
make test             # contract tests (uses .venv; Docker not required)
make logs             # follow compose logs
make down
```

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

- **A0** (this): contracts, skeletons, `/healthz`, contract tests, GitHub repo
- **A1**: mock backend SSE fixture scenarios
- **B1–B3**: React UI on the mock
- **C1–C7**: replace each mock with a real service
- **D1**: replay mode, failure demo, evaluation script

See [`docs/architecture.md`](docs/architecture.md) and [`docs/planned-features.md`](docs/planned-features.md).

## Hard rules (never break)

1. No model-written code is executed.
2. Sealed holdout is opened once, at the end, only via harness → dataset-service.
3. Services do not import each other's code or databases.
4. Mock data always carries `mock: true` and a visible UI banner (Phase B+).
