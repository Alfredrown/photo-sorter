#!/bin/bash
# ─────────────────────────────────────────────────────────────
# PhotoSort AI — Startup Script
# ─────────────────────────────────────────────────────────────
set -e

BACKEND_DIR="$(cd "$(dirname "$0")/backend" && pwd)"
FRONTEND_DIR="$(cd "$(dirname "$0")/frontend" && pwd)"
VENV_DIR="$BACKEND_DIR/.venv"

echo ""
echo "╔════════════════════════════════════╗"
echo "║       PhotoSort AI  ◈              ║"
echo "║   Portrait vs Landscape Sorter     ║"
echo "╚════════════════════════════════════╝"
echo ""

# ── 1. Create / activate Python virtual environment ──────────
if [ ! -d "$VENV_DIR" ]; then
  echo "🔧 Creating Python virtual environment…"
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# ── 2. Install dependencies ───────────────────────────────────
echo "📦 Checking dependencies…"
pip install -q -r "$BACKEND_DIR/requirements.txt"

# ── 3. Start backend server ───────────────────────────────────
echo ""
echo "🚀 Starting AI backend on http://localhost:5050"
echo "   (First run will download ~350MB CLIP model — please wait)"
echo ""

cd "$BACKEND_DIR"
python app.py &
BACKEND_PID=$!

# ── 4. Wait for server to be ready ───────────────────────────
echo "⏳ Waiting for server to start…"
for i in $(seq 1 30); do
  if curl -s http://localhost:5050/status >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

# ── 5. Open the frontend in the browser ──────────────────────
echo ""
echo "🌐 Opening PhotoSort AI in your browser…"
open "$FRONTEND_DIR/index.html"

echo ""
echo "✅ PhotoSort AI is running!"
echo "   Backend: http://localhost:5050"
echo "   Frontend: $FRONTEND_DIR/index.html"
echo ""
echo "   Press Ctrl+C to stop the server."
echo ""

# ── Keep running until Ctrl+C ────────────────────────────────
trap "echo ''; echo '👋 Shutting down…'; kill $BACKEND_PID 2>/dev/null; exit 0" INT TERM
wait $BACKEND_PID
