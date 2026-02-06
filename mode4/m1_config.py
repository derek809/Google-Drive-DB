"""
Mode 4 Configuration - M1 MacBook
Settings for Telegram bot, Gmail, Sheets, and Ollama integration.
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
# PATHS (Corrected)
# ============================================

# Base directory is the directory containing this file (mode4/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Credentials directory - in parent directory (Telgram bot/)
CREDENTIALS_DIR = os.path.join(os.path.dirname(BASE_DIR), "credentials")

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
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# Your Telegram user ID (for security - only respond to you)
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

GMAIL_MCP_LABEL = "MCP"
GMAIL_SEARCH_DAYS = 7


# ============================================
# OLLAMA (Local LLM)
# ============================================

OLLAMA_MODEL = "llama3.2"
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_TEMPERATURE = 0.3
OLLAMA_MAX_TOKENS = 1000


# ============================================
# CLAUDE API (for escalations)
# ============================================

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
CLAUDE_MODEL = "claude-3-haiku-20240307"


# ============================================
# GEMINI API (for image/document analysis)
# ============================================

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY', '')
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_SUPPORTED_TYPES = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif']
GEMINI_MAX_IMAGE_SIZE = 20 * 1024 * 1024


# ============================================
# NVIDIA KIMI K2 API (Smart LLM alternative)
# ============================================

NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY', '')
KIMI_MODEL = "moonshotai/kimi-k2-instruct"
KIMI_BASE_URL = "https://integrate.api.nvidia.com/v1"
KIMI_TEMPERATURE = 0.6
KIMI_TOP_P = 0.9
KIMI_MAX_TOKENS = 4096


# ============================================
# DATABASE SETTINGS (Mode 4 SQLite)
# ============================================

# Database path - Inside mode4/data/
MODE4_DB_PATH = os.path.join(BASE_DIR, "data", "mode4.db")

# Queue settings
QUEUE_MAX_BATCH_SIZE = 50
QUEUE_PROCESS_INTERVAL_SECONDS = 30
DRAFT_CONTEXT_EXPIRY_MINUTES = 30


# ============================================
# CONFIDENCE THRESHOLDS
# ============================================

OLLAMA_ONLY_THRESHOLD = 90
OLLAMA_REVIEW_THRESHOLD = 70


# ============================================
# PROCESSING SETTINGS
# ============================================

API_RATE_LIMIT_SECONDS = 1.0
API_TIMEOUT_SECONDS = 30
MAX_BATCH_SIZE = 20


# ============================================
# NEW FEATURES CONFIGURATION
# ============================================

# SmartParser (Natural Language Parser)
SMART_PARSER_ENABLED = True
SMART_PARSER_MODEL = "qwen2.5:3b"
SMART_PARSER_FALLBACK = True

# ThreadSynthesizer
THREAD_SYNTHESIZER_ENABLED = True
THREAD_HISTORY_MAX_MESSAGES = 50

# ProactiveEngine
PROACTIVE_ENGINE_ENABLED = True
PROACTIVE_CHECK_INTERVAL = 2 * 60 * 60  # 2 hours
PROACTIVE_MAX_SUGGESTIONS_PER_DAY = 1
PROACTIVE_NO_REPLY_DAYS = 3
PROACTIVE_URGENT_HOURS = (15, 17)
PROACTIVE_DRAFT_UNSENT_DAYS = 2
PROACTIVE_MORNING_DIGEST_HOUR = 7


# ============================================
# GOOGLE DOCS (Master Doc for Skills)
# ============================================

# Master Doc ID for storing finalized skills/ideas
# URL format: https://docs.google.com/document/d/DOCUMENT_ID/edit
MASTER_DOC_ID = os.getenv('Docs_ID', os.getenv('MASTER_DOC_ID', ''))

# Google Docs API scopes
GOOGLE_DOCS_SCOPES = ['https://www.googleapis.com/auth/documents']

# Skills settings
SKILL_AUTO_CREATE_TASKS = True  # Auto-create tasks from action items
SKILL_INCLUDE_IN_MORNING_BRIEF = True  # Include pending skills in morning brief


# ============================================
# CONVERSATION MANAGER
# ============================================

CONVERSATION_ENABLED = True
CONVERSATION_INTENT_MODEL = OLLAMA_MODEL
CONVERSATION_CONTEXT_TIMEOUT = 30 * 60
CONVERSATION_GREETING_STYLE = "friendly"
CONVERSATION_CLARIFICATION_MODE = "smart_assumptions"
CONVERSATION_TODO_CONFIRM = False
CONVERSATION_PROACTIVE_SUGGESTIONS = True


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