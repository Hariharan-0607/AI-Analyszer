from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class OutcomeStatus(str, Enum):
    MET = "met"
    PARTIAL = "partial"
    NOT_MET = "not_met"
    NOT_VERIFIABLE = "not_verifiable"


class OverallAlignment(str, Enum):
    STRONG = "strong"
    PARTIAL = "partial"
    WEAK = "weak"


class QuestionType(str, Enum):
    CONCEPTUAL = "conceptual"
    CODEBASE_SPECIFIC = "codebase_specific"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IdCheck(str, Enum):
    VERIFIED = "id_verified"
    FAILED = "id_failed"
    PENDING = "pending"


# --- Skill catalog ---


class SkillCatalogEntry(BaseModel):
    skill_id: str
    skill_name: str


class SuggestedSkill(BaseModel):
    skill_id: str
    skill_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


# --- Questions & evaluation ---


class Question(BaseModel):
    question_type: QuestionType
    text: str
    reference: str | None = None


class SkillQuestions(BaseModel):
    skill_name: str
    skill_id: str
    questions: list[Question]


class OutcomeEvaluation(BaseModel):
    outcome: str
    status: OutcomeStatus
    evidence: str
    gap: str | None = None


class EvaluationSummary(BaseModel):
    overall_alignment: OverallAlignment
    alignment_score: float | None = Field(default=None, ge=0.0, le=1.0)
    narrative: str
    outcome_evaluation: list[OutcomeEvaluation]
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    skills: list[SkillQuestions]
    summary: EvaluationSummary


class AnalysisMetadata(BaseModel):
    files_analyzed: int
    extraction_time_ms: int
    model_tokens_used: int = 0


# --- Analyze submission ---


class AnalyzeSubmissionResponse(BaseModel):
    analysis_id: str
    project_title: str
    suggested_skills: list[SuggestedSkill]
    evaluation_report: EvaluationReport
    metadata: AnalysisMetadata
    processing_time_ms: int
    saved_files: dict[str, str] = Field(default_factory=dict)


# --- Proctoring events ---


LIFECYCLE_EVENTS = {
    "interview_started",
    "id_verified",
    "id_failed",
    "snapshot_captured",
}

INTEGRITY_EVENTS = {
    "gaze_off_screen",
    "multiple_faces_detected",
    "face_not_detected",
    "tab_switched",
    "fullscreen_exited",
    "paste_attempted",
    "screenshot_detected",
    "connection_lost",
    "camera_changed",
    "camera_disconnected",
    "secondary_device_detected",
}

ALL_EVENT_TYPES = LIFECYCLE_EVENTS | INTEGRITY_EVENTS


class ProctoringEvent(BaseModel):
    session_id: str
    event_type: str
    timestamp: datetime
    duration_ms: int | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in ALL_EVENT_TYPES:
            raise ValueError(f"Invalid event_type: {v}")
        return v


class ProctoringFlag(BaseModel):
    type: str
    timestamp: datetime
    duration_ms: int | None = None
    severity: Severity
    confidence: float | None = None


class ProctoringReport(BaseModel):
    session_id: str
    id_check: IdCheck
    integrity_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    flag_summary: dict[str, int]
    flags: list[ProctoringFlag]
    narrative: str


# --- Viva session ---


class VivaStartRequest(BaseModel):
    analysis_id: str


class VivaStartResponse(BaseModel):
    session_id: str
    analysis_id: str
    questions: list[SkillQuestions]
    config: dict[str, Any]


class VivaAnswerSubmission(BaseModel):
    skill_name: str
    question_type: QuestionType
    question_text: str
    reference: str | None = None
    answer_text: str = ""


class VivaEndRequest(BaseModel):
    session_id: str
    answers: list[VivaAnswerSubmission] = Field(default_factory=list)


class AnswerGrade(BaseModel):
    skill_name: str
    question_type: QuestionType
    question_text: str
    answer_text: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    correctness_score: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=1.0)
    grade: str
    feedback: str


class VivaGradingReport(BaseModel):
    answer_grades: list[AnswerGrade]
    overall_viva_score: float = Field(ge=0.0, le=1.0)
    overall_exam_score: float = Field(ge=0.0, le=1.0)
    answers_graded: int
    narrative: str


class CombinedEvaluationResponse(BaseModel):
    project_title: str
    suggested_skills: list[SuggestedSkill]
    evaluation_report: EvaluationReport
    proctoring_report: ProctoringReport
    viva_grading_report: VivaGradingReport | None = None
    metadata: AnalysisMetadata
    processing_time_ms: int
    saved_files: dict[str, str] = Field(default_factory=dict)
