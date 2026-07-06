"""Grade viva answers for relevance and correctness."""

from __future__ import annotations

import json
import re
from typing import Any

from app.models.schemas import (
    AnswerGrade,
    QuestionType,
    VivaAnswerSubmission,
    VivaGradingReport,
)
from app.services.gemini_client import GeminiClient
from app.services.zip_extractor import build_snippet_context
from app.services.zip_extractor import ExtractedProject

GRADE_BANDS = [
    (0.85, "excellent"),
    (0.70, "good"),
    (0.50, "partial"),
    (0.25, "poor"),
    (0.0, "insufficient"),
]


def _letter_grade(score: float) -> str:
    for threshold, label in GRADE_BANDS:
        if score >= threshold:
            return label
    return "insufficient"


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    stop = {"the", "and", "for", "that", "this", "with", "from", "your", "about", "what", "how"}
    return {w for w in words if w not in stop}


def _rule_grade_answer(
    answer: VivaAnswerSubmission,
    project_title: str,
) -> AnswerGrade:
    text = (answer.answer_text or "").strip()
    q_words = _keywords(answer.question_text)
    topic_words = _keywords(answer.skill_name)

    if not text:
        return AnswerGrade(
            skill_name=answer.skill_name,
            question_type=answer.question_type,
            question_text=answer.question_text,
            answer_text=text,
            relevance_score=0.0,
            correctness_score=0.0,
            score=0.0,
            grade="no_answer",
            feedback="No answer provided.",
        )

    if len(text) < 15:
        return AnswerGrade(
            skill_name=answer.skill_name,
            question_type=answer.question_type,
            question_text=answer.question_text,
            answer_text=text,
            relevance_score=0.2,
            correctness_score=0.1,
            score=0.15,
            grade="insufficient",
            feedback="Answer is too brief to demonstrate understanding.",
        )

    a_words = _keywords(text)
    overlap_q = len(a_words & q_words) / max(len(q_words), 1)
    overlap_topic = len(a_words & topic_words) / max(len(topic_words), 1)
    relevance = min(1.0, 0.35 + overlap_q * 0.35 + overlap_topic * 0.35)

    correctness = min(1.0, 0.25 + min(len(text) / 200, 1.0) * 0.35)

    if answer.question_type == QuestionType.CODEBASE_SPECIFIC and answer.reference:
        ref_base = answer.reference.split("::")[0].split("/")[-1].lower()
        ref_tokens = [t for t in re.split(r"[/_.]", answer.reference.lower()) if len(t) > 2]
        mentions_ref = ref_base in text.lower() or any(t in text.lower() for t in ref_tokens)
        if mentions_ref:
            correctness = min(1.0, correctness + 0.25)
            relevance = min(1.0, relevance + 0.15)
        else:
            correctness = max(0.2, correctness - 0.15)
            relevance = max(0.2, relevance - 0.1)

    if answer.question_type == QuestionType.CONCEPTUAL:
        if len(text) >= 80 and overlap_topic >= 0.3:
            correctness = min(1.0, correctness + 0.25)
        if any(w in text.lower() for w in ("because", "used for", "purpose", "allows", "enables")):
            correctness = min(1.0, correctness + 0.1)

    score = round((relevance * 0.4 + correctness * 0.6), 2)
    grade = _letter_grade(score)

    if score >= 0.85:
        feedback = "Strong, relevant answer that addresses the question well."
    elif score >= 0.70:
        feedback = "Good answer with relevant points; minor gaps may exist."
    elif score >= 0.50:
        feedback = "Partially relevant; expand with more specific detail."
    elif score >= 0.25:
        feedback = "Limited relevance or depth; answer does not fully address the question."
    else:
        feedback = "Answer lacks sufficient relevance or correctness."

    return AnswerGrade(
        skill_name=answer.skill_name,
        question_type=answer.question_type,
        question_text=answer.question_text,
        answer_text=text,
        relevance_score=round(relevance, 2),
        correctness_score=round(correctness, 2),
        score=score,
        grade=grade,
        feedback=feedback,
    )


async def _gemini_grade_answers(
    answers: list[VivaAnswerSubmission],
    snippet_context: str,
    project_title: str,
) -> list[AnswerGrade] | None:
    client = GeminiClient()
    if not await client.check_health():
        return None

    payload = [a.model_dump() for a in answers]
    system = "You grade student viva answers. Respond ONLY with valid JSON."
    user = f"""Project: {project_title}

Codebase context:
{snippet_context[:4000]}

Answers to grade:
{json.dumps(payload, indent=2)}

For each answer score:
- relevance_score (0-1): does the answer address the question?
- correctness_score (0-1): is it technically accurate for this project?
- score (0-1): overall weighted quality
- grade: excellent|good|partial|poor|insufficient|no_answer
- feedback: one sentence for mentor

Return JSON:
{{
  "grades": [
    {{
      "skill_name": "...",
      "question_type": "conceptual|codebase_specific",
      "question_text": "...",
      "answer_text": "...",
      "relevance_score": 0.8,
      "correctness_score": 0.75,
      "score": 0.77,
      "grade": "good",
      "feedback": "..."
    }}
  ]
}}
"""
    try:
        data = await client.generate_json(system, user, retry=True)
    except Exception:
        return None

    grades: list[AnswerGrade] = []
    for item in data.get("grades", []):
        try:
            qtype = QuestionType(item.get("question_type", "conceptual"))
        except ValueError:
            qtype = QuestionType.CONCEPTUAL
        grades.append(
            AnswerGrade(
                skill_name=str(item.get("skill_name", "")),
                question_type=qtype,
                question_text=str(item.get("question_text", "")),
                answer_text=str(item.get("answer_text", "")),
                relevance_score=min(1.0, max(0.0, float(item.get("relevance_score", 0)))),
                correctness_score=min(1.0, max(0.0, float(item.get("correctness_score", 0)))),
                score=min(1.0, max(0.0, float(item.get("score", 0)))),
                grade=str(item.get("grade", "partial")),
                feedback=str(item.get("feedback", "")),
            )
        )
    return grades if grades else None


async def grade_viva_answers(
    answers: list[VivaAnswerSubmission],
    project_title: str,
    project_snippets: dict[str, str] | None = None,
) -> VivaGradingReport:
    if not answers:
        return VivaGradingReport(
            answer_grades=[],
            overall_viva_score=0.0,
            overall_exam_score=0.0,
            answers_graded=0,
            narrative="No answers were submitted for grading.",
        )

    grades: list[AnswerGrade] | None = None
    if project_snippets:
        fake_project = ExtractedProject(snippets=project_snippets)
        context = build_snippet_context(fake_project, max_chars=4000)
        grades = await _gemini_grade_answers(answers, context, project_title)

    if not grades or len(grades) != len(answers):
        grades = [_rule_grade_answer(a, project_title) for a in answers]

    overall = round(sum(g.score for g in grades) / len(grades), 2)
    excellent = sum(1 for g in grades if g.score >= 0.85)
    partial = sum(1 for g in grades if g.score < 0.5)

    narrative = (
        f"Graded {len(grades)} answers for {project_title}. "
        f"Overall viva score: {overall:.2f}. "
        f"{excellent} excellent/good answers, {partial} below partial threshold."
    )

    return VivaGradingReport(
        answer_grades=grades,
        overall_viva_score=overall,
        overall_exam_score=overall,
        answers_graded=len(grades),
        narrative=narrative,
    )
