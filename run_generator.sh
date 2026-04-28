#!/usr/bin/env bash
# SmartDelivery Event Generator - run from anywhere.
# Usage:
#   ./run_generator.sh                  # max throughput defaults
#   ./run_generator.sh 1000 50 150      # custom: rate, workers, batch
#
# Press Ctrl+C to stop.

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="$PROJECT_DIR/event-generator/smart-delivery-gen"

# Read defaults from settings.toml (falls back to hardcoded if python3/toml unavailable)
toml_val() { python3 -c "import tomllib,pathlib;c=tomllib.loads(pathlib.Path('$PROJECT_DIR/settings.toml').read_text());print(c$1)" 2>/dev/null; }

RATE="${1:-$(toml_val "['generator']['rate']")}"
RATE="${RATE:-5000}"
WORKERS="${2:-$(toml_val "['generator']['workers']")}"
WORKERS="${WORKERS:-50}"
BATCH="${3:-$(toml_val "['generator']['batch']")}"
BATCH="${BATCH:-200}"

# Build if binary is missing
if [ ! -f "$BIN" ]; then
    if ! command -v go >/dev/null 2>&1; then
        echo "Error: Go is not installed and the pre-built binary is missing."
        echo "Install Go 1.21+ from https://go.dev/dl/ and re-run this script."
        echo "Alternatively, build manually: cd event-generator && go build -o smart-delivery-gen ."
        exit 1
    fi
    echo "Binary not found. Building..."
    (cd "$PROJECT_DIR/event-generator" && go build -o smart-delivery-gen .) || { echo "Build failed"; exit 1; }
fi

echo "Starting event generator: ${RATE} deliveries/sec, ${WORKERS} workers, batch ${BATCH}"
echo "Press Ctrl+C to stop."
exec "$BIN" --continuous --rate "$RATE" --workers "$WORKERS" --batch "$BATCH"
