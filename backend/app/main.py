from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import analyze, viva
from app.config import get_settings

settings = get_settings()

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

app = FastAPI(
    title="Project Submission AI Analyzer",
    description="Analyzes student project submissions and runs proctored live viva sessions.",
    version="1.0.0",
)

cors_origins = settings.cors_origin_list
allow_creds = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if "*" not in cors_origins else ["*"],
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router, tags=["analysis"])
app.include_router(viva.router, tags=["viva"])


@app.get("/health")
def health():
    return {"status": "ok"}


def _serve_spa():
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(
            status_code=503,
            detail="Website not built. Run: cd frontend && npm install && npm run build",
        )
    return FileResponse(index)


@app.get("/")
def serve_home():
    return _serve_spa()


if STATIC_DIR.is_dir():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{page_path:path}")
    def serve_website(page_path: str):
        file_path = STATIC_DIR / page_path
        if file_path.is_file():
            return FileResponse(file_path)
        return _serve_spa()
