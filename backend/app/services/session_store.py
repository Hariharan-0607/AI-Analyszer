from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.models.schemas import (
    AnalyzeSubmissionResponse,
    EvaluationReport,
    ProctoringEvent,
    SuggestedSkill,
    AnalysisMetadata,
)


@dataclass
class AnalysisRecord:
    analysis_id: str
    project_title: str
    suggested_skills: list[SuggestedSkill]
    evaluation_report: EvaluationReport
    metadata: AnalysisMetadata
    processing_time_ms: int
    tech_stack_path: str | None = None
    viva_topics: list[str] = field(default_factory=list)
    project_snippets: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class VivaSession:
    session_id: str
    analysis_id: str
    project_title: str = "project"
    events: list[ProctoringEvent] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_event_at: datetime | None = None
    ended: bool = False
    id_verified: bool = False
    id_failed: bool = False
    interview_started: bool = False


class SessionStore:
    def __init__(self) -> None:
        self._analyses: dict[str, AnalysisRecord] = {}
        self._sessions: dict[str, VivaSession] = {}

    def save_analysis(self, record: AnalysisRecord) -> None:
        self._analyses[record.analysis_id] = record

    def get_analysis(self, analysis_id: str) -> AnalysisRecord | None:
        return self._analyses.get(analysis_id)

    def create_session(self, analysis_id: str, project_title: str) -> VivaSession:
        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        session = VivaSession(
            session_id=session_id,
            analysis_id=analysis_id,
            project_title=project_title,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> VivaSession | None:
        return self._sessions.get(session_id)

    def append_event(self, session_id: str, event: ProctoringEvent) -> VivaSession:
        session = self._sessions[session_id]
        session.events.append(event)
        session.last_event_at = event.timestamp

        if event.event_type == "interview_started":
            session.interview_started = True
        elif event.event_type == "id_verified":
            session.id_verified = True
        elif event.event_type == "id_failed":
            session.id_failed = True

        return session

    def end_session(self, session_id: str) -> VivaSession:
        session = self._sessions[session_id]
        session.ended = True
        return session


store = SessionStore()
