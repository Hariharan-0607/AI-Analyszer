"""Detect the tech stack of an uploaded student project from ZIP contents."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import PurePosixPath

from app.services.question_generator import extract_viva_topics
from app.services.zip_extractor import ExtractedProject

EXT_TO_LANGUAGE = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cpp": "C++",
    ".c": "C",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".vue": "Vue",
    ".kt": "Kotlin",
    ".swift": "Swift",
}

DEP_FRAMEWORK_PATTERNS: list[tuple[str, str]] = [
    (r"fastapi", "FastAPI"),
    (r"flask", "Flask"),
    (r"django", "Django"),
    (r"uvicorn", "Uvicorn"),
    (r"react", "React"),
    (r"vue", "Vue.js"),
    (r"angular", "Angular"),
    (r"express", "Express.js"),
    (r"next", "Next.js"),
    (r"postgresql|psycopg|postgres", "PostgreSQL"),
    (r"mysql|pymysql", "MySQL"),
    (r"mongodb|pymongo", "MongoDB"),
    (r"sqlalchemy", "SQLAlchemy"),
    (r"redis", "Redis"),
    (r"docker", "Docker"),
    (r"pytest|unittest", "Unit Testing"),
    (r"jest|vitest|mocha", "JavaScript Testing"),
    (r"pydantic", "Pydantic"),
    (r"tensorflow", "TensorFlow"),
    (r"torch|pytorch", "PyTorch"),
    (r"sklearn|scikit-learn", "scikit-learn"),
    (r"numpy", "NumPy"),
    (r"pandas", "Pandas"),
    (r"tailwind", "Tailwind CSS"),
    (r"bootstrap", "Bootstrap"),
]

CODE_FRAMEWORK_PATTERNS: list[tuple[str, str]] = [
    (r"from fastapi|import fastapi|APIRouter", "FastAPI"),
    (r"from flask|Flask\(", "Flask"),
    (r"from django", "Django"),
    (r"from react|import React|useState|useEffect", "React"),
    (r"express\(\)|require\(['\"]express", "Express.js"),
    (r"@Entity|JpaRepository", "Spring / JPA"),
    (r"prisma", "Prisma ORM"),
]


def _detect_languages(project: ExtractedProject) -> list[str]:
    counts: Counter[str] = Counter()
    for path in project.file_tree:
        ext = PurePosixPath(path).suffix.lower()
        lang = EXT_TO_LANGUAGE.get(ext)
        if lang:
            counts[lang] += 1
    return [lang for lang, _ in counts.most_common()]


def _detect_frameworks(project: ExtractedProject) -> list[str]:
    found: set[str] = set()
    blob = " ".join(project.dependencies).lower()
    for path, content in project.snippets.items():
        blob += f" {path} {content}".lower()

    for pattern, name in DEP_FRAMEWORK_PATTERNS + CODE_FRAMEWORK_PATTERNS:
        if re.search(pattern, blob, re.IGNORECASE):
            found.add(name)

    return sorted(found)


def _detect_tools(project: ExtractedProject) -> list[str]:
    tools: list[str] = []
    names = {PurePosixPath(p).name.lower() for p in project.file_tree}
    if "dockerfile" in names or any("docker-compose" in n for n in names):
        tools.append("Docker")
    if ".gitignore" in names:
        tools.append("Git")
    if "makefile" in names:
        tools.append("Make")
    if any(n.endswith(".github") or "/.github/" in p for p, n in [(p, p) for p in project.file_tree]):
        tools.append("GitHub Actions / CI")
    if "pytest.ini" in names or "tox.ini" in names:
        tools.append("pytest")
    return tools


def _extension_summary(project: ExtractedProject) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for path in project.file_tree:
        ext = PurePosixPath(path).suffix.lower() or "(no ext)"
        counts[ext] += 1
    return dict(counts.most_common())


def _config_files(project: ExtractedProject) -> list[str]:
    known = {
        "requirements.txt", "package.json", "package-lock.json", "pyproject.toml",
        "pom.xml", "build.gradle", "go.mod", "cargo.toml", "dockerfile",
        "docker-compose.yml", "docker-compose.yaml", ".env.example", "readme.md",
    }
    return sorted(
        p for p in project.file_tree
        if PurePosixPath(p).name.lower() in known
    )


def detect_project_tech_stack(
    project: ExtractedProject,
    project_title: str,
    analysis_id: str,
) -> dict:
    languages = _detect_languages(project)
    frameworks = _detect_frameworks(project)
    tools = _detect_tools(project)

    stack_base = {
        "languages": languages,
        "frameworks": frameworks,
        "tools": tools,
        "dependencies": project.dependencies,
    }
    topics = extract_viva_topics(stack_base)

    return {
        "analysis_id": analysis_id,
        "project_title": project_title,
        "languages": languages,
        "frameworks": frameworks,
        "tools": tools,
        "viva_topics": topics,
        "dependencies": project.dependencies,
        "config_files": _config_files(project),
        "file_extension_counts": _extension_summary(project),
        "total_source_files": project.files_analyzed,
        "file_tree": project.file_tree,
        "summary": (
            f"{project_title} uses {', '.join(languages) or 'unknown languages'}"
            + (f" with {', '.join(frameworks)}" if frameworks else "")
            + f". {project.files_analyzed} source files analyzed."
        ),
    }
