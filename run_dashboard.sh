#!/usr/bin/env bash
# Launch SmartDelivery Streamlit dashboard and open it in the browser.
# Usage:
#   ./run_dashboard.sh          # default port 8503
#   ./run_dashboard.sh 8501     # custom port
#
# Press Ctrl+C to stop.

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Read port from settings.toml (falls back to hardcoded if python3/toml unavailable)
toml_val() { python3 -c "import tomllib,pathlib;c=tomllib.loads(pathlib.Path('$PROJECT_DIR/settings.toml').read_text());print(c$1)" 2>/dev/null; }

PORT="${1:-$(toml_val "['dashboard']['port']")}"
PORT="${PORT:-8503}"

# Kill any existing process on the target port
PID=$(lsof -ti:"$PORT" 2>/dev/null)
if [ -n "$PID" ]; then
    echo "Port $PORT in use (PID $PID). Killing..."
    kill -9 $PID 2>/dev/null
    sleep 1
fi

# Build the event generator binary if missing
GEN_BIN="$PROJECT_DIR/event-generator/smart-delivery-gen"
if [ ! -f "$GEN_BIN" ]; then
    if command -v go >/dev/null 2>&1; then
        echo "Event generator binary not found. Building..."
        (cd "$PROJECT_DIR/event-generator" && go build -o smart-delivery-gen .) || echo "Warning: Go build failed. Start Event Stream button will not work."
    else
        echo "Warning: Go is not installed and event generator binary is missing."
        echo "Install Go 1.21+ from https://go.dev/dl/ or build manually: cd event-generator && go build -o smart-delivery-gen ."
        echo "The dashboard will still launch, but Start Event Stream will not work."
    fi
fi

# Open browser after a short delay (runs in background)
(sleep 3 && open "http://localhost:$PORT") &

cd "$PROJECT_DIR" && streamlit run app/main.py --server.port "$PORT" --server.headless true
