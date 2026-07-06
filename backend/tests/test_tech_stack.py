import io
import zipfile

import pytest

from app.services.tech_stack_detector import detect_project_tech_stack
from app.services.zip_extractor import extract_zip


def _make_zip(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_detect_fastapi_project_tech_stack():
    data = _make_zip({
        "app/main.py": "from fastapi import FastAPI\nfrom pydantic import BaseModel\napp = FastAPI()\n",
        "requirements.txt": "fastapi>=0.109.0\nuvicorn>=0.27.0\npydantic>=2.5.0\n",
    })
    project = extract_zip(data)
    stack = detect_project_tech_stack(project, "Todo API", "ana-test123")

    from app.services.question_generator import extract_viva_topics

    topics = extract_viva_topics(stack)

    assert "Python" in stack["languages"]
    assert "FastAPI" in stack["frameworks"]
    assert any("fastapi" in d.lower() for d in stack["dependencies"])
    assert stack["analysis_id"] == "ana-test123"
    assert "Python" in topics
    assert "FastAPI" in topics
    assert "Pydantic" in topics
    assert "Uvicorn" in topics
    assert len(stack["viva_topics"]) == len(topics)


def test_two_questions_per_tech_topic():
    data = _make_zip({
        "app/main.py": "from fastapi import FastAPI\nfrom pydantic import BaseModel\napp = FastAPI()\n",
        "requirements.txt": "fastapi>=0.109.0\npydantic>=2.5.0\nuvicorn>=0.27.0\n",
    })
    project = extract_zip(data)
    stack = detect_project_tech_stack(project, "Todo API", "ana-test123")

    from app.services.question_generator import build_questions_for_topics, extract_viva_topics

    topics = extract_viva_topics(stack)
    questions = build_questions_for_topics(topics, project, "Todo API")
    assert len(questions) == len(topics)
    assert {sq.skill_name for sq in questions} == set(topics)
    for sq in questions:
        assert len(sq.questions) == 2
        types = {q.question_type.value for q in sq.questions}
        assert "conceptual" in types
        assert "codebase_specific" in types


def test_ensure_all_topics_covered_fills_missing_llm_topics():
    from app.services.question_generator import ensure_all_topics_covered, extract_viva_topics

    data = _make_zip({
        "app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
        "requirements.txt": "fastapi>=0.109.0\npydantic>=2.5.0\n",
    })
    project = extract_zip(data)
    stack = detect_project_tech_stack(project, "Todo API", "ana-test123")
    topics = extract_viva_topics(stack)

    # LLM only returned FastAPI — other topics must still be filled in
    from app.models.schemas import Question, QuestionType, SkillQuestions

    partial = [
        SkillQuestions(
            skill_id="tech-fastapi",
            skill_name="FastAPI",
            questions=[
                Question(question_type=QuestionType.CONCEPTUAL, text="What is FastAPI?", reference=None),
                Question(
                    question_type=QuestionType.CODEBASE_SPECIFIC,
                    text="How did you use FastAPI?",
                    reference="app/main.py",
                ),
            ],
        )
    ]
    covered = ensure_all_topics_covered(partial, topics, project, "Todo API")
    assert len(covered) == len(topics)
    assert {sq.skill_name for sq in covered} == set(topics)


def test_validate_questions_cover_all_topics_rebuilds_when_llm_skips():
    from app.services.question_generator import validate_questions_cover_all_topics

    data = _make_zip({
        "app/main.py": "from fastapi import FastAPI\nfrom pydantic import BaseModel\napp = FastAPI()\n",
        "requirements.txt": "fastapi>=0.109.0\npydantic>=2.5.0\nuvicorn>=0.27.0\n",
    })
    project = extract_zip(data)
    stack = detect_project_tech_stack(project, "Todo API", "ana-test123")
    topics = stack["viva_topics"]

    from app.models.schemas import Question, QuestionType, SkillQuestions

    partial = [
        SkillQuestions(
            skill_id="tech-fastapi",
            skill_name="FastAPI",
            questions=[
                Question(question_type=QuestionType.CONCEPTUAL, text="What is FastAPI?", reference=None),
                Question(
                    question_type=QuestionType.CODEBASE_SPECIFIC,
                    text="How did you use FastAPI?",
                    reference="app/main.py",
                ),
            ],
        )
    ]
    final = validate_questions_cover_all_topics(partial, topics, project, "Todo API")
    assert len(final) == len(topics)
    assert [sq.skill_name for sq in final] == topics
    for sq in final:
        assert len(sq.questions) == 2
