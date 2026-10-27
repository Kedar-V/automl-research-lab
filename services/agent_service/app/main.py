"""Agent-service skeleton — LLM subagents arrive in Stage C5."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services"))

from contracts import AgentInvokeRequest, AgentInvokeResponse, HealthResponse  # noqa: E402
from _shared.correlation import CorrelationIdMiddleware  # noqa: E402

SERVICE_NAME = "agent_service"

app = FastAPI(title="AutoML Agent Service", version="0.1.0")
app.add_middleware(CorrelationIdMiddleware)


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, mock=True)


@app.post(
    "/agents/{lead}/{subagent}/invoke",
    response_model=AgentInvokeResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def invoke_agent(lead: str, subagent: str, _body: AgentInvokeRequest) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"detail": f"planned: invoke {lead}/{subagent} (Stage C5)"},
    )
