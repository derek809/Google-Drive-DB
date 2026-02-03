"""
Mode 4 Configuration - M1 MacBook
Settings for Telegram bot, Gmail, Sheets, and Ollama integration.

SETUP INSTRUCTIONS:
1. Copy this file to your M1 at ~/mode4/m1_config.py
2. Update the configuration values below
3. Create credentials directory: mkdir ~/mode4/credentials
4. Place service account JSON in ~/mode4/credentials/
"""

import os

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load from mode4/.env
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(dotenv_path)
except ImportError:
    print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")

# ============================================
# PATHS (Update for your M1 setup)
# ============================================

# Base directory for Mode 4 - use current script location
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Credentials directory - in parent folder
CREDENTIALS_DIR = os.path.join(BASE_DIR, "credentials")

# Google Sheets service account JSON
SHEETS_CREDENTIALS_PATH = os.path.join(CREDENTIALS_DIR, "sheets_service_account.json")

# Gmail OAuth credentials (token will be stored alongside)
GMAIL_CREDENTIALS_PATH = os.path.join(CREDENTIALS_DIR, "gmail_credentials.json")
GMAIL_TOKEN_PATH = os.path.join(CREDENTIALS_DIR, "gmail_token.json")

# Telegram bot configuration
TELEGRAM_CONFIG_PATH = os.path.join(CREDENTIALS_DIR, "telegram_config.json")

# Log file
LOG_PATH = os.path.join(BASE_DIR, "mode4.log")


# ============================================
# GOOGLE SHEETS
# ============================================

# The spreadsheet ID from your Google Sheet URL
# URL format: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', 'YOUR_SPREADSHEET_ID_HERE')

# Sheet names (must match what bootstrap_sync_sheets.py creates)
PATTERNS_SHEET = "Patterns"
TEMPLATES_SHEET = "Templates"
CONTACTS_SHEET = "Contacts"
MCP_QUEUE_SHEET = "MCP"

# M1 status columns in MCP sheet (for Mode 4 to write)
# These columns allow Mode 1 and Mode 4 to coexist
M1_STATUS_COLUMNS = {
    'processed_by': 'P',      # ollama / ollama+review / claude_team / apps_script
    'processing_mode': 'Q',   # mode1 / mode4
    'm1_status': 'R',         # pending / processing / done / error / escalated_to_claude
    'm1_notes': 'S'           # Processing notes from M1
}


# ============================================
# TELEGRAM BOT
# ============================================

# Bot token from @BotFather
# Get this by: 1) Open Telegram, 2) Search @BotFather, 3) /newbot, 4) Copy token
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# Your Telegram user ID (for security - only respond to you)
# Get this by: Send a message to @userinfobot on Telegram
_allowed_users_str = os.getenv('TELEGRAM_ALLOWED_USERS', '')
TELEGRAM_ALLOWED_USERS = [int(x.strip()) for x in _allowed_users_str.strip('[]').split(',') if x.strip()] if _allowed_users_str else []

# Chat ID to send notifications to
TELEGRAM_ADMIN_CHAT_ID = int(os.getenv('TELEGRAM_ADMIN_CHAT_ID')) if os.getenv('TELEGRAM_ADMIN_CHAT_ID') else None


# ============================================
# GMAIL API
# ============================================

# Gmail API scopes needed
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.modify'
]

# Label used to identify MCP emails
GMAIL_MCP_LABEL = "MCP"

# How many days back to search for emails
GMAIL_SEARCH_DAYS = 7


# ============================================
# OLLAMA (Local LLM)
# ============================================

# Ollama model to use for triage and draft generation
# Options: llama3.2, llama3, mistral, etc.
OLLAMA_MODEL = "llama3.2"

# Ollama API endpoint (default local)
OLLAMA_HOST = "http://localhost:11434"

# Temperature for generation (lower = more deterministic)
OLLAMA_TEMPERATURE = 0.3

# Max tokens for draft generation
OLLAMA_MAX_TOKENS = 1000


# ============================================
# CLAUDE API (for escalations)
# ============================================

# Claude Team API key from https://console.anthropic.com/
# Get this by:
# 1. Go to https://console.anthropic.com/
# 2. Sign in with your Claude Team account
# 3. Navigate to API Keys → Create new key
# 4. Copy the key (starts with 'sk-ant-')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

# Model to use for drafts (haiku is fast and cheap)
CLAUDE_MODEL = "claude-3-haiku-20240307"


# ============================================
# GEMINI API (for image/document analysis)
# ============================================

# Google Gemini API key
# Get this from: https://aistudio.google.com/app/apikey
# Can use either GEMINI_API_KEY or GOOGLE_API_KEY environment variable
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY', '')

# Model to use for vision tasks (Flash is fast and cost-effective)
GEMINI_MODEL = "gemini-2.0-flash"

# Supported image types for analysis
GEMINI_SUPPORTED_TYPES = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif']

# Max image size (in bytes) - 20MB limit for Gemini
GEMINI_MAX_IMAGE_SIZE = 20 * 1024 * 1024


# ============================================
# DATABASE SETTINGS (Mode 4 SQLite)
# ============================================

# Database path (separate from work laptop's mcp_learning.db)
MODE4_DB_PATH = os.path.join(BASE_DIR, "data", "mode4.db")

# Queue settings
QUEUE_MAX_BATCH_SIZE = 50
QUEUE_PROCESS_INTERVAL_SECONDS = 30

# Draft context expiry (minutes)
DRAFT_CONTEXT_EXPIRY_MINUTES = 30


# ============================================
# CONFIDENCE THRESHOLDS
# ============================================

# Confidence score thresholds for routing decisions
# >= OLLAMA_ONLY_THRESHOLD: Ollama generates draft alone, no review needed
OLLAMA_ONLY_THRESHOLD = 90

# >= OLLAMA_REVIEW_THRESHOLD and < OLLAMA_ONLY_THRESHOLD: Ollama generates, flag for review
OLLAMA_REVIEW_THRESHOLD = 70

# < OLLAMA_REVIEW_THRESHOLD: Low confidence, flag for Claude Desktop (no draft created)
# This is implicit - anything below OLLAMA_REVIEW_THRESHOLD


# ============================================
# PROCESSING SETTINGS
# ============================================

# Rate limiting
API_RATE_LIMIT_SECONDS = 1.0  # Minimum seconds between API calls

# Timeout for API calls
API_TIMEOUT_SECONDS = 30

# Maximum emails to process in one batch
MAX_BATCH_SIZE = 20


# ============================================
# NEW FEATURES CONFIGURATION
# ============================================

# SmartParser (Natural Language Parser)
SMART_PARSER_ENABLED = True
SMART_PARSER_MODEL = "qwen2.5:3b"  # Ollama model for parsing
SMART_PARSER_FALLBACK = True  # Use regex fallback if LLM unavailable

# ThreadSynthesizer
THREAD_SYNTHESIZER_ENABLED = True
THREAD_HISTORY_MAX_MESSAGES = 50  # Max messages to fetch per thread

# ProactiveEngine
PROACTIVE_ENGINE_ENABLED = True
PROACTIVE_CHECK_INTERVAL = 2 * 60 * 60  # 2 hours in seconds
PROACTIVE_MAX_SUGGESTIONS_PER_DAY = 1
PROACTIVE_NO_REPLY_DAYS = 3  # Days before suggesting follow-up
PROACTIVE_URGENT_HOURS = (15, 17)  # 3pm-5pm for urgent reminders
PROACTIVE_DRAFT_UNSENT_DAYS = 2  # Days before reminding about unsent drafts
PROACTIVE_MORNING_DIGEST_HOUR = 7  # 7am morning summary


# ============================================
# CONVERSATION MANAGER
# ============================================

# Enable conversational interface (natural language)
CONVERSATION_ENABLED = True

# Intent classification model (uses Ollama)
CONVERSATION_INTENT_MODEL = OLLAMA_MODEL  # Reuse Ollama model for consistency

# Context timeout (seconds) - how long to remember conversation
CONVERSATION_CONTEXT_TIMEOUT = 30 * 60  # 30 minutes

# Response style
CONVERSATION_GREETING_STYLE = "friendly"  # friendly, brief, personality

# Clarification behavior
CONVERSATION_CLARIFICATION_MODE = "smart_assumptions"  # smart_assumptions, ask_always, interactive

# Todo handling
CONVERSATION_TODO_CONFIRM = False  # Just add it vs confirm first

# Proactive suggestions
CONVERSATION_PROACTIVE_SUGGESTIONS = True  # Offer suggestions for vague requests


# ============================================
# HELPER FUNCTIONS
# ============================================

def load_telegram_config():
    """Load Telegram configuration from JSON file."""
    import json

    if os.path.exists(TELEGRAM_CONFIG_PATH):
        with open(TELEGRAM_CONFIG_PATH, 'r') as f:
            config = json.load(f)
            return {
                'bot_token': config.get('bot_token', TELEGRAM_BOT_TOKEN),
                'allowed_users': config.get('allowed_users', TELEGRAM_ALLOWED_USERS),
                'admin_chat_id': config.get('admin_chat_id', TELEGRAM_ADMIN_CHAT_ID)
            }

    return {
        'bot_token': TELEGRAM_BOT_TOKEN,
        'allowed_users': TELEGRAM_ALLOWED_USERS,
        'admin_chat_id': TELEGRAM_ADMIN_CHAT_ID
    }


def validate_config():
    """Validate configuration is properly set up."""
    errors = []

    if SPREADSHEET_ID == "YOUR_SPREADSHEET_ID_HERE":
        errors.append("SPREADSHEET_ID not configured")

    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        errors.append("TELEGRAM_BOT_TOKEN not configured")

    if not TELEGRAM_ALLOWED_USERS:
        errors.append("TELEGRAM_ALLOWED_USERS is empty - bot will respond to no one")

    if not os.path.exists(SHEETS_CREDENTIALS_PATH):
        errors.append(f"Sheets credentials not found: {SHEETS_CREDENTIALS_PATH}")

    if not os.path.exists(GMAIL_CREDENTIALS_PATH):
        errors.append(f"Gmail credentials not found: {GMAIL_CREDENTIALS_PATH}")

    return errors


def print_config_status():
    """Print configuration status for debugging."""
    print("Mode 4 Configuration Status")
    print("=" * 50)
    print(f"Base directory: {BASE_DIR}")
    print(f"Credentials directory: {CREDENTIALS_DIR}")
    print(f"Database path: {MODE4_DB_PATH}")
    print()
    print("Files:")
    print(f"  Sheets creds: {'OK' if os.path.exists(SHEETS_CREDENTIALS_PATH) else 'MISSING'}")
    print(f"  Gmail creds: {'OK' if os.path.exists(GMAIL_CREDENTIALS_PATH) else 'MISSING'}")
    print(f"  Telegram config: {'OK' if os.path.exists(TELEGRAM_CONFIG_PATH) else 'MISSING'}")
    print(f"  Mode4 database: {'OK' if os.path.exists(MODE4_DB_PATH) else 'NOT YET CREATED'}")
    print()
    print("Settings:")
    print(f"  Spreadsheet ID: {'SET' if SPREADSHEET_ID != 'YOUR_SPREADSHEET_ID_HERE' else 'NOT SET'}")
    print(f"  Telegram token: {'SET' if TELEGRAM_BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE' else 'NOT SET'}")
    print(f"  Allowed users: {len(TELEGRAM_ALLOWED_USERS)} configured")
    print(f"  Ollama model: {OLLAMA_MODEL}")
    print(f"  Claude API: {'SET' if ANTHROPIC_API_KEY else 'NOT SET (optional)'}")
    print(f"  Gemini API: {'SET' if GEMINI_API_KEY else 'NOT SET (optional)'}")
    print(f"  Gemini model: {GEMINI_MODEL}")
    print()

    errors = validate_config()
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("Configuration OK!")


if __name__ == "__main__":
    print_config_status()
