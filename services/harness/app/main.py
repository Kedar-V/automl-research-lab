"""Harness skeleton — tools and policy.py arrive in Stage C2."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services"))

from contracts import (  # noqa: E402
    CompareExperimentsRequest,
    GenerateReportRequest,
    GetHistoryRequest,
    HealthResponse,
    InspectDataRequest,
    RunExperimentRequest,
    SaveArtifactRequest,
    ValidateExperimentRequest,
)
from _shared.correlation import CorrelationIdMiddleware  # noqa: E402

SERVICE_NAME = "harness"

app = FastAPI(title="AutoML Harness Service", version="0.1.0")
app.add_middleware(CorrelationIdMiddleware)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, mock=True)


@app.get("/policy")
def get_policy() -> dict[str, Any]:
    # Placeholder limits so OpenAPI and demos have a stable shape early.
    return {
        "max_experiments": 10,
        "max_retries_per_experiment": 3,
        "per_trial_timeout_seconds": 120,
        "wall_clock_budget_seconds": 900,
        "mock": True,
        "note": "real policy.py arrives in Stage C2",
    }


def _planned(tool: str) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": f"planned: {tool} (Stage C2)"})


@app.post("/tools/inspect_data", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def inspect_data(_body: InspectDataRequest) -> JSONResponse:
    return _planned("inspect_data")


@app.post("/tools/validate_experiment", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def validate_experiment(_body: ValidateExperimentRequest) -> JSONResponse:
    return _planned("validate_experiment")


@app.post("/tools/run_experiment", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def run_experiment(_body: RunExperimentRequest) -> JSONResponse:
    return _planned("run_experiment")


@app.post("/tools/compare_experiments", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def compare_experiments(_body: CompareExperimentsRequest) -> JSONResponse:
    return _planned("compare_experiments")


@app.get("/tools/get_history", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_history(
    session_id: str = "",
    correlation_id: str = "",
    limit: int = 50,
) -> JSONResponse:
    _ = GetHistoryRequest(session_id=session_id or "x", correlation_id=correlation_id or "x", limit=limit)
    return _planned("get_history")


@app.post("/tools/save_artifact", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def save_artifact(_body: SaveArtifactRequest) -> JSONResponse:
    return _planned("save_artifact")


@app.post("/tools/generate_report", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def generate_report(_body: GenerateReportRequest) -> JSONResponse:
    return _planned("generate_report")
