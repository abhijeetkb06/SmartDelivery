#!/usr/bin/env bash
# Launch SmartDelivery Streamlit dashboard and open it in the browser.
# Usage:
#   ./run_dashboard.sh          # default port 8503
#   ./run_dashboard.sh 8501     # custom port
#
# Press Ctrl+C to stop.

PORT="${1:-8503}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Kill any existing process on the target port
PID=$(lsof -ti:"$PORT" 2>/dev/null)
if [ -n "$PID" ]; then
    echo "Port $PORT in use (PID $PID). Killing..."
    kill -9 $PID 2>/dev/null
    sleep 1
fi

# Open browser after a short delay (runs in background)
(sleep 3 && open "http://localhost:$PORT") &

cd "$PROJECT_DIR" && streamlit run app/main.py --server.port "$PORT" --server.headless true
