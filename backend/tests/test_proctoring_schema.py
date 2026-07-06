from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    CombinedEvaluationResponse,
    EvaluationReport,
    EvaluationSummary,
    IdCheck,
    OutcomeStatus,
    OverallAlignment,
    ProctoringEvent,
    ProctoringReport,
    RiskLevel,
    Severity,
    SuggestedSkill,
)
from app.services.proctoring import build_proctoring_report, compute_overall_exam_score
from app.services.session_store import VivaSession


def test_proctoring_event_schema_valid():
    event = ProctoringEvent(
        session_id="sess-test",
        event_type="gaze_off_screen",
        timestamp=datetime.now(timezone.utc),
        duration_ms=4200,
        confidence=0.81,
    )
    assert event.event_type == "gaze_off_screen"


def test_proctoring_event_schema_invalid_type():
    with pytest.raises(ValidationError):
        ProctoringEvent(
            session_id="sess-test",
            event_type="invalid_event",
            timestamp=datetime.now(timezone.utc),
        )


def test_integrity_score_with_flags():
    session = VivaSession(session_id="sess-abc", analysis_id="ana-xyz")
    session.interview_started = True
    session.id_verified = True

    now = datetime.now(timezone.utc)
    session.events = [
        ProctoringEvent(
            session_id="sess-abc",
            event_type="interview_started",
            timestamp=now,
        ),
        ProctoringEvent(
            session_id="sess-abc",
            event_type="id_verified",
            timestamp=now,
        ),
        ProctoringEvent(
            session_id="sess-abc",
            event_type="gaze_off_screen",
            timestamp=now,
            duration_ms=5000,
            confidence=0.8,
        ),
        ProctoringEvent(
            session_id="sess-abc",
            event_type="tab_switched",
            timestamp=now,
            confidence=1.0,
        ),
    ]
    session.last_event_at = now

    report = build_proctoring_report(session)
    assert 0 <= report.integrity_score <= 1
    assert report.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH)
    assert report.id_check == IdCheck.VERIFIED
    assert report.flag_summary.get("gaze_off_screen", 0) >= 1


def test_combined_output_matches_schema():
    summary = EvaluationSummary(
        overall_alignment=OverallAlignment.PARTIAL,
        alignment_score=0.72,
        narrative="Test narrative for mentor.",
        outcome_evaluation=[
            {
                "outcome": "Build REST API",
                "status": OutcomeStatus.MET,
                "evidence": "app/routes/todos.py",
                "gap": None,
            }
        ],
        strengths=["Good structure"],
        gaps=["No tests"],
    )
    report = ProctoringReport(
        session_id="sess-abc",
        id_check=IdCheck.VERIFIED,
        integrity_score=0.86,
        risk_level=RiskLevel.LOW,
        flag_summary={"gaze_off_screen": 1},
        flags=[
            {
                "type": "gaze_off_screen",
                "timestamp": datetime.now(timezone.utc),
                "duration_ms": 4200,
                "severity": Severity.LOW,
            }
        ],
        narrative="Student remained attentive.",
    )

    combined = CombinedEvaluationResponse(
        project_title="Test Project",
        suggested_skills=[
            SuggestedSkill(
                skill_id="uuid-python",
                skill_name="Python",
                confidence=0.9,
                rationale="Used in main.py",
            )
        ],
        evaluation_report=EvaluationReport(skills=[], summary=summary),
        proctoring_report=report,
        metadata={"files_analyzed": 5, "extraction_time_ms": 100, "model_tokens_used": 500},
        processing_time_ms=1000,
    )
    data = combined.model_dump()
    assert data["proctoring_report"]["integrity_score"] == 0.86
    assert data["project_title"] == "Test Project"


def test_multiple_screenshot_strikes_reduce_integrity_more():
    session = VivaSession(session_id="sess-shot", analysis_id="ana-xyz")
    session.interview_started = True
    session.id_verified = True

    now = datetime.now(timezone.utc)
    session.events = [
        ProctoringEvent(
            session_id="sess-shot",
            event_type="screenshot_detected",
            timestamp=now,
            confidence=0.9,
        ),
        ProctoringEvent(
            session_id="sess-shot",
            event_type="screenshot_detected",
            timestamp=now,
            confidence=0.9,
        ),
    ]
    session.last_event_at = now

    report = build_proctoring_report(session)
    assert report.flag_summary.get("screenshot_detected", 0) == 2
    assert report.integrity_score < 0.82


def test_new_device_event_types_are_valid():
    from app.models.schemas import ProctoringEvent

    now = datetime.now(timezone.utc)
    for event_type in (
        "camera_changed",
        "camera_disconnected",
        "secondary_device_detected",
    ):
        event = ProctoringEvent(
            session_id="sess-device",
            event_type=event_type,
            timestamp=now,
            confidence=0.9,
        )
        assert event.event_type == event_type


def test_combined_exam_score_weighting():
    assert compute_overall_exam_score(1.0, 1.0) == 1.0
    assert compute_overall_exam_score(0.8, 1.0) == 0.86
    assert compute_overall_exam_score(0.0, 1.0) == 0.3
