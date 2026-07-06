from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.schemas import (
    EvaluationReport,
    EvaluationSummary,
    OutcomeEvaluation,
    OutcomeStatus,
    OverallAlignment,
    Question,
    QuestionType,
    SkillCatalogEntry,
    SkillQuestions,
    SuggestedSkill,
)
from app.services.fallback_analyzer import run_fallback_analysis
from app.services.gemini_client import GeminiClient, GeminiParseError, GeminiUnavailableError
from app.services.question_generator import (
    build_questions_for_topics,
    ensure_all_topics_covered,
    extract_viva_topics,
    tech_stack_to_suggested_skills,
    validate_questions_cover_all_topics,
)
from app.services.zip_extractor import ExtractedProject, build_snippet_context

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "skill_catalog.json"


def load_skill_catalog() -> list[SkillCatalogEntry]:
    with open(CATALOG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return [SkillCatalogEntry(**entry) for entry in data]


def _catalog_map(catalog: list[SkillCatalogEntry]) -> dict[str, SkillCatalogEntry]:
    return {s.skill_id: s for s in catalog}


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


async def suggest_skills(
    client: GeminiClient,
    catalog: list[SkillCatalogEntry],
    snippet_context: str,
    project_title: str,
    project_description: str | None,
) -> list[SuggestedSkill]:
    catalog_json = json.dumps([c.model_dump() for c in catalog], indent=2)
    system = (
        "You are a technical mentor analyzing a student project codebase. "
        "Respond ONLY with valid JSON matching the requested schema. "
        "Only suggest skills from the provided catalog."
    )
    user = f"""Project: {project_title}
Description: {project_description or "N/A"}

Skill catalog (ONLY use these):
{catalog_json}

Codebase evidence:
{snippet_context}

Return JSON:
{{
  "suggested_skills": [
    {{
      "skill_id": "uuid-from-catalog",
      "skill_name": "name-from-catalog",
      "confidence": 0.85,
      "rationale": "specific evidence from the codebase"
    }}
  ]
}}

Rules:
- Only skills from the catalog
- confidence between 0 and 1
- rationale must cite real files or patterns
- Return 2-6 most relevant skills, ranked by confidence
"""
    data = await client.generate_json(system, user)
    catalog_by_id = _catalog_map(catalog)
    results: list[SuggestedSkill] = []

    for item in data.get("suggested_skills", []):
        skill_id = item.get("skill_id", "")
        if skill_id not in catalog_by_id:
            continue
        entry = catalog_by_id[skill_id]
        results.append(
            SuggestedSkill(
                skill_id=entry.skill_id,
                skill_name=entry.skill_name,
                confidence=min(1.0, max(0.0, float(item.get("confidence", 0.5)))),
                rationale=str(item.get("rationale", "")),
            )
        )

    results.sort(key=lambda s: s.confidence, reverse=True)
    return results[:6]


async def generate_questions(
    client: GeminiClient,
    topics: list[str],
    snippet_context: str,
    project_title: str,
) -> list[SkillQuestions]:
    system = (
        "You are a viva examiner. Generate interview questions for each technology topic. "
        "Respond ONLY with valid JSON."
    )
    topics_json = json.dumps(topics, indent=2)
    # Random seed forces the LLM to produce different questions on each call
    # even for the same project and topics
    variation_seed = uuid.uuid4().hex[:8]
    user = f"""Project: {project_title}
Session variation: {variation_seed}

Technologies to examine (EVERY topic must have exactly 2 questions):
{topics_json}

Codebase:
{snippet_context}

For EACH topic generate EXACTLY 2 UNIQUE questions (variation seed: {variation_seed} — questions must differ from any previous session):
1. conceptual — a specific, probing general knowledge question about the technology.
   Vary the angle: ask about internals, trade-offs, alternatives, limitations, or design philosophy.
   Do NOT use generic "What is X?" phrasing — go deeper.
2. codebase_specific — a specific question about WHERE and HOW they used it in THIS project.
   Reference real file paths, function names, or patterns visible in the codebase.
   Ask about a specific design decision, edge case, or trade-off in their code.

Return JSON:
{{
  "skills": [
    {{
      "skill_name": "NumPy",
      "questions": [
        {{ "question_type": "conceptual", "text": "...", "reference": null }},
        {{ "question_type": "codebase_specific", "text": "...", "reference": "path/to/file.py" }}
      ]
    }}
  ]
}}

Rules:
- One entry per topic — do not skip any
- Exactly 2 questions per topic: 1 conceptual + 1 codebase_specific
- codebase_specific must cite real files from the codebase
- Questions must be specific and varied — never reuse the same phrasing
"""
    data = await client.generate_json(system, user, temperature=0.9)
    skill_questions: list[SkillQuestions] = []

    for item in data.get("skills", []):
        questions: list[Question] = []
        for q in item.get("questions", []):
            qtype = q.get("question_type", "conceptual")
            try:
                qt = QuestionType(qtype)
            except ValueError:
                qt = QuestionType.CONCEPTUAL
            questions.append(
                Question(
                    question_type=qt,
                    text=str(q.get("text", "")),
                    reference=q.get("reference"),
                )
            )
        if questions:
            skill_questions.append(
                SkillQuestions(
                    skill_id=str(item.get("skill_id", "")),
                    skill_name=str(item.get("skill_name", "")),
                    questions=questions,
                )
            )

    return skill_questions


async def evaluate_outcomes(
    client: GeminiClient,
    project_outcomes: str,
    snippet_context: str,
    project_title: str,
) -> EvaluationSummary:
    outcomes = _parse_outcomes(project_outcomes)
    outcomes_text = "\n".join(f"- {o}" for o in outcomes)

    system = (
        "You are evaluating whether a student project meets stated learning outcomes. "
        "Compare ZIP evidence against each outcome. Respond ONLY with valid JSON."
    )
    user = f"""Project: {project_title}

Stated outcomes:
{outcomes_text}

Codebase evidence:
{snippet_context}

Return JSON:
{{
  "overall_alignment": "strong|partial|weak",
  "alignment_score": 0.72,
  "narrative": "2-4 plain English sentences for the mentor",
  "outcome_evaluation": [
    {{
      "outcome": "the outcome text",
      "status": "met|partial|not_met|not_verifiable",
      "evidence": "cite real files, modules, or patterns",
      "gap": "what is missing, or null"
    }}
  ],
  "strengths": ["..."],
  "gaps": ["..."]
}}

Rules:
- evidence must cite real files from the codebase
- status must be one of: met, partial, not_met, not_verifiable
"""
    data = await client.generate_json(system, user)

    outcome_evals: list[OutcomeEvaluation] = []
    for item in data.get("outcome_evaluation", []):
        try:
            status = OutcomeStatus(item.get("status", "not_verifiable"))
        except ValueError:
            status = OutcomeStatus.NOT_VERIFIABLE
        outcome_evals.append(
            OutcomeEvaluation(
                outcome=str(item.get("outcome", "")),
                status=status,
                evidence=str(item.get("evidence", "")),
                gap=item.get("gap"),
            )
        )

    try:
        alignment = OverallAlignment(data.get("overall_alignment", "partial"))
    except ValueError:
        alignment = OverallAlignment.PARTIAL

    score = data.get("alignment_score")
    if score is not None:
        score = min(1.0, max(0.0, float(score)))

    return EvaluationSummary(
        overall_alignment=alignment,
        alignment_score=score,
        narrative=str(data.get("narrative", "")),
        outcome_evaluation=outcome_evals,
        strengths=[str(s) for s in data.get("strengths", [])],
        gaps=[str(g) for g in data.get("gaps", [])],
    )


async def run_analysis(
    project: ExtractedProject,
    project_title: str,
    project_description: str | None,
    project_outcomes: str,
    tech_stack: dict,
) -> tuple[list[SuggestedSkill], EvaluationReport, int]:
    import logging
    log = logging.getLogger(__name__)

    topics = extract_viva_topics(tech_stack)
    if not topics:
        topics = ["Python", "Project Implementation"]

    # Always generate rule-based questions as a safety net covering all topics
    questions = build_questions_for_topics(topics, project, project_title)

    client = GeminiClient()
    if await client.check_health():
        log.info("Gemini available — generating questions and evaluation with LLM")
        context = build_snippet_context(project)
        try:
            # High temperature (0.9) for questions ensures varied output on repeated uploads
            llm_questions = await generate_questions(client, topics, context, project_title)
            validated = validate_questions_cover_all_topics(
                llm_questions, topics, project, project_title
            )
            questions = validated
            log.info("LLM questions generated successfully for %d topics", len(topics))
        except Exception as exc:
            log.warning("LLM question generation failed (%s) — using rule-based fallback", exc)

        try:
            summary = await evaluate_outcomes(client, project_outcomes, context, project_title)
        except Exception as exc:
            log.warning("LLM outcome evaluation failed (%s) — using fallback summary", exc)
            _, fallback_report = run_fallback_analysis(
                project, project_title, project_outcomes, tech_stack
            )
            summary = fallback_report.summary

        tokens = client.total_tokens
    else:
        log.warning(
            "Gemini unavailable (API key missing or invalid) — using rule-based fallback. "
            "Set GEMINI_API_KEY in backend/.env to enable LLM questions."
        )
        skills, report = run_fallback_analysis(
            project, project_title, project_outcomes, tech_stack
        )
        return skills, report, 0

    questions = validate_questions_cover_all_topics(
        questions, topics, project, project_title
    )

    skills = tech_stack_to_suggested_skills(topics, project)
    report = EvaluationReport(skills=questions, summary=summary)
    return skills, report, tokens


def new_analysis_id() -> str:
    return f"ana-{uuid.uuid4().hex[:12]}"
