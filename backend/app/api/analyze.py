import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.schemas import (
    AnalysisMetadata,
    AnalyzeSubmissionResponse,
)
from app.services.analyzer import new_analysis_id, run_analysis
from app.services.file_storage import save_project_tech_stack
from app.services.gemini_client import GeminiParseError, GeminiUnavailableError
from app.services.session_store import AnalysisRecord, store
from app.services.tech_stack_detector import detect_project_tech_stack
from app.services.zip_extractor import EmptyProjectError, ZipSecurityError, extract_zip

router = APIRouter()


@router.post("/analyze-submission", response_model=AnalyzeSubmissionResponse)
async def analyze_submission(
    project_title: str = Form(...),
    project_outcomes: str = Form(...),
    zip_file: UploadFile = File(...),
    project_description: str | None = Form(None),
    questions_per_skill: int = Form(2),
):
    if not project_title.strip():
        raise HTTPException(status_code=422, detail="project_title is required")
    if not project_outcomes.strip():
        raise HTTPException(status_code=422, detail="project_outcomes is required")

    start = time.perf_counter()

    try:
        zip_bytes = await zip_file.read()
        if not zip_bytes:
            raise HTTPException(status_code=422, detail="ZIP file is empty")
        project = extract_zip(zip_bytes)
    except ZipSecurityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EmptyProjectError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    analysis_id = new_analysis_id()
    tech_stack = detect_project_tech_stack(project, project_title, analysis_id)
    tech_stack_path = save_project_tech_stack(analysis_id, tech_stack)

    try:
        skills, report, tokens = await run_analysis(
            project=project,
            project_title=project_title,
            project_description=project_description,
            project_outcomes=project_outcomes,
            tech_stack=tech_stack,
        )
    except GeminiUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GeminiParseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    processing_ms = int((time.perf_counter() - start) * 1000)

    metadata = AnalysisMetadata(
        files_analyzed=project.files_analyzed,
        extraction_time_ms=project.extraction_time_ms,
        model_tokens_used=tokens,
    )

    response = AnalyzeSubmissionResponse(
        analysis_id=analysis_id,
        project_title=project_title,
        suggested_skills=skills,
        evaluation_report=report,
        metadata=metadata,
        processing_time_ms=processing_ms,
        saved_files={"uploaded_project_tech_stack": tech_stack_path},
    )

    viva_topics = tech_stack.get("viva_topics") or []

    store.save_analysis(
        AnalysisRecord(
            analysis_id=analysis_id,
            project_title=project_title,
            suggested_skills=skills,
            evaluation_report=report,
            metadata=metadata,
            processing_time_ms=processing_ms,
            tech_stack_path=tech_stack_path,
            viva_topics=viva_topics,
            project_snippets=project.snippets,
        )
    )

    return response
