from datetime import datetime, timezone

import pytest

from app.models.schemas import ProctoringEvent, QuestionType, VivaAnswerSubmission
from app.services.answer_grader import grade_viva_answers
from app.services.proctoring import build_proctoring_report
from app.services.session_store import VivaSession


@pytest.mark.asyncio
async def test_grade_good_answer_higher_than_empty():
    good = VivaAnswerSubmission(
        skill_name="FastAPI",
        question_type=QuestionType.CONCEPTUAL,
        question_text="What is FastAPI and why use it?",
        answer_text=(
            "FastAPI is a Python web framework used for building REST APIs quickly. "
            "It provides automatic validation with Pydantic and is used in our project "
            "because it allows fast development of CRUD endpoints."
        ),
    )
    empty = VivaAnswerSubmission(
        skill_name="FastAPI",
        question_type=QuestionType.CONCEPTUAL,
        question_text="What is FastAPI?",
        answer_text="",
    )

    report = await grade_viva_answers([good, empty], "Todo API")
    assert report.answer_grades[0].score > report.answer_grades[1].score
    assert report.answer_grades[0].score >= 0.7
    assert report.answer_grades[1].score == 0.0


def test_clean_session_gets_full_integrity_score():
    session = VivaSession(session_id="sess-clean", analysis_id="ana-1")
    session.interview_started = True
    session.id_verified = True
    now = datetime.now(timezone.utc)
    session.events = [
        ProctoringEvent(session_id="sess-clean", event_type="interview_started", timestamp=now),
        ProctoringEvent(session_id="sess-clean", event_type="id_verified", timestamp=now),
        ProctoringEvent(session_id="sess-clean", event_type="snapshot_captured", timestamp=now),
    ]
    report = build_proctoring_report(session)
    assert report.integrity_score == 1.0
    assert report.risk_level.value == "low"


def test_repeated_gaze_flags_do_not_destroy_score():
    session = VivaSession(session_id="sess-gaze", analysis_id="ana-1")
    session.interview_started = True
    session.id_verified = True
    now = datetime.now(timezone.utc)
    session.events = [
        ProctoringEvent(session_id="sess-gaze", event_type="interview_started", timestamp=now),
        ProctoringEvent(session_id="sess-gaze", event_type="id_verified", timestamp=now),
    ]
    for _ in range(5):
        session.events.append(
            ProctoringEvent(
                session_id="sess-gaze",
                event_type="gaze_off_screen",
                timestamp=now,
                duration_ms=4000,
            )
        )

    report = build_proctoring_report(session)
    assert report.integrity_score >= 0.85
