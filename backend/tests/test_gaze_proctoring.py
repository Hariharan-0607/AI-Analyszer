"""Parity checks for iris gaze thresholds (mirrors frontend gazeDetection.ts)."""

from app.services.proctoring import _severity_for_event


def test_screenshot_and_fullscreen_are_high_severity():
    assert _severity_for_event("screenshot_detected", None).value == "high"
    assert _severity_for_event("fullscreen_exited", None).value == "medium"


def test_gaze_off_screen_severity_scales_with_duration():
    low = _severity_for_event("gaze_off_screen", 3000)   # 3s → low (below 5s medium threshold)
    medium = _severity_for_event("gaze_off_screen", 6000) # 6s → medium
    assert low.value == "low"
    assert medium.value == "medium"


def test_tab_switch_is_multi_strike():
    """Each tab switch must count as a separate strike, not be deduplicated."""
    from datetime import datetime, timezone

    from app.models.schemas import ProctoringEvent
    from app.services.proctoring import build_proctoring_report
    from app.services.session_store import VivaSession

    session = VivaSession(session_id="sess-tab", analysis_id="ana-1")
    session.interview_started = True
    session.id_verified = True
    now = datetime.now(timezone.utc)
    session.events = [
        ProctoringEvent(session_id="sess-tab", event_type="interview_started", timestamp=now),
        ProctoringEvent(session_id="sess-tab", event_type="id_verified", timestamp=now),
        ProctoringEvent(session_id="sess-tab", event_type="tab_switched", timestamp=now, confidence=1.0),
        ProctoringEvent(session_id="sess-tab", event_type="tab_switched", timestamp=now, confidence=1.0),
        ProctoringEvent(session_id="sess-tab", event_type="tab_switched", timestamp=now, confidence=1.0),
    ]
    session.last_event_at = now
    report = build_proctoring_report(session)
    # All 3 tab switches must be counted individually
    assert report.flag_summary.get("tab_switched", 0) == 3
    # 3 MEDIUM strikes → meaningful deduction (capped at 0.20 → score = 0.80)
    assert report.integrity_score <= 0.80


def test_paste_is_multi_strike():
    """Each paste attempt must count as a separate strike."""
    from datetime import datetime, timezone

    from app.models.schemas import ProctoringEvent
    from app.services.proctoring import build_proctoring_report
    from app.services.session_store import VivaSession

    session = VivaSession(session_id="sess-paste", analysis_id="ana-1")
    session.interview_started = True
    session.id_verified = True
    now = datetime.now(timezone.utc)
    session.events = [
        ProctoringEvent(session_id="sess-paste", event_type="interview_started", timestamp=now),
        ProctoringEvent(session_id="sess-paste", event_type="id_verified", timestamp=now),
        ProctoringEvent(session_id="sess-paste", event_type="paste_attempted", timestamp=now, confidence=1.0),
        ProctoringEvent(session_id="sess-paste", event_type="paste_attempted", timestamp=now, confidence=1.0),
    ]
    session.last_event_at = now
    report = build_proctoring_report(session)
    assert report.flag_summary.get("paste_attempted", 0) == 2
    assert report.integrity_score < 0.70
