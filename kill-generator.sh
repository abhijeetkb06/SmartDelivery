#!/usr/bin/env bash
# kill-generator.sh — Emergency kill switch for the SmartDelivery Go event generator.
# Usage: ./kill-generator.sh

set -euo pipefail

BINARY="smart-delivery-gen"

echo "Searching for running ${BINARY} processes..."

PIDS=$(pgrep -f "${BINARY}" 2>/dev/null || true)

if [ -z "${PIDS}" ]; then
    echo "No ${BINARY} processes found."
    exit 0
fi

echo "Found processes:"
ps -o pid,ppid,%cpu,%mem,etime,command -p ${PIDS}
echo ""

echo "Sending SIGKILL to all ${BINARY} processes..."
pkill -9 -f "${BINARY}" 2>/dev/null || true
sleep 1

# Verify
REMAINING=$(pgrep -f "${BINARY}" 2>/dev/null || true)
if [ -z "${REMAINING}" ]; then
    echo "All ${BINARY} processes terminated."
else
    echo "WARNING: Some processes still running:"
    ps -o pid,ppid,%cpu,%mem,etime,command -p ${REMAINING}
    echo "Try: sudo kill -9 ${REMAINING}"
fi
