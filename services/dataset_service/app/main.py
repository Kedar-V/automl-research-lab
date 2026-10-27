"""Dataset-service skeleton — sealed holdout arrives in Stage C1."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services"))

from contracts import HealthResponse  # noqa: E402
from _shared.correlation import CorrelationIdMiddleware  # noqa: E402

SERVICE_NAME = "dataset_service"

app = FastAPI(title="AutoML Dataset Service", version="0.1.0")
app.add_middleware(CorrelationIdMiddleware)


class HoldoutEvaluateRequest(BaseModel):
    session_id: str
    model_ref: str
    metric: str = "f1"
    idempotency_key: str


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, mock=True)


@app.post("/datasets", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def create_dataset() -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "planned: Stage C1 upload + fixed split"})


@app.get("/datasets/{dataset_id}/profile-view", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def profile_view(dataset_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"detail": f"planned: train/validation profile for {dataset_id}"},
    )


@app.get("/datasets/{dataset_id}/splits/{name}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_split(dataset_id: str, name: str) -> JSONResponse:
    # Holdout is intentionally not a valid split name for public reads (enforced in C1).
    return JSONResponse(
        status_code=501,
        content={"detail": f"planned: split {name} for {dataset_id}"},
    )


@app.post("/internal/holdout/evaluate", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def holdout_evaluate(_body: HoldoutEvaluateRequest) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"detail": "planned: evaluate-once sealed holdout (Stage C1)"},
    )
