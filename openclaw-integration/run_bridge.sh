#!/bin/bash
# OpenClaw ↔ Work Bot Bridge Startup Script
#
# Runs bridge.py as a standalone process.
# The bridge watches inbox/ for tasks from OpenClaw and writes results to outbox/.
#
# Usage:
#   ./run_bridge.sh                    # default: inbox/outbox next to this script
#   ./run_bridge.sh --poll 5           # poll every 5 seconds instead of 2
#   INBOX=/tmp/oc/inbox OUTBOX=/tmp/oc/outbox ./run_bridge.sh
#
# Run alongside Mode 4:
#   ./start_mode4.sh &     # terminal 1 (or screen/tmux)
#   ./openclaw-integration/run_bridge.sh  # terminal 2

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRIDGE_DIR="$BASE_DIR/openclaw-integration"
CORE_DIR="$BASE_DIR/core"
INFRA_DIR="$BASE_DIR/core/Infrastructure"
LLM_DIR="$BASE_DIR/LLM"
BRAIN_DIR="$BASE_DIR/brain"
ACTIONS_DIR="$BASE_DIR/Bot_actions"

# Default inbox/outbox — override via environment variables
INBOX="${INBOX:-$BRIDGE_DIR/inbox}"
OUTBOX="${OUTBOX:-$BRIDGE_DIR/outbox}"
POLL="${POLL:-2}"

export PYTHONPATH="$BASE_DIR:$CORE_DIR:$INFRA_DIR:$LLM_DIR:$BRAIN_DIR:$ACTIONS_DIR:${PYTHONPATH:-}"

echo "OpenClaw Bridge starting..."
echo "  Inbox:  $INBOX"
echo "  Outbox: $OUTBOX"
echo "  Poll interval: ${POLL}s"
echo "  PYTHONPATH set."
echo ""

# Create inbox/outbox directories if they don't exist
mkdir -p "$INBOX" "$OUTBOX" "$INBOX/processed" "$INBOX/failed"

exec python3 "$BRIDGE_DIR/bridge.py" \
    --inbox "$INBOX" \
    --outbox "$OUTBOX" \
    --poll "$POLL" \
    "$@"
