import io
import zipfile

import pytest

from app.services.zip_extractor import ZipSecurityError, extract_zip


def _make_zip(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_path_traversal_rejected():
    data = _make_zip({"../../etc/passwd": "evil"})
    with pytest.raises(ZipSecurityError, match="Unsafe path"):
        extract_zip(data)


def test_valid_zip_extracts():
    data = _make_zip({
        "app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
        "requirements.txt": "fastapi>=0.100.0\n",
        "README.md": "# Demo project\n",
    })
    result = extract_zip(data)
    assert result.files_analyzed >= 1
    assert "app/main.py" in result.file_tree
    assert any("fastapi" in d for d in result.dependencies)
