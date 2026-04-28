#!/usr/bin/env bash
# SmartDelivery Event Generator - run from anywhere.
# Usage:
#   ./run_generator.sh                  # max throughput defaults
#   ./run_generator.sh 1000 50 150      # custom: rate, workers, batch
#
# Press Ctrl+C to stop.

RATE="${1:-5000}"
WORKERS="${2:-50}"
BATCH="${3:-200}"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="$PROJECT_DIR/event-generator/smart-delivery-gen"

# Build if binary is missing
if [ ! -f "$BIN" ]; then
    echo "Binary not found. Building..."
    (cd "$PROJECT_DIR/event-generator" && go build -o smart-delivery-gen main.go) || { echo "Build failed"; exit 1; }
fi

echo "Starting event generator: ${RATE} deliveries/sec, ${WORKERS} workers, batch ${BATCH}"
echo "Press Ctrl+C to stop."
exec "$BIN" --continuous --rate "$RATE" --workers "$WORKERS" --batch "$BATCH"
