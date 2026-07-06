# Project Submission AI Analyzer with Proctored Live Viva

A web app for student project evaluation: upload a ZIP, detect tech stack, generate viva questions (2 per technology), and run a **proctored live viva** with browser-based monitoring. Uses **Google Gemini API** for analysis and grading (free tier available).

---

## Deliverables Checklist

| # | Deliverable | Location |
|---|-------------|----------|
| 6 | Runnable project (one command start) | `start.ps1` / `start.sh` |
| 7 | README (this file) | setup, env, structure, tests, API examples |
| 8 | Demo test ZIP (5–15 source files) | `demo_zip/fastapi-todo.zip` |
| 9 | Unit tests (2+ required) | `backend/tests/` — **20 tests** |
| 10 | Privacy write-up | [NOTES.md](NOTES.md) |

**Demo video:** add your link in the [Demo Video](#demo-video) section below before submission.

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Google Gemini API key** (free tier): https://aistudio.google.com/apikey

Add your key to `backend/.env`:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash
```

If the API key is missing or Gemini is unreachable, the backend uses a **rule-based fallback** analyzer automatically.

---

## Quick Start (one command)

Everything runs as a **single website** at http://localhost:8000 (API + UI).

### Windows

```powershell
.\start.ps1
```

### Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

The script will:

1. `npm install` + `npm run build` (frontend → `frontend/dist/`)
2. `pip install -r backend/requirements.txt`
3. Copy `backend/.env.example` → `backend/.env` if missing
4. Start uvicorn on `0.0.0.0:8000`

Open **http://localhost:8000** in your browser.

### Manual start

```bash
cd frontend && npm install && npm run build
cd ../backend
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Folder Structure

```
skillfirst project/
├── backend/
│   ├── app/
│   │   ├── api/              # POST /analyze-submission, /viva-session/*
│   │   ├── services/         # zip, gemini, analyzer, proctoring, grading
│   │   ├── models/           # Pydantic schemas
│   │   ├── data/             # skill_catalog.json
│   │   ├── config.py
│   │   └── main.py           # FastAPI + serves frontend/dist/
│   ├── tests/                # pytest (20 tests)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/                  # React + MediaPipe proctoring
│   └── dist/                 # Built site (served by FastAPI)
├── demo_zip/
│   ├── fastapi-todo/         # Sample project (9 source files)
│   └── fastapi-todo.zip      # Upload this for demo
├── output/
│   ├── tech_stacks/          # Detected tech stack JSON
│   ├── proctoring_logs/      # Integrity event logs
│   └── evaluations/          # Final exam JSON
├── start.ps1 / start.sh
├── README.md
├── NOTES.md                  # Privacy approach
└── PROJECT_WORKING.md        # End-to-end system flow
```

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *(required)* | Google AI Studio API key |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model for analysis & grading |
| `GAZE_LOW_SEC` | `1.0` | Seconds looking away before gaze flag |
| `GAZE_MEDIUM_SEC` | `3.5` | Longer gaze → higher severity |
| `FACE_NOT_DETECTED_SEC` | `5.0` | No face visible threshold |
| `CONNECTION_TIMEOUT_SEC` | `30.0` | Event gap → connection_lost |
| `RISK_LOW_MIN_SCORE` | `0.75` | Integrity score band |
| `RISK_MEDIUM_MIN_SCORE` | `0.50` | Integrity score band |
| `MAX_ZIP_FILES` | `200` | Max files extracted from ZIP |
| `MAX_ZIP_UNCOMPRESSED_BYTES` | `52428800` | Max uncompressed size (50 MB) |
| `CORS_ORIGINS` | `*` | CORS allowed origins |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |

---

## Demo ZIP

**File:** `demo_zip/fastapi-todo.zip` (9 source files — FastAPI Todo CRUD)

Contents:

- `app/main.py`, `app/models.py`, `app/database.py`
- `app/routes/todos.py`
- `requirements.txt`, `README.md`
- `tests/test_todos.py`

Upload via the web UI or the curl example below.

---

## API Examples

### Health check

```bash
curl http://localhost:8000/health
```

### POST /analyze-submission

Upload a project ZIP and get analysis + viva questions:

```bash
curl -X POST http://localhost:8000/analyze-submission \
  -F "project_title=FastAPI Todo CRUD" \
  -F "project_description=A REST API for managing todo items" \
  -F "project_outcomes=1. Build REST API with CRUD endpoints
2. Use Python and FastAPI
3. Validate with Pydantic
4. Structure code into modules" \
  -F "questions_per_skill=2" \
  -F "zip_file=@demo_zip/fastapi-todo.zip"
```

**Response (abbreviated):**

```json
{
  "analysis_id": "ana-abc123def456",
  "project_title": "FastAPI Todo CRUD",
  "suggested_skills": [...],
  "evaluation_report": {
    "skills": [
      {
        "skill_name": "Python",
        "questions": [
          { "question_type": "conceptual", "text": "..." },
          { "question_type": "codebase_specific", "text": "...", "reference": "app/main.py" }
        ]
      }
    ]
  },
  "saved_files": {
    "uploaded_project_tech_stack": "D:\\...\\output\\tech_stacks\\fastapi-todo-crud__ana-abc123__tech_stack.json"
  }
}
```

Save `analysis_id` for the viva flow.

### Viva session flow

```bash
# 1. Start proctored session
curl -X POST http://localhost:8000/viva-session/start \
  -H "Content-Type: application/json" \
  -d '{"analysis_id": "ana-abc123def456"}'

# Response: session_id, questions[], proctoring config

# 2. Post integrity events during viva (from browser or manual test)
curl -X POST http://localhost:8000/viva-session/event \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess-xyz789",
    "event_type": "interview_started",
    "timestamp": "2026-07-05T10:00:00Z",
    "confidence": 1.0
  }'

curl -X POST http://localhost:8000/viva-session/event \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess-xyz789",
    "event_type": "gaze_off_screen",
    "timestamp": "2026-07-05T10:01:30Z",
    "duration_ms": 2100,
    "confidence": 0.85
  }'

# 3. End session — grades answers + proctoring, saves JSON
curl -X POST http://localhost:8000/viva-session/end \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess-xyz789",
    "answers": [
      {
        "skill_name": "Python",
        "question_type": "conceptual",
        "question_text": "What is Python?",
        "reference": null,
        "answer_text": "Python is a high-level programming language..."
      }
    ]
  }'
```

**End response** includes `viva_grading_report`, `proctoring_report`, and `saved_files` paths under `output/evaluations/` and `output/proctoring_logs/`.

For the full flow with camera, gaze calibration, and fullscreen, use the **website** at http://localhost:8000.

---

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

**20 tests** across:

| File | What it covers |
|------|----------------|
| `test_zip_security.py` | Path-traversal ZIP rejected; valid ZIP extracts |
| `test_proctoring_schema.py` | Event schema validation; integrity scoring; combined output schema |
| `test_tech_stack.py` | Tech stack detection; 2 questions per topic |
| `test_file_storage.py` | Output file naming |
| `test_answer_grading.py` | Answer grading logic |
| `test_gaze_proctoring.py` | Gaze/fullscreen severity rules |

---

## Saved Output Files

| File pattern | When |
|--------------|------|
| `output/tech_stacks/{slug}__{analysis_id}__tech_stack.json` | After ZIP analysis |
| `output/proctoring_logs/{slug}__{session_id}__{analysis_id}__proctoring_log.json` | During/after viva |
| `output/evaluations/{slug}__{session_id}__{analysis_id}__viva_evaluation.json` | After viva ends |

---

## Proctoring Events

| Event | Trigger |
|-------|---------|
| `interview_started` | Viva begins |
| `id_verified` / `id_failed` | Face identity check |
| `gaze_off_screen` | Calibrated iris/blendshape gaze away |
| `face_not_detected` | No face for > N seconds |
| `multiple_faces_detected` | More than one face |
| `secondary_device_detected` | Phone/laptop in camera (MediaPipe object detector) |
| `camera_changed` | Webcam source switched |
| `camera_disconnected` | Camera stopped/unplugged |
| `tab_switched` | Page hidden (Visibility API) |
| `fullscreen_exited` | Left fullscreen during exam |
| `paste_attempted` | Paste blocked in answer field |
| `screenshot_detected` | Screenshot shortcut detected |
| `snapshot_captured` | Heartbeat (no image data) |
| `connection_lost` | Event stream gap |

---

## Demo Video

> **Add your demo video link here before submission** (Google Drive / OneDrive with view access).
>
> Example: `https://drive.google.com/file/d/YOUR_FILE_ID/view?usp=sharing`
>
> Suggested recording: upload demo ZIP → analyze → start viva → answer 1–2 questions → show proctoring alert → submit → show evaluation JSON.

---

## Privacy

See **[NOTES.md](NOTES.md)** for the proctoring privacy approach (signals, not surveillance).

---

## Tech Stack (all free)

| Layer | Tools |
|-------|-------|
| Backend | FastAPI, Pydantic, httpx |
| LLM | **Google Gemini API** + rule-based fallback |
| Frontend | React, Vite, MediaPipe Face Landmarker + Object Detector |
| Proctoring | Client-side only; JSON events to server |

---

## License

Academic / project submission use.
