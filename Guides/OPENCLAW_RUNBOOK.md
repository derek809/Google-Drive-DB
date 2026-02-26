# Mode 4 Telegram Bot — Open Claw Knowledge Base

> **Audience**: Open Claw (AI agent) — you both operate and develop this bot.
> **Format**: Every section follows **purpose → file path → key functions → data flow → gotchas**.
> **Rule**: When in doubt, trust this document over assumptions. File paths are absolute from project root.

---

## 0. QUICK REFERENCE TABLE

| Concept | Primary File | Key Class / Function | Notes |
|---|---|---|---|
| Entry point | `core/mode4_processor.py` | `Mode4Processor` | Launched via `start_mode4.sh` |
| Startup script | `start_mode4.sh` | — | Sets PYTHONPATH, starts Ollama, runs processor |
| Telegram I/O | `LLM/telegram_handler.py` | `TelegramHandler._handle_message()` | Auth check on every message |
| Intent classification | `core/InputOutput/intent_tree.py` | `IntentClassifier.classify()` | Walks `playbook/intent_tree.json` |
| Conversation routing | `brain/conversation_manager.py` | `ConversationManager.handle_message()` | 158KB file — largest in project |
| Smart parser (NLP) | `brain/smart_parser.py` | `SmartParser.parse()` | Uses Ollama qwen2.5:3b |
| Pattern matcher | `brain/pattern_matcher.py` | `PatternMatcher.match_pattern()` | Templates from Google Sheets |
| Actions registry | `core/Infrastructure/actions.py` | `ACTIONS` dict, `ActionSchema` | Pydantic v2 model, `extra="allow"` |
| Action extractor | `core/InputOutput/action_extractor.py` | `ActionExtractor.extract_params()` | Regex layer 1, LLM layer 2 |
| Action validator | `core/InputOutput/action_validator.py` | `ActionValidator.validate()` | Triggers confirmation for HIGH risk |
| Safety interceptor | `core/Infrastructure/safety_interceptor.py` | `RiskAwareActionValidator` | `email_send` → `email_draft` redirect |
| Context manager | `core/State_Memory/context_manager.py` | `ContextManager.inject_context()` | Pronoun resolution ("it" → last entity) |
| Conversation state | `core/State_Memory/conversation_state.py` | `ConversationStateMachine` | States: Idle, Executing, Awaiting |
| Session state | `core/State_Memory/session_state.py` | `SessionState` | Short-term memory for #N refs |
| LLM recommendation | `brain/llm_router.py` | `LLMRouter.analyze()` | Recommends ollama vs claude vs kimi |
| LLM execution | `core/Inference/m1_model_router.py` | `M1ModelRouter` | litellm Router with fallback chain |
| Thread synthesizer | `brain/thread_synthesizer.py` | `ThreadSynthesizer.synthesize()` | "State of Play" summaries |
| Proactive engine | `brain/proactive_engine.py` | `ProactiveEngine.worker_loop()` | 2-hour background cycle |
| Config hub | `core/Infrastructure/m1_config.py` | — | Loads `.env` + `credentials/*.json` |
| Database | `core/Infrastructure/db_manager.py` | `DatabaseManager` | SQLite at `~/mode4/data/mode4.db` |
| Gmail client | `LLM/gmail_client.py` | `GmailClient` | OAuth2, `credentials/gmail_*.json` |
| Ollama client | `LLM/ollama_client.py` | `OllamaClient` | Local at `http://localhost:11434` |
| Claude client | `LLM/claude_client.py` | `ClaudeClient` | Anthropic API |
| Kimi client | `LLM/kimi_client.py` | `KimiClient` | NVIDIA API (`NVIDIA_API_KEY`) |
| Gemini client | `LLM/gemini_client.py` | `GeminiClient` | Google `gemini-2.5-flash` |
| Sheets client | `LLM/sheets_client.py` | `GoogleSheetsClient` | Service account auth |
| Todo manager | `Bot_actions/todo_manager.py` | `TodoManager` | Google Sheets-backed tasks |
| Skill manager | `Bot_actions/skill_manager.py` | `SkillManager` | Idea capture + Master Doc |
| Idea bouncer | `Bot_actions/idea_bouncer.py` | `IdeaBouncer` | Interactive brainstorming |
| Daily digest | `Bot_actions/daily_digest.py` | `DailyDigest` | Morning email summary |
| On-demand digest | `Bot_actions/on_demand_digest.py` | `OnDemandDigest` | Snapshot summary on request |
| Queue processor | `Bot_actions/queue_processor.py` | `QueueProcessor` | Offline message queue |
| Quick capture | `Bot_actions/quick_capture.py` | `QuickCapture` | Fast-capture notes |
| Template manager | `Bot_actions/template_manager.py` | `TemplateManager` | Email templates |
| Workflow manager | `Bot_actions/workflow_manager.py` | `WorkflowManager` | Multi-step task chains |
| File fetcher | `Bot_actions/file_fetcher.py` | `FileFetcher` | Google Drive file retrieval |
| M365 Graph client | `active/graph_client.py` | `GraphClient` | MSAL async, persistent token cache |
| M365 session mgr | `active/async_session_manager.py` | `AsyncSessionManager` | Two sessions: 30s API, 5min files |
| M365 file fetcher | `active/file_fetcher.py` | `HybridFileFetcher` | SharePoint + GDrive, circuit breaker |
| M365 SharePoint | `active/sharepoint_list_reader.py` | `SharePointListReader` | Read/write SharePoint lists |
| M365 OneNote | `active/onenote_client.py` | `OneNoteClient` | OneNote page CRUD |
| M365 setup | `active/setup_m365_lists.py` | — | Provisions lists (`--dry-run`) |
| M365 validator | `active/migration_validator.py` | — | 10-check readiness validator |
| M365 proactive | `active/proactive_engine.py` | `ProactiveEngine` | M365-specific sync (separate from brain/) |
| Observability | `core/Infrastructure/observability.py` | `HealthChecker`, `CircuitBreaker` | System health + circuit breakers |
| Ambiguity resolver | `core/InputOutput/ambiguity_resolver.py` | `AmbiguityResolver` | Disambiguation when intent unclear |
| Hybrid classifier | `core/InputOutput/hybrid_intent_classifier.py` | `HybridIntentClassifier` | Combines tree + LLM classification |
| Notification router | `core/InputOutput/notification_router.py` | `NotificationRouter` | Routes responses to Telegram |
| Update stream | `core/InputOutput/update_stream.py` | `UpdateStream` | Live status updates during tasks |

---

## 1. STARTUP AND PYTHONPATH

### How the bot starts

**Script**: `start_mode4.sh` (project root)

```
BASE_DIR    = /Users/work/Telgram bot
CORE_DIR    = $BASE_DIR/core
INFRA_DIR   = $BASE_DIR/core/Infrastructure
LLM_DIR     = $BASE_DIR/LLM
BRAIN_DIR   = $BASE_DIR/brain
ACTIONS_DIR = $BASE_DIR/Bot_actions
```

**PYTHONPATH** is set to: `$BASE_DIR:$CORE_DIR:$INFRA_DIR:$LLM_DIR:$BRAIN_DIR:$ACTIONS_DIR`

Then it:
1. Checks `.env` exists (creates skeleton if not)
2. Starts Ollama if not running (`ollama serve &`)
3. Runs `python3 $CORE_DIR/mode4_processor.py`

### Why flat imports work

Because `LLM/` is on PYTHONPATH, `mode4_processor.py` can do:
```python
from gmail_client import GmailClient      # resolves to LLM/gmail_client.py
from pattern_matcher import PatternMatcher  # resolves to brain/pattern_matcher.py
from queue_processor import QueueProcessor  # resolves to Bot_actions/queue_processor.py
from m1_config import M365_ENABLED          # resolves to core/Infrastructure/m1_config.py
```

### Additional sys.path in mode4_processor.py (lines 52-57)

```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project root
sys.path.insert(0, active_dir)  # active/ directory for M365 imports
```

### Gotchas

- **NEVER run a .py file directly** without replicating PYTHONPATH from `start_mode4.sh`. Imports will fail.
- **`mode4/` subdirectory at project root is NOT the active entry point.** It has its own `.env` and `__pycache__` but is legacy. The real entry is `core/mode4_processor.py`.
- If you add a new directory with modules, you must add it to PYTHONPATH in `start_mode4.sh` too.

---

## 2. THE BRIDGE PATTERN

### What it is

`core/__init__.py` is a **universal action registry** that imports from subdirectories and re-exports everything. To enable this, each subdirectory module has a **bridge file** in `core/` that is just a re-export.

### Complete bridge map

| Bridge file (in `core/`) | Real file (in subdirectory) |
|---|---|
| `core/actions.py` | `core/Infrastructure/actions.py` |
| `core/safety_interceptor.py` | `core/Infrastructure/safety_interceptor.py` |
| `core/observability.py` | `core/Infrastructure/observability.py` |
| `core/m1_model_router.py` | `core/Inference/m1_model_router.py` |
| `core/intent_tree.py` | `core/InputOutput/intent_tree.py` |
| `core/action_extractor.py` | `core/InputOutput/action_extractor.py` |
| `core/action_validator.py` | `core/InputOutput/action_validator.py` |
| `core/ambiguity_resolver.py` | `core/InputOutput/ambiguity_resolver.py` |
| `core/notification_router.py` | `core/InputOutput/notification_router.py` |
| `core/update_stream.py` | `core/InputOutput/update_stream.py` |
| `core/hybrid_intent_classifier.py` | `core/InputOutput/hybrid_intent_classifier.py` |
| `core/context_manager.py` | `core/State_Memory/context_manager.py` |
| `core/conversation_state.py` | `core/State_Memory/conversation_state.py` |
| `core/session_state.py` | `core/State_Memory/session_state.py` |

### Rules

1. **Always edit the REAL file** in the subdirectory (e.g., `core/Infrastructure/actions.py`), never the bridge file.
2. Bridge files are 1-2 lines: `from core.Infrastructure.actions import *`
3. If you add a new module to a subdirectory, you **must**:
   - Create a bridge file in `core/`
   - Add it to `core/__init__.py` imports and `__all__`
4. Everything in `core/__init__.py` is importable as `from core import Foo`.

### What `core/__init__.py` exports

```python
from core import (
    ACTIONS, ActionSchema, RiskLevel, get_action_schema, get_action_name,
    ActionExtractor, ActionValidator, ValidationResult,
    SessionState, ContextManager, NotificationRouter, UpdateStream,
    IntentClassifier, IntentResult, DecisionNode,
    AmbiguityResolver, DisambiguationResult,
    ConversationStateMachine, ConversationState,
    StructuredLogger, PerformanceTracker, HealthChecker, CircuitBreaker,
    M1ModelRouter,
    SafetyViolationError, RiskAwareActionValidator, risk_based_safety_interceptor,
    HybridIntentClassifier,
)
```

---

## 3. THE PYDANTIC V2 BUG AND IMPORT WORKAROUND

### The bug

`core/Infrastructure/actions.py` (lines 440-453) has a merge loop that loads runtime metadata from `playbook/actions.json` and sets extra attributes on `ActionSchema` instances:

```python
for _action_key, _json_meta in _ACTIONS_JSON.items():
    _schema = ACTIONS[_action_key]
    _schema.progress_updates = _json_meta.get("progress_updates", [])
    _schema.timeout_seconds = _json_meta.get("timeout_seconds", 30)
    _schema.allows_undo = _json_meta.get("allows_undo", False)
    _schema.action_class = _json_meta.get("action_class", "")
```

### Current fix

`ActionSchema` at line 58 has:
```python
model_config = ConfigDict(extra="allow")
```

This tells pydantic v2 to accept arbitrary extra fields. **This fix is currently in place and working.**

### When it breaks

- If someone removes `extra="allow"` from `ActionSchema`
- If `playbook/actions.json` has keys that conflict with pydantic internals
- If `core/__init__.py` is imported before pydantic is installed

### Import chain failure mode

`core/__init__.py` imports in a fixed order. If ANY single import fails, **ALL of `core` becomes unimportable**. The chain is:

```
core/__init__.py
  → core.actions (→ core/Infrastructure/actions.py → pydantic → playbook/actions.json merge)
  → core.action_extractor
  → core.action_validator
  → core.session_state
  → core.context_manager
  → ... (14 total imports)
```

### Testing workaround

If `import core` fails, bypass the bridge entirely:

```python
import importlib.util

spec = importlib.util.spec_from_file_location(
    "actions",
    "/Users/work/Telgram bot/core/Infrastructure/actions.py"
)
actions_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actions_module)

# Now use: actions_module.ACTIONS, actions_module.ActionSchema, etc.
```

Or mock the core package:
```python
import types
core = types.ModuleType("core")
sys.modules["core"] = core
```

---

## 4. COMPLETE MESSAGE PIPELINE

### Full trace: Telegram message → response

```
Step 1: ARRIVAL
───────────────
File: LLM/telegram_handler.py
Function: TelegramHandler._handle_message() (line ~361)

  → Auth check: user.id must be in TELEGRAM_ALLOWED_USERS
  → Shows typing indicator
  → Attempts parse via SmartParser (LLM) then regex fallback


Step 2: CONVERSATION ROUTING
────────────────────────────
File: brain/conversation_manager.py
Function: ConversationManager.handle_message() (line ~206)

  Priority chain (checked in order):
  1. Is user in AWAITING state? → resolve clarification/confirmation
  2. Active clarification flow? → db_manager.get_clarification()
  3. Queue response? ("yes 1", "no 2", "yes all")
  4. Legacy email format? ("Re: ...", "From: ...")
  5. Task completion? ("1 is done", "complete #3")
  6. Full intent classification → _classify_intent()


Step 3: INTENT CLASSIFICATION
─────────────────────────────
File: core/InputOutput/intent_tree.py
Function: IntentClassifier.classify()

  Walks playbook/intent_tree.json decision tree.
  Returns: IntentResult(category, confidence, parameters, follow_up_question)

  Categories: email_action, todo_action, skill_action, digest_action,
              sheet_action, workflow_action, casual, clarification_needed


Step 4: PARAMETER EXTRACTION
────────────────────────────
File: core/InputOutput/action_extractor.py
Function: ActionExtractor.extract_params()

  Layer 1: Deterministic regex (patterns from ActionSchema.deterministic_patterns)
  Layer 2: LLM fallback for fuzzy phrases ("the big one", "that email")


Step 5: CONTEXT INJECTION
─────────────────────────
File: core/State_Memory/context_manager.py
Function: ContextManager.inject_context()

  → Pronoun resolution: "it" → last entity from topic stack
  → Semantic matching: ensures "Send it" is compatible with "Email"
  → Injects thread_id, email_id, etc. into params


Step 6: VALIDATION & SAFETY
───────────────────────────
File: core/InputOutput/action_validator.py → core/Infrastructure/safety_interceptor.py

  ActionValidator.validate():
    → All required params present?
    → Risk level check (LOW/MEDIUM/HIGH)
    → HIGH risk → ask for user confirmation

  RiskAwareActionValidator.validate_and_maybe_redirect():
    → email_send → silently redirected to email_draft with [BOT DRAFT] prefix
    → HIGH risk + no redirect + not confirmed → SafetyViolationError


Step 7: EXECUTION (Email flow)
──────────────────────────────
File: core/mode4_processor.py
Function: Mode4Processor.process_message() (line ~467)

  1. GmailClient.search_email() — find matching email
  2. PatternMatcher.match_pattern() — check against known patterns
  3. If use_inline_buttons=True (default):
     → TelegramHandler.send_draft_request_with_buttons()
     → User picks LLM via inline button (Ollama / Kimi / Claude)
  4. Button callback triggers draft generation with selected LLM
  5. GmailClient.create_reply_draft() — save draft
  6. Response sent to Telegram


Step 8: EXECUTION (Non-email flows)
────────────────────────────────────
Routed by ConversationManager based on intent:

  todo_*     → TodoManager         (Bot_actions/todo_manager.py)
  skill_*    → SkillManager        (Bot_actions/skill_manager.py)
  idea       → IdeaBouncer         (Bot_actions/idea_bouncer.py)
  digest     → OnDemandDigest      (Bot_actions/on_demand_digest.py)
  casual     → Direct LLM response (greeting logic)
  unread     → Gmail unread list
  synthesize → ThreadSynthesizer   (brain/thread_synthesizer.py)
```

### Visual flow

```
USER (Telegram)
    │
    ▼
TelegramHandler._handle_message()  ─── auth check ───  REJECTED (unknown user)
    │
    ▼
SmartParser.parse()  ──or──  regex fallback
    │
    ▼
ConversationManager.handle_message()
    │
    ├── AWAITING state? ──→ resolve pending flow
    ├── Queue response? ──→ process queue action
    ├── Legacy format? ──→ Mode4Processor.process_message()
    │
    ▼
IntentClassifier.classify()
    │
    ├── email_action ──→ process_message() ──→ Gmail search ──→ LLM draft ──→ Gmail draft
    ├── todo_action ──→ TodoManager
    ├── skill_action ──→ SkillManager
    ├── digest_action ──→ OnDemandDigest
    ├── casual ──→ direct response
    └── clarification_needed ──→ ask follow-up question
    │
    ▼
Response sent to Telegram
```

---

## 5. LLM ROUTING LOGIC

### Two-layer architecture

| Layer | File | Purpose |
|---|---|---|
| Recommendation | `brain/llm_router.py` | **Suggests** which LLM to use based on task analysis |
| Execution | `core/Inference/m1_model_router.py` | **Calls** the LLM via litellm with fallback chain |

**Key principle**: For drafts, the user ALWAYS chooses via Telegram button. The router only provides recommendations. For internal calls (intent classification, data extraction), the router auto-selects.

### Recommendation logic (`LLMRouter.analyze()`)

Decision rules in priority order:
1. Compliance/legal keywords (FINRA, SEC, audit, legal) → **Claude**
2. Complex reasoning keywords (negotiate, strategy, analyze) → **Claude**
3. Ambiguous input (< 3 words, "help", "not sure") → **Claude**
4. Pattern confidence >= 90% → **Ollama**
5. Pattern confidence >= 70% AND sender is known → **Ollama**
6. Otherwise → **either** (user chooses via button)

### Capability routing table (`ROUTING_TABLE`)

```python
"intent_classification":        ("ollama/qwen2.5:3b",  2s)   # Fast local intent detection
"email_draft_simple":           ("ollama/qwen2.5:3b",  5s)   # Simple email with style
"email_draft_complex":          ("claude/sonnet",       10s)  # Multi-thread context drafts
"data_extraction_structured":   ("gemini/flash",        5s)   # JSON-mode structured extraction
"data_extraction_unstructured": ("claude/sonnet",       10s)  # Reasoning-heavy extraction
"summarization_long":           ("claude/sonnet",       15s)  # 100k+ context summarization
"code_generation":              ("claude/opus",         20s)  # High-quality code generation
"idea_bounce":                  ("kimi/k2",             10s)  # Creative brainstorming
```

### Cost per 1K tokens (USD)

```
ollama:        $0.00
claude/haiku:  $0.00025
claude/sonnet: $0.003
claude/opus:   $0.015
gemini/flash:  $0.0001
kimi/k2:       $0.002
```

### Execution fallback chain

`M1ModelRouter` uses litellm `Router`:
```
claude → kimi → ollama
```
If Claude fails (rate limit, timeout), retries with Kimi. If Kimi fails, falls back to local Ollama.

### Circuit breakers

Per-model `_ModelCircuit`:
- **Threshold**: 5 failures in 60-second window
- **Recovery**: Circuit opens for 120 seconds, then resets
- When circuit is open, model is skipped and next in fallback chain is used

---

## 6. ACTIONS REGISTRY AND SAFETY MODEL

### Actions registry structure

**File**: `core/Infrastructure/actions.py`

Each action is an `ActionSchema` (pydantic v2 BaseModel):
```python
ActionSchema(
    intent="TODO_COMPLETE",           # Maps to Intent enum
    required_params=["task_id"],      # Must be present before execution
    optional_params=[],               # Nice to have
    context_needed=["active_tasks"],  # Context injected by ContextManager
    risk_level=RiskLevel.LOW,         # LOW, MEDIUM, HIGH
    fallback_strategy="fuzzy_match_then_ask",  # What to do when params missing
    description="Mark a task as complete",
    deterministic_patterns=[r"#(\d+)"],  # Regex for ActionExtractor layer 1
    confirmation_template="Mark task #{task_id}?",
)
```

### Complete action list with risk levels

| Action | Intent | Risk | Description |
|---|---|---|---|
| `todo_complete` | TODO_COMPLETE | LOW | Mark task as complete |
| `todo_add` | TODO_ADD | LOW | Create new task |
| `todo_delete` | TODO_DELETE | **HIGH** | Permanently delete task |
| `todo_list` | TODO_LIST | LOW | List active tasks |
| `email_draft` | EMAIL_DRAFT | MEDIUM | Generate email draft |
| `email_send` | EMAIL_SEND | **HIGH** | Send composed draft |
| `email_search` | EMAIL_SEARCH | LOW | Search Gmail |
| `email_synthesize` | EMAIL_SYNTHESIZE | LOW | Thread summary / State of Play |
| `skill_create` | SKILL_CREATE | MEDIUM | Create skill from brainstorm |
| `skill_finalize` | SKILL_FINALIZE | MEDIUM | Finalize and archive skill |
| `skill_list` | SKILL_LIST | LOW | List skills/brainstorms |
| `skill_search` | SKILL_SEARCH | LOW | Search skills by keyword |
| `skill_synthesize` | SKILL_SYNTHESIZE | LOW | Synthesize multiple skills |
| `digest_generate` | DIGEST_GENERATE | LOW | Morning digest |
| `reminder_set` | REMINDER_SET | LOW | Set follow-up reminder |
| `draft_nudge` | DRAFT_NUDGE | LOW | Nudge about unsent draft |
| `thread_monitor` | THREAD_MONITOR | LOW | Monitor thread for triggers |
| `data_structure` | DATA_STRUCTURE | LOW | Convert unstructured → JSON |
| `sheet_sync` | SHEET_SYNC | MEDIUM | Lookup & update sheet row |
| `doc_generate` | DOC_GENERATE | MEDIUM | Generate formatted Google Doc |
| `workflow_condition` | WORKFLOW_CONDITION | LOW | If/then decision gate |
| `context_link` | CONTEXT_LINK | LOW | Link resources cross-platform |
| `status` | INFO_STATUS | LOW | Show system health |
| `unread` | EMAIL_UNREAD | LOW | Show unread emails |
| `learning_negative` | LEARNING_NEGATIVE | LOW | Track rejection feedback |

### Runtime metadata merge

At import time, `playbook/actions.json` is loaded and merged into each `ActionSchema`:
- `progress_updates`: List of status messages shown during execution
- `timeout_seconds`: Max execution time (default 30)
- `allows_undo`: Whether action can be reversed
- `action_class`: Categorization string

### Safety interceptor

**File**: `core/Infrastructure/safety_interceptor.py`

**Redirect map**:
```python
REDIRECT_MAP = {
    "email_send": "email_draft",  # Sends become drafts
}
```

**Flow**:
1. If risk != HIGH → pass through unchanged
2. If risk == HIGH AND user confirmed → allow through
3. If risk == HIGH AND redirect exists → redirect (e.g., email_send → email_draft, prefix subject with `[BOT DRAFT]`)
4. If risk == HIGH AND no redirect AND not confirmed → `SafetyViolationError`

**Decorator**: `@risk_based_safety_interceptor` can wrap async handlers.

### Fallback strategies

| Strategy | Behavior |
|---|---|
| `ask` | Always ask user for missing params |
| `fuzzy_match_then_ask` | Try regex first, ask if no match |
| `always_confirm` | Require explicit user confirmation (HIGH risk) |
| `smart_suggest` | Assume best match and proceed |

---

## 7. CONFIG AND CREDENTIALS CHAIN

### Config file

**File**: `core/Infrastructure/m1_config.py`

**Path resolution**:
```
CURRENT_DIR = core/Infrastructure/
CORE_DIR    = core/                    (parent)
ROOT_DIR    = /Users/work/Telgram bot/ (grandparent)
CREDENTIALS_DIR = ROOT_DIR/credentials/
```

**Load order**: `.env` from ROOT_DIR via `python-dotenv`, then JSON files from `credentials/`.

### Credential files

| File | Service | Auth Type |
|---|---|---|
| `credentials/telegram_config.json` | Telegram Bot API | Bot token |
| `credentials/gmail_credentials.json` | Gmail API | OAuth2 client |
| `credentials/gmail_token.json` | Gmail API | OAuth2 refresh token (auto-refreshed) |
| `credentials/sheets_service_account.json` | Google Sheets API | Service account |
| `credentials/microsoft_login.json` | Microsoft Graph API | Azure AD client credentials |
| `credentials/.msal_token_cache.json` | Microsoft 365 | MSAL persistent token cache |

### Config value priority (for each setting)

```
1. Environment variable (from .env or shell)  ← checked first
2. JSON credential file                       ← fallback
3. Hardcoded default in m1_config.py          ← last resort
```

**Example for M365**:
```python
M365_CLIENT_ID = os.getenv('M365_CLIENT_ID') or _M365_CREDS.get('azure_ad_application', {}).get('client_id', '')
```
The `.env` vars for M365 are commented out, so credentials load from `microsoft_login.json`.

### Feature flags

| Flag | Default | Location | Purpose |
|---|---|---|---|
| `M365_ENABLED` | `false` | `.env` | Gates all Microsoft 365 integration |
| `PROACTIVE_ENGINE_ENABLED` | `True` | m1_config.py:223 | Background workspace monitor |
| `SMART_PARSER_ENABLED` | `True` | m1_config.py:214 | LLM-based message parsing |
| `THREAD_SYNTHESIZER_ENABLED` | `True` | m1_config.py:219 | Thread summaries |
| `ACTION_REGISTRY_ENABLED` | `True` | m1_config.py:366 | Action registry layer |
| `CONVERSATION_ENABLED` | `True` | m1_config.py:283 | Conversation manager |

### Known `.env` issue

Lines 28-33 contain an unparseable `Nvida_Model=payload={...}` block. python-dotenv warns about this but it does NOT block operation. Non-fatal.

---

## 8. DATABASE SCHEMA

### Database path

Default: `~/mode4/data/mode4.db` (SQLite)

Set by `DatabaseManager.__init__()` in `core/Infrastructure/db_manager.py` line 46-50. Note: `m1_config.py` defines a different `MODE4_DB_PATH` but `mode4_processor.py` uses the default.

### Tables

| Table | Purpose | Key Columns |
|---|---|---|
| `message_queue` | Offline message processing | telegram_message_id, user_id, chat_id, status, llm_choice, confidence_score, model_used |
| `draft_contexts` | Button callback state | draft_id (PK), context_json, draft_json, expires_at, status |
| `tasks` | Todo items | id, title, status, priority, deadline, skill_slug (FK→skills) |
| `quick_links` | File shortcuts | name (UNIQUE), url, file_type |
| `idea_sessions` | Brainstorming sessions | id (PK), idea, questions_json, answers_json, gameplan, use_claude, status |
| `skills` | Finalized brainstorms | slug (PK), type, title, body, action_items, tags, doc_position, sheet_row_ids |
| `workspace_items` | Proactive engine threads | thread_id (UNIQUE), subject, from_name, urgency, status, days_old, suggestion_count |
| `suggestion_log` | Proactive suggestion audit | workspace_item_id (FK), suggestion_type, user_action |
| `workflows` | Multi-step task chains | workflow_id (PK), workflow_type, state, context, step_history |
| `clarification_state` | Multi-step form collection | user_id (PK), intent, missing_fields, collected_data, expires_at |
| `topic_stacks` | Topic memory | user_id, topic, context_json, message_count, status |
| `context_trims` | Archived messages for learning | user_id, topic_stack_id (FK), trimmed_messages, reason |
| `topic_transitions` | Topic switch log | user_id, from_topic, to_topic, trigger_message |
| `db_migrations` | Migration tracking | migration_name, applied_at |

### Convenience methods

```python
db = DatabaseManager()
db.execute(sql, params)   # Returns list of rows, auto-commits
db.fetchall(sql, params)  # Returns list of sqlite3.Row objects
db.fetchone(sql, params)  # Returns single sqlite3.Row or None
```

Singleton pattern: `get_db()` returns global `_db_instance`.

---

## 9. SUBSYSTEM REFERENCE CARDS

### SmartParser
- **Purpose**: NLP message parsing using local LLM, with regex fallback
- **File**: `brain/smart_parser.py`
- **Key class**: `SmartParser`
- **Key functions**: `parse(message_text)` → `{email_reference, instruction, search_type, parsed_with}`
- **Config**: `SMART_PARSER_ENABLED` (m1_config.py:214)
- **Depends on**: OllamaClient (qwen2.5:3b)
- **Gotchas**: Returns `parsed_with: "llm"` or `"regex"` — check this to know which path was taken

### PatternMatcher
- **Purpose**: Match email content against templates/patterns from Google Sheets
- **File**: `brain/pattern_matcher.py`
- **Key class**: `PatternMatcher`
- **Key functions**: `load_data()`, `match_pattern(subject, body)`, `is_known_sender(email)`
- **Depends on**: GoogleSheetsClient, SPREADSHEET_ID
- **Gotchas**: Must call `load_data()` before matching. Data comes from Sheets tabs: Patterns, Templates, Contacts

### ConversationManager
- **Purpose**: Full intent routing hub — classifies every message and routes to handler
- **File**: `brain/conversation_manager.py`
- **Key class**: `ConversationManager`
- **Key functions**: `handle_message()`, `_classify_intent()`, `_is_legacy_email_format()`
- **Depends on**: IntentClassifier, ActionExtractor, ActionValidator, ContextManager, SessionState, DatabaseManager, all Bot_actions modules
- **Gotchas**: **158KB — the largest file in the project.** Contains 25+ intent enum values. If editing, be aware of context window limits. Has its own `Intent` enum separate from the action registry intents.

### ThreadSynthesizer
- **Purpose**: Email thread summarization ("State of Play")
- **File**: `brain/thread_synthesizer.py`
- **Key class**: `ThreadSynthesizer`
- **Key functions**: `synthesize(thread_id)`, `generate_state_of_play(emails)`
- **Config**: `THREAD_SYNTHESIZER_ENABLED` (m1_config.py:219)
- **Depends on**: GmailClient, ClaudeClient or OllamaClient

### ProactiveEngine (Brain)
- **Purpose**: Background workspace monitor — checks for stale threads, unsent drafts, deadlines
- **File**: `brain/proactive_engine.py`
- **Key class**: `ProactiveEngine`
- **Key functions**: `worker_loop()`, `sync_workspace()`, `run_all_checks()`, `run_hygiene_checks()`
- **Config**: `PROACTIVE_ENGINE_ENABLED`, `PROACTIVE_CHECK_INTERVAL`
- **Depends on**: GmailClient, DatabaseManager, TelegramHandler
- **Gotchas**: Runs as background asyncio task in Mode4Processor. Separate from `active/proactive_engine.py` (M365 version). Both can run simultaneously.

### TodoManager
- **Purpose**: Google Sheets-backed task list management
- **File**: `Bot_actions/todo_manager.py`
- **Key class**: `TodoManager`
- **Key functions**: `add_task()`, `complete_task()`, `list_tasks()`, `delete_task()`
- **Depends on**: GoogleSheetsClient, DatabaseManager

### SkillManager
- **Purpose**: Idea capture + finalization to Master Doc in Google Docs
- **File**: `Bot_actions/skill_manager.py`
- **Key class**: `SkillManager`
- **Key functions**: `create_skill()`, `finalize_skill()`, `list_skills()`, `search_skills()`
- **Depends on**: DatabaseManager, GoogleSheetsClient, Google Docs client

### IdeaBouncer
- **Purpose**: Interactive brainstorming — asks structured questions, generates game plan
- **File**: `Bot_actions/idea_bouncer.py`
- **Key class**: `IdeaBouncer`
- **Key functions**: `start_session()`, `answer_question()`, `generate_gameplan()`
- **Depends on**: OllamaClient or ClaudeClient, DatabaseManager

### GmailClient
- **Purpose**: Gmail API wrapper — search, read, draft, send
- **File**: `LLM/gmail_client.py`
- **Key class**: `GmailClient`
- **Key functions**: `authenticate()`, `search_email()`, `create_reply_draft()`, `get_thread()`
- **Config**: `GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH`, `GMAIL_SCOPES`
- **Gotchas**: Must call `authenticate()` before any operation. Token auto-refreshes.

### OllamaClient
- **Purpose**: Local LLM interface — zero cost, fast inference
- **File**: `LLM/ollama_client.py`
- **Key class**: `OllamaClient`
- **Key functions**: `is_available()`, `triage()`, `generate_draft()`, `classify_intent()`
- **Config**: Runs at `http://localhost:11434`, model `qwen2.5:3b`
- **Gotchas**: Must check `is_available()` — Ollama server may not be running

### ClaudeClient
- **Purpose**: Anthropic API for complex reasoning tasks
- **File**: `LLM/claude_client.py`
- **Key class**: `ClaudeClient`
- **Config**: `ANTHROPIC_API_KEY` env var
- **Gotchas**: Optional — bot functions without it, just uses Ollama/Kimi instead

### KimiClient
- **Purpose**: NVIDIA/Kimi K2 API for creative and analytical tasks
- **File**: `LLM/kimi_client.py`
- **Key class**: `KimiClient`
- **Config**: `NVIDIA_API_KEY` env var, endpoint `https://integrate.api.nvidia.com/v1`
- **Gotchas**: Uses NVIDIA API infrastructure, not Kimi directly

### GeminiClient
- **Purpose**: Google Gemini for structured data extraction and image analysis
- **File**: `LLM/gemini_client.py`
- **Key class**: `GeminiClient`
- **Config**: `GOOGLE_API_KEY` env var, model `gemini-2.5-flash`

---

## 10. MICROSOFT 365 INTEGRATION STATUS

### Feature gate

Everything M365 is behind `M365_ENABLED` (env var, default `false`).

Current `.env` has `M365_ENABLED=true` but `M365_CLIENT_ID` and `M365_TENANT_ID` are **commented out**. Doesn't matter — `m1_config.py` falls back to `credentials/microsoft_login.json` which has all values populated.

### Files in `active/`

| File | Purpose |
|---|---|
| `graph_client.py` | MSAL async wrapper, persistent token cache at `credentials/.msal_token_cache.json`, 401 auto-retry |
| `async_session_manager.py` | Two httpx sessions: `get_session()` (30s for API calls), `get_file_session()` (5min for downloads) |
| `file_fetcher.py` | Hybrid SharePoint + Google Drive file retrieval with circuit breaker |
| `sharepoint_list_reader.py` | Read/write SharePoint lists (Action_Items, Idea_Board) |
| `onenote_client.py` | OneNote page CRUD, maps `OneNotePageID` (UUID→API) vs `OneNoteLink` (URL→Telegram) |
| `onenote_html_sanitizer.py` | Clean OneNote HTML for display |
| `proactive_engine.py` | M365-specific proactive engine — syncs workspace across M365 and Google. **Separate from** `brain/proactive_engine.py` |
| `setup_m365_lists.py` | Provisions Action_Items + Idea_Board SharePoint lists. Run with `--dry-run` first. |
| `migration_validator.py` | 10-check end-to-end readiness validator. Run before enabling M365. |

### Where M365 is gated in `mode4_processor.py`

- **Line 78-85**: Conditional import of M365 config (falls back to `M365_ENABLED = False` on ImportError)
- **Lines 139-144**: Lazy-load properties for M365 clients (graph, sharepoint, onenote, file_fetcher, m365_proactive_engine)
- **Lines 398-431**: `start_m365_engine()` — creates M365ProactiveEngine and starts `_m365_sync_loop` as background task
- **Lines 849-850**: `if M365_ENABLED: await self.start_m365_engine()` during `run_async()`
- **Lines 875-880**: M365 sync loop in TaskGroup (conditional)

### Hybrid migration mode

`HYBRID_MIGRATION_MODE` in `.env` (default: `"dual"`):
- `"dual"` — sync both Google and Microsoft
- `"google_only"` — Google Sheets/Docs only
- `"microsoft_only"` — SharePoint/OneNote only

### Archived

`possibly_deprecating/` contains old Google-only versions: `sheets_client.py`, `google_docs_client.py`, `file_fetcher.py`

---

## 11. PLAYBOOK CONFIGURATION FILES

All in `playbook/` directory:

| File | Purpose |
|---|---|
| `intent_tree.json` | Decision tree definition. Nodes have `condition_type`, `condition_data`, `true_branch`, `false_branch`. Thresholds: auto_route=0.8, suggest=0.5, clarify=0.0 |
| `actions.json` | Runtime metadata merged into ACTIONS registry at import. Defines `progress_updates`, `timeout_seconds`, `allows_undo`, `action_class` per action |
| `Personality.json` | Bot personality config (greeting style, tone, formality level) |
| `context_rules.json` | Rules for context injection and pronoun resolution |
| `templates.json` | Email draft templates keyed by pattern type |
| `workflows.json` | Multi-step workflow definitions (steps, transitions, conditions) |

---

## 12. KNOWN BUGS AND WORKAROUNDS

### 1. Pydantic v2 / `core/__init__.py`
**Status**: Fixed by `ConfigDict(extra="allow")` in `ActionSchema`.
**If it resurfaces**: Use `importlib` workaround (see Section 3).

### 2. `.env` parsing warning
**Lines 28-33**: `Nvida_Model=payload={...}` is unparseable by python-dotenv.
**Impact**: Console warning only, non-blocking.

### 3. Dual LOG_PATH definitions
**File**: `m1_config.py` lines 55 and 60.
**Bug**: Second definition (`BASE_DIR/mode4.log`) overwrites first (`ROOT_DIR/mode4.log`).
**Result**: Logs go to `core/Infrastructure/mode4.log`, not project root.
**Note**: `mode4_processor.py` defines its OWN log path at line 36 (`core/mode4.log`), which is what actually gets used.

### 4. `conversation_manager.py` is 158KB
**Impact**: If you try to read the entire file in one context window, it may truncate. Read in sections or search for specific functions.

### 5. `mode4/` directory confusion
**Location**: Project root has a `mode4/` directory with its own `.env` and `__pycache__`.
**Status**: Legacy/unused. The real entry point is `core/mode4_processor.py`.

### 6. Database path discrepancy
**`DatabaseManager.__init__`** defaults to `~/mode4/data/mode4.db`.
**`m1_config.py`** defines `MODE4_DB_PATH` pointing elsewhere.
**`mode4_processor.py`** creates `DatabaseManager()` with no args (so uses `~/mode4/data/` default).

---

## 13. DEVELOPER GUIDE — HOW TO ADD FEATURES

### Adding a new action

1. **Define schema** in `core/Infrastructure/actions.py` → add entry to `ACTIONS` dict
2. **Add runtime metadata** in `playbook/actions.json` (progress_updates, timeout, etc.)
3. **Add intent keywords** in `playbook/intent_tree.json` decision tree
4. **Add handler** in `brain/conversation_manager.py` → route the new intent to a handler function
5. **Test**: Verify `from core import ACTIONS` still works (pydantic merge doesn't break)

### Adding a new LLM client

1. **Create file** in `LLM/` (e.g., `LLM/new_client.py`)
2. **Add lazy-load property** in `Mode4Processor` (`core/mode4_processor.py`)
3. **Add to routing table** in `brain/llm_router.py` → `ROUTING_TABLE`
4. **Add model config** in `core/Infrastructure/m1_config.py` (API key, model name)
5. **Add to fallback chain** in `core/Inference/m1_model_router.py` if needed

### Adding a new Bot_action module

1. **Create file** in `Bot_actions/` (e.g., `Bot_actions/new_feature.py`)
2. **Add lazy-load property** in `Mode4Processor`
3. **Add import** in `core/mode4_processor.py` header
4. **Wire intent routing** in `brain/conversation_manager.py`
5. **Create action** if needed (follow "Adding a new action" above)

### Adding a new core module

1. **Create implementation** in appropriate subdirectory:
   - `Infrastructure/` for foundations, persistence, config
   - `InputOutput/` for user-facing translation and feedback
   - `State_Memory/` for context and continuity
   - `Inference/` for LLM execution
2. **Create bridge file** in `core/` (one line: `from core.SubDir.new_module import *`)
3. **Add to `core/__init__.py`** imports and `__all__`

### Running tests

Tests are in `tests/` directory. Must set PYTHONPATH same as `start_mode4.sh`:
```bash
export PYTHONPATH="$BASE_DIR:$CORE_DIR:$INFRA_DIR:$LLM_DIR:$BRAIN_DIR:$ACTIONS_DIR"
python -m pytest tests/
```

---

## 14. OPERATOR GUIDE — HOW TO USE THE BOT

### Email commands

```
Re: W9 Request - send W9 and wiring instructions
From Jason - reply with updated timeline
latest from Sarah - forward to accounting
Draft an email to Jason about the Q4 report
```

### Todo commands

```
Add "Buy milk" to my todo list
show my tasks
mark 3 as done        (or: complete #3, 3 is done)
delete task 5          (requires confirmation — HIGH risk)
```

### Ideas and brainstorming

```
Brainstorm: New product pricing strategy
help me think about marketing approaches
Idea: subscription model for services
finalize #pricing-strategy
show my skills
```

### System commands

```
/status     - Check system health
/help       - Show help
/synthesize <thread_id>  - Thread summary
/start      - Initialize
```

### Queue responses

When the bot presents numbered options:
```
yes 1       - Accept option 1
yes all     - Accept all
no 2        - Reject option 2
review 3    - Review option 3 in detail
```

### Natural conversation

The bot understands natural language via SmartParser:
```
Hello
Hey, can you help me with something?
What do I have to do today?
Remind me to follow up with Sarah
```

---

## 15. DIRECTORY MAP

```
/Users/work/Telgram bot/                    ← ROOT_DIR (on PYTHONPATH)
├── start_mode4.sh                          ← Entry point script
├── .env                                    ← Environment variables
├── mode4.log                               ← Main log file
│
├── core/                                   ← On PYTHONPATH
│   ├── __init__.py                         ← Universal action registry (bridge hub)
│   ├── mode4_processor.py                  ← MAIN ORCHESTRATOR
│   ├── actions.py                          ← Bridge → Infrastructure/actions.py
│   ├── action_extractor.py                 ← Bridge → InputOutput/action_extractor.py
│   ├── action_validator.py                 ← Bridge → InputOutput/action_validator.py
│   ├── ambiguity_resolver.py               ← Bridge → InputOutput/ambiguity_resolver.py
│   ├── context_manager.py                  ← Bridge → State_Memory/context_manager.py
│   ├── conversation_state.py               ← Bridge → State_Memory/conversation_state.py
│   ├── session_state.py                    ← Bridge → State_Memory/session_state.py
│   ├── hybrid_intent_classifier.py         ← Bridge → InputOutput/hybrid_intent_classifier.py
│   ├── intent_tree.py                      ← Bridge → InputOutput/intent_tree.py
│   ├── m1_model_router.py                  ← Bridge → Inference/m1_model_router.py
│   ├── notification_router.py              ← Bridge → InputOutput/notification_router.py
│   ├── observability.py                    ← Bridge → Infrastructure/observability.py
│   ├── safety_interceptor.py               ← Bridge → Infrastructure/safety_interceptor.py
│   ├── update_stream.py                    ← Bridge → InputOutput/update_stream.py
│   │
│   ├── Infrastructure/                     ← On PYTHONPATH — Foundations & Persistence
│   │   ├── actions.py                      ← ACTIONS registry, ActionSchema, RiskLevel
│   │   ├── db_manager.py                   ← SQLite DatabaseManager
│   │   ├── m1_config.py                    ← Central config hub
│   │   ├── observability.py                ← HealthChecker, CircuitBreaker
│   │   └── safety_interceptor.py           ← Risk-based action redirector
│   │
│   ├── InputOutput/                        ← Translation & Feedback
│   │   ├── intent_tree.py                  ← IntentClassifier
│   │   ├── action_extractor.py             ← ActionExtractor (regex + LLM)
│   │   ├── action_validator.py             ← ActionValidator
│   │   ├── ambiguity_resolver.py           ← AmbiguityResolver
│   │   ├── hybrid_intent_classifier.py     ← HybridIntentClassifier
│   │   ├── notification_router.py          ← NotificationRouter
│   │   └── update_stream.py               ← UpdateStream (live status)
│   │
│   ├── State_Memory/                       ← Context & Continuity
│   │   ├── context_manager.py              ← Pronoun resolution
│   │   ├── conversation_state.py           ← State machine (Idle/Executing/Awaiting)
│   │   └── session_state.py                ← Short-term #N memory
│   │
│   └── Inference/                          ← LLM Execution
│       └── m1_model_router.py              ← litellm Router with fallback chain
│
├── brain/                                  ← On PYTHONPATH — Decision-Making
│   ├── conversation_manager.py             ← Intent routing hub (158KB!)
│   ├── llm_router.py                       ← LLM recommendation layer
│   ├── smart_parser.py                     ← NLP parsing via Ollama
│   ├── pattern_matcher.py                  ← Template/contact matching
│   ├── thread_synthesizer.py               ← Email thread summaries
│   └── proactive_engine.py                 ← Background workspace monitor
│
├── LLM/                                    ← On PYTHONPATH — Model Clients & I/O
│   ├── telegram_handler.py                 ← Telegram polling + button callbacks
│   ├── gmail_client.py                     ← Gmail API wrapper
│   ├── ollama_client.py                    ← Local LLM (qwen2.5:3b)
│   ├── claude_client.py                    ← Anthropic Claude API
│   ├── kimi_client.py                      ← NVIDIA/Kimi K2 API
│   ├── gemini_client.py                    ← Google Gemini API
│   ├── sheets_client.py                    ← Google Sheets API
│   └── google_docs_client.py               ← Google Docs API
│
├── Bot_actions/                            ← On PYTHONPATH — Capability Modules
│   ├── todo_manager.py                     ← Task CRUD (Sheets-backed)
│   ├── skill_manager.py                    ← Idea capture + Master Doc
│   ├── idea_bouncer.py                     ← Interactive brainstorming
│   ├── daily_digest.py                     ← Morning email summary
│   ├── on_demand_digest.py                 ← On-demand snapshot
│   ├── queue_processor.py                  ← Offline message queue
│   ├── quick_capture.py                    ← Fast-capture notes
│   ├── template_manager.py                 ← Email templates
│   ├── workflow_manager.py                 ← Multi-step task chains
│   └── file_fetcher.py                     ← Google Drive files
│
├── active/                                 ← M365 Integration (added to sys.path at runtime)
│   ├── graph_client.py                     ← MSAL async wrapper
│   ├── async_session_manager.py            ← Dual httpx sessions
│   ├── file_fetcher.py                     ← Hybrid SharePoint+GDrive
│   ├── sharepoint_list_reader.py           ← SharePoint lists
│   ├── onenote_client.py                   ← OneNote pages
│   ├── onenote_html_sanitizer.py           ← HTML cleanup
│   ├── proactive_engine.py                 ← M365 proactive sync
│   ├── setup_m365_lists.py                 ← List provisioning
│   └── migration_validator.py              ← Readiness checker
│
├── playbook/                               ← Configuration Files
│   ├── intent_tree.json                    ← Decision tree
│   ├── actions.json                        ← Runtime action metadata
│   ├── Personality.json                    ← Bot personality
│   ├── context_rules.json                  ← Context injection rules
│   ├── templates.json                      ← Email templates
│   └── workflows.json                      ← Workflow definitions
│
├── credentials/                            ← Auth Files (NEVER commit)
│   ├── telegram_config.json
│   ├── gmail_credentials.json
│   ├── gmail_token.json
│   ├── sheets_service_account.json
│   ├── microsoft_login.json
│   └── .msal_token_cache.json
│
├── Guides/                                 ← Documentation
│   ├── README_START_HERE.md
│   └── OPENCLAW_RUNBOOK.md                 ← THIS FILE
│
├── possibly_deprecating/                   ← Archived Google-only versions
│
└── mode4/                                  ← LEGACY — DO NOT USE
    ├── .env                                ← (stale copy)
    └── __pycache__/
```

---

## 16. WHAT MODE 4 ACTUALLY DOES (Purpose Statement)

Mode 4 is a **privacy-first operational assistant** that runs on an M1 MacBook. It receives natural language commands via Telegram and:

1. **Drafts emails** — searches Gmail, finds matching threads, generates contextual replies using local (Ollama) or cloud (Claude/Kimi) LLMs, creates Gmail drafts for human review
2. **Manages tasks** — add/complete/delete tasks backed by Google Sheets
3. **Captures ideas** — interactive brainstorming with structured Q&A, finalized to Master Doc
4. **Monitors workspace** — background engine detects stale threads, unsent drafts, approaching deadlines, sends proactive Telegram notifications
5. **Generates digests** — morning summaries of unread emails and pending tasks
6. **Synthesizes threads** — "State of Play" summaries for complex email threads

**Design philosophy**: Local-first (Ollama for speed/cost), escalate to cloud when reasoning demands it. The bot NEVER sends emails directly — it creates drafts for human review (enforced by safety interceptor). All sensitive data stays on the local machine unless the user explicitly chooses a cloud LLM.
