#!/bin/bash

# 1. Define the Source of Truth directories
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_DIR="$BASE_DIR/core"
INFRA_DIR="$BASE_DIR/core/Infrastructure"
LLM_DIR="$BASE_DIR/LLM"
BRAIN_DIR="$BASE_DIR/brain"
ACTIONS_DIR="$BASE_DIR/Bot_actions"

# 2. Add ALL necessary paths to PYTHONPATH
#    - LLM: for gmail_client, telegram_handler, ollama_client
#    - brain: for pattern_matcher, smart_parser
#    - Bot_actions: for queue_processor
#    - Infrastructure: for m1_config, db_manager
export PYTHONPATH="$BASE_DIR:$CORE_DIR:$INFRA_DIR:$LLM_DIR:$BRAIN_DIR:$ACTIONS_DIR:$PYTHONPATH"

echo "Starting Mode 4 Email Assistant..."
echo "   Base Dir: $BASE_DIR"

# 3. Check for .env file
if [ -f "$BASE_DIR/.env" ]; then
    echo "✅ .env file found."
else
    echo "⚠️  WARNING: .env file not found!"
    echo "   Creating a default .env file..."
    echo "TELEGRAM_BOT_TOKEN=YOUR_TOKEN_HERE" > "$BASE_DIR/.env"
    echo "TELEGRAM_ALLOWED_USERS=123456789" >> "$BASE_DIR/.env"
    echo "   Please edit the .env file with your actual Telegram Token."
fi

# 4. Check for Ollama (AI Model Server)
if pgrep -x "ollama" > /dev/null; then
    echo "✅ Ollama is running."
else
    echo "🔄 Starting Ollama..."
    ollama serve &
    sleep 5
fi

# 5. Start the Bot
echo "🚀 Starting Mode 4 Processor..."
echo "---------------------------------------"
python3 "$CORE_DIR/mode4_processor.py"
