# Project Working — How the System Operates

This document describes the **complete end-to-end working** of the Project Submission AI Analyzer with Proctored Live Viva.

---

## 1. Purpose

The system helps mentors evaluate student project submissions by:

1. Analyzing an uploaded project ZIP
2. Detecting the student's tech stack and relevant skills
3. Generating tailored viva questions
4. Running a live, proctored viva session
5. Producing a single evaluation package with integrity report

Everything is delivered as a **website** at `http://localhost:8000` (or your network IP for other devices).

---

## 2. High-Level Flow

```
Student uploads ZIP + metadata
        │
        ▼
[1] Safe ZIP extraction → file tree, dependencies, code snippets
        │
        ▼
[2] Tech stack detection → saved to output/tech_stacks/
        │
        ▼
[3] AI analysis (Google Gemini) or rule-based fallback
        │
        ▼
[4] Interview questions generated per skill
        │
        ▼
[5] Outcome evaluation against stated project outcomes
        │
        ▼
[6] LIVE VIVA — proctored on camera (client-side monitoring)
        │
        ▼
[7] Integrity report computed from proctoring events
        │
        ▼
[8] Combined JSON saved → evaluation + integrity log + tech stack reference
```

---

## 3. Step-by-Step Working

### Step 1 — Upload & Analyze (`POST /analyze-submission`)

The student (or mentor) fills the website form:

- Project title, description, outcomes
- ZIP file of the project
- Questions per skill (default: 2)

The backend:

1. **Safely extracts** the ZIP (rejects path traversal, caps size/file count)
2. **Builds** file tree, parses `requirements.txt` / `package.json` dependencies
3. **Detects uploaded project tech stack** — languages, frameworks, tools from files and deps
4. **Saves tech stack** to `output/tech_stacks/{analysis_id}_tech_stack.json`
5. **Runs AI analysis** via **Google Gemini** (or rule-based fallback if API key missing):
   - Detects viva topics from tech stack (2 questions per technology)
   - Generates conceptual + codebase-specific questions
   - Evaluates each stated outcome (met / partial / not_met / not_verifiable)
6. Returns `analysis_id` and full analysis JSON

### Step 2 — Start Viva (`POST /viva-session/start`)

Using the `analysis_id`, a live session is created:

- Returns `session_id` and all generated questions
- Initializes integrity log file at `output/proctoring_logs/{session_id}_integrity_log.json`
- Student must accept consent before camera monitoring begins

### Step 3 — Live Proctoring (`POST /viva-session/event`)

During the viva, the **browser** (not the server) monitors:

| Condition | How detected | Event sent |
|-----------|--------------|------------|
| Identity check | MediaPipe face landmarks | `id_verified` / `id_failed` |
| Gaze off screen | Eye landmark offset | `gaze_off_screen` |
| No face visible | No landmarks | `face_not_detected` |
| Multiple faces | >1 face detected | `multiple_faces_detected` |
| Tab switch | Page Visibility API | `tab_switched` |
| Left fullscreen | Fullscreen API | `fullscreen_exited` |
| Paste during answer | Clipboard event | `paste_attempted` |
| Screenshot attempt | PrintScreen key | `screenshot_detected` |
| Heartbeat | Periodic timer | `snapshot_captured` |

**Privacy:** Raw video never leaves the browser. Only lightweight JSON events are sent to the server.

Each event is **immediately saved** to the integrity log file, grouped by condition type.

### Step 4 — End Viva (`POST /viva-session/end`)

When the student finishes answering:

1. Server computes **integrity score** (0–1) and **risk level** (low/medium/high)
2. Merges technical evaluation + proctoring report
3. **Saves files:**
   - `output/evaluations/{session_id}_evaluation.json` — full combined package
   - Finalizes `output/proctoring_logs/{session_id}_integrity_log.json`
   - References `output/tech_stacks/{analysis_id}_tech_stack.json` from upload

---

## 4. Output Files

| File | When created | Contents |
|------|--------------|----------|
| `output/tech_stacks/{analysis_id}_tech_stack.json` | After ZIP upload/analysis | **Uploaded project's** languages, frameworks, dependencies, file tree |
| `output/proctoring_logs/{session_id}_integrity_log.json` | During + after viva | All integrity events: tab switches, gaze, paste, etc. |
| `output/evaluations/{session_id}_evaluation.json` | After viva ends | Skills, questions, outcome evaluation, proctoring report |

---

## 5. API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Website UI |
| `/analyze-submission` | POST | Upload ZIP, analyze, detect tech stack |
| `/viva-session/start` | POST | Begin proctored session |
| `/viva-session/event` | POST | Post integrity event |
| `/viva-session/end` | POST | End session, save final JSON |
| `/health` | GET | Server health check |
| `/network-info` | GET | Network URL for other devices |
| `/docs` | GET | API documentation |

---

## 6. Network Access

The server binds to `0.0.0.0:8000` so other devices on the same Wi-Fi can access it.

- This PC: `http://localhost:8000`
- Other devices: `http://<your-ip>:8000` (shown on homepage and `/network-info`)

---

## 7. AI Engine

- **Primary:** Google Gemini API (`gemini-2.0-flash` by default) — analysis, question generation, outcome evaluation, answer grading
- **Fallback:** Rule-based analyzer when `GEMINI_API_KEY` is missing or Gemini is unreachable — still produces valid questions and outcomes from ZIP evidence

Set in `backend/.env`:

```env
GEMINI_API_KEY=your_key_from_https://aistudio.google.com/apikey
GEMINI_MODEL=gemini-2.0-flash
```

---

## 8. Integrity Scoring

Starting score: 1.0. Deductions per flag based on severity:

- **Low** (e.g. brief gaze away): small deduction
- **Medium** (e.g. tab switch): moderate deduction
- **High** (e.g. paste, connection lost): large deduction

Thresholds are configurable in `backend/.env` (`GAZE_LOW_SEC`, `CONNECTION_TIMEOUT_SEC`, etc.).

---

## 9. How to Run

```powershell
.\start.ps1
```

Then open http://localhost:8000, upload a ZIP, analyze, start viva, complete questions, and check `output/` for saved files.

---

## 10. Demo Flow for Video

1. Start server → show website
2. Upload `demo_zip/fastapi-todo.zip` → analyze
3. Show tech stack file in `output/tech_stacks/`
4. Start proctored viva → consent → identity check → answer questions
5. Deliberately trigger a flag (look away or switch tab)
6. Finish viva → show final JSON and integrity log in `output/`
