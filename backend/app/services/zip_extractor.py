from __future__ import annotations

import io
import os
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.config import get_settings

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
    ".cpp", ".c", ".h", ".cs", ".rb", ".php", ".sql", ".html",
    ".css", ".scss", ".vue", ".kt", ".swift", ".md",
}

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "coverage", ".pytest_cache",
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll", ".so",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3",
    ".pyc", ".pyo", ".class", ".jar", ".lock",
}


class ZipSecurityError(ValueError):
    pass


class EmptyProjectError(ValueError):
    pass


@dataclass
class ExtractedProject:
    file_tree: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    snippets: dict[str, str] = field(default_factory=dict)
    files_analyzed: int = 0
    extraction_time_ms: int = 0


def _is_safe_zip_path(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute():
        return False
    for part in path.parts:
        if part in ("..", ""):
            return False
        if part.startswith("/") or (len(part) > 1 and part[1] == ":"):
            return False
    return True


def _should_skip_path(rel_path: str) -> bool:
    parts = PurePosixPath(rel_path).parts
    for part in parts:
        if part in SKIP_DIRS:
            return True
    ext = PurePosixPath(rel_path).suffix.lower()
    if ext in SKIP_EXTENSIONS:
        return True
    return False


def _parse_requirements(content: str) -> list[str]:
    deps: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        deps.append(line.split("#")[0].strip())
    return deps


def _parse_package_json(content: str) -> list[str]:
    import json

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    deps: list[str] = []
    for key in ("dependencies", "devDependencies"):
        if key in data and isinstance(data[key], dict):
            deps.extend(f"{k}@{v}" for k, v in data[key].items())
    return deps


def extract_zip(zip_bytes: bytes) -> ExtractedProject:
    settings = get_settings()
    start = time.perf_counter()
    result = ExtractedProject()

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise ZipSecurityError("Invalid or corrupted ZIP file") from exc

    infos = zf.infolist()
    if not infos:
        raise EmptyProjectError("ZIP file is empty")

    if len(infos) > settings.max_zip_files:
        raise ZipSecurityError(f"ZIP exceeds maximum file count ({settings.max_zip_files})")

    total_size = sum(i.file_size for i in infos)
    if total_size > settings.max_zip_uncompressed_bytes:
        raise ZipSecurityError("ZIP exceeds maximum uncompressed size")

    safe_entries: list[tuple[str, zipfile.ZipInfo]] = []
    for info in infos:
        if info.is_dir():
            continue
        if not _is_safe_zip_path(info.filename):
            raise ZipSecurityError(f"Unsafe path in ZIP: {info.filename}")
        safe_entries.append((info.filename.replace("\\", "/"), info))

    if not safe_entries:
        raise EmptyProjectError("ZIP contains no files")

    for rel_path, info in safe_entries:
        if _should_skip_path(rel_path):
            continue
        result.file_tree.append(rel_path)

        ext = PurePosixPath(rel_path).suffix.lower()
        if ext not in CODE_EXTENSIONS:
            continue

        try:
            raw = zf.read(info)
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            continue

        if len(text.strip()) < 10:
            continue

        result.snippets[rel_path] = text[:2000]
        result.files_analyzed += 1

    for rel_path, info in safe_entries:
        base = os.path.basename(rel_path).lower()
        if base == "requirements.txt":
            try:
                content = zf.read(info).decode("utf-8", errors="replace")
                result.dependencies.extend(_parse_requirements(content))
            except Exception:
                pass
        elif base == "package.json":
            try:
                content = zf.read(info).decode("utf-8", errors="replace")
                result.dependencies.extend(_parse_package_json(content))
            except Exception:
                pass

    if result.files_analyzed == 0:
        raise EmptyProjectError("No analyzable source files found in ZIP")

    result.file_tree.sort()
    result.extraction_time_ms = int((time.perf_counter() - start) * 1000)
    return result


def build_snippet_context(project: ExtractedProject, max_chars: int | None = None) -> str:
    settings = get_settings()
    limit = max_chars or settings.max_snippet_chars
    parts: list[str] = []
    chars = 0

    if project.dependencies:
        parts.append("DEPENDENCIES:\n" + "\n".join(project.dependencies[:30]))
        chars += len(parts[-1])

    parts.append("\nFILE TREE:\n" + "\n".join(project.file_tree[:80]))
    chars += len(parts[-1])

    for path, content in sorted(project.snippets.items()):
        block = f"\n--- {path} ---\n{content}\n"
        if chars + len(block) > limit:
            remaining = limit - chars
            if remaining > 100:
                parts.append(block[:remaining])
            break
        parts.append(block)
        chars += len(block)

    return "".join(parts)


def project_from_snippets(snippets: dict[str, str]) -> ExtractedProject:
    """Rebuild minimal project context for question generation after analysis."""
    deps: list[str] = []
    req = snippets.get("requirements.txt") or snippets.get("package.json") or ""
    if req:
        for line in req.splitlines():
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#") and not cleaned.startswith("//"):
                deps.append(cleaned)
    return ExtractedProject(
        file_tree=sorted(snippets.keys()),
        dependencies=deps,
        snippets=snippets,
        files_analyzed=len(snippets),
    )
