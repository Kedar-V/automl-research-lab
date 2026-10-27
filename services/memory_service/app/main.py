"""Memory-service skeleton — four stores arrive in Stage C4."""

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

SERVICE_NAME = "memory_service"

app = FastAPI(title="AutoML Memory Service", version="0.1.0")
app.add_middleware(CorrelationIdMiddleware)


class MemoryWrite(BaseModel):
    session_id: str
    writer: str
    content: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, mock=True)


@app.post("/findings", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def post_findings(_body: MemoryWrite) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "planned: Stage C4 findings"})


@app.get("/findings", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_findings(session_id: str = "") -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "planned: Stage C4 findings"})


@app.post("/history", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def post_history(_body: MemoryWrite) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "planned: Stage C4 history"})


@app.get("/history", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_history(session_id: str = "") -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "planned: Stage C4 history"})


@app.post("/lessons", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def post_lessons(_body: MemoryWrite) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "planned: Stage C4 lessons"})


@app.get("/lessons", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_lessons(q: str = "") -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": "planned: Stage C4 lessons"})


@app.post("/working/{agent}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def post_working(agent: str, _body: MemoryWrite) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": f"planned: working memory for {agent}"})


@app.get("/working/{agent}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_working(agent: str, session_id: str = "") -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": f"planned: working memory for {agent}"})
