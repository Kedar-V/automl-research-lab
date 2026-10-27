"""Gateway session command contracts."""

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    dataset_id: str | None = None
    # If uploading via multipart, dataset_id is filled after dataset-service responds.
    task_type: str = "classification"
    target_column: str
    metric: str = "f1"
    target_score: float = 0.7
    experiment_budget: int = 10
    scenario: str | None = None  # mock A1: happy|revise_loop|repair|...
    mock: bool = True


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str = "created"
    mock: bool = True


class SessionCommandResponse(BaseModel):
    session_id: str
    status: str
    message: str = ""
    mock: bool = True
