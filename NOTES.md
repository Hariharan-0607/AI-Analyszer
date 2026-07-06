# Privacy Approach for Proctoring

## Summary

This project follows a **signals, not surveillance** design. Raw video and audio **never leave the student's browser**. All face, gaze, and object detection runs **client-side** using MediaPipe (WASM) in the browser on the local machine.

## What is sent to the server

**Proctoring:** Only lightweight integrity events (gaze, tab switch, etc.) — no video.

**Analysis & grading:** When Gemini is enabled, **code snippets and viva answers** from the uploaded ZIP are sent to Google's Gemini API for analysis and grading. Set `GEMINI_API_KEY` only on a trusted server; do not commit the key to git.

Integrity events include:

- `gaze_off_screen` — duration + confidence (no eye coordinates stored long-term in events)
- `face_not_detected`, `multiple_faces_detected`
- `secondary_device_detected` — label only (e.g. "cell phone"), not a cropped image
- `camera_changed`, `camera_disconnected`
- `tab_switched`, `fullscreen_exited`
- `paste_attempted`, `screenshot_detected`
- `snapshot_captured` — heartbeat only; **no image payload**

Each event includes `session_id`, `event_type`, ISO timestamp, and optional `duration_ms` / `confidence`. No frames, screenshots, biometric templates, or raw landmark arrays are transmitted.

## What stays on the device

- Live camera feed
- Face landmarks and iris positions (used in-memory for gaze calibration)
- MediaPipe model inference

## Consent and transparency

Students must **explicitly consent** before a viva session begins. The consent modal lists what is monitored (camera, gaze, fullscreen, tab focus, paste/screenshot detection, secondary devices). They can decline and exit without starting the session.

## Storage

- **Session state:** in-memory on the server for the duration of the exam (not a persistent user database).
- **Output files:** JSON logs under `output/proctoring_logs/` and `output/evaluations/` on the server filesystem — event metadata only, not video.
- **Tech stack JSON:** detected languages/frameworks from the uploaded ZIP under `output/tech_stacks/`.

## Design rationale

This approach minimizes privacy risk, reduces bandwidth, keeps compute cost at zero (no cloud vision APIs), and still gives mentors actionable integrity signals — gaze patterns, device/camera tampering, tab switching — for fair review without storing surveillance footage.

## Limitations (honest disclosure)

Browser-based proctoring **cannot** fully prevent screenshots via OS menus or external cameras. The system **detects and penalizes** known shortcuts and visible secondary devices rather than claiming perfect prevention. Mentors should treat integrity scores as **signals for review**, not sole proof of misconduct.
