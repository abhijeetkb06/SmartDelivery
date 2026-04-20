#!/usr/bin/env bash
# Continuously generate SmartDelivery events until manually stopped (Ctrl+C).
#
# Usage:
#   ./scripts/run_generator.sh                  # max throughput defaults
#   ./scripts/run_generator.sh 1000 50 150      # custom: rate, workers, batch
#
# Defaults are tuned for maximum Couchbase ops/sec demonstration:
#   5000 deliveries/sec × ~7 docs each ≈ 35K+ raw writes/sec
#   + Eventing read/write multiplier → 50-80K+ ops/sec on Capella dashboard

RATE="${1:-5000}"
WORKERS="${2:-50}"
BATCH="${3:-200}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GEN_DIR="$SCRIPT_DIR/../event-generator"
BIN="$GEN_DIR/smart-delivery-gen"

# Build if binary is missing
if [ ! -f "$BIN" ]; then
    echo "Binary not found. Building..."
    (cd "$GEN_DIR" && go build -o smart-delivery-gen main.go) || { echo "Build failed"; exit 1; }
fi

echo "Starting event generator: ${RATE} deliveries/sec, ${WORKERS} workers, batch ${BATCH}"
echo "Press Ctrl+C to stop."
exec "$BIN" --continuous --rate "$RATE" --workers "$WORKERS" --batch "$BATCH"
