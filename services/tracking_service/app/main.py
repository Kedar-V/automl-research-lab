"""Tracking-service skeleton — MLflow + optional W&B mirroring in Stage C3."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services"))

from contracts import HealthResponse  # noqa: E402
from _shared.correlation import CorrelationIdMiddleware  # noqa: E402

SERVICE_NAME = "tracking_service"

app = FastAPI(title="AutoML Tracking Service", version="0.1.0")
app.add_middleware(CorrelationIdMiddleware)


class TrackingRunCreate(BaseModel):
    session_id: str
    experiment_id: str
    config: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)
    idempotency_key: str


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, mock=True)


@app.post("/runs", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def create_run(_body: TrackingRunCreate) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "planned: Stage C3 MLflow logging"})


@app.get("/runs/{run_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_run(run_id: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": f"planned: get run {run_id}"})


@app.get("/experiments/{session_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def list_session_experiments(session_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"detail": f"planned: experiments for session {session_id}"},
    )
