"""
Mode 4 Configuration - M1 MacBook
Settings for Telegram bot, Gmail, Sheets, and Ollama integration.
"""



# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    import os
    
    # 1. Get the folder where this file is (core/Infrastructure)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Go up two levels to the Root Folder (Telgram bot)
    root_dir = os.path.dirname(os.path.dirname(current_dir))
    
    # 3. Load .env from the Root
    dotenv_path = os.path.join(root_dir, '.env')
    load_dotenv(dotenv_path)
    
    print(f"✅ Loaded config from: {dotenv_path}")

except ImportError:
    print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")

# ============================================
# PATHS (Fixed for Root Credentials)
# ============================================

# 1. Identify where this file is: .../core/Infrastructure/
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Go up two levels to find the Root Folder: .../Telgram bot/
CORE_DIR = os.path.dirname(CURRENT_DIR)      # .../core
ROOT_DIR = os.path.dirname(CORE_DIR)         # .../Telgram bot

# 3. Define paths relative to the Root
BASE_DIR = CURRENT_DIR  # Keep this for internal logic
CREDENTIALS_DIR = os.path.join(ROOT_DIR, "credentials")  # <--- Now points to main folder

# Google Sheets service account JSON
SHEETS_CREDENTIALS_PATH = os.path.join(CREDENTIALS_DIR, "sheets_service_account.json")

# Gmail OAuth credentials
GMAIL_CREDENTIALS_PATH = os.path.join(CREDENTIALS_DIR, "gmail_credentials.json")
GMAIL_TOKEN_PATH = os.path.join(CREDENTIALS_DIR, "gmail_token.json")

# Telegram bot configuration
TELEGRAM_CONFIG_PATH = os.path.join(CREDENTIALS_DIR, "telegram_config.json")

# Log file (Keep logs in root or core, your choice. This puts them in root)
LOG_PATH = os.path.join(ROOT_DIR, "mode4.log")
LOG_MAX_BYTES = 2 * 1024 * 1024   # 2 MB max per log file
LOG_BACKUP_COUNT = 3               # Keep 3 rotated backups

# Log file
LOG_PATH = os.path.join(BASE_DIR, "mode4.log")
LOG_MAX_BYTES = 2 * 1024 * 1024   # 2 MB max per log file
LOG_BACKUP_COUNT = 3               # Keep 3 rotated backups


# ============================================
# MEMORY LIMITS
# ============================================

MAX_CONVERSATION_CONTEXTS = 50     # Max user contexts kept in memory
MAX_DRAFT_CONTEXTS = 100           # Max pending draft sessions in memory


# ============================================
# GOOGLE SHEETS (Legacy/Fallback)
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
# GMAIL API (Legacy/Fallback)
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
KIMI_TEMPERATURE = 1.00
KIMI_TOP_P = 1.00
KIMI_MAX_TOKENS = 16384


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
# MODE 4 MODEL ROUTING (litellm)
# ============================================

# Timeouts for litellm router
OLLAMA_TIMEOUT = 10       # seconds for local Ollama calls
API_TIMEOUT = 30          # seconds for remote API calls (Claude, Kimi, Gemini)

# Fallback chain: ordered list of provider keys for the litellm Router.
# M1ModelRouter maps these to actual model strings at runtime.
FALLBACK_CHAIN = ["claude", "kimi", "ollama"]


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
# GOOGLE DOCS (Legacy/Fallback - Master Doc for Skills)
# ============================================

# Master Doc ID for storing finalized skills/ideas
# URL format: https://docs.google.com/document/d/DOCUMENT_ID/edit
# Supports both env var names for backward compatibility
MASTER_DOC_ID = os.getenv('MASTER_DOC_ID') or os.getenv('Docs_ID', '')

# Google Docs API scopes
GOOGLE_DOCS_SCOPES = ['https://www.googleapis.com/auth/documents']

# Skills settings
SKILL_AUTO_CREATE_TASKS = True  # Auto-create tasks from action items
SKILL_INCLUDE_IN_MORNING_BRIEF = True  # Include pending skills in morning brief


# ============================================
# TODO MANAGEMENT (Legacy/Fallback - Google Sheets as source of truth)
# ============================================

TODOS_ACTIVE_SHEET = "todos_active"
TODOS_HISTORY_SHEET = "todos_history"


# ============================================
# BRAINSTORM (Legacy/Fallback - Google Docs)
# ============================================

# Brainstorm Doc ID - can be same as MASTER_DOC_ID or separate
BRAINSTORM_DOC_ID = os.getenv('BRAINSTORM_DOC_ID') or MASTER_DOC_ID


# ============================================
# CLARIFICATION STATE
# ============================================

CLARIFICATION_TIMEOUT_MINUTES = 5


# ============================================
# CONFIRMATION SETTINGS
# ============================================

CONFIRMATION_REQUIRED = True  # All mutations require yes/no confirmation


# ============================================
# CONVERSATION MANAGER
# ============================================

CONVERSATION_ENABLED = True
CONVERSATION_INTENT_MODEL = OLLAMA_MODEL
CONVERSATION_CONTEXT_TIMEOUT = 30 * 60
CONVERSATION_GREETING_STYLE = "friendly"
CONVERSATION_CLARIFICATION_MODE = "smart_assumptions"
CONVERSATION_TODO_CONFIRM = True
CONVERSATION_PROACTIVE_SUGGESTIONS = True

# Task completion context TTL - how long after showing todos
# a bare-number completion like "1 is done" is accepted
TASK_COMPLETION_CONTEXT_TTL = 300  # 5 minutes


# ============================================
# MICROSOFT 365 (Graph API)
# ============================================

# Credentials file path
MICROSOFT_CREDENTIALS_PATH = os.path.join(CREDENTIALS_DIR, "microsoft_login.json")

# Load M365 credentials from JSON file
_M365_CREDS = {}
try:
    if os.path.exists(MICROSOFT_CREDENTIALS_PATH):
        import json as _json
        with open(MICROSOFT_CREDENTIALS_PATH, 'r') as _f:
            _M365_CREDS = _json.load(_f)
except Exception as _e:
    print(f"Warning: Could not load Microsoft credentials: {_e}")

# Azure AD Application (env vars override JSON file)
M365_CLIENT_ID = (
    os.getenv('M365_CLIENT_ID')
    or _M365_CREDS.get('azure_ad_application', {}).get('client_id', '')
)
M365_TENANT_ID = (
    os.getenv('M365_TENANT_ID')
    or _M365_CREDS.get('azure_ad_application', {}).get('tenant_id', '')
)
M365_CLIENT_SECRET = (
    os.getenv('M365_CLIENT_SECRET')
    or _M365_CREDS.get('azure_ad_application', {}).get('client_secret', '')
)

# SharePoint
SHAREPOINT_SITE_ID = (
    os.getenv('SHAREPOINT_SITE_ID')
    or _M365_CREDS.get('sharepoint', {}).get('site_id', '')
)

# OneNote
ONENOTE_NOTEBOOK_ID = os.getenv('ONENOTE_NOTEBOOK_ID', '')

# Microsoft Lists
ACTION_ITEMS_LIST_ID = os.getenv('ACTION_ITEMS_LIST_ID', '')
IDEA_BOARD_LIST_ID = os.getenv('IDEA_BOARD_LIST_ID', '')

# Persistent token cache path (saves Azure AD quota across restarts)
M365_TOKEN_CACHE_PATH = os.path.join(CREDENTIALS_DIR, '.msal_token_cache.json')

# Operational settings
M365_STALE_TASK_THRESHOLD_MINUTES = int(
    os.getenv('M365_STALE_TASK_THRESHOLD_MINUTES', '15')
)
M365_MAX_FILE_SIZE_MB = int(os.getenv('M365_MAX_FILE_SIZE_MB', '10'))
M365_CIRCUIT_BREAKER_COOLDOWN_SECONDS = int(
    os.getenv('M365_CIRCUIT_BREAKER_COOLDOWN_SECONDS', '300')
)

# Hybrid migration mode: "dual", "google_only", "microsoft_only"
HYBRID_MIGRATION_MODE = os.getenv('HYBRID_MIGRATION_MODE', 'dual')

# Feature flag — nothing changes until explicitly opted in
M365_ENABLED = os.getenv('M365_ENABLED', 'false').lower() == 'true'


# ============================================
# ACTION REGISTRY SYSTEM
# ============================================

# Feature flag - set to True to enable the Action Registry layer
# between intent detection and execution. When False, the system
# falls through to the existing direct routing flow.
ACTION_REGISTRY_ENABLED = True

# Confidence threshold below which the registry triggers a
# clarification loop instead of guessing.
ACTION_REGISTRY_CONFIDENCE_GATE = 0.65


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_m365_config_loader():
    """
    Return a callable that resolves dotted config keys to M365 values.

    The active/ clients (SharePointListReader, OneNoteClient, etc.)
    expect a config_loader("microsoft.action_items_list_id") interface.
    This bridges from m1_config constants to that interface.

    Returns:
        Callable[[str], Any] that resolves dotted keys.
    """
    config_map = {
        "sharepoint.site_id": SHAREPOINT_SITE_ID,
        "microsoft.onenote_notebook_id": ONENOTE_NOTEBOOK_ID,
        "microsoft.action_items_list_id": ACTION_ITEMS_LIST_ID,
        "microsoft.idea_board_list_id": IDEA_BOARD_LIST_ID,
        "microsoft.token_cache_path": M365_TOKEN_CACHE_PATH,
        "microsoft.stale_task_threshold_minutes": M365_STALE_TASK_THRESHOLD_MINUTES,
        "microsoft.max_file_size_mb": M365_MAX_FILE_SIZE_MB,
        "microsoft.circuit_breaker_cooldown_seconds": M365_CIRCUIT_BREAKER_COOLDOWN_SECONDS,
        "hybrid.migration_mode": HYBRID_MIGRATION_MODE,
    }
    return lambda key: config_map.get(key)


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
    """
    Validate configuration is properly set up.

    Returns list of error strings. Empty list = all good.
    Checks env vars, credential files, and API keys.
    """
    errors = []

    # Critical: Telegram bot
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN not configured (set in .env or environment)")

    if not TELEGRAM_ALLOWED_USERS:
        errors.append("TELEGRAM_ALLOWED_USERS is empty - bot will respond to no one")

    # Google Sheets
    if SPREADSHEET_ID == "YOUR_SPREADSHEET_ID_HERE":
        errors.append("SPREADSHEET_ID not configured (set in .env)")

    if not os.path.exists(SHEETS_CREDENTIALS_PATH):
        errors.append(f"Sheets credentials not found: {SHEETS_CREDENTIALS_PATH}")

    # Gmail
    if not os.path.exists(GMAIL_CREDENTIALS_PATH):
        errors.append(f"Gmail credentials not found: {GMAIL_CREDENTIALS_PATH}")

    # Database path
    db_dir = os.path.dirname(MODE4_DB_PATH)
    if not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
        except OSError as e:
            errors.append(f"Cannot create database directory {db_dir}: {e}")

    # Optional but recommended
    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY not set - Claude API unavailable (non-critical)")

    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY / GOOGLE_API_KEY not set - Gemini unavailable (non-critical)")

    # Microsoft 365 (only validate when enabled)
    if M365_ENABLED:
        if not M365_CLIENT_ID or not M365_TENANT_ID or not M365_CLIENT_SECRET:
            errors.append(
                "M365_ENABLED=true but Azure AD credentials missing "
                "(check credentials/microsoft_login.json or M365_* env vars)"
            )
        if not SHAREPOINT_SITE_ID:
            errors.append("SHAREPOINT_SITE_ID not configured")
        if not ACTION_ITEMS_LIST_ID:
            errors.append("ACTION_ITEMS_LIST_ID not configured (non-critical for M365)")

    return errors
