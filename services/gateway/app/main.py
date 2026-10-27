"""Gateway — Stage A1 mock mode serves sessions + timed SSE fixture replay."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services"))

from contracts import (  # noqa: E402
    CreateSessionRequest,
    CreateSessionResponse,
    HealthResponse,
    SessionCommandResponse,
)
from mocks.fixtures import SCENARIO_NAMES  # noqa: E402
from _shared.correlation import CorrelationIdMiddleware  # noqa: E402

from services.gateway.app.mock_sessions import store  # noqa: E402
from services.gateway.app import mock_sessions as mock_mod  # noqa: E402

SERVICE_NAME = "gateway"
MOCK_GATEWAY = os.getenv("MOCK_GATEWAY", "true").lower() in {"1", "true", "yes"}

app = FastAPI(title="AutoML Gateway", version="0.1.0")
app.add_middleware(CorrelationIdMiddleware)


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "unknown")


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        mock=MOCK_GATEWAY,
        details={"mode": "mock" if MOCK_GATEWAY else "live", "scenarios": list(SCENARIO_NAMES)},
    )


@app.post("/sessions", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(body: CreateSessionRequest, request: Request) -> CreateSessionResponse:
    if not MOCK_GATEWAY:
        raise HTTPException(status_code=501, detail="live gateway arrives in Stage C7")
    scenario = body.scenario or "happy"
    if scenario not in SCENARIO_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"unknown scenario {scenario!r}; choose one of {list(SCENARIO_NAMES)}",
        )
    session = await store.create(scenario=scenario, correlation_id=_correlation_id(request))
    return CreateSessionResponse(session_id=session.session_id, status="created", mock=True)


@app.post("/sessions/{session_id}/pause", response_model=SessionCommandResponse)
async def pause_session(session_id: str) -> SessionCommandResponse:
    if not MOCK_GATEWAY:
        raise HTTPException(status_code=501, detail="live gateway arrives in Stage C7")
    try:
        session = await store.pause(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found") from None
    return SessionCommandResponse(
        session_id=session.session_id,
        status=session.status.value,
        message="paused at next fixture step",
        mock=True,
    )


@app.post("/sessions/{session_id}/resume", response_model=SessionCommandResponse)
async def resume_session(session_id: str) -> SessionCommandResponse:
    if not MOCK_GATEWAY:
        raise HTTPException(status_code=501, detail="live gateway arrives in Stage C7")
    try:
        session = await store.resume(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found") from None
    return SessionCommandResponse(
        session_id=session.session_id,
        status=session.status.value,
        message="resumed",
        mock=True,
    )


@app.post("/sessions/{session_id}/reset", response_model=SessionCommandResponse)
async def reset_session(session_id: str) -> SessionCommandResponse:
    if not MOCK_GATEWAY:
        raise HTTPException(status_code=501, detail="live gateway arrives in Stage C7")
    try:
        session = await store.reset(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found") from None
    return SessionCommandResponse(
        session_id=session.session_id,
        status=session.status.value,
        message="reset — SSE stream cancelled",
        mock=True,
    )


@app.get("/sessions/{session_id}/events")
async def session_events(
    session_id: str,
    scenario: str | None = Query(
        default=None,
        description="Ignored if session already created; listed for curl demos",
    ),
) -> StreamingResponse:
    """SSE fan-out of fixture events. Every event has mock: true."""
    if not MOCK_GATEWAY:
        raise HTTPException(status_code=501, detail="live SSE arrives in Stage C7")
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    _ = scenario  # OpenAPI discoverability; session already bound to a scenario.

    async def event_stream():
        async for event in mock_mod.replay_scenario(session):
            # SSE: data is a JSON EventEnvelope; comment marks mock for humans watching curl.
            payload = event.model_dump(mode="json")
            yield f": mock fixture event\n"
            yield f"event: {event.type.value}\n"
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Mock-Backend": "true",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/sessions/{session_id}/datasets")
async def upload_dataset(
    session_id: str,
    file: UploadFile | None = File(default=None),
) -> JSONResponse:
    """Mock upload proxy — records filename only; no real split yet (Stage C1)."""
    if not MOCK_GATEWAY:
        raise HTTPException(status_code=501, detail="live upload proxy arrives in Stage C7")
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    filename = file.filename if file else "churn_sample.csv"
    return JSONResponse(
        {
            "session_id": session_id,
            "dataset_id": f"ds-mock-{session_id[-8:]}",
            "filename": filename,
            "mock": True,
            "note": "SAMPLE: upload accepted in mock mode; real split in Stage C1",
        }
    )
