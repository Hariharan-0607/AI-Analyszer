from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    CombinedEvaluationResponse,
    ProctoringEvent,
    VivaEndRequest,
    VivaStartRequest,
    VivaStartResponse,
)
from app.services.answer_grader import grade_viva_answers
from app.services.file_storage import (
    append_integrity_event,
    finalize_integrity_log,
    init_integrity_log,
    save_evaluation_package,
)
from app.services.proctoring import (
    build_proctoring_report,
    compute_overall_exam_score,
    get_proctoring_config,
)
from app.services.question_generator import validate_questions_cover_all_topics
from app.services.zip_extractor import project_from_snippets
from app.services.session_store import store

router = APIRouter(prefix="/viva-session")


def _resolve_viva_questions(analysis) -> list:
    topics = list(analysis.viva_topics)
    if not topics:
        topics = [sq.skill_name for sq in analysis.evaluation_report.skills]

    project = project_from_snippets(analysis.project_snippets)
    return validate_questions_cover_all_topics(
        analysis.evaluation_report.skills,
        topics,
        project,
        analysis.project_title,
    )


@router.post("/start", response_model=VivaStartResponse)
async def start_viva_session(body: VivaStartRequest):
    analysis = store.get_analysis(body.analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis not found: {body.analysis_id}")

    session = store.create_session(body.analysis_id, analysis.project_title)
    init_integrity_log(session.session_id, body.analysis_id, analysis.project_title)

    return VivaStartResponse(
        session_id=session.session_id,
        analysis_id=body.analysis_id,
        questions=_resolve_viva_questions(analysis),
        config=get_proctoring_config(),
    )


@router.post("/event")
async def post_viva_event(event: ProctoringEvent):
    session = store.get_session(event.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {event.session_id}")
    if session.ended:
        raise HTTPException(status_code=400, detail="Session has already ended")

    analysis = store.get_analysis(session.analysis_id)

    store.append_event(event.session_id, event)
    project_title = analysis.project_title if analysis else session.project_title
    log_path = append_integrity_event(
        event.session_id,
        session.analysis_id,
        project_title,
        event,
    )

    return {"status": "ok", "event_type": event.event_type, "log_file": log_path}


@router.post("/end", response_model=CombinedEvaluationResponse)
async def end_viva_session(body: VivaEndRequest):
    session = store.get_session(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {body.session_id}")

    analysis = store.get_analysis(session.analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Linked analysis not found")

    store.end_session(body.session_id)
    proctoring_report = build_proctoring_report(session)

    grading_report = await grade_viva_answers(
        answers=body.answers,
        project_title=analysis.project_title,
        project_snippets=analysis.project_snippets,
    )
    grading_report.overall_exam_score = compute_overall_exam_score(
        grading_report.overall_viva_score,
        proctoring_report.integrity_score,
    )
    grading_report.narrative = (
        f"{grading_report.narrative} "
        f"Proctoring integrity: {proctoring_report.integrity_score:.2f}. "
        f"Combined exam score (70% answers, 30% integrity): {grading_report.overall_exam_score:.2f}."
    )

    integrity_path = finalize_integrity_log(
        body.session_id,
        session.analysis_id,
        analysis.project_title,
        proctoring_report,
    )

    response = CombinedEvaluationResponse(
        project_title=analysis.project_title,
        suggested_skills=analysis.suggested_skills,
        evaluation_report=analysis.evaluation_report,
        proctoring_report=proctoring_report,
        viva_grading_report=grading_report,
        metadata=analysis.metadata,
        processing_time_ms=analysis.processing_time_ms,
    )

    evaluation_path = save_evaluation_package(
        body.session_id,
        session.analysis_id,
        analysis.project_title,
        response,
        tech_stack_path=analysis.tech_stack_path,
    )
    response.saved_files = {
        "evaluation_json": evaluation_path,
        "integrity_log": integrity_path,
        "uploaded_project_tech_stack": analysis.tech_stack_path or "",
    }

    return response
