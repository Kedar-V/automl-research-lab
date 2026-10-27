"""Gateway skeleton — session commands and SSE fan-out (real logic in C7 / A1)."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

# Make shared middleware and contracts importable inside the container.
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services"))

from contracts import (  # noqa: E402
    CreateSessionRequest,
    CreateSessionResponse,
    HealthResponse,
    SessionCommandResponse,
)
from _shared.correlation import CorrelationIdMiddleware  # noqa: E402

SERVICE_NAME = "gateway"

app = FastAPI(title="AutoML Gateway", version="0.1.0")
app.add_middleware(CorrelationIdMiddleware)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, mock=True)


@app.post("/sessions", response_model=CreateSessionResponse, status_code=status.HTTP_501_NOT_IMPLEMENTED)
def create_session(_body: CreateSessionRequest) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": "planned: Stage A1 mock backend / C7 real gateway"},
    )


@app.post(
    "/sessions/{session_id}/pause",
    response_model=SessionCommandResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def pause_session(session_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": f"planned: pause {session_id}"},
    )


@app.post(
    "/sessions/{session_id}/resume",
    response_model=SessionCommandResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def resume_session(session_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": f"planned: resume {session_id}"},
    )


@app.post(
    "/sessions/{session_id}/reset",
    response_model=SessionCommandResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def reset_session(session_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": f"planned: reset {session_id}"},
    )


@app.get("/sessions/{session_id}/events", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def session_events(session_id: str) -> JSONResponse:
    # Path reserved for SSE in Stage A1; keep OpenAPI stable.
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": f"planned: SSE events for {session_id} (Stage A1)"},
    )


@app.post(
    "/sessions/{session_id}/datasets",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def upload_dataset(session_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": f"planned: dataset upload proxy for {session_id}"},
    )
