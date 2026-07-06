"""Generate exactly 2 viva questions per tech-stack topic: 1 general + 1 project-specific."""

from __future__ import annotations

import random
import re
import uuid
from typing import Any

from app.models.schemas import Question, QuestionType, SkillQuestions, SuggestedSkill
from app.services.zip_extractor import ExtractedProject

PACKAGE_DISPLAY_NAMES: dict[str, str] = {
    "numpy": "NumPy",
    "pandas": "Pandas",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "pydantic": "Pydantic",
    "uvicorn": "Uvicorn",
    "react": "React",
    "express": "Express.js",
    "sqlalchemy": "SQLAlchemy",
    "psycopg2": "PostgreSQL",
    "psycopg": "PostgreSQL",
    "pytest": "pytest",
    "tensorflow": "TensorFlow",
    "torch": "PyTorch",
    "sklearn": "scikit-learn",
    "scikit-learn": "scikit-learn",
}


SKIP_PACKAGES = {
    "pip", "setuptools", "wheel", "idna", "certifi", "charset-normalizer",
    "urllib3", "httpcore", "anyio", "h11", "click", "starlette", "sniffio",
    "typing-extensions", "typing_extensions", "annotated-types", "colorama",
    "python-dotenv", "httpx", "httptools", "watchfiles", "websockets",
    "pyyaml", "pluggy", "iniconfig", "packaging", "pygments", "tomli",
}

TOPIC_ALIASES: dict[str, str] = {
    "psycopg2": "PostgreSQL",
    "psycopg2-binary": "PostgreSQL",
    "psycopg": "PostgreSQL",
    "postgres": "PostgreSQL",
    "pytorch": "PyTorch",
    "scikit_learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "js": "JavaScript",
    "ts": "TypeScript",
}


def extract_viva_topics(tech_stack: dict[str, Any]) -> list[str]:
    """Every language, framework, tool, and meaningful dependency from the uploaded project."""
    if tech_stack.get("viva_topics"):
        return list(tech_stack["viva_topics"])

    topics: list[str] = []
    seen: set[str] = set()

    def canonical(name: str) -> str:
        key = name.lower().strip().replace("_", "-")
        if key in TOPIC_ALIASES:
            return TOPIC_ALIASES[key]
        if key in PACKAGE_DISPLAY_NAMES:
            return PACKAGE_DISPLAY_NAMES[key]
        return name.strip()

    def add(name: str) -> None:
        display = canonical(name)
        key = display.lower()
        if not key or key in seen:
            return
        seen.add(key)
        topics.append(display)

    for key in ("languages", "frameworks", "tools"):
        for item in tech_stack.get(key, []):
            add(str(item))

    for dep in tech_stack.get("dependencies", []):
        pkg = re.split(r"[<>=!~\[]", dep.strip())[0].strip().lower()
        if not pkg or pkg in SKIP_PACKAGES:
            continue
        display = PACKAGE_DISPLAY_NAMES.get(pkg, pkg.replace("-", " ").title())
        add(display)

    return topics


def _find_evidence(topic: str, project: ExtractedProject) -> tuple[str, str]:
    needles = [
        topic.lower(),
        topic.lower().replace(" ", ""),
        topic.lower().replace(".js", ""),
    ]
    for path, content in project.snippets.items():
        combined = f"{path} {content}".lower()
        if any(n in combined for n in needles if n):
            return path, content[:300]

    for dep in project.dependencies:
        if any(n in dep.lower() for n in needles if n):
            return "requirements.txt", dep

    if project.file_tree:
        return project.file_tree[0], ""
    return "project", ""


def _topic_to_skill_id(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return f"tech-{slug or uuid.uuid4().hex[:8]}"


# Variation pools so the same upload never gets identical questions twice
_CONCEPTUAL_TEMPLATES = [
    "What is {topic} and what core problem does it solve? Explain its main features.",
    "Describe {topic}: its purpose, key concepts, and when you would choose it over alternatives.",
    "How does {topic} work under the hood? Explain its architecture and core design principles.",
    "What are the strengths and limitations of {topic}? When would you avoid using it?",
    "Walk me through the fundamental concepts of {topic} that every developer using it must understand.",
    "Compare {topic} to at least one alternative. What makes it the right tool for your use case?",
    "What problem does {topic} solve that would be tedious to handle without it?",
    "Explain {topic} to someone who has never used it. What is its purpose and how does it work?",
]

_CODEBASE_TEMPLATES = [
    (
        "In '{project_title}', where exactly did you use {topic}? Open {ref_path} and walk me through "
        "the implementation — what does it do and why did you structure it that way?"
    ),
    (
        "Look at {ref_path} in your project. How did you integrate {topic} there, "
        "and what would break if you removed it?"
    ),
    (
        "In '{project_title}', what specific feature relies on {topic}? "
        "Trace the code flow in {ref_path} and explain each step."
    ),
    (
        "What design decision did you make when using {topic} in {ref_path}? "
        "Was there an alternative approach you considered?"
    ),
    (
        "Point me to the most important part of your {topic} usage in '{project_title}'. "
        "Explain what that code in {ref_path} does and why it is written that way."
    ),
    (
        "If I reviewed {ref_path}, what would I find related to {topic}? "
        "Explain the implementation and any edge cases you handled."
    ),
    (
        "How did you configure or initialize {topic} in '{project_title}'? "
        "Walk through {ref_path} and explain each key setting or call."
    ),
    (
        "What would you change about your {topic} implementation in {ref_path} "
        "if you had more time? What works well and what are the trade-offs?"
    ),
]


def _pick_conceptual(topic: str) -> str:
    template = random.choice(_CONCEPTUAL_TEMPLATES)
    return template.format(topic=topic)


def _pick_codebase(topic: str, project_title: str, ref_path: str) -> str:
    template = random.choice(_CODEBASE_TEMPLATES)
    return template.format(topic=topic, project_title=project_title, ref_path=ref_path)


def build_questions_for_topics(
    topics: list[str],
    project: ExtractedProject,
    project_title: str,
) -> list[SkillQuestions]:
    """Exactly 2 questions per topic: conceptual (general) + codebase_specific (project).
    Templates are randomly varied so the same project upload always gets fresh questions."""
    result: list[SkillQuestions] = []

    for topic in topics:
        ref_path, _ = _find_evidence(topic, project)
        result.append(
            SkillQuestions(
                skill_id=_topic_to_skill_id(topic),
                skill_name=topic,
                questions=[
                    Question(
                        question_type=QuestionType.CONCEPTUAL,
                        text=_pick_conceptual(topic),
                        reference=None,
                    ),
                    Question(
                        question_type=QuestionType.CODEBASE_SPECIFIC,
                        text=_pick_codebase(topic, project_title, ref_path),
                        reference=ref_path,
                    ),
                ],
            )
        )

    return result


def tech_stack_to_suggested_skills(
    topics: list[str],
    project: ExtractedProject,
) -> list[SuggestedSkill]:
    skills: list[SuggestedSkill] = []
    for topic in topics:
        ref_path, snippet = _find_evidence(topic, project)
        rationale = (
            f"Detected in {ref_path}"
            if ref_path != "project"
            else f"Part of uploaded project tech stack"
        )
        if snippet:
            rationale += f" — {snippet[:80].strip()}..."
        skills.append(
            SuggestedSkill(
                skill_id=_topic_to_skill_id(topic),
                skill_name=topic,
                confidence=0.85,
                rationale=rationale,
            )
        )
    return skills


def _normalize_topic_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _lookup_skill_questions(
    by_name: dict[str, SkillQuestions],
    topic: str,
) -> SkillQuestions | None:
    direct = by_name.get(topic.lower())
    if direct:
        return direct
    norm = _normalize_topic_key(topic)
    for sq in by_name.values():
        if _normalize_topic_key(sq.skill_name) == norm:
            return sq
    return None


def ensure_all_topics_covered(
    questions: list[SkillQuestions],
    topics: list[str],
    project: ExtractedProject,
    project_title: str,
) -> list[SkillQuestions]:
    """Guarantee exactly one skill block with 2 questions for every tech-stack topic, in order."""
    by_name: dict[str, SkillQuestions] = {}
    for q in questions:
        by_name[q.skill_name.lower()] = q

    result: list[SkillQuestions] = []
    for topic in topics:
        existing = _lookup_skill_questions(by_name, topic)
        if existing and len(existing.questions) >= 2:
            conceptual = next(
                (x for x in existing.questions if x.question_type == QuestionType.CONCEPTUAL),
                None,
            )
            codebase = next(
                (x for x in existing.questions if x.question_type == QuestionType.CODEBASE_SPECIFIC),
                None,
            )
            ref_path, _ = _find_evidence(topic, project)
            result.append(
                SkillQuestions(
                    skill_id=existing.skill_id or _topic_to_skill_id(topic),
                    skill_name=topic,
                    questions=[
                        conceptual or Question(
                            question_type=QuestionType.CONCEPTUAL,
                            text=f"What is {topic} in general? Explain its purpose and typical use cases.",
                            reference=None,
                        ),
                        codebase or Question(
                            question_type=QuestionType.CODEBASE_SPECIFIC,
                            text=f"Where did you use {topic} in '{project_title}'? Explain that part of your code.",
                            reference=ref_path,
                        ),
                    ],
                )
            )
        else:
            result.extend(build_questions_for_topics([topic], project, project_title))

    return result


# Backward-compatible aliases
ensure_two_questions_per_topic = ensure_all_topics_covered


def validate_questions_cover_all_topics(
    questions: list[SkillQuestions],
    topics: list[str],
    project: ExtractedProject,
    project_title: str,
) -> list[SkillQuestions]:
    """Final gate: every tech-stack topic must appear exactly once with 2 questions."""
    covered = ensure_all_topics_covered(questions, topics, project, project_title)
    if len(covered) != len(topics):
        return build_questions_for_topics(topics, project, project_title)
    names = [_normalize_topic_key(sq.skill_name) for sq in covered]
    expected = [_normalize_topic_key(t) for t in topics]
    if names != expected:
        return build_questions_for_topics(topics, project, project_title)
    return covered
