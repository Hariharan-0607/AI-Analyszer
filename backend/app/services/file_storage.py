"""Persist evaluation packages and proctoring integrity logs to disk."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.schemas import CombinedEvaluationResponse, ProctoringEvent, ProctoringReport

OUTPUT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "output"
EVALUATIONS_DIR = OUTPUT_ROOT / "evaluations"
INTEGRITY_DIR = OUTPUT_ROOT / "proctoring_logs"
TECH_STACK_DIR = OUTPUT_ROOT / "tech_stacks"


def slugify_project_title(title: str, max_len: int = 48) -> str:
    """Filesystem-safe slug from a project title."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        slug = "project"
    return slug[:max_len].rstrip("-")


def _ensure_dirs() -> None:
    EVALUATIONS_DIR.mkdir(parents=True, exist_ok=True)
    INTEGRITY_DIR.mkdir(parents=True, exist_ok=True)
    TECH_STACK_DIR.mkdir(parents=True, exist_ok=True)


def tech_stack_filename(analysis_id: str, project_title: str) -> str:
    slug = slugify_project_title(project_title)
    return f"{slug}__{analysis_id}__tech_stack.json"


def proctoring_log_filename(session_id: str, analysis_id: str, project_title: str) -> str:
    slug = slugify_project_title(project_title)
    return f"{slug}__{session_id}__{analysis_id}__proctoring_log.json"


def viva_evaluation_filename(session_id: str, analysis_id: str, project_title: str) -> str:
    slug = slugify_project_title(project_title)
    return f"{slug}__{session_id}__{analysis_id}__viva_evaluation.json"


def _tech_stack_path(analysis_id: str, project_title: str) -> Path:
    return TECH_STACK_DIR / tech_stack_filename(analysis_id, project_title)


def _integrity_log_path(session_id: str, analysis_id: str, project_title: str) -> Path:
    return INTEGRITY_DIR / proctoring_log_filename(session_id, analysis_id, project_title)


def _evaluation_path(session_id: str, analysis_id: str, project_title: str) -> Path:
    return EVALUATIONS_DIR / viva_evaluation_filename(session_id, analysis_id, project_title)


def _load_integrity_log(session_id: str, analysis_id: str, project_title: str) -> dict[str, Any]:
    path = _integrity_log_path(session_id, analysis_id, project_title)
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {
        "session_id": session_id,
        "analysis_id": analysis_id,
        "project_title": project_title,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "events": [],
        "conditions_detected": {
            "tab_switched": [],
            "gaze_off_screen": [],
            "face_not_detected": [],
            "multiple_faces_detected": [],
            "fullscreen_exited": [],
            "paste_attempted": [],
            "screenshot_detected": [],
            "connection_lost": [],
            "camera_changed": [],
            "camera_disconnected": [],
            "secondary_device_detected": [],
            "id_verified": [],
            "id_failed": [],
            "interview_started": [],
            "snapshot_captured": [],
        },
    }


def _write_json(path: Path, data: dict[str, Any]) -> str:
    _ensure_dirs()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return str(path.resolve())


def init_integrity_log(session_id: str, analysis_id: str, project_title: str) -> str:
    log = _load_integrity_log(session_id, analysis_id, project_title)
    return _write_json(_integrity_log_path(session_id, analysis_id, project_title), log)


def append_integrity_event(
    session_id: str,
    analysis_id: str,
    project_title: str,
    event: ProctoringEvent,
) -> str:
    log = _load_integrity_log(session_id, analysis_id, project_title)
    event_data = event.model_dump(mode="json")
    log["events"].append(event_data)

    conditions = log["conditions_detected"]
    bucket = conditions.get(event.event_type)
    if bucket is not None:
        bucket.append(
            {
                "timestamp": event_data["timestamp"],
                "duration_ms": event.duration_ms,
                "confidence": event.confidence,
            }
        )

    return _write_json(_integrity_log_path(session_id, analysis_id, project_title), log)


def finalize_integrity_log(
    session_id: str,
    analysis_id: str,
    project_title: str,
    proctoring_report: ProctoringReport,
) -> str:
    log = _load_integrity_log(session_id, analysis_id, project_title)
    log["ended_at"] = datetime.now(timezone.utc).isoformat()
    log["integrity_score"] = proctoring_report.integrity_score
    log["risk_level"] = proctoring_report.risk_level.value
    log["id_check"] = proctoring_report.id_check.value
    log["flag_summary"] = proctoring_report.flag_summary
    log["flags"] = [f.model_dump(mode="json") for f in proctoring_report.flags]
    log["narrative"] = proctoring_report.narrative
    return _write_json(_integrity_log_path(session_id, analysis_id, project_title), log)


def save_project_tech_stack(analysis_id: str, tech_stack: dict[str, Any]) -> str:
    project_title = str(tech_stack.get("project_title") or "project")
    data = dict(tech_stack)
    data["saved_at"] = datetime.now(timezone.utc).isoformat()
    return _write_json(_tech_stack_path(analysis_id, project_title), data)


def save_evaluation_package(
    session_id: str,
    analysis_id: str,
    project_title: str,
    package: CombinedEvaluationResponse,
    tech_stack_path: str | None = None,
) -> str:
    data = package.model_dump(mode="json")
    data["saved_at"] = datetime.now(timezone.utc).isoformat()
    data["session_id"] = session_id
    data["analysis_id"] = analysis_id
    data["project_title"] = project_title
    if tech_stack_path:
        data["uploaded_project_tech_stack_file"] = tech_stack_path
    return _write_json(_evaluation_path(session_id, analysis_id, project_title), data)
