"""In-memory mock session store and timed SSE replay (Stage A1)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator

from contracts import EventEnvelope, EventType
from mocks.fixtures import SCENARIO_NAMES, load_scenario


class SessionStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    RESET = "reset"


@dataclass
class MockSession:
    session_id: str
    scenario: str
    correlation_id: str
    status: SessionStatus = SessionStatus.RUNNING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    history: list[EventEnvelope] = field(default_factory=list)
    _resume: asyncio.Event = field(default_factory=asyncio.Event)
    _cancel: asyncio.Event = field(default_factory=asyncio.Event)
    _live_stream_active: bool = False

    def __post_init__(self) -> None:
        self._resume.set()


class MockSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, MockSession] = {}

    async def create(self, scenario: str, correlation_id: str | None = None) -> MockSession:
        if scenario not in SCENARIO_NAMES:
            raise ValueError(f"unknown scenario {scenario!r}; choose one of {SCENARIO_NAMES}")
        session = MockSession(
            session_id=f"s-mock-{uuid.uuid4().hex[:8]}",
            scenario=scenario,
            correlation_id=correlation_id or str(uuid.uuid4()),
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> MockSession | None:
        return self._sessions.get(session_id)

    async def pause(self, session_id: str) -> MockSession:
        session = self._require(session_id)
        if session.status == SessionStatus.RUNNING:
            session.status = SessionStatus.PAUSED
            session._resume.clear()
        return session

    async def resume(self, session_id: str) -> MockSession:
        session = self._require(session_id)
        if session.status == SessionStatus.PAUSED:
            session.status = SessionStatus.RUNNING
            session._resume.set()
        return session

    async def reset(self, session_id: str) -> MockSession:
        session = self._require(session_id)
        session._cancel.set()
        session._resume.set()
        session.status = SessionStatus.RESET
        return session

    def _require(self, session_id: str) -> MockSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session


store = MockSessionStore()


def build_event(session: MockSession, step: dict[str, Any]) -> EventEnvelope:
    return EventEnvelope(
        timestamp=datetime.now(timezone.utc),
        session_id=session.session_id,
        correlation_id=session.correlation_id,
        source_service=step["source_service"],
        source_agent=step.get("source_agent"),
        type=EventType(step["type"]),
        payload=dict(step.get("payload") or {}),
        mock=True,
    )


async def replay_scenario(session: MockSession) -> AsyncIterator[EventEnvelope]:
    """Timed fixture replay. Completed sessions re-send history for reconnects."""
    if session.status == SessionStatus.COMPLETED and session.history:
        for event in session.history:
            yield event
        return

    if session._live_stream_active:
        # Another client already owns the live replay; send history so far only.
        for event in list(session.history):
            yield event
        return

    session._live_stream_active = True
    try:
        steps = load_scenario(session.scenario)
        for step in steps:
            if session._cancel.is_set() or session.status == SessionStatus.RESET:
                break
            await session._resume.wait()
            if session._cancel.is_set():
                break
            delay_ms = int(step.get("delay_ms") or 0)
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000.0)
            await session._resume.wait()
            if session._cancel.is_set():
                break
            event = build_event(session, step)
            session.history.append(event)
            yield event
            if event.payload.get("done") is True:
                session.status = SessionStatus.COMPLETED
                return
        if session.status == SessionStatus.RUNNING:
            session.status = SessionStatus.COMPLETED
    finally:
        session._live_stream_active = False
