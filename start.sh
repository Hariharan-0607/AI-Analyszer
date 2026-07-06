#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Checking Gemini API key..."
cd "$ROOT/backend"
[ -f .env ] || cp .env.example .env
if grep -qE '^GEMINI_API_KEY=\s*your_gemini' .env 2>/dev/null || ! grep -qE '^GEMINI_API_KEY=\S+' .env; then
  echo "WARNING: Set GEMINI_API_KEY in backend/.env"
  echo "  Get a free key: https://aistudio.google.com/apikey"
else
  echo "Gemini API key found in .env"
fi

echo "Building website..."
cd "$ROOT/frontend"
npm install --silent
npm run build
cd "$ROOT"

echo "Starting server on all network interfaces..."
cd "$ROOT/backend"
pip install -r requirements.txt -q
echo ""
echo "  This PC:       http://localhost:8000"
echo "  Other devices: http://<your-ip>:8000"
echo ""
uvicorn app.main:app --host 0.0.0.0 --port 8000
