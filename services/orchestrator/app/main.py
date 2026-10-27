"""Orchestrator skeleton — LangGraph wiring arrives in Stage C6."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services"))

from contracts import HealthResponse  # noqa: E402
from _shared.correlation import CorrelationIdMiddleware  # noqa: E402

SERVICE_NAME = "orchestrator"

app = FastAPI(title="AutoML Orchestrator", version="0.1.0")
app.add_middleware(CorrelationIdMiddleware)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, mock=True)


@app.post("/runs", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def create_run() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "planned: Stage C6"})


@app.get("/runs/{run_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_run(run_id: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": f"planned: get run {run_id}"})


@app.post("/runs/{run_id}/pause", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def pause_run(run_id: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": f"planned: pause {run_id}"})


@app.post("/runs/{run_id}/resume", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def resume_run(run_id: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": f"planned: resume {run_id}"})
