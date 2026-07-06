from __future__ import annotations

from datetime import datetime, timezone

from app.config import get_settings
from app.models.schemas import (
    IdCheck,
    ProctoringEvent,
    ProctoringFlag,
    ProctoringReport,
    RiskLevel,
    Severity,
)
from app.services.session_store import VivaSession

FLAG_EVENT_TYPES = {
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

SEVERITY_DEDUCTION = {
    Severity.LOW: 0.04,
    Severity.MEDIUM: 0.10,
    Severity.HIGH: 0.18,
}

MAX_DEDUCTION_PER_TYPE = {
    Severity.LOW: 0.12,
    Severity.MEDIUM: 0.20,
    Severity.HIGH: 0.36,
}

# Each occurrence counts separately toward the integrity penalty cap.
MULTI_STRIKE_TYPES = {
    "screenshot_detected",
    "paste_attempted",
    "secondary_device_detected",
    "camera_changed",
    "tab_switched",
    "fullscreen_exited",
}


def _severity_for_event(event_type: str, duration_ms: int | None) -> Severity:
    settings = get_settings()
    duration_sec = (duration_ms or 0) / 1000.0

    if event_type in (
        "paste_attempted",
        "screenshot_detected",
        "connection_lost",
        "id_failed",
        "camera_changed",
        "camera_disconnected",
        "secondary_device_detected",
    ):
        return Severity.HIGH
    if event_type == "tab_switched":
        return Severity.MEDIUM
    if event_type == "multiple_faces_detected":
        return Severity.HIGH
    if event_type == "fullscreen_exited":
        return Severity.MEDIUM
    if event_type == "gaze_off_screen":
        if duration_sec >= settings.gaze_medium_sec:
            return Severity.MEDIUM
        return Severity.LOW
    if event_type == "face_not_detected":
        if duration_sec >= settings.face_not_detected_sec:
            return Severity.MEDIUM
        return Severity.LOW

    return Severity.LOW


def _event_to_flag(event: ProctoringEvent) -> ProctoringFlag:
    return ProctoringFlag(
        type=event.event_type,
        timestamp=event.timestamp,
        duration_ms=event.duration_ms,
        severity=_severity_for_event(event.event_type, event.duration_ms),
        confidence=event.confidence,
    )


def _aggregate_flags(flags: list[ProctoringFlag]) -> list[ProctoringFlag]:
    """One representative flag per type for non-strike events (highest severity wins).
    Multi-strike types (tab_switched, screenshot, paste, etc.) keep every occurrence."""
    severity_rank = {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}
    best: dict[str, ProctoringFlag] = {}
    multi: list[ProctoringFlag] = []
    for flag in flags:
        if flag.type in MULTI_STRIKE_TYPES:
            multi.append(flag)
            continue
        current = best.get(flag.type)
        if not current or severity_rank[flag.severity] > severity_rank[current.severity]:
            best[flag.type] = flag
    return list(best.values()) + multi


def _check_connection_gaps(session: VivaSession) -> list[ProctoringFlag]:
    settings = get_settings()
    flags: list[ProctoringFlag] = []
    timeout_ms = settings.connection_timeout_sec * 1000

    monitoring_events = [
        e for e in session.events
        if e.event_type in FLAG_EVENT_TYPES or e.event_type == "snapshot_captured"
    ]

    if not monitoring_events and session.interview_started:
        flags.append(
            ProctoringFlag(
                type="connection_lost",
                timestamp=datetime.now(timezone.utc),
                duration_ms=int(settings.connection_timeout_sec * 1000),
                severity=Severity.HIGH,
            )
        )
        return flags

    sorted_events = sorted(monitoring_events, key=lambda e: e.timestamp)
    for i in range(1, len(sorted_events)):
        prev_ts = sorted_events[i - 1].timestamp
        curr_ts = sorted_events[i].timestamp
        gap_ms = int((curr_ts - prev_ts).total_seconds() * 1000)
        if gap_ms > timeout_ms:
            flags.append(
                ProctoringFlag(
                    type="connection_lost",
                    timestamp=curr_ts,
                    duration_ms=gap_ms,
                    severity=Severity.HIGH,
                )
            )

    return flags


def _compute_integrity_score(
    flags: list[ProctoringFlag],
    flag_counts: dict[str, int],
    id_verified: bool,
    id_failed: bool,
) -> float:
    if id_failed:
        return round(max(0.0, 0.45 - 0.05 * len(flags)), 2)

    if not flags and id_verified:
        return 1.0

    deductions_by_type: dict[str, float] = {}
    for flag in flags:
        if flag.type == "id_failed":
            continue
        if flag.type in MULTI_STRIKE_TYPES:
            count = max(1, flag_counts.get(flag.type, 1))
            add = SEVERITY_DEDUCTION.get(flag.severity, 0.04)
            cap = MAX_DEDUCTION_PER_TYPE.get(flag.severity, 0.12)
            deductions_by_type[flag.type] = min(cap, count * add)
            continue
        add = SEVERITY_DEDUCTION.get(flag.severity, 0.04)
        cap = MAX_DEDUCTION_PER_TYPE.get(flag.severity, 0.12)
        deductions_by_type[flag.type] = min(cap, deductions_by_type.get(flag.type, 0.0) + add)

    total_deduction = sum(deductions_by_type.values())

    if not id_verified:
        total_deduction += 0.12

    score = 1.0 - total_deduction
    return max(0.0, min(1.0, round(score, 2)))


def _risk_level(score: float) -> RiskLevel:
    settings = get_settings()
    if score >= settings.risk_low_min_score:
        return RiskLevel.LOW
    if score >= settings.risk_medium_min_score:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


def _build_narrative(
    flags: list[ProctoringFlag],
    id_check: IdCheck,
    integrity_score: float,
    risk_level: RiskLevel,
) -> str:
    if id_check == IdCheck.FAILED:
        return (
            "Identity verification failed before questioning began. "
            "The session integrity cannot be confirmed and should be reviewed by a mentor."
        )

    if not flags:
        return (
            "The student remained on-screen and attentive throughout the session. "
            "No integrity concerns were detected during monitoring."
        )

    flag_types = {f.type for f in flags}
    parts: list[str] = []
    if "gaze_off_screen" in flag_types:
        parts.append("brief glances away from the screen were recorded")
    if "tab_switched" in flag_types:
        parts.append("tab switching was detected during the session")
    if "face_not_detected" in flag_types:
        parts.append("periods without a visible face were noted")
    if "multiple_faces_detected" in flag_types:
        parts.append("multiple faces were detected at times")
    if "paste_attempted" in flag_types:
        parts.append("clipboard paste attempts were detected during answers")
    if "screenshot_detected" in flag_types:
        parts.append("screenshot capture attempts were detected")
    if "fullscreen_exited" in flag_types:
        parts.append("the student left fullscreen during the exam")
    if "secondary_device_detected" in flag_types:
        parts.append("a phone or secondary device was visible in the camera")
    if "camera_changed" in flag_types:
        parts.append("the webcam source was switched during the session")
    if "camera_disconnected" in flag_types:
        parts.append("the webcam disconnected or was interrupted")
    if "connection_lost" in flag_types:
        parts.append("gaps in event transmission suggest connection or camera issues")

    concern_text = "; ".join(parts) if parts else "minor integrity signals were recorded"
    return (
        f"The student completed the viva with an integrity score of {integrity_score:.2f} "
        f"({risk_level.value} risk). During monitoring, {concern_text}. "
        "Review flagged timestamps if further investigation is needed."
    )


def build_proctoring_report(session: VivaSession) -> ProctoringReport:
    raw_flags: list[ProctoringFlag] = []

    for event in session.events:
        if event.event_type in FLAG_EVENT_TYPES:
            raw_flags.append(_event_to_flag(event))

    raw_flags.extend(_check_connection_gaps(session))

    if session.id_failed:
        raw_flags.append(
            ProctoringFlag(
                type="id_failed",
                timestamp=session.started_at,
                severity=Severity.HIGH,
            )
        )

    flags = _aggregate_flags(raw_flags)

    flag_summary: dict[str, int] = {}
    for flag in raw_flags:
        flag_summary[flag.type] = flag_summary.get(flag.type, 0) + 1

    if session.id_failed:
        id_check = IdCheck.FAILED
    elif session.id_verified:
        id_check = IdCheck.VERIFIED
    else:
        id_check = IdCheck.FAILED

    integrity_score = _compute_integrity_score(
        flags, flag_summary, session.id_verified, session.id_failed
    )
    risk = _risk_level(integrity_score)

    return ProctoringReport(
        session_id=session.session_id,
        id_check=id_check,
        integrity_score=integrity_score,
        risk_level=risk,
        flag_summary=flag_summary,
        flags=flags,
        narrative=_build_narrative(flags, id_check, integrity_score, risk),
    )


def compute_overall_exam_score(viva_score: float, integrity_score: float) -> float:
    """70% answer quality + 30% proctoring integrity."""
    combined = viva_score * 0.7 + integrity_score * 0.3
    return max(0.0, min(1.0, round(combined, 2)))


def get_proctoring_config() -> dict:
    settings = get_settings()
    return {
        "gaze_low_sec": settings.gaze_low_sec,
        "gaze_medium_sec": settings.gaze_medium_sec,
        "face_not_detected_sec": settings.face_not_detected_sec,
        "connection_timeout_sec": settings.connection_timeout_sec,
        "heartbeat_interval_sec": 15,
    }
