"""Rule-based analysis fallback when Gemini is unavailable."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.models.schemas import (
    EvaluationReport,
    EvaluationSummary,
    OutcomeEvaluation,
    OutcomeStatus,
    OverallAlignment,
    SkillCatalogEntry,
)
from app.services.question_generator import (
    build_questions_for_topics,
    extract_viva_topics,
    tech_stack_to_suggested_skills,
    validate_questions_cover_all_topics,
)
from app.services.zip_extractor import ExtractedProject

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "skill_catalog.json"


def load_skill_catalog() -> list[SkillCatalogEntry]:
    with open(CATALOG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return [SkillCatalogEntry(**entry) for entry in data]


def _parse_outcomes(project_outcomes: str) -> list[str]:
    lines = []
    for line in project_outcomes.replace("\r\n", "\n").split("\n"):
        cleaned = line.strip()
        if not cleaned:
            continue
        cleaned = re.sub(r"^[\d]+[\.\)]\s*", "", cleaned)
        cleaned = re.sub(r"^[-*•]\s*", "", cleaned)
        if cleaned:
            lines.append(cleaned)
    return lines if lines else [project_outcomes.strip()]


def run_fallback_analysis(
    project: ExtractedProject,
    project_title: str,
    project_outcomes: str,
    tech_stack: dict[str, Any],
) -> tuple[list, EvaluationReport]:
    from app.models.schemas import SuggestedSkill

    topics = extract_viva_topics(tech_stack)
    if not topics:
        topics = ["Python", "Project Implementation"]

    skills = tech_stack_to_suggested_skills(topics, project)
    questions = validate_questions_cover_all_topics(
        build_questions_for_topics(topics, project, project_title),
        topics,
        project,
        project_title,
    )

    outcomes = _parse_outcomes(project_outcomes)
    outcome_evals: list[OutcomeEvaluation] = []
    met_count = 0
    py_files = [p for p in project.snippets if p.endswith(".py")]
    main_file = py_files[0] if py_files else next(iter(project.snippets), "unknown")

    for outcome in outcomes:
        keywords = [w.lower() for w in re.findall(r"[a-zA-Z]{4,}", outcome)]
        matched = [p for p in project.file_tree if any(k in p.lower() for k in keywords)]
        if not matched:
            matched = [p for p, c in project.snippets.items() if any(k in c.lower() for k in keywords)]

        if matched:
            status = OutcomeStatus.MET
            met_count += 1
            evidence = f"Evidence in {', '.join(matched[:3])}"
            gap = None
        elif py_files or project.dependencies:
            status = OutcomeStatus.PARTIAL
            evidence = f"Related code in {main_file}"
            gap = "Could not find explicit implementation for all outcome keywords"
        else:
            status = OutcomeStatus.NOT_VERIFIABLE
            evidence = "Insufficient code evidence in ZIP"
            gap = outcome

        outcome_evals.append(
            OutcomeEvaluation(outcome=outcome, status=status, evidence=evidence, gap=gap)
        )

    ratio = met_count / max(len(outcomes), 1)
    if ratio >= 0.7:
        alignment = OverallAlignment.STRONG
    elif ratio >= 0.4:
        alignment = OverallAlignment.PARTIAL
    else:
        alignment = OverallAlignment.WEAK

    topic_list = ", ".join(topics)
    summary = EvaluationSummary(
        overall_alignment=alignment,
        alignment_score=round(ratio, 2),
        narrative=(
            f"The {project_title} submission shows {alignment.value} alignment with stated outcomes. "
            f"Viva covers each detected technology: {topic_list}. "
            f"{project.files_analyzed} source files were examined."
        ),
        outcome_evaluation=outcome_evals,
        strengths=[f"Tech stack: {topic_list}"] if topics else [],
        gaps=[],
    )

    return skills, EvaluationReport(skills=questions, summary=summary)
