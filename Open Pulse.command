#!/bin/bash
# Double-click this file to start Pulse (backend + browser)
cd "$(dirname "$0")"

# Kill any previous backend instance on port 5001
lsof -ti:5001 | xargs kill -9 2>/dev/null

# Start Flask backend
cd backend
source .venv/bin/activate 2>/dev/null || (python3 -m venv .venv && source .venv/bin/activate && pip install -q -r requirements.txt)
python3 server.py &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 2

# Open Pulse in browser
open "index.html"

echo "✅ Pulse backend running at http://localhost:5001"
echo "   Press Ctrl+C to stop the backend when done."

# Keep script running so backend stays alive; clean up on exit
trap "kill $BACKEND_PID 2>/dev/null" EXIT
wait $BACKEND_PID
