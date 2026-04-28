#!/usr/bin/env bash
# Create the vector index for Vector Search & AI Copilot.
# Usage: ./vector_index.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Creating vector index..."
python "$PROJECT_DIR/scripts/vector_index.py"
