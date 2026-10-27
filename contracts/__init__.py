"""Shared request/response/event models for AutoML Research Lab services."""

from contracts.agents import AgentInvokeRequest, AgentInvokeResponse, LeadName, SubagentName
from contracts.domain import (
    DataProfile,
    ExecutionResult,
    ExperimentSpec,
    ResearchState,
    Verdict,
    VerdictAction,
)
from contracts.errors import ServiceError
from contracts.events import EventEnvelope, EventType
from contracts.health import HealthResponse
from contracts.ids import CorrelationId, SessionId
from contracts.sessions import (
    CreateSessionRequest,
    CreateSessionResponse,
    SessionCommandResponse,
)
from contracts.tools import (
    CompareExperimentsRequest,
    CompareExperimentsResponse,
    GenerateReportRequest,
    GenerateReportResponse,
    GetHistoryRequest,
    GetHistoryResponse,
    InspectDataRequest,
    InspectDataResponse,
    RunExperimentRequest,
    RunExperimentResponse,
    SaveArtifactRequest,
    SaveArtifactResponse,
    ValidateExperimentRequest,
    ValidateExperimentResponse,
)

__all__ = [
    "AgentInvokeRequest",
    "AgentInvokeResponse",
    "CompareExperimentsRequest",
    "CompareExperimentsResponse",
    "CorrelationId",
    "CreateSessionRequest",
    "CreateSessionResponse",
    "DataProfile",
    "EventEnvelope",
    "EventType",
    "ExecutionResult",
    "ExperimentSpec",
    "GenerateReportRequest",
    "GenerateReportResponse",
    "GetHistoryRequest",
    "GetHistoryResponse",
    "HealthResponse",
    "InspectDataRequest",
    "InspectDataResponse",
    "LeadName",
    "ResearchState",
    "RunExperimentRequest",
    "RunExperimentResponse",
    "SaveArtifactRequest",
    "SaveArtifactResponse",
    "ServiceError",
    "SessionCommandResponse",
    "SessionId",
    "SubagentName",
    "ValidateExperimentRequest",
    "ValidateExperimentResponse",
    "Verdict",
    "VerdictAction",
]
