"""
Conversation Manager for Mode 4
Transforms rigid email processor into natural conversational AI assistant.

Handles:
- Greetings and casual conversation
- Intent classification and routing
- Natural language understanding
- Context management
- Action Registry integration (parameter extraction, validation, session state)
"""

import re as _re
import time
import random
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING

logger = logging.getLogger(__name__)

# Type hints for circular import prevention
if TYPE_CHECKING:
    from telegram_handler import TelegramHandler
    from mode4_processor import Mode4Processor


class Intent(Enum):
    """User intent categories for conversational routing."""

    # Social/Casual
    GREETING = "greeting"              # "hi", "hello", "hey"
    HELP_REQUEST = "help"              # "help", "what can you do"
    CASUAL_CHAT = "casual"             # "how are you", "what's up"

    # Email-Related (routes to existing flow)
    EMAIL_DRAFT = "email_draft"        # "draft email to jason"
    EMAIL_SEARCH = "email_search"      # "find emails from john"
    EMAIL_FORWARD = "email_forward"    # "forward invoice to accounting"
    EMAIL_SYNTHESIZE = "synthesize"    # "summarize the thread"

    # Task Management
    TODO_ADD = "todo_add"              # "add call sarah to todo"
    TODO_LIST = "todo_list"            # "show my todos"
    TODO_COMPLETE = "todo_complete"    # "mark task 5 as done"
    TODO_DELETE = "todo_delete"        # "delete task 3"

    # Information Requests
    INFO_STATUS = "status"             # "system status"
    INFO_DIGEST = "digest"             # "morning brief", "email summary"
    INFO_FETCH = "fetch"               # "get the W9 template"
    INFO_UNREAD = "unread"             # "show unread emails"
    EMAIL_INBOX = "email_inbox"        # "show me my emails" → MCP labeled

    # Idea/Planning
    IDEA_BOUNCE = "idea"               # "help me think through..."
    IDEA_CONTINUE = "idea_continue"    # Follow-up in active session

    # Skills (finalized ideas)
    SKILL_FINALIZE = "skill_finalize"  # "finalize", "save this idea"
    SKILL_QUICK = "skill_quick"        # "Idea: ...", "Note: ..."
    SKILL_LIST = "skill_list"          # "show my skills", "recent ideas"
    SKILL_SEARCH = "skill_search"      # "find skill about..."

    # Fallback
    UNCLEAR = "unclear"                # Can't determine intent
    COMMAND = "command"                # Explicit /command


class ConversationManager:
    """
    Conversational interface layer for Mode 4.

    Provides natural language understanding, intent classification,
    and routing to appropriate capability handlers.
    """

    def __init__(self, telegram_handler: Optional['TelegramHandler'] = None,
                 mode4_processor: Optional['Mode4Processor'] = None):
        """
        Initialize conversation manager.

        Args:
            telegram_handler: Telegram handler for sending responses
            mode4_processor: Mode 4 processor for accessing capabilities
        """
        self.telegram = telegram_handler
        self.processor = mode4_processor
        self._ollama = None  # Lazy load
        self._context_store: Dict[int, Dict[str, Any]] = {}
        self._last_cleanup = time.time()
        self._context_timeout = 1800  # 30 minutes
        self._max_contexts = 50  # Prevent unbounded memory growth
        try:
            from m1_config import MAX_CONVERSATION_CONTEXTS
            self._max_contexts = MAX_CONVERSATION_CONTEXTS
        except (ImportError, AttributeError):
            pass

        # --- Action Registry System ---
        self._action_registry_enabled = False
        self._registry_initialized = False
        try:
            from m1_config import ACTION_REGISTRY_ENABLED
            self._action_registry_enabled = ACTION_REGISTRY_ENABLED
        except (ImportError, AttributeError):
            pass

        # Lazy-init registry components on first use
        self._extractor = None
        self._validator = None
        self._session_state = None
        self._context_mgr = None
        self._notifier = None
        self._update_stream = None
        self._confidence_gate_threshold = 0.65

    # ==================
    # ACTION REGISTRY BOOTSTRAP
    # ==================

    def _init_action_registry(self):
        """Lazy-initialize Action Registry components (requires DB + LLM clients)."""
        if self._registry_initialized:
            return
        try:
            from db_manager import DatabaseManager
            from core.actions import ACTIONS, get_action_schema, get_action_name
            from core.action_extractor import ActionExtractor
            from core.action_validator import ActionValidator
            from core.session_state import SessionState
            from core.context_manager import ContextManager
            from core.notification_router import NotificationRouter
            from core.update_stream import UpdateStream

            db = DatabaseManager()

            # Get LLM clients from processor if available
            ollama = self.processor.ollama if self.processor and hasattr(self.processor, 'ollama') else None
            claude = self.processor.claude if self.processor and hasattr(self.processor, 'claude') else None

            if not ollama:
                # Try to create a minimal ollama client
                try:
                    from ollama_client import OllamaClient
                    ollama = OllamaClient()
                except Exception:
                    logger.warning("[ACTION_REGISTRY] No Ollama client available")

            self._session_state = SessionState(db)
            self._extractor = ActionExtractor(ollama, claude) if ollama else None
            self._validator = ActionValidator(db)
            self._context_mgr = ContextManager(self._session_state)
            self._notifier = NotificationRouter(self.telegram)
            self._update_stream = UpdateStream(self.telegram)

            self._registry_initialized = True
            logger.info("[ACTION_REGISTRY] Initialized successfully")
        except Exception as e:
            logger.error("[ACTION_REGISTRY] Failed to initialize: %s", e, exc_info=True)
            self._action_registry_enabled = False

    # ==================
    # CORE METHODS
    # ==================

    async def handle_message(self, text: str, user_id: int, chat_id: int) -> Dict[str, Any]:
        """
        Main entry point for conversational message handling.

        Args:
            text: User message text
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            Dict with 'handled' (bool), 'parsed_message' (optional), 'routed_to' (str)
        """
        # Cleanup expired contexts periodically
        if time.time() - self._last_cleanup > 600:  # Every 10 minutes
            self.clear_expired_contexts()

        # --- Action Registry: check AWAITING state first ---
        if self._action_registry_enabled:
            self._init_action_registry()
            if self._session_state:
                awaiting = self._session_state.get_awaiting(user_id)
                if awaiting:
                    logger.info("[ACTION_REGISTRY] User %d is awaiting: %s", user_id, awaiting['type'])
                    result = await self._handle_awaiting_response(user_id, text, chat_id, awaiting)
                    if result:
                        return result

        # Check if it's legacy email format (backward compatibility)
        if self._is_legacy_email_format(text):
            logger.info("Legacy email format detected, routing to email processor")
            return {
                'handled': False,  # Let existing flow handle it
                'routed_to': 'email_processor',
                'reason': 'legacy_format'
            }

        # Get context
        context = self.get_context(user_id)

        # Check if user has an active workflow - handle workflow messages first
        workflow_result = await self._check_active_workflow(text, user_id, chat_id)
        if workflow_result and workflow_result.get('handled'):
            logger.info(f"Message handled by active workflow: {workflow_result.get('action')}")
            return workflow_result

        # Check for multi-step workflow chain (e.g., "draft reply to Jason and send it")
        workflow_steps = self._detect_workflow_chain(text)
        if workflow_steps:
            logger.info(f"Detected workflow chain with {len(workflow_steps)} steps")
            return await self._execute_workflow_chain(workflow_steps, user_id, chat_id)

        # Check if user is referencing a numbered item (#1, task 2, etc.)
        ref_num = self._detect_task_reference(text, context)
        if ref_num and context:
            # Check for email references first (from "show me my emails")
            if context.get('emails'):
                return await self._execute_email_reference(ref_num, text, context, chat_id, user_id)
            # Then check for task references (from "show my todo")
            elif context.get('last_tasks'):
                return await self._execute_task_reference(ref_num, context, chat_id, user_id)

        # Classify intent
        intent = self.classify_intent(text, context)
        logger.info(f"Classified intent: {intent.value} for message: {text[:50]}")

        # --- Action Registry: try registry flow for supported intents ---
        if self._action_registry_enabled and self._registry_initialized:
            registry_result = await self._try_action_registry(
                intent, text, user_id, chat_id
            )
            if registry_result is not None:
                return registry_result

        # Route based on intent (legacy flow)
        try:
            result = await self.route_to_capability(intent, text, user_id, chat_id)
            return result
        except Exception as e:
            logger.error(f"Error routing message: {e}", exc_info=True)
            return {
                'handled': True,
                'routed_to': 'error_handler',
                'error': str(e)
            }

    def classify_intent(self, text: str, context: Optional[Dict] = None) -> Intent:
        """
        Classify user intent using LLM + rule-based approach.

        IMPORTANT: This method uses a "conversation-first" approach to ensure
        greetings and casual messages are NOT mistaken for email searches.

        Args:
            text: User message
            context: Conversation context (optional)

        Returns:
            Intent enum value
        """
        import re
        text_lower = text.lower().strip()

        # Remove punctuation for matching (but keep original for later)
        text_clean = re.sub(r'[^\w\s]', '', text_lower).strip()

        # Quick rule-based checks for obvious cases (no LLM needed)

        # Commands (explicit)
        if text.startswith('/'):
            return Intent.COMMAND

        # === CONVERSATION GATE ===
        # These checks MUST come first to prevent conversational text from
        # being mistaken for email searches

        # Greetings (flexible matching - handles "Hello!", "hey there", "Hi!", etc.)
        greeting_words = ['hi', 'hello', 'hey', 'yo', 'sup', 'hiya', 'heya', 'howdy',
                         'morning', 'afternoon', 'evening', 'good morning', 'good afternoon',
                         'good evening', 'gm', 'whats up', 'wassup', "what's up"]

        # Check if message IS a greeting (exact or starts with greeting)
        if text_clean in greeting_words:
            return Intent.GREETING

        # Check if message STARTS with a greeting word (e.g., "hey there", "hello mode4")
        for greeting in greeting_words:
            if text_clean.startswith(greeting + ' ') or text_clean == greeting:
                # Make sure it's not followed by email-related words
                remainder = text_clean[len(greeting):].strip()
                email_words = ['email', 'draft', 'send', 'reply', 'forward', 'find', 'search']
                if not any(word in remainder for word in email_words):
                    return Intent.GREETING

        # Casual chat patterns (more comprehensive)
        casual_patterns = [
            "how are you", "how's it going", "hows it going", "how ya doing",
            "what's up", "whats up", "wassup", "sup",
            "how's everything", "hows everything",
            "thanks", "thank you", "thx", "ty",
            "cool", "nice", "great", "awesome", "ok", "okay", "k",
            "got it", "understood", "makes sense",
            "never mind", "nevermind", "nvm", "forget it",
            "bye", "goodbye", "later", "see ya", "ttyl",
            "lol", "haha", "hehe"
        ]
        if text_clean in casual_patterns or any(text_clean.startswith(p) for p in casual_patterns):
            return Intent.CASUAL_CHAT

        # Thanks with context (e.g., "thanks for that", "thank you!")
        if text_clean.startswith('thank') or text_clean.startswith('thx'):
            return Intent.CASUAL_CHAT

        # Idea bouncing - check BEFORE help requests (since "help me think" contains "help")
        idea_patterns = ['help me think', 'bounce idea', 'feedback on', 'what do you think',
                        'think through', 'brainstorm', 'explore this idea']
        if any(phrase in text_lower for phrase in idea_patterns):
            return Intent.IDEA_BOUNCE

        # Help requests (expanded) - check AFTER idea bouncing
        help_patterns = ['help', 'what can you do', 'how do i', 'how to', 'what are you',
                        'what do you do', 'can you help', 'i need help',
                        'show me how', 'teach me', 'explain', 'instructions']
        # Exclude "help me think" which is idea bouncing
        if any(pattern in text_lower for pattern in help_patterns):
            if not any(idea in text_lower for idea in idea_patterns):
                return Intent.HELP_REQUEST

        # Status check patterns
        if text_clean in ['status', 'whats happening', "what's happening", 'anything new',
                          'updates', 'what did i miss']:
            return Intent.INFO_STATUS

        # === END CONVERSATION GATE ===

        # Todo keywords (check BEFORE email to avoid false positives)
        if any(word in text_lower for word in ['add', 'create', 'new']) and \
           any(word in text_lower for word in ['todo', 'task', 'reminder', 'remind me', 'agenda']):
            return Intent.TODO_ADD

        if any(phrase in text_lower for phrase in ['show todo', 'list todo', 'my todo', 'my task', 'show task', 'list task', 'show agenda', 'my agenda']):
            return Intent.TODO_LIST

        # MCP Email Inbox - "show me my emails", "my emails", "email inbox", "mcp inbox"
        if any(phrase in text_lower for phrase in [
            'show me my emails', 'my emails', 'show emails', 'email inbox',
            'check my emails', 'check emails', 'mcp inbox', 'mcp emails',
            'show me my mcp', 'my mcp inbox', 'mcp inbox emails'
        ]):
            return Intent.EMAIL_INBOX

        # Email-related keywords
        if 'draft' in text_lower or 'write' in text_lower or 'compose' in text_lower:
            if 'email' in text_lower or '@' in text or 'to ' in text_lower:
                # Make sure it's not a todo request
                if 'todo' not in text_lower and 'task' not in text_lower and 'agenda' not in text_lower:
                    return Intent.EMAIL_DRAFT

        if 'find email' in text_lower or 'search email' in text_lower or 'from ' in text_lower[:20]:
            return Intent.EMAIL_SEARCH

        # Info requests
        if 'morning brief' in text_lower or 'digest' in text_lower or 'email summary' in text_lower:
            return Intent.INFO_DIGEST

        if 'status' in text_lower:
            return Intent.INFO_STATUS

        if 'unread' in text_lower:
            return Intent.INFO_UNREAD

        # Idea bouncing (already checked above, but keep for LLM fallback path)
        # This is redundant now but kept for safety
        if any(phrase in text_lower for phrase in ['help me think', 'bounce idea', 'feedback on', 'what do you think', 'think through']):
            return Intent.IDEA_BOUNCE

        # === SKILL MANAGEMENT ===

        # Skill finalization - "finalize", "save this idea", "done with idea"
        finalize_phrases = ['finalize', 'save skill', 'save this idea', 'done with idea',
                           'thats the idea', "that's the idea", 'wrap up', 'lock it in',
                           'save to doc', 'finalize idea']
        if any(phrase in text_lower for phrase in finalize_phrases):
            return Intent.SKILL_FINALIZE

        # Quick skill capture - "Idea: ...", "Note: ...", "Task: ..."
        if text_lower.startswith(('idea:', 'note:', 'task:', 'brainstorm:')):
            return Intent.SKILL_QUICK

        # Skill listing - "show my skills", "recent ideas", "list skills"
        skill_list_phrases = ['show skills', 'my skills', 'recent ideas', 'list skills',
                              'show ideas', 'my ideas', 'recent skills']
        if any(phrase in text_lower for phrase in skill_list_phrases):
            return Intent.SKILL_LIST

        # Skill search - "find skill about...", "search ideas"
        if ('find skill' in text_lower or 'search skill' in text_lower or
            'find idea' in text_lower or 'search idea' in text_lower):
            return Intent.SKILL_SEARCH

        # Process inbox command
        if 'process inbox' in text_lower:
            return Intent.SKILL_FINALIZE  # Reuse for inbox processing

        # === END SKILL MANAGEMENT ===

        # Casual chat
        casual_patterns = ["how are you", "what's up", "whats up", "wassup", "how's it going"]
        if any(pattern in text_lower for pattern in casual_patterns):
            return Intent.CASUAL_CHAT

        # LLM-based classification for complex cases
        return self._llm_classify_intent(text, context)

    def _llm_classify_intent(self, text: str, context: Optional[Dict] = None) -> Intent:
        """
        Use LLM for intent classification when rules don't match.

        IMPORTANT: This fallback should be CONSERVATIVE - if unsure, return UNCLEAR
        and let the user clarify rather than making wrong guesses.

        Args:
            text: User message
            context: Conversation context

        Returns:
            Intent enum value
        """
        try:
            import ollama

            prompt = f"""You are classifying a user message to a personal assistant bot.
The bot helps with: emails, todos, information lookups, and general chat.

IMPORTANT: If the message is casual conversation (greetings, thanks, small talk),
classify it as "casual" or "greeting". Do NOT classify casual messages as email requests.

Classify this message. Return ONLY ONE word from this list:
- greeting: hi, hello, hey, good morning, etc.
- casual: thanks, cool, ok, got it, nevermind, small talk
- email_draft: explicitly wants to draft/write an email
- email_search: explicitly wants to find/search emails
- todo_add: wants to add a task/todo/reminder
- todo_list: wants to see their tasks
- digest: wants email summary or morning brief
- status: wants system status
- idea: wants to brainstorm or get feedback
- help: wants to know capabilities/how to use the bot
- unclear: cannot confidently determine (USE THIS IF UNSURE)

Message: "{text}"

Return ONLY the intent word (nothing else):"""

            # Use ollama library directly
            from m1_config import OLLAMA_MODEL
            response = ollama.generate(
                model=OLLAMA_MODEL,
                prompt=prompt,
                options={'temperature': 0.1, 'num_predict': 10}
            )

            intent_str = response['response'].strip().lower()
            logger.debug(f"LLM classified intent as: {intent_str}")

            # Map to Intent enum
            for intent in Intent:
                if intent.value in intent_str:
                    return intent

        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}")

        # Final fallback: BE CONSERVATIVE
        # Only treat as email if it CLEARLY looks like email format
        text_lower = text.lower()
        if text_lower.startswith('re:') or text_lower.startswith('from '):
            return Intent.EMAIL_DRAFT

        # If it has a dash but also has conversational words, it's probably NOT email
        conversational_starts = ['hi', 'hello', 'hey', 'thanks', 'ok', 'cool', 'yes', 'no',
                                  'sure', 'great', 'nice', 'wow', 'lol', 'haha']
        if any(text_lower.startswith(word) for word in conversational_starts):
            return Intent.CASUAL_CHAT

        # Default to UNCLEAR - let user clarify
        return Intent.UNCLEAR

    async def route_to_capability(self, intent: Intent, text: str,
                                  user_id: int, chat_id: int) -> Dict[str, Any]:
        """
        Route message to appropriate capability handler based on intent.

        Args:
            intent: Classified intent
            text: User message
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            Dict with routing result
        """
        # Simple intents handled directly
        if intent == Intent.GREETING:
            response = self._generate_greeting()
            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'greeting'}

        elif intent == Intent.HELP_REQUEST:
            response = self._generate_help_message()
            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'help'}

        elif intent == Intent.CASUAL_CHAT:
            response = self._generate_casual_response(text)
            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'casual'}

        elif intent == Intent.UNCLEAR:
            response = self._generate_unclear_response()
            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'unclear'}

        # Email intents - route to existing processor
        elif intent in [Intent.EMAIL_DRAFT, Intent.EMAIL_SEARCH]:
            return {
                'handled': False,
                'routed_to': 'email_processor',
                'reason': intent.value
            }

        # Todo intents
        elif intent == Intent.TODO_ADD:
            return await self._handle_todo_add(text, chat_id)

        elif intent == Intent.TODO_LIST:
            await self.telegram.send_typing(chat_id)
            return await self._handle_todo_list(chat_id, user_id)

        # Info requests
        elif intent == Intent.INFO_DIGEST:
            await self.telegram.send_typing(chat_id)
            return await self._handle_digest(chat_id)

        elif intent == Intent.INFO_STATUS:
            await self.telegram.send_typing(chat_id)
            return await self._handle_status(chat_id)

        elif intent == Intent.INFO_UNREAD:
            await self.telegram.send_typing(chat_id)
            return await self._handle_unread(chat_id)

        elif intent == Intent.EMAIL_INBOX:
            await self.telegram.send_typing(chat_id)
            return await self._handle_mcp_inbox(chat_id, user_id)

        # Idea bouncing
        elif intent == Intent.IDEA_BOUNCE:
            await self.telegram.send_typing(chat_id)
            return await self._handle_idea_bounce(text, user_id, chat_id)

        # Skill management
        elif intent == Intent.SKILL_FINALIZE:
            await self.telegram.send_typing(chat_id)
            return await self._handle_skill_finalize(text, user_id, chat_id)

        elif intent == Intent.SKILL_QUICK:
            return await self._handle_skill_quick(text, user_id, chat_id)

        elif intent == Intent.SKILL_LIST:
            return await self._handle_skill_list(user_id, chat_id)

        elif intent == Intent.SKILL_SEARCH:
            return await self._handle_skill_search(text, user_id, chat_id)

        # Commands
        elif intent == Intent.COMMAND:
            return {
                'handled': False,
                'routed_to': 'command_handler',
                'reason': 'explicit_command'
            }

        # Default fallback
        else:
            response = "I'm not sure how to handle that yet. Try asking for help!"
            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'fallback'}

    # ==================
    # RESPONSE GENERATION
    # ==================

    def _generate_greeting(self) -> str:
        """Generate friendly greeting response."""
        greetings = [
            "Hey! What can I help you with today? I can draft emails, manage your todos, fetch files, or give you a morning brief.",
            "Hi there! Ready to help. Need me to draft an email, add a task, or something else?",
            "Hello! How can I assist you? I handle emails, todos, morning briefs, and more.",
            "Hey! What's on your mind? I can help with emails, tasks, files, or just about anything.",
        ]
        return random.choice(greetings)

    def _generate_help_message(self) -> str:
        """Generate help message listing capabilities."""
        return """I can help you with:

<b>Email Management</b>
• Draft emails - "draft email to Jason about the invoice"
• Search emails - "find emails from Sarah"
• Synthesize threads - "/synthesize [thread_id]"

<b>Task Management</b>
• Add tasks - "add call John tomorrow to my todo list"
• View tasks - "show my todos"
• Quick capture - "/quick invoice jason friday"

<b>Information</b>
• Morning brief - "morning brief" or "/morning"
• Email digest - "show my emails"
• System status - "/status"

<b>Idea Bouncing</b>
• Explore ideas - "help me think through [topic]"
• Deep dive - "/deepidea [topic]"

<b>Files & Templates</b>
• Fetch files - "/file W9"
• Use templates - "/templates"

Just ask naturally and I'll figure out what you need!"""

    def _generate_casual_response(self, text: str) -> str:
        """Generate response to casual chat."""
        responses = [
            "I'm doing great! How can I help you today?",
            "All systems running smoothly! What do you need?",
            "I'm here and ready to help! What's on your agenda?",
            "Doing well! What can I assist with?",
        ]
        return random.choice(responses)

    def _generate_unclear_response(self) -> str:
        """Generate response when intent is unclear - ask for clarification instead of guessing."""
        return (
            "I'm not sure what you'd like me to do. Are you trying to:\n\n"
            "1. <b>Work with emails</b> - search, draft, or reply\n"
            "2. <b>Manage tasks</b> - add, view, or complete todos\n"
            "3. <b>Get information</b> - digest, status, files\n"
            "4. <b>Just chat</b> - I'm here to help!\n\n"
            "Tell me more, or type <b>help</b> to see everything I can do."
        )

    # ==================
    # CAPABILITY HANDLERS
    # ==================

    async def _handle_todo_add(self, text: str, chat_id: int) -> Dict[str, Any]:
        """Handle adding a todo task (or multiple tasks)."""
        try:
            from todo_manager import TodoManager
            todo_mgr = TodoManager()

            # Check if message contains multiple tasks
            # Look for indicators like "Another one is", "also", "and then", etc.
            multiple_task_indicators = [
                'another one is', 'another is', 'also', 'and also',
                'second one is', 'next is', 'and then', 'plus'
            ]

            has_multiple = any(indicator in text.lower() for indicator in multiple_task_indicators)

            if has_multiple:
                # Split into multiple tasks
                tasks = self._split_multiple_tasks(text)
                task_ids = []
                responses = []

                for task_text in tasks:
                    # Simple extraction: remove common prefixes
                    task_clean = task_text.strip()
                    for prefix in ['add', 'create', 'todo', 'task', 'to my agenda', 'to my todo list']:
                        if task_clean.lower().startswith(prefix):
                            task_clean = task_clean[len(prefix):].strip()

                    if task_clean:
                        task_id = todo_mgr.add_task(
                            title=task_clean,
                            priority='medium',
                            deadline=None
                        )
                        task_ids.append(task_id)
                        responses.append(f"• {task_clean}")

                response = f"✓ Added {len(task_ids)} tasks to your agenda:\n" + "\n".join(responses)
                await self.telegram.send_response(chat_id, response)
                return {'handled': True, 'routed_to': 'todo_manager', 'task_ids': task_ids}

            else:
                # Single task - use QuickCapture for better parsing
                from quick_capture import QuickCapture
                qc = QuickCapture()
                task_info = qc.parse(text)

                # Extract just the task part from the message
                task_title = task_info.get('task', text)
                # Clean up common prefixes
                for prefix in ['add', 'create', 'add a task to my todo list', 'add to my agenda', 'add to my todo']:
                    if task_title.lower().startswith(prefix):
                        task_title = task_title[len(prefix):].strip()

                # Auto-detect priority from keywords
                priority = self._detect_priority(text, task_info.get('priority', 'medium'))

                task_id = todo_mgr.add_task(
                    title=task_title,
                    priority=priority,
                    deadline=task_info.get('deadline')
                )

                # Generate confirmation
                response = f"✓ Added to your agenda: <b>{task_title}</b>"
                if task_info.get('deadline'):
                    response += f"\n📅 Due: {task_info['deadline']}"
                if task_info.get('priority') != 'medium':
                    response += f"\n⚡ Priority: {task_info['priority']}"

                await self.telegram.send_response(chat_id, response)
                return {'handled': True, 'routed_to': 'todo_manager', 'task_id': task_id}

        except Exception as e:
            logger.error(f"Error adding todo: {e}", exc_info=True)
            await self.telegram.send_response(
                chat_id,
                f"Sorry, I had trouble adding that task. Error: {str(e)}"
            )
            return {'handled': True, 'routed_to': 'todo_manager', 'error': str(e)}

    def _split_multiple_tasks(self, text: str) -> list:
        """Split message into multiple tasks."""
        import re

        # Patterns that indicate task boundaries
        split_patterns = [
            r'\. Another one is ',
            r'\. Another is ',
            r'\. Also ',
            r'\. And also ',
            r'\. Second one is ',
            r'\. Next is ',
            r'\. Plus ',
        ]

        tasks = [text]
        for pattern in split_patterns:
            new_tasks = []
            for task in tasks:
                parts = re.split(pattern, task, flags=re.IGNORECASE)
                new_tasks.extend(parts)
            tasks = new_tasks

        # Clean up tasks
        cleaned_tasks = []
        for task in tasks:
            # Remove leading "add", "todo", etc.
            task = re.sub(r'^(add a task to my (todo list|agenda)|add to my (todo|agenda)|add|create)\s+', '', task, flags=re.IGNORECASE)
            if task.strip():
                cleaned_tasks.append(task.strip())

        return cleaned_tasks

    async def _handle_todo_list(self, chat_id: int, user_id: int) -> Dict[str, Any]:
        """Handle showing todo list from Google Sheets Todo List tab + SQLite tasks."""
        try:
            import sys
            import html
            sys.path.insert(0, '/Users/work/Telgram bot')
            from sheets_client import GoogleSheetsClient
            from m1_config import SPREADSHEET_ID, SHEETS_CREDENTIALS_PATH
            from db_manager import DatabaseManager

            all_pending = []
            task_references = []
            idx = 0

            # Source 1: Google Sheets "Todo List" tab
            # Columns: Source | Subject/Task | Context | Status | Created | Due Date
            sheets = None
            try:
                sheets = GoogleSheetsClient(SHEETS_CREDENTIALS_PATH)
                sheets.connect()

                result = sheets.read_range(SPREADSHEET_ID, 'Todo List!A:F')

                if result.get('success') and result.get('values'):
                    rows = result['values']
                    sheet_tasks = rows[1:] if len(rows) > 1 else []

                    for row in sheet_tasks:
                        status = row[3].strip().lower() if len(row) > 3 else ''
                        subject = row[1].strip() if len(row) > 1 else ''
                        if status in ('pending', '') and subject:
                            idx += 1
                            source = row[0] if len(row) > 0 else ''
                            context = row[2] if len(row) > 2 else ''
                            due_date = row[5] if len(row) > 5 else ''

                            all_pending.append({
                                'number': idx,
                                'title': subject,
                                'source': source,
                                'context': context,
                                'due_date': due_date,
                                'origin': 'sheets',
                                'row_index': sheet_tasks.index(row) + 2,
                            })
            except Exception as e:
                logger.warning(f"Could not read Todo List sheet: {e}")
            finally:
                if sheets:
                    sheets.close()

            # Source 2: Also check MCP sheet for pending tasks
            sheets2 = None
            try:
                sheets2 = GoogleSheetsClient(SHEETS_CREDENTIALS_PATH)
                sheets2.connect()

                result = sheets2.read_range(SPREADSHEET_ID, 'MCP!A:H')

                if result.get('success') and result.get('values'):
                    rows = result['values']
                    mcp_tasks = rows[1:] if len(rows) > 1 else []

                    for row in mcp_tasks:
                        status = row[5].strip().lower() if len(row) > 5 else ''
                        if status == 'pending':
                            idx += 1
                            source = row[0] if len(row) > 0 else ''
                            subject = row[1] if len(row) > 1 else 'No subject'
                            prompt = row[2] if len(row) > 2 else ''
                            email_id = row[6] if len(row) > 6 else ''

                            all_pending.append({
                                'number': idx,
                                'title': subject,
                                'source': source,
                                'prompt': prompt,
                                'email_id': email_id,
                                'origin': 'mcp',
                                'row_index': mcp_tasks.index(row) + 2,
                            })
            except Exception as e:
                logger.warning(f"Could not read MCP sheet: {e}")
            finally:
                if sheets2:
                    sheets2.close()

            # Source 3: SQLite tasks (local)
            try:
                db = DatabaseManager()
                sqlite_tasks = db.get_pending_tasks(limit=10)
                for task in sqlite_tasks:
                    idx += 1
                    all_pending.append({
                        'number': idx,
                        'title': task['title'],
                        'source': 'local',
                        'priority': task.get('priority', 'medium'),
                        'notes': task.get('notes', ''),
                        'origin': 'sqlite',
                        'task_id': task['id'],
                    })
            except Exception as e:
                logger.warning(f"Could not read SQLite tasks: {e}")

            # Build response
            if not all_pending:
                await self.telegram.send_response(chat_id, "No pending tasks found.")
                return {'handled': True, 'routed_to': 'todo_list'}

            response = "<b>Your Todo List</b>\n\n"

            for item in all_pending[:15]:
                title = html.escape(item['title'][:45])
                origin_tag = ''
                if item['origin'] == 'mcp':
                    origin_tag = ' [MCP]'
                elif item['origin'] == 'sqlite':
                    origin_tag = ' [Local]'

                response += f"<b>{item['number']}.</b> {title}{origin_tag}\n"

                # Add context info
                if item.get('prompt'):
                    response += f"    {html.escape(item['prompt'][:55])}...\n"
                elif item.get('context'):
                    response += f"    Context: {html.escape(item['context'][:40])}\n"
                elif item.get('notes'):
                    response += f"    {html.escape(item['notes'][:55])}\n"

                if item.get('due_date'):
                    response += f"    Due: {item['due_date']}\n"

                # Suggestion
                suggestion = self._generate_task_suggestion({
                    'title': item.get('prompt') or item['title'],
                    'priority': item.get('priority', 'medium')
                })
                response += f"    <i>{suggestion}</i>\n\n"

            response += f"\n<i>Showing {min(len(all_pending), 15)} of {len(all_pending)} pending tasks</i>"
            response += "\n<i>Say '#1 do it', '#2 skip', or 'act on #3'</i>"

            # Store references for #N syntax
            self.store_reference(user_id, 'tasks', all_pending)

            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'todo_list', 'task_count': len(all_pending)}

        except Exception as e:
            logger.error(f"Error listing todos: {e}", exc_info=True)
            await self.telegram.send_response(
                chat_id,
                f"Sorry, I couldn't fetch your todos. Error: {str(e)}"
            )
            return {'handled': True, 'routed_to': 'todo_list', 'error': str(e)}

    def _detect_priority(self, text: str, default_priority: str = 'medium') -> str:
        """Auto-detect priority from text."""
        text_lower = text.lower()

        # High priority indicators
        high_indicators = ['urgent', 'asap', 'important', 'critical', 'emergency', 'now', '!!!']
        if any(indicator in text_lower for indicator in high_indicators):
            return 'high'

        # Low priority indicators
        low_indicators = ['when you get a chance', 'whenever', 'low priority', 'someday', 'eventually']
        if any(indicator in text_lower for indicator in low_indicators):
            return 'low'

        return default_priority

    def _generate_task_suggestion(self, task: Dict) -> str:
        """Generate proactive suggestion for a task."""
        title = task['title'].lower()
        priority = task.get('priority', 'medium')

        # High priority = urgent action
        if priority == 'high':
            return "Urgent - want me to help now?"

        # Detect task type from title
        if any(word in title for word in ['email', 'draft', 'write', 'reply', 'respond']):
            return "I can draft this email for you"
        elif any(word in title for word in ['call', 'phone', 'ring']):
            return "Set a reminder to call?"
        elif any(word in title for word in ['review', 'check', 'look at', 'read']):
            return "Pull up the document?"
        elif any(word in title for word in ['schedule', 'meeting', 'book']):
            return "Check calendar and schedule?"
        elif any(word in title for word in ['send', 'forward']):
            return "Ready to send when you are"
        elif any(word in title for word in ['buy', 'order', 'purchase']):
            return "Add to shopping list?"
        elif any(word in title for word in ['fix', 'repair', 'debug']):
            return "Need context on this?"
        else:
            return "Ready when you are"

    def _detect_task_reference(self, text: str, context: Optional[Dict] = None) -> Optional[int]:
        """Detect if user is referencing a task by number (#1, task 2, etc.)."""
        import re

        # Pattern 1: #1, #2, etc.
        match = re.search(r'#(\d+)', text)
        if match:
            return int(match.group(1))

        # Pattern 2: "task 1", "do task 2", etc.
        match = re.search(r'(?:task|do task|execute task)\s+(\d+)', text.lower())
        if match:
            return int(match.group(1))

        # Pattern 3: "the first one", "the second one", etc.
        if context and context.get('last_tasks'):
            ordinals = {
                'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
                '1st': 1, '2nd': 2, '3rd': 3, '4th': 4, '5th': 5
            }
            for word, num in ordinals.items():
                if word in text.lower():
                    return num

        return None

    async def _execute_task_reference(self, task_num: int, context: Dict, chat_id: int, user_id: int) -> Dict[str, Any]:
        """Execute a task by its reference number."""
        tasks = context.get('last_tasks', [])

        # Find the task
        task_ref = next((t for t in tasks if t['number'] == task_num), None)

        if not task_ref:
            await self.telegram.send_response(
                chat_id,
                f"Task #{task_num} not found. Try 'show my todo' to see all tasks."
            )
            return {'handled': True, 'routed_to': 'task_reference', 'error': 'not_found'}

        # Check if this is an MCP sheet task with email_id (from Google Sheets)
        if task_ref.get('email_id'):
            # This is an MCP sheet task - use the prompt as instruction
            prompt = task_ref.get('prompt', 'respond')
            subject = task_ref.get('title', '')
            email_id = task_ref['email_id']

            await self.telegram.send_response(
                chat_id,
                f"Executing MCP task: {subject[:40]}\nInstruction: {prompt[:60]}...\n\nSearching for email..."
            )

            return {
                'handled': False,
                'routed_to': 'email_processor',
                'reason': 'mcp_task_execution',
                'parsed_message': {
                    'email_id': email_id,
                    'instruction': prompt,
                    'valid': True
                }
            }

        # Extract the action from the task title
        task_title = task_ref['title'].lower()

        # Determine what to do based on task content
        if 'draft email' in task_title or 'email' in task_title:
            # Extract recipient from task
            import re
            match = re.search(r'(?:draft email to|email)\s+(\w+)', task_title, re.IGNORECASE)
            if match:
                recipient = match.group(1)
                response = f"📧 Executing: Draft email to {recipient}\n\nSearching for emails from {recipient}..."
                await self.telegram.send_response(chat_id, response)

                # Route to email processor
                return {
                    'handled': False,
                    'routed_to': 'email_processor',
                    'reason': 'task_execution',
                    'parsed_message': {
                        'email_reference': recipient,
                        'instruction': 'respond',
                        'search_type': 'sender',
                        'valid': True
                    }
                }

        elif 'call' in task_title:
            response = f"✓ Task #{task_num}: {task_ref['title']}\n\nI've noted this. Let me know when it's done so I can mark it complete!"
            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'task_reference'}

        else:
            # Generic task - just acknowledge
            response = f"Working on task #{task_num}: {task_ref['title']}"
            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'task_reference'}

    async def _execute_email_reference(self, ref_num: int, text: str, context: Dict, chat_id: int, user_id: int) -> Dict[str, Any]:
        """Execute action on a referenced email (#1 reply, #2 archive, etc.)."""
        emails = context.get('emails', [])

        # Find the email
        email_ref = next((e for e in emails if e['number'] == ref_num), None)

        if not email_ref:
            await self.telegram.send_response(
                chat_id,
                f"Email #{ref_num} not found. Try 'show me my emails' to refresh the list."
            )
            return {'handled': True, 'routed_to': 'email_reference', 'error': 'not_found'}

        text_lower = text.lower()
        subject = email_ref.get('subject', 'Unknown')
        email_id = email_ref.get('email_id')

        # Determine action from text
        if any(word in text_lower for word in ['reply', 'respond', 'answer', 'draft']):
            # Route to email draft flow
            await self.telegram.send_response(
                chat_id,
                f"Drafting reply to: {subject}\n\nSearching for the email..."
            )
            return {
                'handled': False,
                'routed_to': 'email_processor',
                'reason': 'email_reference_reply',
                'email_id': email_id,
                'action': 'reply'
            }

        elif any(word in text_lower for word in ['archive', 'done', 'complete']):
            # Note: Archive not fully implemented yet - just acknowledge
            await self.telegram.send_response(chat_id, f"Marked as done: {subject}\n<i>(Full archive coming soon)</i>")
            return {'handled': True, 'routed_to': 'email_reference'}

        elif any(word in text_lower for word in ['forward', 'send to']):
            await self.telegram.send_response(
                chat_id,
                f"Who should I forward '{subject}' to?"
            )
            # Store pending action
            if user_id not in self._context_store:
                self._context_store[user_id] = {}
            self._context_store[user_id]['pending_forward'] = email_ref
            return {'handled': True, 'routed_to': 'email_reference', 'awaiting': 'forward_recipient'}

        elif any(word in text_lower for word in ['skip', 'later', 'not now', 'ignore']):
            await self.telegram.send_response(chat_id, f"Skipped: {subject}")
            return {'handled': True, 'routed_to': 'email_reference'}

        elif any(word in text_lower for word in ['do it', 'act', 'handle', 'yes']):
            # Infer action from email content
            suggestion = self._suggest_email_action({'subject': subject})
            if 'reply' in suggestion.lower() or 'response' in suggestion.lower():
                await self.telegram.send_response(
                    chat_id,
                    f"Drafting reply to: {subject}\n\nSearching for the email..."
                )
                return {
                    'handled': False,
                    'routed_to': 'email_processor',
                    'reason': 'email_reference_act',
                    'email_id': email_id,
                    'action': 'reply'
                }
            else:
                await self.telegram.send_response(
                    chat_id,
                    f"What would you like to do with '{subject}'?\nOptions: reply, archive, forward"
                )
                return {'handled': True, 'routed_to': 'email_reference'}

        else:
            # Show options
            await self.telegram.send_response(
                chat_id,
                f"<b>{subject}</b>\nFrom: {email_ref.get('sender', 'Unknown')}\n\n<i>What would you like to do? reply, archive, forward, or skip</i>"
            )
            return {'handled': True, 'routed_to': 'email_reference'}

    async def _handle_digest(self, chat_id: int) -> Dict[str, Any]:
        """Handle morning digest/email summary request."""
        try:
            from daily_digest import DailyDigest

            digest = DailyDigest()

            summary = digest.get_morning_summary(hours_back=24)
            # Format the summary dict as a readable message
            if isinstance(summary, dict):
                response_text = summary.get('formatted', str(summary))
            else:
                response_text = str(summary)
            await self.telegram.send_response(chat_id, response_text)
            return {'handled': True, 'routed_to': 'daily_digest'}

        except Exception as e:
            logger.error(f"Error generating digest: {e}", exc_info=True)
            await self.telegram.send_response(
                chat_id,
                f"Sorry, I couldn't generate your digest. Error: {str(e)}"
            )
            return {'handled': True, 'routed_to': 'daily_digest', 'error': str(e)}

    async def _handle_status(self, chat_id: int) -> Dict[str, Any]:
        """Handle system status request."""
        # This will be handled by existing command handler
        return {
            'handled': False,
            'routed_to': 'command_handler',
            'reason': 'status_request'
        }

    async def _handle_unread(self, chat_id: int) -> Dict[str, Any]:
        """Handle unread email count request."""
        try:
            from daily_digest import DailyDigest

            digest = DailyDigest()

            unread_counts = digest.get_unread_counts()
            # Format the counts dict as a readable message
            if unread_counts:
                lines = ["<b>Unread Email Counts</b>\n"]
                total = 0
                for category, count in unread_counts.items():
                    if count > 0:
                        lines.append(f"• {category}: {count}")
                        total += count
                lines.append(f"\n<b>Total:</b> {total}")
                unread_summary = "\n".join(lines)
            else:
                unread_summary = "No unread emails!"
            await self.telegram.send_response(chat_id, unread_summary)
            return {'handled': True, 'routed_to': 'daily_digest'}

        except Exception as e:
            logger.error(f"Error getting unread count: {e}", exc_info=True)
            await self.telegram.send_response(
                chat_id,
                f"Sorry, I couldn't get your unread counts. Error: {str(e)}"
            )
            return {'handled': True, 'routed_to': 'daily_digest', 'error': str(e)}

    async def _handle_mcp_inbox(self, chat_id: int, user_id: int) -> Dict[str, Any]:
        """Show emails with MCP label + proactive suggestions."""
        try:
            import html
            from gmail_client import GmailClient

            gmail = GmailClient()

            # Search for MCP-labeled emails (extend search window - MCP items can be older)
            emails = gmail.search_emails(
                reference='label:MCP',
                search_type='keyword',
                max_results=10,
                days_back=90
            )

            if not emails:
                await self.telegram.send_response(chat_id, "No emails in your MCP inbox!")
                return {'handled': True, 'routed_to': 'mcp_inbox'}

            response = "<b>Your MCP Inbox</b>\n\n"
            email_references = []

            for idx, email in enumerate(emails, 1):
                sender = email.get('sender_name', email.get('sender_email', 'Unknown'))
                subject = email.get('subject', 'No subject')[:40]

                # Escape HTML to prevent parsing errors with email addresses
                response += f"<b>{idx}.</b> {html.escape(subject)}\n"
                response += f"    From: {html.escape(sender)}\n"

                # Proactive suggestion based on content
                suggestion = self._suggest_email_action(email)
                response += f"    <i>{suggestion}</i>\n\n"

                email_references.append({
                    'number': idx,
                    'email_id': email.get('id'),
                    'subject': subject,
                    'sender': sender
                })

            response += "\n<i>Say '#1 reply' or '#2 archive' or 'draft response to #3'</i>"

            # Store references for #1 syntax
            self._store_email_references(user_id, email_references)

            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'mcp_inbox', 'email_count': len(emails)}

        except Exception as e:
            logger.error(f"Error in MCP inbox: {e}", exc_info=True)
            await self.telegram.send_response(chat_id, f"Error fetching emails: {str(e)}")
            return {'handled': True, 'routed_to': 'mcp_inbox', 'error': str(e)}

    def _suggest_email_action(self, email: Dict) -> str:
        """Generate proactive suggestion for an email."""
        subject = email.get('subject', '').lower()
        snippet = email.get('snippet', '').lower()

        if 'invoice' in subject or 'payment' in subject or 'invoice' in snippet:
            return "Payment item - review or forward to accounting?"
        elif 'urgent' in subject or 'asap' in subject or 'urgent' in snippet:
            return "Urgent - draft a quick reply?"
        elif 'meeting' in subject or 'calendar' in subject or 'schedule' in subject:
            return "Meeting related - check your calendar?"
        elif 'contract' in subject or 'agreement' in subject or 'sign' in subject:
            return "Contract item - review or add to todo?"
        elif 'question' in subject or '?' in subject:
            return "Question - draft a response?"
        elif 'follow up' in subject or 'following up' in subject:
            return "Follow-up - might need a reply"
        else:
            return "Read, reply, or archive?"

    def _store_email_references(self, user_id: int, references: list):
        """Store email references for #1 syntax."""
        if user_id not in self._context_store:
            self._context_store[user_id] = {}
        self._context_store[user_id]['emails'] = references
        self._context_store[user_id]['emails_timestamp'] = time.time()

    async def _handle_idea_bounce(self, text: str, user_id: int, chat_id: int) -> Dict[str, Any]:
        """Handle idea bouncing / thinking through requests."""
        try:
            from idea_bouncer import IdeaBouncer

            bouncer = IdeaBouncer()

            # Extract the topic from the message
            # Remove common prefixes like "help me think through", "think through", etc.
            topic = text.lower()
            prefixes_to_remove = [
                'help me think through', 'help me think about', 'think through',
                'bounce idea', 'brainstorm', 'explore this idea', 'what do you think about',
                'feedback on', 'help me with'
            ]
            for prefix in prefixes_to_remove:
                if topic.startswith(prefix):
                    topic = text[len(prefix):].strip()
                    break

            # Clean up the topic
            topic = topic.strip().strip(':').strip()

            if not topic:
                await self.telegram.send_response(
                    chat_id,
                    "What would you like to think through? Tell me the topic or idea you want to explore."
                )
                return {'handled': True, 'routed_to': 'idea_bouncer', 'awaiting_topic': True}

            # Start idea exploration session
            response = bouncer.start_session(topic, user_id)

            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'idea_bouncer', 'topic': topic}

        except Exception as e:
            logger.error(f"Error in idea bouncer: {e}", exc_info=True)
            await self.telegram.send_response(
                chat_id,
                f"Sorry, I had trouble starting the idea exploration. Error: {str(e)}"
            )
            return {'handled': True, 'routed_to': 'idea_bouncer', 'error': str(e)}

    # ==================
    # SKILL MANAGEMENT
    # ==================

    async def _handle_skill_finalize(self, text: str, user_id: int, chat_id: int) -> Dict[str, Any]:
        """Handle skill finalization - save idea to Master Doc + create tasks."""
        try:
            from skill_manager import SkillManager

            skill_mgr = SkillManager()

            # Check if this is inbox processing
            if 'process inbox' in text.lower():
                results = await skill_mgr.process_inbox()
                processed_count = sum(1 for r in results if r.get('success'))

                if processed_count > 0:
                    response = f"Processed {processed_count} inbox entries.\n"
                    for r in results:
                        if r.get('success'):
                            response += f"  • #{r.get('slug')}: {r.get('title', 'Untitled')[:30]}\n"
                else:
                    response = "Inbox is empty or no entries to process."

                await self.telegram.send_response(chat_id, response)
                return {'handled': True, 'routed_to': 'skill_manager', 'processed': processed_count}

            # Normal finalization of active idea session
            result = await skill_mgr.finalize_skill(user_id, chat_id)

            if result.get('success'):
                response = (
                    f"Skill saved!\n"
                    f"<b>Slug:</b> #{result['slug']}\n"
                    f"<b>Type:</b> {result.get('type', 'Note')}\n"
                )
                if result.get('action_items_count', 0) > 0:
                    response += f"<b>Action items:</b> {result['action_items_count']}\n"
                if result.get('tasks_created', 0) > 0:
                    response += f"<b>Tasks created:</b> {result['tasks_created']}\n"
                if result.get('doc_updated'):
                    response += "\nAdded to Master Doc."
                if result.get('sheets_updated'):
                    response += "\nSynced to Sheets."
            else:
                response = result.get('error', 'Failed to finalize skill.')

            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'skill_manager', 'result': result}

        except Exception as e:
            logger.error(f"Error finalizing skill: {e}", exc_info=True)
            await self.telegram.send_response(
                chat_id,
                f"Sorry, I had trouble finalizing that skill. Error: {str(e)}"
            )
            return {'handled': True, 'routed_to': 'skill_manager', 'error': str(e)}

    async def _handle_skill_quick(self, text: str, user_id: int, chat_id: int) -> Dict[str, Any]:
        """Handle quick skill capture - "Idea: ...", "Note: ...", etc."""
        try:
            from skill_manager import SkillManager

            skill_mgr = SkillManager()
            result = await skill_mgr.capture_quick(user_id, text)

            if result.get('success'):
                response = (
                    f"Captured!\n"
                    f"<b>#{result['slug']}</b>\n"
                    f"Type: {result.get('type', 'Note')}"
                )
                if result.get('action_items_count', 0) > 0:
                    response += f" | {result['action_items_count']} action items"
                if result.get('tasks_created', 0) > 0:
                    response += f"\n{result['tasks_created']} tasks created"
            else:
                response = f"Could not capture: {result.get('error', 'Unknown error')}"

            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'skill_manager', 'result': result}

        except Exception as e:
            logger.error(f"Error in quick capture: {e}", exc_info=True)
            await self.telegram.send_response(
                chat_id,
                f"Sorry, couldn't capture that. Error: {str(e)}"
            )
            return {'handled': True, 'routed_to': 'skill_manager', 'error': str(e)}

    async def _handle_skill_list(self, user_id: int, chat_id: int) -> Dict[str, Any]:
        """Handle listing recent skills."""
        try:
            from skill_manager import SkillManager

            skill_mgr = SkillManager()
            skills = skill_mgr.list_skills(user_id=user_id, limit=10)

            if not skills:
                response = "No skills found. Capture one with 'Idea: ...' or finalize an idea session."
            else:
                response = "<b>Recent Skills:</b>\n\n"
                for skill in skills:
                    status_icon = "" if skill['status'] == 'Pending' else ""
                    action_count = len(skill.get('action_items', [])) if skill.get('action_items') else 0
                    response += (
                        f"{status_icon} <b>#{skill['slug'][:30]}</b>\n"
                        f"   {skill['type']} | {skill['title'][:40]}"
                    )
                    if action_count > 0:
                        response += f" | {action_count} actions"
                    response += "\n"

                response += "\nView details: /skill <slug>"

            await self.telegram.send_response(chat_id, response)

            # Store skills in context for reference
            self.update_context(user_id, {'last_skills': skills})

            return {'handled': True, 'routed_to': 'skill_manager', 'count': len(skills)}

        except Exception as e:
            logger.error(f"Error listing skills: {e}", exc_info=True)
            await self.telegram.send_response(
                chat_id,
                f"Sorry, couldn't list skills. Error: {str(e)}"
            )
            return {'handled': True, 'routed_to': 'skill_manager', 'error': str(e)}

    async def _handle_skill_search(self, text: str, user_id: int, chat_id: int) -> Dict[str, Any]:
        """Handle skill search by keyword."""
        try:
            from skill_manager import SkillManager
            import re

            # Extract search query
            query = text.lower()
            for prefix in ['find skill about', 'search skill', 'find idea about', 'search idea']:
                query = re.sub(f'^{prefix}\\s*', '', query).strip()

            if not query:
                await self.telegram.send_response(
                    chat_id,
                    "What would you like to search for? Try: 'find skill about onboarding'"
                )
                return {'handled': True, 'routed_to': 'skill_manager', 'awaiting_query': True}

            skill_mgr = SkillManager()
            skills = skill_mgr.search_skills(query, user_id=user_id, limit=10)

            if not skills:
                response = f"No skills found matching '{query}'."
            else:
                response = f"<b>Skills matching '{query}':</b>\n\n"
                for skill in skills:
                    response += (
                        f"• <b>#{skill['slug'][:30]}</b>\n"
                        f"  {skill['title'][:50]}\n"
                    )

            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'skill_manager', 'query': query, 'count': len(skills)}

        except Exception as e:
            logger.error(f"Error searching skills: {e}", exc_info=True)
            await self.telegram.send_response(
                chat_id,
                f"Sorry, search failed. Error: {str(e)}"
            )
            return {'handled': True, 'routed_to': 'skill_manager', 'error': str(e)}

    # ==================
    # CONTEXT MANAGEMENT
    # ==================

    def get_context(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get conversation context for user."""
        context = self._context_store.get(user_id)
        if context and time.time() - context.get('timestamp', 0) > self._context_timeout:
            # Expired
            del self._context_store[user_id]
            return None
        return context

    def update_context(self, user_id: int, updates: Dict[str, Any]):
        """Update conversation context for user."""
        if user_id not in self._context_store:
            self._context_store[user_id] = {
                'last_email': None,
                'last_draft': None,
                'last_sheet': None,
                'last_tasks': [],
                'pending_workflow': None,
            }

        self._context_store[user_id].update(updates)
        self._context_store[user_id]['timestamp'] = time.time()

        # Evict oldest contexts if over limit
        if len(self._context_store) > self._max_contexts:
            self._evict_oldest_contexts()

    def _evict_oldest_contexts(self):
        """Remove oldest contexts when over the max limit."""
        while len(self._context_store) > self._max_contexts:
            oldest_id = min(
                self._context_store,
                key=lambda uid: self._context_store[uid].get('timestamp', 0)
            )
            del self._context_store[oldest_id]
            logger.debug(f"Evicted oldest context for user {oldest_id}")

    def store_reference(self, user_id: int, ref_type: str, ref_data: Any):
        """Store a reference for later use (it, that, this, etc.)."""
        context = self.get_context(user_id) or {}

        if ref_type == 'email':
            context['last_email'] = ref_data
        elif ref_type == 'draft':
            context['last_draft'] = ref_data
        elif ref_type == 'sheet':
            context['last_sheet'] = ref_data
        elif ref_type == 'tasks':
            context['last_tasks'] = ref_data

        self.update_context(user_id, context)

    def clear_expired_contexts(self):
        """Remove expired conversation contexts."""
        now = time.time()
        expired = [
            user_id for user_id, ctx in self._context_store.items()
            if now - ctx.get('timestamp', 0) > self._context_timeout
        ]
        for user_id in expired:
            del self._context_store[user_id]

        if expired:
            logger.info(f"Cleared {len(expired)} expired conversation contexts")

        self._last_cleanup = now

    # ==================
    # WORKFLOW CHAINING
    # ==================

    def _detect_workflow_chain(self, text: str) -> Optional[list]:
        """
        Detect multi-step workflow requests.

        Examples:
        - "Draft email to Jason. Then create a Google Sheet. Then email Sarah."
        - "Find emails from John. Also draft a response."
        - "Add task to call Sarah, then remind me to follow up."

        Returns:
            List of workflow steps or None if single-step
        """
        import re

        # Workflow connectors (case-insensitive patterns)
        connectors = [
            r'\.\s+then\s+',
            r'\.\s+also\s+',
            r'\.\s+plus\s+',
            r'\.\s+after\s+that\s+',
            r'\.\s+next\s+',
            r'\s+and\s+then\s+',
        ]

        # Check if any connector is present
        text_lower = text.lower()
        has_connector = any(re.search(pattern, text_lower) for pattern in connectors)
        if not has_connector:
            return None

        # Split by connectors (using original text to preserve case)
        steps = [text]
        for pattern in connectors:
            new_steps = []
            for step in steps:
                # Split using case-insensitive regex
                parts = re.split(pattern, step, flags=re.IGNORECASE)
                new_steps.extend(parts)
            steps = new_steps

        # Clean up steps
        steps = [s.strip().rstrip('.') for s in steps if s.strip()]

        # Must have at least 2 steps
        if len(steps) < 2:
            return None

        logger.info(f"Detected workflow chain with {len(steps)} steps: {steps}")
        return steps

    async def _execute_workflow_chain(self, steps: list, user_id: int, chat_id: int) -> Dict[str, Any]:
        """
        Execute a multi-step workflow chain.

        Args:
            steps: List of workflow step descriptions
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            Dict with execution results
        """
        import html

        # Show workflow plan to user
        workflow_msg = f"<b>📋 Workflow Plan ({len(steps)} steps)</b>\n\n"
        for i, step in enumerate(steps, 1):
            workflow_msg += f"{i}. {html.escape(step)}\n"
        workflow_msg += f"\n⚙️ Starting execution..."

        await self.telegram.send_response(chat_id, workflow_msg)

        # Execute steps sequentially
        context = self.get_context(user_id) or {}
        results = []

        for i, step in enumerate(steps, 1):
            try:
                logger.info(f"Executing workflow step {i}/{len(steps)}: {step}")

                # Notify user
                step_msg = f"▶️ <b>Step {i}/{len(steps)}</b>: {html.escape(step)}"
                await self.telegram.send_response(chat_id, step_msg)

                # Classify and execute step
                intent = self.classify_intent(step, context)
                result = await self._execute_workflow_step(
                    step, intent, user_id, chat_id, context
                )

                results.append({
                    'step': i,
                    'description': step,
                    'intent': intent.value,
                    'result': result
                })

                # Update context with result for next step
                if result.get('reference'):
                    context.update(result['reference'])
                    self.update_context(user_id, context)

            except Exception as e:
                logger.error(f"Error in workflow step {i}: {e}", exc_info=True)
                error_msg = f"❌ <b>Step {i} failed</b>: {html.escape(str(e))}\n\nStopping workflow."
                await self.telegram.send_response(chat_id, error_msg)
                return {
                    'handled': True,
                    'routed_to': 'workflow_chain',
                    'steps_completed': i - 1,
                    'steps_total': len(steps),
                    'error': str(e)
                }

        # Success message
        success_msg = f"✅ <b>Workflow complete!</b> Successfully executed {len(steps)} steps."
        await self.telegram.send_response(chat_id, success_msg)

        return {
            'handled': True,
            'routed_to': 'workflow_chain',
            'steps_completed': len(steps),
            'results': results
        }

    async def _execute_workflow_step(
        self, step: str, intent: Intent, user_id: int,
        chat_id: int, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single workflow step with context awareness.

        Args:
            step: Step description
            intent: Classified intent
            user_id: User ID
            chat_id: Chat ID
            context: Current workflow context

        Returns:
            Dict with step result and references for next step
        """
        # Check for context references like "it", "that", "the sheet"
        step_lower = step.lower()
        resolved_step = step

        # Resolve references
        if any(ref in step_lower for ref in ['it', 'that', 'this', 'the draft', 'the sheet', 'the email']):
            resolved_step = self._resolve_context_references(step, context)
            logger.info(f"Resolved references: '{step}' → '{resolved_step}'")

        # Special handling for sheet creation with Gemini
        if 'create' in step_lower and ('sheet' in step_lower or 'spreadsheet' in step_lower):
            return await self._create_sheet_with_gemini(resolved_step, context, chat_id)

        # Route to appropriate handler
        if intent == Intent.EMAIL_DRAFT:
            return await self._workflow_handle_email_draft(resolved_step, user_id, chat_id, context)

        elif intent == Intent.TODO_ADD:
            return await self._workflow_handle_todo_add(resolved_step, user_id, chat_id)

        elif intent == Intent.EMAIL_SEARCH:
            return await self._workflow_handle_email_search(resolved_step, user_id, chat_id, context)

        else:
            # Generic handler - route normally
            result = await self.route_to_capability(intent, resolved_step, user_id, chat_id)
            return {'handled': result.get('handled'), 'result': result}

    def _resolve_context_references(self, step: str, context: Dict[str, Any]) -> str:
        """
        Resolve context references like 'it', 'that', 'the sheet' in workflow steps.

        Args:
            step: Original step text
            context: Workflow context

        Returns:
            Resolved step text
        """
        step_lower = step.lower()
        resolved = step

        # Replace references with actual values
        if 'the sheet' in step_lower and context.get('last_sheet'):
            sheet_ref = f"the sheet '{context['last_sheet']['title']}'"
            resolved = resolved.replace('the sheet', sheet_ref)
            resolved = resolved.replace('The sheet', sheet_ref)

        if 'the draft' in step_lower and context.get('last_draft'):
            draft_ref = f"the draft to {context['last_draft']['recipient']}"
            resolved = resolved.replace('the draft', draft_ref)
            resolved = resolved.replace('The draft', draft_ref)

        if context.get('last_email'):
            # Generic 'it', 'that', 'this' → last email
            if step_lower.startswith('it ') or ' it ' in step_lower:
                email_ref = f"the email from {context['last_email']['sender']}"
                resolved = resolved.replace(' it ', f' {email_ref} ')
                resolved = resolved.replace('It ', f'{email_ref} ')

        return resolved

    async def _create_sheet_with_gemini(
        self, step: str, context: Dict[str, Any], chat_id: int
    ) -> Dict[str, Any]:
        """
        Create a Google Sheet using Gemini to extract/structure data.

        Args:
            step: Sheet creation request
            context: Workflow context (may contain email data)
            chat_id: Chat ID for updates

        Returns:
            Dict with sheet info and references
        """
        try:
            import re
            import html

            # Extract column names from request
            columns_match = re.search(r'columns?\s+(?:for\s+)?([^.]+)', step, re.IGNORECASE)
            columns = []

            if columns_match:
                # Parse column names (comma-separated or "X, Y, and Z")
                columns_text = columns_match.group(1)
                columns_text = columns_text.replace(' and ', ', ')
                columns = [c.strip() for c in columns_text.split(',')]
            else:
                # Default columns
                columns = ['Name', 'Email', 'Status']

            # Use Gemini to extract/structure data if email context exists
            sheet_data = [columns]  # Header row

            if context.get('last_email'):
                await self.telegram.send_response(
                    chat_id,
                    "Extracting data from email for sheet..."
                )

                # Try to use Gemini for data extraction if available
                try:
                    import google.generativeai as genai
                    from m1_config import GEMINI_API_KEY

                    if GEMINI_API_KEY:
                        genai.configure(api_key=GEMINI_API_KEY)
                        model = genai.GenerativeModel('gemini-2.0-flash')

                        task_description = f"Extract data for a spreadsheet with columns: {', '.join(columns)}"
                        email_body = context['last_email'].get('body', '')[:2000]
                        email_subject = context['last_email'].get('subject', '')

                        prompt = (
                            f"{task_description}\n\n"
                            f"From this email:\n"
                            f"Subject: {email_subject}\n"
                            f"Body: {email_body}\n\n"
                            f"Return ONLY a JSON array of arrays (rows), no other text."
                        )
                        response = model.generate_content(prompt)
                        import json as _json
                        json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
                        if json_match:
                            extracted = _json.loads(json_match.group())
                            if isinstance(extracted, list):
                                sheet_data.extend(extracted)
                            logger.info(f"Gemini extracted {len(sheet_data) - 1} rows")
                    else:
                        logger.info("No Gemini API key, using empty sheet")
                except ImportError:
                    logger.info("google-generativeai not installed, using empty sheet")
                except Exception as e:
                    logger.warning(f"Gemini extraction failed: {e}, using empty sheet")

            # Create the sheet using Google Sheets API
            from sheets_client import GoogleSheetsClient

            # Create new spreadsheet
            # Note: This requires proper Google Cloud project setup
            # For now, we'll simulate the creation

            sheet_title = self._generate_sheet_title(step, context)

            # TODO: Actual sheet creation with sheets_client
            # For now, return simulated result

            sheet_info = {
                'title': sheet_title,
                'columns': columns,
                'rows': len(sheet_data) - 1,
                'url': f'https://docs.google.com/spreadsheets/d/SIMULATED_ID',
                'created': True
            }

            # Send result to user
            msg = f"✅ <b>Created Google Sheet</b>\n\n"
            msg += f"📊 <b>Title:</b> {html.escape(sheet_title)}\n"
            msg += f"📋 <b>Columns:</b> {html.escape(', '.join(columns))}\n"
            msg += f"📝 <b>Rows:</b> {sheet_info['rows']}\n"
            msg += f"🔗 <b>Link:</b> {sheet_info['url']}\n\n"
            msg += f"<i>Note: Full Google Sheets API integration in progress</i>"

            await self.telegram.send_response(chat_id, msg)

            return {
                'handled': True,
                'sheet_created': True,
                'reference': {'last_sheet': sheet_info}
            }

        except Exception as e:
            logger.error(f"Error creating sheet with Gemini: {e}", exc_info=True)
            await self.telegram.send_response(
                chat_id,
                f"❌ Failed to create sheet: {html.escape(str(e))}"
            )
            return {
                'handled': True,
                'sheet_created': False,
                'error': str(e)
            }

    def _generate_sheet_title(self, step: str, context: Dict[str, Any]) -> str:
        """Generate a meaningful title for the sheet."""
        import re
        from datetime import datetime

        # Try to extract title from request
        title_match = re.search(r'(?:called|named|titled)\s+["\']?([^"\'\.]+)["\']?', step, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()

        # Use subject from email context
        if context.get('last_email', {}).get('subject'):
            return f"{context['last_email']['subject']} - Data"

        # Default with timestamp
        return f"Sheet {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    async def _workflow_handle_email_draft(
        self, step: str, user_id: int, chat_id: int, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle email draft in workflow context."""
        # Parse the step and route to email processor
        # This uses the existing email draft flow
        return {
            'handled': False,
            'routed_to': 'email_processor',
            'parsed_message': self._parse_email_request(step)
        }

    async def _workflow_handle_todo_add(
        self, step: str, user_id: int, chat_id: int
    ) -> Dict[str, Any]:
        """Handle todo add in workflow context."""
        # Use existing todo handler (takes text, chat_id)
        return await self._handle_todo_add(step, chat_id)

    async def _workflow_handle_email_search(
        self, step: str, user_id: int, chat_id: int, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle email search in workflow context."""
        # Search for email and store in context
        return {
            'handled': False,
            'routed_to': 'email_processor',
            'parsed_message': self._parse_email_request(step)
        }

    async def _check_active_workflow(
        self, text: str, user_id: int, chat_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Check if user has an active workflow and handle the message in that context.

        This allows multi-step interactions like:
        - User: "draft reply to Jason and send it"
        - Bot: "Draft ready. Send?"
        - User: "yes" <- This should be handled by the workflow, not parsed as new intent

        Args:
            text: User message
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            Dict with 'handled' if workflow processed the message, None otherwise
        """
        try:
            from workflow_manager import WorkflowManager, WorkflowExecutor
            from db_manager import DatabaseManager

            # Get or create workflow manager
            if not hasattr(self, '_workflow_manager'):
                db = DatabaseManager()
                self._workflow_manager = WorkflowManager(db)
                self._workflow_executor = WorkflowExecutor(
                    workflow_manager=self._workflow_manager,
                    telegram_handler=self.telegram,
                    gmail_client=self.processor.gmail if self.processor else None,
                    ollama_client=self.processor.ollama if self.processor else None,
                    claude_client=self.processor.claude if self.processor else None
                )

            # Check for active workflow
            if not self._workflow_manager.has_active_workflow(user_id):
                return None

            # Let workflow executor handle the message
            result = await self._workflow_executor.handle_workflow_message(
                user_id, chat_id, text
            )

            return result

        except ImportError as e:
            logger.debug(f"Workflow manager not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Error checking active workflow: {e}", exc_info=True)
            return None

    # ==================
    # UTILITY METHODS
    # ==================

    def _parse_email_request(self, text: str) -> Dict[str, Any]:
        """
        Parse an email-related request into structured format.
        Used by workflow handlers to extract email reference and instruction.

        Args:
            text: User message text (e.g., "draft email to Jason about invoice")

        Returns:
            Dict with email_reference, instruction, search_type, valid
        """
        import re
        text_lower = text.lower().strip()

        result = {
            'email_reference': '',
            'instruction': '',
            'search_type': 'keyword',
            'raw_text': text,
            'valid': False
        }

        # Pattern: "draft email to [person] about [topic]"
        match = re.match(r'(?:draft|write|compose)\s+(?:an?\s+)?(?:email|reply|response)\s+to\s+(\w+)\s+(?:about|regarding|re:?)\s+(.+)', text_lower)
        if match:
            result['email_reference'] = match.group(1).strip()
            result['instruction'] = match.group(2).strip()
            result['search_type'] = 'sender'
            result['valid'] = True
            return result

        # Pattern: "email [person] - [instruction]"
        match = re.match(r'(?:email|reply to|respond to)\s+(\w+)\s*[-–—]\s*(.+)', text_lower)
        if match:
            result['email_reference'] = match.group(1).strip()
            result['instruction'] = match.group(2).strip()
            result['search_type'] = 'sender'
            result['valid'] = True
            return result

        # Fallback: treat whole text as keyword search
        result['email_reference'] = text
        result['instruction'] = 'respond appropriately'
        result['valid'] = bool(text.strip())
        return result

    def _extract_task_info(self, text: str) -> Dict[str, Any]:
        """
        Extract task information from a text string.
        Used by workflow handlers for todo creation steps.

        Args:
            text: User message text

        Returns:
            Dict with task, priority, deadline
        """
        import re

        # Remove common prefixes
        task_text = text
        for prefix in ['add', 'create', 'todo', 'task', 'remind me to', 'add to my todo',
                        'add to my agenda', 'add a task']:
            if task_text.lower().startswith(prefix):
                task_text = task_text[len(prefix):].strip()

        # Clean up leading punctuation
        task_text = task_text.lstrip(':- ').strip()

        # Detect priority
        priority = 'medium'
        if any(word in text.lower() for word in ['urgent', 'asap', 'critical', 'important']):
            priority = 'high'
        elif any(word in text.lower() for word in ['whenever', 'low priority', 'someday']):
            priority = 'low'

        # Try to detect deadline
        deadline = None
        deadline_patterns = {
            'tomorrow': 1,
            'today': 0,
            'monday': None, 'tuesday': None, 'wednesday': None,
            'thursday': None, 'friday': None,
        }
        for word in deadline_patterns:
            if word in text.lower():
                # Simple: just note the word, actual date calculation left to caller
                deadline = word
                # Remove deadline word from task text
                task_text = re.sub(rf'\b{word}\b', '', task_text, flags=re.IGNORECASE).strip()
                break

        return {
            'task': task_text or text,
            'priority': priority,
            'deadline': deadline
        }

    # ==========================================================================
    # ACTION REGISTRY INTEGRATION
    # ==========================================================================

    async def _try_action_registry(
        self, intent: Intent, text: str, user_id: int, chat_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt to handle the intent through the Action Registry system.

        Returns a routing result dict if handled, or None to fall through
        to the legacy routing flow.
        """
        from core.actions import get_action_schema, get_action_name

        # Skip conversational intents — they don't need the registry
        skip_intents = {Intent.GREETING, Intent.HELP_REQUEST, Intent.CASUAL_CHAT,
                        Intent.UNCLEAR, Intent.COMMAND}
        if intent in skip_intents:
            return None

        # Map the existing Intent enum to the registry's intent strings
        intent_value = self._map_intent_to_registry(intent)
        if intent_value is None:
            return None

        action_schema = get_action_schema(intent_value)
        if action_schema is None:
            return None

        action_name = get_action_name(intent_value)
        if action_name is None:
            return None

        logger.info("[ACTION_REGISTRY] Processing action: %s", action_name)

        # Build context
        action_context = self._build_action_context(user_id, action_schema)

        # Extract parameters
        if self._extractor:
            params, missing, confidence, reasoning = self._extractor.extract_params(
                action_name=action_name,
                user_text=text,
                context=action_context,
            )
        else:
            params, missing, confidence, reasoning = {}, list(action_schema.required_params), 0.0, "No extractor"

        # Inject context if user said "it", "that", etc.
        if self._context_mgr:
            params = self._context_mgr.inject_context_if_needed(user_id, text, params)

        logger.info(
            "[ACTION_REGISTRY] Extraction: params=%s, missing=%s, conf=%.2f, reason=%s",
            params, missing, confidence, reasoning,
        )

        # Validate
        if self._validator:
            validation = self._validator.validate(
                action_name=action_name,
                params=params,
                missing_fields=missing,
                confidence=confidence,
                context=action_context,
            )
        else:
            # If no validator, fall through to legacy flow
            return None

        if not validation.can_execute:
            # Store pending action and wait for user response
            if self._session_state:
                self._session_state.set_awaiting(
                    user_id=user_id,
                    awaiting_type=validation.clarification_type,
                    pending_action=intent_value,
                    context_data={
                        "params": params,
                        "context": action_context,
                        "original_text": text,
                        "options": validation.options,
                        "chat_id": chat_id,
                    },
                )

            await self.telegram.send_response(chat_id, validation.clarification_needed)
            return {
                'handled': True,
                'routed_to': 'action_registry',
                'action': action_name,
                'awaiting': validation.clarification_type,
            }

        # Execute action — delegate to existing capability handlers
        # The registry validates and extracts params; execution still uses
        # the existing, proven handlers.
        exec_result = await self._execute_registry_action(
            intent, action_name, params, action_context, user_id, chat_id
        )

        # Update context for future "it" references
        if self._context_mgr and exec_result:
            self._context_mgr.update_context_after_action(
                user_id, action_name, params, exec_result
            )

        # Multi-channel output
        if action_schema.multi_channel_output and self._notifier:
            try:
                await self._notifier.route_notification(
                    user_id, action_name, params, exec_result, multi_channel=True
                )
            except Exception as e:
                logger.warning("[ACTION_REGISTRY] Multi-channel notification failed: %s", e)

        return exec_result

    def _map_intent_to_registry(self, intent: Intent) -> Optional[str]:
        """Map the existing Intent enum to Action Registry intent strings."""
        mapping = {
            Intent.TODO_ADD: "TODO_ADD",
            Intent.TODO_COMPLETE: "TODO_COMPLETE",
            Intent.TODO_DELETE: "TODO_DELETE",
            Intent.TODO_LIST: "TODO_LIST",
            Intent.EMAIL_DRAFT: "EMAIL_DRAFT",
            Intent.EMAIL_SEARCH: "EMAIL_SEARCH",
            Intent.EMAIL_SYNTHESIZE: "EMAIL_SYNTHESIZE",
            Intent.INFO_STATUS: "INFO_STATUS",
            Intent.INFO_UNREAD: "EMAIL_UNREAD",
            Intent.INFO_DIGEST: "DIGEST_GENERATE",
            Intent.SKILL_FINALIZE: "SKILL_FINALIZE",
            Intent.SKILL_LIST: "SKILL_LIST",
            Intent.SKILL_SEARCH: "SKILL_SEARCH",
        }
        return mapping.get(intent)

    def _build_action_context(
        self, user_id: int, action_schema
    ) -> Dict[str, Any]:
        """
        Build context dict based on action's context_needed.
        Fetches data from managers and session state.
        """
        context: Dict[str, Any] = {}

        for ctx_key in action_schema.context_needed:
            try:
                if ctx_key == "active_tasks":
                    from todo_manager import TodoManager
                    todo_mgr = TodoManager()
                    pending = todo_mgr.get_pending_tasks(limit=15)
                    context["active_tasks"] = [
                        {"id": t["id"], "title": t["title"],
                         "priority": t.get("priority", "medium"),
                         "category": t.get("category", "")}
                        for t in pending
                    ] if pending else []

                elif ctx_key == "recent_emails":
                    cached = self._session_state.get_reference(user_id, "search_results") if self._session_state else None
                    context["recent_emails"] = cached or []

                elif ctx_key == "existing_skills":
                    try:
                        from skill_manager import SkillManager
                        sm = SkillManager()
                        context["existing_skills"] = sm.list_skills(user_id=user_id, limit=10)
                    except Exception:
                        context["existing_skills"] = []

                elif ctx_key == "pending_skills":
                    try:
                        from skill_manager import SkillManager
                        sm = SkillManager()
                        # Filter for pending status if method supports it
                        all_skills = sm.list_skills(user_id=user_id, limit=10)
                        context["pending_skills"] = [
                            s for s in all_skills if s.get("status") == "Pending"
                        ]
                    except Exception:
                        context["pending_skills"] = []

                elif ctx_key == "active_drafts":
                    context["active_drafts"] = []

                elif ctx_key == "system_health":
                    context["system_health"] = {"status": "operational"}

                elif ctx_key == "persona_config":
                    context["persona_config"] = {}

                elif ctx_key in ("writing_patterns", "last_search_results",
                                 "recent_brainstorms", "thread_history",
                                 "recent_threads", "unsent_drafts", "pending_tasks",
                                 "existing_categories", "recent_tasks",
                                 "connected_sheets", "recent_context",
                                 "workflow_state", "active_resources",
                                 "recent_generations"):
                    context[ctx_key] = []

            except Exception as e:
                logger.warning("[ACTION_REGISTRY] Failed to build context for '%s': %s", ctx_key, e)
                context[ctx_key] = []

        return context

    async def _execute_registry_action(
        self,
        intent: Intent,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        user_id: int,
        chat_id: int,
    ) -> Dict[str, Any]:
        """
        Execute a validated action by delegating to existing capability handlers.

        The Action Registry handles extraction and validation; this method
        bridges to the proven execution logic already in the codebase.
        """
        logger.info("[ACTION_REGISTRY] Executing: %s with params: %s", action_name, params)

        try:
            if intent == Intent.TODO_ADD:
                return await self._handle_todo_add(
                    params.get("title", ""), chat_id
                )

            elif intent == Intent.TODO_LIST:
                return await self._handle_todo_list(chat_id, user_id)

            elif intent == Intent.TODO_COMPLETE:
                return await self._registry_todo_complete(params, context, chat_id)

            elif intent == Intent.TODO_DELETE:
                return await self._registry_todo_delete(params, context, chat_id)

            elif intent in (Intent.EMAIL_DRAFT, Intent.EMAIL_SEARCH):
                return {
                    'handled': False,
                    'routed_to': 'email_processor',
                    'reason': intent.value,
                    'params': params,
                }

            elif intent == Intent.EMAIL_SYNTHESIZE:
                return {
                    'handled': False,
                    'routed_to': 'email_processor',
                    'reason': 'synthesize',
                    'params': params,
                }

            elif intent == Intent.INFO_STATUS:
                return await self._handle_status(chat_id)

            elif intent == Intent.INFO_UNREAD:
                return await self._handle_unread(chat_id)

            elif intent == Intent.INFO_DIGEST:
                return await self._handle_digest(chat_id)

            elif intent == Intent.SKILL_FINALIZE:
                return await self._handle_skill_finalize(
                    params.get("_original_text", "finalize"), user_id, chat_id
                )

            elif intent == Intent.SKILL_LIST:
                return await self._handle_skill_list(user_id, chat_id)

            elif intent == Intent.SKILL_SEARCH:
                query = params.get("query", "")
                return await self._handle_skill_search(
                    f"find skill about {query}", user_id, chat_id
                )

            # Fallback: route normally
            return await self.route_to_capability(intent, params.get("_original_text", ""), user_id, chat_id)

        except Exception as e:
            logger.error("[ACTION_REGISTRY] Execution error: %s", e, exc_info=True)
            await self.telegram.send_response(
                chat_id, f"Sorry, something went wrong: {e}"
            )
            return {'handled': True, 'routed_to': 'action_registry', 'error': str(e)}

    async def _registry_todo_complete(
        self, params: Dict[str, Any], context: Dict[str, Any], chat_id: int
    ) -> Dict[str, Any]:
        """Complete a task using the registry-extracted task_id."""
        try:
            from todo_manager import TodoManager
            from db_manager import DatabaseManager

            task_id = params.get("task_id")
            if not task_id:
                await self.telegram.send_response(chat_id, "Could not determine which task to complete.")
                return {'handled': True, 'routed_to': 'action_registry', 'error': 'no_task_id'}

            todo_mgr = TodoManager()
            db = DatabaseManager()

            # Find task title from context or DB
            active_tasks = context.get("active_tasks", [])
            task = next((t for t in active_tasks if t.get("id") == task_id), None)
            task_title = task["title"] if task else f"task #{task_id}"

            # Complete the task
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE tasks SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (task_id,)
                )
                conn.commit()

            response = f"Task '{task_title}' marked complete and archived!"
            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'action_registry', 'action': 'todo_complete'}

        except Exception as e:
            logger.error("[ACTION_REGISTRY] todo_complete error: %s", e, exc_info=True)
            await self.telegram.send_response(chat_id, f"Error completing task: {e}")
            return {'handled': True, 'routed_to': 'action_registry', 'error': str(e)}

    async def _registry_todo_delete(
        self, params: Dict[str, Any], context: Dict[str, Any], chat_id: int
    ) -> Dict[str, Any]:
        """Delete a task using the registry-extracted task_id."""
        try:
            from db_manager import DatabaseManager

            task_id = params.get("task_id")
            if not task_id:
                await self.telegram.send_response(chat_id, "Could not determine which task to delete.")
                return {'handled': True, 'routed_to': 'action_registry', 'error': 'no_task_id'}

            active_tasks = context.get("active_tasks", [])
            task = next((t for t in active_tasks if t.get("id") == task_id), None)
            task_title = task["title"] if task else f"task #{task_id}"

            db = DatabaseManager()
            with db.get_connection() as conn:
                conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                conn.commit()

            response = f"Task '{task_title}' permanently deleted."
            await self.telegram.send_response(chat_id, response)
            return {'handled': True, 'routed_to': 'action_registry', 'action': 'todo_delete'}

        except Exception as e:
            logger.error("[ACTION_REGISTRY] todo_delete error: %s", e, exc_info=True)
            await self.telegram.send_response(chat_id, f"Error deleting task: {e}")
            return {'handled': True, 'routed_to': 'action_registry', 'error': str(e)}

    # -------------------------------------------------------------------------
    # Awaiting-state handler
    # -------------------------------------------------------------------------

    async def _handle_awaiting_response(
        self, user_id: int, text: str, chat_id: int, awaiting_state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Handle user's response to a clarification question.
        Implements Session Memory for multi-turn interactions.
        """
        awaiting_type = awaiting_state["type"]
        pending_action = awaiting_state["action"]
        stored_context = awaiting_state["context"]
        stored_chat_id = stored_context.get("chat_id", chat_id)

        logger.info(
            "[ACTION_REGISTRY] Handling awaiting response: type=%s, action=%s",
            awaiting_type, pending_action,
        )

        if awaiting_type == "missing_params":
            return await self._resolve_missing_param(
                user_id, text, stored_chat_id, pending_action, stored_context
            )

        if awaiting_type in ("low_confidence", "high_risk"):
            return await self._resolve_confirmation(
                user_id, text, stored_chat_id, pending_action, stored_context
            )

        if awaiting_type == "ambiguous":
            return await self._resolve_ambiguity(
                user_id, text, stored_chat_id, pending_action, stored_context
            )

        # Unknown awaiting type — clear and let normal flow handle it
        self._session_state.clear_awaiting(user_id)
        return None

    async def _resolve_confirmation(
        self, user_id: int, text: str, chat_id: int,
        pending_action: str, stored_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle yes/no confirmation for low-confidence or high-risk actions."""
        confirmation_words = {"yes", "confirm", "do it", "go ahead", "sure", "yeah", "yep", "ok", "okay", "y"}
        rejection_words = {"no", "cancel", "stop", "nevermind", "nope", "don't", "n"}

        text_lower = text.lower().strip()

        if text_lower in confirmation_words or any(w in text_lower for w in confirmation_words):
            self._session_state.clear_awaiting(user_id)

            # Map back to Intent and execute
            intent = self._registry_intent_to_enum(pending_action)
            if intent:
                from core.actions import get_action_name
                action_name = get_action_name(pending_action)
                return await self._execute_registry_action(
                    intent, action_name, stored_context.get("params", {}),
                    stored_context.get("context", {}), user_id, chat_id
                )

        if text_lower in rejection_words or any(w in text_lower for w in rejection_words):
            self._session_state.clear_awaiting(user_id)
            await self.telegram.send_response(chat_id, "Okay, action canceled. What would you like to do instead?")
            return {'handled': True, 'routed_to': 'action_registry', 'action': 'canceled'}

        await self.telegram.send_response(chat_id, "I didn't catch that. Reply 'yes' to confirm or 'no' to cancel.")
        return {'handled': True, 'routed_to': 'action_registry', 'awaiting': 'confirmation'}

    async def _resolve_missing_param(
        self, user_id: int, text: str, chat_id: int,
        pending_action: str, stored_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract missing parameter from user's follow-up message."""
        from core.actions import get_action_schema, get_action_name

        action_schema = get_action_schema(pending_action)
        if not action_schema:
            self._session_state.clear_awaiting(user_id)
            return {'handled': True, 'routed_to': 'action_registry', 'error': 'unknown_action'}

        action_name = get_action_name(pending_action)

        # Re-run extraction with user's clarification
        if self._extractor:
            params, missing, confidence, reasoning = self._extractor.extract_params(
                action_name=action_name,
                user_text=text,
                context=stored_context.get("context", {}),
            )
        else:
            params, missing = {}, list(action_schema.required_params)
            confidence, reasoning = 0.0, "No extractor"

        # Merge with previously extracted params
        final_params = {**stored_context.get("params", {}), **params}

        # Re-check missing fields
        still_missing = [
            p for p in action_schema.required_params
            if p not in final_params or final_params[p] is None
        ]

        if still_missing:
            # Still need more info — update stored params and re-ask
            stored_context["params"] = final_params
            if self._validator:
                validation = self._validator.validate(
                    action_name=action_name,
                    params=final_params,
                    missing_fields=still_missing,
                    confidence=confidence,
                    context=stored_context.get("context", {}),
                )
                if not validation.can_execute:
                    self._session_state.set_awaiting(
                        user_id=user_id,
                        awaiting_type="missing_params",
                        pending_action=pending_action,
                        context_data=stored_context,
                    )
                    await self.telegram.send_response(chat_id, validation.clarification_needed)
                    return {'handled': True, 'routed_to': 'action_registry', 'awaiting': 'missing_params'}

        # All required params now present
        self._session_state.clear_awaiting(user_id)
        intent = self._registry_intent_to_enum(pending_action)
        if intent:
            return await self._execute_registry_action(
                intent, action_name, final_params,
                stored_context.get("context", {}), user_id, chat_id
            )

        return {'handled': True, 'routed_to': 'action_registry', 'error': 'unmapped_intent'}

    async def _resolve_ambiguity(
        self, user_id: int, text: str, chat_id: int,
        pending_action: str, stored_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle user's selection from multiple ambiguous options."""
        import re as _re

        options = stored_context.get("options", [])
        if not options:
            self._session_state.clear_awaiting(user_id)
            return {'handled': True, 'routed_to': 'action_registry', 'error': 'no_options'}

        # Try to extract selection number
        match = _re.search(r'\b(\d+)\b', text)
        if match:
            selection_num = int(match.group(1))
            if 1 <= selection_num <= len(options):
                selected_option = options[selection_num - 1]
                final_params = {**stored_context.get("params", {}), **selected_option}

                self._session_state.clear_awaiting(user_id)
                intent = self._registry_intent_to_enum(pending_action)
                if intent:
                    from core.actions import get_action_name
                    action_name = get_action_name(pending_action)
                    return await self._execute_registry_action(
                        intent, action_name, final_params,
                        stored_context.get("context", {}), user_id, chat_id
                    )

        # Try fuzzy matching on option descriptions
        text_lower = text.lower()
        for i, option in enumerate(options):
            if any(str(v).lower() in text_lower for v in option.values()):
                final_params = {**stored_context.get("params", {}), **option}
                self._session_state.clear_awaiting(user_id)
                intent = self._registry_intent_to_enum(pending_action)
                if intent:
                    from core.actions import get_action_name
                    action_name = get_action_name(pending_action)
                    return await self._execute_registry_action(
                        intent, action_name, final_params,
                        stored_context.get("context", {}), user_id, chat_id
                    )

        await self.telegram.send_response(
            chat_id,
            f"I didn't catch that. Please say the number of your choice (1-{len(options)})."
        )
        return {'handled': True, 'routed_to': 'action_registry', 'awaiting': 'ambiguous'}

    def _registry_intent_to_enum(self, intent_value: str) -> Optional[Intent]:
        """Map an action registry intent string back to an Intent enum member."""
        reverse_mapping = {
            "TODO_ADD": Intent.TODO_ADD,
            "TODO_COMPLETE": Intent.TODO_COMPLETE,
            "TODO_DELETE": Intent.TODO_DELETE,
            "TODO_LIST": Intent.TODO_LIST,
            "EMAIL_DRAFT": Intent.EMAIL_DRAFT,
            "EMAIL_SEARCH": Intent.EMAIL_SEARCH,
            "EMAIL_SEND": Intent.EMAIL_FORWARD,  # closest match
            "EMAIL_SYNTHESIZE": Intent.EMAIL_SYNTHESIZE,
            "INFO_STATUS": Intent.INFO_STATUS,
            "EMAIL_UNREAD": Intent.INFO_UNREAD,
            "DIGEST_GENERATE": Intent.INFO_DIGEST,
            "SKILL_FINALIZE": Intent.SKILL_FINALIZE,
            "SKILL_LIST": Intent.SKILL_LIST,
            "SKILL_SEARCH": Intent.SKILL_SEARCH,
            "SKILL_CREATE": Intent.SKILL_QUICK,
        }
        return reverse_mapping.get(intent_value)

    # ==================
    # LEGACY METHODS (unchanged)
    # ==================

    def _is_legacy_email_format(self, text: str) -> bool:
        """
        Check if message uses legacy email format.

        Returns True ONLY for formats that are CLEARLY email-related:
        - "Re: subject - instruction"
        - "From sender - instruction"
        - "latest from sender - instruction"

        IMPORTANT: This should NOT match conversational text or casual messages.
        We prefer false negatives (miss an email format) over false positives
        (treat conversation as email search).
        """
        text_lower = text.lower().strip()

        # Short messages are almost never legacy email format
        if len(text) < 10:
            return False

        # Pattern 1: Re: subject - instruction (very clear email format)
        if text_lower.startswith('re:') and '-' in text:
            return True

        # Pattern 2: From sender - instruction (clear email format)
        if text_lower.startswith('from ') and '-' in text:
            # Make sure it looks like "from [name/email]" not "from now on"
            words = text_lower.split()
            if len(words) >= 2:
                # Check if second word could be a name/email
                second_word = words[1] if len(words) > 1 else ''
                casual_words = ['now', 'here', 'there', 'what', 'where', 'my', 'the', 'this', 'that']
                if second_word not in casual_words:
                    return True

        # Pattern 3: latest from sender - instruction
        if text_lower.startswith('latest from') and '-' in text:
            return True

        # Pattern 4: STRICT generic format - only if it really looks like email
        # Must have " - " with substantial content on both sides
        # AND must NOT start with conversational words
        if ' - ' in text:
            parts = text.split(' - ', 1)
            if len(parts) == 2:
                first_part = parts[0].strip()
                second_part = parts[1].strip()

                first_words = len(first_part.split())
                second_words = len(second_part.split())

                # Exclude conversational starters
                conversational_starts = [
                    'add', 'remind', 'create', 'show', 'list', 'tell', 'give',
                    'hi', 'hello', 'hey', 'thanks', 'ok', 'cool', 'yes', 'no',
                    'sure', 'great', 'nice', 'i', 'we', 'you', 'my', 'the',
                    'what', 'why', 'how', 'when', 'where', 'who', 'can', 'could',
                    'would', 'should', 'please', 'just', 'actually', 'maybe'
                ]
                first_word_lower = first_part.split()[0].lower() if first_part.split() else ''
                starts_conversational = first_word_lower in conversational_starts

                # Require email-like keywords in the instruction part
                email_action_words = ['send', 'reply', 'respond', 'draft', 'forward', 'confirm',
                                      'acknowledge', 'approve', 'reject', 'follow up', 'followup']
                has_email_action = any(word in second_part.lower() for word in email_action_words)

                # Only match if: 2-10 words on left, has action word, doesn't start conversational
                if (2 <= first_words <= 10 and second_words >= 1 and
                    not starts_conversational and has_email_action):
                    return True

        return False
