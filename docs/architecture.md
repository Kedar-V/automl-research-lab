# Architecture (Stage A0 stub)

Seven application services plus Redis, MLflow, an artifact volume, and optional W&B MCP.

| Service | Owns | Talks to |
| --- | --- | --- |
| `web` | React UI | gateway only |
| `gateway` | session commands, SSE | orchestrator, dataset-service, Redis |
| `orchestrator` | LangGraph + checkpointer | agent, harness, memory, tracking, dataset (metadata) |
| `agent-service` | LLM subagents | LLM provider, read-only W&B MCP |
| `harness` | seven tools + `policy.py` | dataset, tracking, optional W&B report MCP |
| `dataset-service` | splits + sealed holdout | none |
| `memory-service` | findings / history / lessons / working | none |
| `tracking-service` | MLflow (+ optional W&B SDK mirror) | MLflow, W&B cloud |

**Network boundary:** LLM reasoning (`agent-service`) never executes experiments. Only `harness` runs validated tools.

**Holdout:** only `POST /internal/holdout/evaluate` on `dataset-service`, once per session, harness token only. No route returns holdout rows.

Visual reference: root PDF design canvas.
