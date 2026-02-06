#!/bin/bash

# Start Mode 4 with Ollama
# This script makes it easy to start the bot with one command

echo "🚀 Starting Mode 4 Email Assistant..."
echo ""

# Check if Ollama is running
if ! pgrep -x "ollama" > /dev/null; then
    echo "⚠️  Ollama is not running. Starting Ollama..."
    ollama serve &
    OLLAMA_PID=$!
    echo "   Ollama started (PID: $OLLAMA_PID)"
    sleep 2
else
    echo "✓ Ollama is already running"
fi

# Check if qwen2.5:3b is installed
echo ""
echo "Checking for qwen2.5:3b model..."
if ollama list | grep -q "qwen2.5:3b"; then
    echo "✓ qwen2.5:3b model found"
else
    echo "⚠️  qwen2.5:3b not found. Installing..."
    ollama pull qwen2.5:3b
fi

echo ""
echo "✓ All dependencies ready"
echo ""
echo "📱 Starting Telegram bot..."
echo "   (Press Ctrl+C to stop)"
echo ""

# Cleanup on exit (must be set before the blocking python call)
trap 'echo ""; echo "👋 Shutting down Mode 4..."; exit 0' INT TERM

# Start Mode 4
cd "$(dirname "$0")"
python3 mode4_processor.py
