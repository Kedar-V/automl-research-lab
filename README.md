# AutoML Research Lab

Teaching demo for multi-agent AutoML: LangGraph orchestrator, sealed holdout, microservices over HTTP. UI runs on live SSE when `MOCK_*=false`.

Design canvas: [`AutoML_Research_Lab_demo_canvas.pdf`](AutoML_Research_Lab_demo_canvas.pdf)  
Build plan: [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) · Mock demo: [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)

## Student path (< 10 minutes)

```bash
cp .env.example .env
# Optional: set CURSOR_API_KEY + WANDB_API_KEY in .env (Composer 2.5 / W&B).
# Without them, agents use deterministic fallbacks; W&B mirroring stays off if WANDB_ENABLED=false.

make install
make up                 # rebuilds images + starts stack
make health             # all /healthz should return ok, mock:false

cd frontend && npm install && npm run dev
# open http://127.0.0.1:5173
```

1. Upload `datasets/churn_sample.csv`, target `churned`, start a research session.
2. Watch the live agent graph; mock banner should be **gone** when all `MOCK_*=false`.
3. MLflow UI: http://127.0.0.1:5050 — each trial logged; holdout tagged `final`.

Equal-budget baselines (after `make up`):

```bash
.venv/bin/python scripts/eval_baselines.py
```

Failure demo: `docker compose -f infra/docker-compose.yml stop harness` then start a session — typed error + bounded retry on the graph.

### Mock fixtures (teaching)

Set `MOCK_GATEWAY=true` (and other mocks as needed) to replay fixtures without training:

| Scenario | What you see |
| --- | --- |
| `happy` | Profile → experiment → accept → holdout → stop |
| `revise_loop` | Judge revises once |
| `repair` | Invalid config → one Error repair → retry |
| `terminal_failure` / `budget_stop` / `service_down` | Bounded failure modes |

```bash
make demo-sse SCENARIO=happy
```

### Ports

| Service | Host port |
| --- | --- |
| gateway | 8000 |
| orchestrator | 8011 |
| agent_service | 8002 |
| harness | 8003 |
| dataset_service | 8004 |
| memory_service | 8005 |
| tracking_service | 8006 |
| MLflow | 5050 |

`wandb-mcp`: `docker compose -f infra/docker-compose.yml --profile wandb up` when `WANDB_API_KEY` is set.

## Hard rules

1. No model-written code is executed.
2. Sealed holdout opened once via harness → dataset-service `/internal/holdout/evaluate`.
3. No cross-service DB reads; every limit lives in harness `policy.py`.
4. `WANDB_API_KEY` / `CURSOR_API_KEY` never appear in events, logs, or UI.

## Modes (Setup page)

| Mode | Banner | Source |
| --- | --- | --- |
| **Live research** | none | Real dataset → orchestrator → harness; events also `XADD` to Redis Streams |
| **Replay** | “Replay of a recorded real run” | `mocks/recordings/real_run_churn.json` |
| **Mock fixture** | MOCK BACKEND | `mocks/fixtures/*` scenarios |

## Stages

A0–D1 **done**. Extension ideas (not built): [`docs/planned-features.md`](docs/planned-features.md).
