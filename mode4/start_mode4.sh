#!/bin/bash

# Start Mode 4 with Ollama
# This script makes it easy to start the bot with one command

echo "Starting Mode 4 Email Assistant..."
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Check for .env file
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found in mode4/"
    echo "  Create one with TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USERS, etc."
    echo ""
fi

# Validate critical environment variables
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from m1_config import validate_config
    errors = validate_config()
    critical = [e for e in errors if 'non-critical' not in e]
    warnings = [e for e in errors if 'non-critical' in e]

    if warnings:
        for w in warnings:
            print(f'  Warning: {w}')
        print()

    if critical:
        print('Configuration errors:')
        for e in critical:
            print(f'  ERROR: {e}')
        print()
        print('Fix these before starting. See m1_config.py for details.')
        sys.exit(1)
    else:
        print('Configuration OK')
except Exception as e:
    print(f'Warning: Could not validate config: {e}')
"
CONFIG_STATUS=$?
if [ $CONFIG_STATUS -ne 0 ]; then
    echo "Fix configuration errors before starting."
    exit 1
fi

echo ""

# Check if Ollama is running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Ollama is not running. Starting Ollama..."
    ollama serve &
    OLLAMA_PID=$!
    echo "   Ollama started (PID: $OLLAMA_PID)"
    sleep 2
else
    echo "Ollama is already running"
fi

# Check if qwen2.5:3b is installed (with retry)
echo ""
echo "Checking for qwen2.5:3b model..."
MAX_RETRIES=2
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if ollama list 2>/dev/null | grep -q "qwen2.5:3b"; then
        echo "qwen2.5:3b model found"
        break
    else
        if [ $RETRY -eq 0 ]; then
            echo "qwen2.5:3b not found. Pulling..."
            ollama pull qwen2.5:3b
        else
            echo "Warning: Could not verify qwen2.5:3b. SmartParser will use regex fallback."
        fi
    fi
    RETRY=$((RETRY + 1))
done

echo ""
echo "All dependencies ready"
echo ""
echo "Starting Telegram bot..."
echo "   (Press Ctrl+C to stop)"
echo ""

# Cleanup on exit
trap 'echo ""; echo "Shutting down Mode 4..."; exit 0' INT TERM

# Start Mode 4
python3 mode4_processor.py
