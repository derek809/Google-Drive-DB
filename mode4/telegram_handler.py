"""
Telegram Handler for Mode 4
Receives and parses Telegram messages, sends responses.

Usage:
    from telegram_handler import TelegramHandler

    handler = TelegramHandler(bot_token, allowed_users)

    # Parse a message
    parsed = handler.parse_message("Re: W9 Request - send W9 and wiring")

    # Send a response
    await handler.send_response(chat_id, "Draft created!")
"""

import re
import json
import asyncio
import logging
import html
from typing import Dict, List, Optional, Any, Callable

# Telegram library
try:
    from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramHandlerError(Exception):
    """Custom exception for Telegram handler errors."""
    pass


class TelegramHandler:
    """
    Telegram bot handler for Mode 4.

    Receives messages from Telegram, parses them to extract email references
    and instructions, and sends responses back.
    """

    def __init__(
        self,
        bot_token: str = None,
        allowed_users: List[int] = None,
        admin_chat_id: int = None
    ):
        """
        Initialize Telegram handler.

        Args:
            bot_token: Telegram bot token from @BotFather
            allowed_users: List of allowed Telegram user IDs
            admin_chat_id: Admin chat ID for notifications
        """
        if not TELEGRAM_AVAILABLE:
            raise TelegramHandlerError(
                "Telegram package not installed. Run:\n"
                "pip install python-telegram-bot[job-queue]"
            )

        # Try to load from config
        try:
            from m1_config import load_telegram_config
            config = load_telegram_config()
            self.bot_token = bot_token or config.get('bot_token')
            self.allowed_users = allowed_users or config.get('allowed_users', [])
            self.admin_chat_id = admin_chat_id or config.get('admin_chat_id')
        except ImportError:
            self.bot_token = bot_token
            self.allowed_users = allowed_users or []
            self.admin_chat_id = admin_chat_id

        if not self.bot_token or self.bot_token == "YOUR_BOT_TOKEN_HERE":
            raise TelegramHandlerError(
                "Telegram bot token not configured.\n"
                "1. Open Telegram and search for @BotFather\n"
                "2. Send /newbot and follow instructions\n"
                "3. Copy the token and add it to m1_config.py"
            )

        self.bot = Bot(token=self.bot_token)
        self.application = None
        self.message_callback: Optional[Callable] = None

        # Draft context storage for inline button callbacks
        # {draft_id: {context_data, timestamp, user_id, chat_id}}
        self._draft_contexts: Dict[str, Dict[str, Any]] = {}
        self._context_expiry_minutes = 30

        # Conversation manager for natural language interface (lazy loaded)
        self._conversation_manager = None

    @property
    def conversation_manager(self):
        """Lazy-load conversation manager."""
        if self._conversation_manager is None:
            try:
                from conversation_manager import ConversationManager
                # Will be properly initialized with processor reference later
                self._conversation_manager = ConversationManager(
                    telegram_handler=self,
                    mode4_processor=None  # Set by processor on first use
                )
                logger.info("Conversation manager initialized")
            except ImportError as e:
                logger.warning(f"Could not load conversation manager: {e}")
                self._conversation_manager = None
        return self._conversation_manager

    def set_conversation_processor(self, processor):
        """Set the Mode4Processor reference for conversation manager."""
        if self.conversation_manager:
            self.conversation_manager.processor = processor

    # ==================
    # MESSAGE PARSING
    # ==================

    def parse_message(self, text: str) -> Dict[str, Any]:
        """
        Parse a Telegram message to extract email reference and instruction.

        Supported formats:
        - "Re: [subject] - [instruction]"
        - "From [sender] - [instruction]"
        - "[subject] - [instruction]"
        - "latest from [sender] - [instruction]"

        Uses SmartParser (LLM + regex fallback) if enabled, otherwise uses legacy regex.

        Args:
            text: Raw message text

        Returns:
            Dict with:
                - email_reference: Subject or sender to search for
                - instruction: What to do with the email
                - search_type: "subject", "sender", or "keyword"
                - raw_text: Original message
                - parsed_with: "llm", "rules", or "fallback" (if SmartParser used)
        """
        text = text.strip()

        # Use SmartParser if enabled
        from m1_config import SMART_PARSER_ENABLED
        if SMART_PARSER_ENABLED:
            try:
                parsed = self.processor.smart_parser.parse_with_fallback(text)
                # Convert SmartParser output to expected format
                result = {
                    'email_reference': parsed.get('email_reference', ''),
                    'instruction': parsed.get('instruction', ''),
                    'search_type': parsed.get('search_type', 'keyword'),
                    'raw_text': text,
                    'valid': True,
                    'parsed_with': parsed.get('parsed_with', 'unknown')
                }
                return result
            except Exception as e:
                logger.warning(f"SmartParser failed: {e}, using legacy parser")

        # Legacy regex parsing (backward compatibility)
        result = {
            'email_reference': '',
            'instruction': '',
            'search_type': 'keyword',
            'raw_text': text,
            'valid': False
        }

        # Pattern 1: "Re: [subject] - [instruction]"
        match = re.match(r'^[Rr]e:\s*(.+?)\s*[-–—]\s*(.+)$', text)
        if match:
            result['email_reference'] = match.group(1).strip()
            result['instruction'] = match.group(2).strip()
            result['search_type'] = 'subject'
            result['valid'] = True
            return result

        # Pattern 2: "From [sender] - [instruction]" or "from [sender] - [instruction]"
        match = re.match(r'^[Ff]rom\s+([^\s-]+(?:@[^\s-]+)?)\s*[-–—]\s*(.+)$', text)
        if match:
            result['email_reference'] = match.group(1).strip()
            result['instruction'] = match.group(2).strip()
            result['search_type'] = 'sender'
            result['valid'] = True
            return result

        # Pattern 3: "latest from [sender] - [instruction]"
        match = re.match(r'^[Ll]atest\s+from\s+([^\s-]+(?:@[^\s-]+)?)\s*[-–—]\s*(.+)$', text)
        if match:
            result['email_reference'] = match.group(1).strip()
            result['instruction'] = match.group(2).strip()
            result['search_type'] = 'sender'
            result['valid'] = True
            return result

        # Pattern 4: "[subject/keyword] - [instruction]" (generic)
        match = re.match(r'^(.+?)\s*[-–—]\s*(.+)$', text)
        if match:
            ref = match.group(1).strip()
            instruction = match.group(2).strip()

            # Determine search type based on reference
            if '@' in ref:
                result['search_type'] = 'sender'
            else:
                result['search_type'] = 'keyword'

            result['email_reference'] = ref
            result['instruction'] = instruction
            result['valid'] = True
            return result

        # Pattern 5: Commands starting with /
        if text.startswith('/'):
            parts = text.split(maxsplit=1)
            result['command'] = parts[0].lower()
            result['args'] = parts[1] if len(parts) > 1 else ''
            result['valid'] = True
            return result

        # Could not parse - might be a simple keyword search
        result['email_reference'] = text
        result['instruction'] = 'respond appropriately'
        result['search_type'] = 'keyword'
        result['valid'] = bool(text)

        return result

    # ==================
    # BOT SETUP
    # ==================

    def setup_bot(self, message_callback: Callable = None):
        """
        Set up the Telegram bot with handlers.

        Args:
            message_callback: Async function to call when a message is received.
                             Signature: async callback(parsed_message, chat_id, user_id)
        """
        self.message_callback = message_callback

        self.application = Application.builder().token(self.bot_token).build()

        # Add handlers
        self.application.add_handler(CommandHandler("start", self._cmd_start))
        self.application.add_handler(CommandHandler("help", self._cmd_help))
        self.application.add_handler(CommandHandler("status", self._cmd_status))
        self.application.add_handler(CommandHandler("retry", self._cmd_retry))
        self.application.add_handler(CommandHandler("synthesize", self._cmd_synthesize))
        self.application.add_handler(CommandHandler("digest", self._cmd_digest))

        # Message handler for processing emails
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        # Photo handler for image analysis
        self.application.add_handler(
            MessageHandler(filters.PHOTO, self._handle_photo)
        )

        # Document handler for PDFs and files
        self.application.add_handler(
            MessageHandler(filters.Document.ALL, self._handle_document)
        )

        # Callback query handler for inline buttons
        self.application.add_handler(CallbackQueryHandler(self._handle_callback_query))

        # Error handler
        self.application.add_error_handler(self._error_handler)

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        chat_id = update.effective_chat.id

        if not self._is_authorized(user.id):
            await update.message.reply_text(
                "Unauthorized. Your user ID is not in the allowed list."
            )
            logger.warning(f"Unauthorized access attempt from user {user.id}")
            return

        await update.message.reply_text(
            "MCP Email Processor - Mode 4\n\n"
            "Send me a message in this format:\n"
            "  Re: [subject] - [instruction]\n"
            "  From [sender] - [instruction]\n\n"
            "Examples:\n"
            "  Re: W9 Request - send W9 and wiring\n"
            "  From john@example.com - confirm payment\n\n"
            "Commands:\n"
            "  /status - Check system status\n"
            "  /help - Show this message\n"
            "  /retry - Retry last failed email"
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        await self._cmd_start(update, context)

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        user = update.effective_user

        if not self._is_authorized(user.id):
            await update.message.reply_text("Unauthorized.")
            return

        # Check system status
        status_lines = ["System Status:"]

        # Check Ollama
        try:
            from ollama_client import OllamaClient
            ollama = OllamaClient()
            if ollama.is_available():
                status_lines.append("  Ollama: OK")
            else:
                status_lines.append("  Ollama: Model not available")
        except Exception as e:
            status_lines.append(f"  Ollama: Error - {str(e)[:50]}")

        # Check Gmail
        try:
            from gmail_client import GmailClient
            gmail = GmailClient()
            # Don't authenticate, just check if credentials exist
            import os
            from m1_config import GMAIL_TOKEN_PATH
            if os.path.exists(GMAIL_TOKEN_PATH):
                status_lines.append("  Gmail: Configured")
            else:
                status_lines.append("  Gmail: Needs OAuth setup")
        except Exception as e:
            status_lines.append(f"  Gmail: Error - {str(e)[:50]}")

        await update.message.reply_text("\n".join(status_lines))

    async def _cmd_retry(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /retry command."""
        user = update.effective_user

        if not self._is_authorized(user.id):
            await update.message.reply_text("Unauthorized.")
            return

        await update.message.reply_text(
            "Retry not implemented yet. "
            "Send the email reference again to reprocess."
        )

    async def _cmd_synthesize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /synthesize command to create thread summaries."""
        user = update.effective_user

        if not self._is_authorized(user.id):
            await update.message.reply_text("Unauthorized.")
            return

        # Check if ThreadSynthesizer is enabled
        from m1_config import THREAD_SYNTHESIZER_ENABLED
        if not THREAD_SYNTHESIZER_ENABLED:
            await update.message.reply_text("Thread Synthesizer is disabled in config.")
            return

        # Parse thread_id from command: "/synthesize 12345"
        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "Usage: /synthesize <thread_id>\n\n"
                "Example: /synthesize 18a1b2c3d4e5f6g7"
            )
            return

        thread_id = context.args[0]

        try:
            await update.message.reply_text(f"Fetching thread history for {thread_id}...")

            # Get thread history
            history = self.processor.thread_synthesizer.get_thread_history(thread_id)

            if not history:
                await update.message.reply_text(f"No messages found for thread {thread_id}")
                return

            await update.message.reply_text(
                f"Found {len(history)} messages. Generating summary..."
            )

            # Create synthesis prompt
            prompt = self.processor.thread_synthesizer.create_synthesis_prompt(history)

            # Send to Claude for synthesis
            try:
                # Import Claude client
                from claude_client import ClaudeClient

                claude = ClaudeClient()
                synthesis = await claude.synthesize_thread(prompt)

                # Send summary back to user
                await update.message.reply_text(
                    f"📊 Thread Summary:\n\n{synthesis}",
                    parse_mode='Markdown'
                )

            except Exception as e:
                logger.error(f"Claude synthesis failed: {e}")
                await update.message.reply_text(
                    f"Error generating synthesis: {str(e)}\n\n"
                    f"Try using Claude API key or check logs."
                )

        except Exception as e:
            logger.error(f"Synthesize command error: {e}", exc_info=True)
            await update.message.reply_text(f"Error: {str(e)}")

    async def _cmd_digest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /digest command for on-demand daily digest."""
        user = update.effective_user

        if not self._is_authorized(user.id):
            await update.message.reply_text("Unauthorized.")
            return

        await update.message.reply_text("Generating your digest...")

        try:
            from on_demand_digest import OnDemandDigest
            from todo_manager import TodoManager
            from db_manager import DatabaseManager

            # Get clients from processor if available
            gmail_client = self.processor.gmail if hasattr(self, 'processor') and self.processor else None
            claude_client = self.processor.claude if hasattr(self, 'processor') and self.processor else None

            # Initialize managers
            todo_manager = TodoManager()
            db_manager = DatabaseManager()

            # Create digest generator
            digest_gen = OnDemandDigest(
                gmail_client=gmail_client,
                todo_manager=todo_manager,
                claude_client=claude_client,
                db_manager=db_manager
            )

            # Generate digest
            digest = await digest_gen.generate_digest(user.id)

            # Send digest
            await update.message.reply_text(
                digest,
                parse_mode='HTML'
            )

        except ImportError as e:
            logger.error(f"Import error for digest: {e}")
            await update.message.reply_text(
                f"Digest module not available: {str(e)}\n\n"
                f"Make sure on_demand_digest.py is in the mode4 directory."
            )
        except Exception as e:
            logger.error(f"Digest command error: {e}", exc_info=True)
            await update.message.reply_text(f"Error generating digest: {str(e)[:200]}")

    async def _handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming photos/images for analysis with Gemini."""
        user = update.effective_user
        chat_id = update.effective_chat.id

        if not self._is_authorized(user.id):
            await update.message.reply_text("Unauthorized.")
            return

        await update.message.reply_text("Analyzing image...")

        try:
            import os
            import tempfile
            from gemini_client import GeminiClient

            # Get the highest resolution photo
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)

            # Download to temp file
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"mode4_{photo.file_id}.jpg")

            await file.download_to_drive(temp_path)
            logger.info(f"Downloaded image to {temp_path}")

            # Analyze with Gemini
            gemini = GeminiClient()

            if not gemini.is_available():
                await update.message.reply_text(
                    "Gemini API not configured.\n\n"
                    "Set GOOGLE_API_KEY or GEMINI_API_KEY in your environment."
                )
                return

            # Check if user included a caption as a custom prompt
            caption = update.message.caption
            if caption:
                analysis = await gemini.analyze_image(temp_path, prompt=caption)
            else:
                # Auto-detect type of analysis needed
                analysis = await gemini.analyze_image(temp_path)

            # Clean up temp file
            try:
                os.remove(temp_path)
            except:
                pass

            # Send analysis (escape HTML in response)
            response = f"<b>Image Analysis:</b>\n\n{html.escape(analysis)}"

            # Telegram message limit is 4096 chars
            if len(response) > 4000:
                response = response[:4000] + "...\n\n<i>(truncated)</i>"

            await update.message.reply_text(response, parse_mode='HTML')

        except ImportError as e:
            logger.error(f"Gemini import error: {e}")
            await update.message.reply_text(
                "Gemini client not available.\n\n"
                "Make sure google-generativeai is installed:\n"
                "pip install google-generativeai"
            )
        except Exception as e:
            logger.error(f"Photo analysis error: {e}", exc_info=True)
            await update.message.reply_text(f"Error analyzing image: {str(e)[:200]}")

    async def _handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming documents (PDFs, etc.) for analysis."""
        user = update.effective_user
        chat_id = update.effective_chat.id

        if not self._is_authorized(user.id):
            await update.message.reply_text("Unauthorized.")
            return

        document = update.message.document
        file_name = document.file_name or "document"
        mime_type = document.mime_type or ""

        # Check file type
        supported_types = ['application/pdf', 'image/']
        is_supported = any(mime_type.startswith(t) for t in supported_types)

        if not is_supported:
            await update.message.reply_text(
                f"File type not supported for analysis: {mime_type}\n\n"
                "I can analyze: images, PDFs, and screenshots."
            )
            return

        await update.message.reply_text(f"Analyzing {file_name}...")

        try:
            import os
            import tempfile

            # Download file
            file = await context.bot.get_file(document.file_id)
            temp_dir = tempfile.gettempdir()

            # Determine extension
            ext = os.path.splitext(file_name)[1] or '.bin'
            temp_path = os.path.join(temp_dir, f"mode4_{document.file_id}{ext}")

            await file.download_to_drive(temp_path)
            logger.info(f"Downloaded document to {temp_path}")

            # Handle based on type
            if mime_type == 'application/pdf':
                # For PDFs, we'd need to convert to images first
                # For now, inform user
                await update.message.reply_text(
                    "PDF analysis requires image conversion.\n\n"
                    "For now, please take a screenshot of the relevant page "
                    "and send it as an image."
                )
                try:
                    os.remove(temp_path)
                except:
                    pass
                return

            elif mime_type.startswith('image/'):
                # Analyze as image
                from gemini_client import GeminiClient
                gemini = GeminiClient()

                if not gemini.is_available():
                    await update.message.reply_text(
                        "Gemini API not configured.\n\n"
                        "Set GOOGLE_API_KEY or GEMINI_API_KEY."
                    )
                    return

                caption = update.message.caption
                if caption:
                    analysis = await gemini.analyze_image(temp_path, prompt=caption)
                else:
                    # Treat as document
                    result = await gemini.analyze_document(temp_path)
                    analysis = result.get('raw_response', str(result))

                # Clean up
                try:
                    os.remove(temp_path)
                except:
                    pass

                response = f"<b>Document Analysis:</b>\n\n{html.escape(analysis)}"
                if len(response) > 4000:
                    response = response[:4000] + "...\n\n<i>(truncated)</i>"

                await update.message.reply_text(response, parse_mode='HTML')

        except Exception as e:
            logger.error(f"Document analysis error: {e}", exc_info=True)
            await update.message.reply_text(f"Error analyzing document: {str(e)[:200]}")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages."""
        user = update.effective_user
        chat_id = update.effective_chat.id
        text = update.message.text

        if not self._is_authorized(user.id):
            await update.message.reply_text(
                f"Unauthorized. Your user ID ({user.id}) is not in the allowed list."
            )
            logger.warning(f"Unauthorized message from user {user.id}: {text[:50]}")
            return

        logger.info(f"Message from {user.id}: {text[:100]}")

        # NEW: Use ConversationManager first for natural language handling
        if self.conversation_manager:
            try:
                result = await self.conversation_manager.handle_message(text, user.id, chat_id)

                # If ConversationManager handled it completely, we're done
                if result.get('handled'):
                    logger.info(f"Message handled by conversation manager: {result.get('routed_to')}")
                    return

                # Otherwise, it detected legacy format or email request - continue to parser
                logger.info(f"Conversation manager routing to: {result.get('routed_to')}")

            except Exception as e:
                logger.error(f"ConversationManager error: {e}", exc_info=True)
                # Fall through to legacy parser

        # Parse the message (legacy format or email processing)
        parsed = self.parse_message(text)

        if not parsed.get('valid'):
            # More helpful message that doesn't assume email format
            await update.message.reply_text(
                "I'm not sure what you'd like me to do.\n\n"
                "<b>Try one of these:</b>\n"
                "• Just say hi or ask for help\n"
                "• <i>Draft email to Jason about invoice</i>\n"
                "• <i>Add call Sarah to my todos</i>\n"
                "• <i>Show my tasks</i>\n"
                "• <b>/digest</b> for your daily summary\n\n"
                "Type <b>help</b> to see all my capabilities!",
                parse_mode='HTML'
            )
            return

        # If callback is set, call it
        if self.message_callback:
            try:
                await self.message_callback(parsed, chat_id, user.id)
            except Exception as e:
                logger.error(f"Callback error: {e}")
                await update.message.reply_text(
                    f"Error processing request: {str(e)[:200]}"
                )
        else:
            # No callback, just acknowledge
            await update.message.reply_text(
                f"Parsed:\n"
                f"  Reference: {parsed['email_reference']}\n"
                f"  Instruction: {parsed['instruction']}\n"
                f"  Search type: {parsed['search_type']}\n\n"
                f"(No processor configured - message not processed)"
            )

    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors."""
        logger.error(f"Update {update} caused error {context.error}")

        if update and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"An error occurred: {str(context.error)[:200]}"
            )

    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        if not self.allowed_users:
            # If no allowed users configured, allow all (for testing)
            logger.warning("No allowed_users configured - allowing all users")
            return True
        return user_id in self.allowed_users

    # ==================
    # INLINE BUTTON HANDLING
    # ==================

    def _generate_draft_id(self) -> str:
        """Generate a unique draft ID for context tracking."""
        import uuid
        return str(uuid.uuid4())[:8]

    def _store_draft_context(
        self,
        draft_id: str,
        user_id: int,
        chat_id: int,
        email_data: Dict[str, Any],
        instruction: str,
        pattern_match: Optional[Dict] = None,
        recommendation: str = ""
    ):
        """Store draft context for callback handling."""
        import time
        self._draft_contexts[draft_id] = {
            'user_id': user_id,
            'chat_id': chat_id,
            'email_data': email_data,
            'instruction': instruction,
            'pattern_match': pattern_match,
            'recommendation': recommendation,
            'timestamp': time.time(),
            'draft_text': None,
            'model_used': None
        }
        # Cleanup old contexts
        self._cleanup_expired_contexts()

    def _get_draft_context(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """Get draft context by ID."""
        return self._draft_contexts.get(draft_id)

    def _update_draft_context(self, draft_id: str, updates: Dict[str, Any]):
        """Update an existing draft context."""
        if draft_id in self._draft_contexts:
            self._draft_contexts[draft_id].update(updates)

    def _cleanup_expired_contexts(self):
        """Remove expired draft contexts."""
        import time
        current_time = time.time()
        expiry_seconds = self._context_expiry_minutes * 60

        expired = [
            draft_id for draft_id, ctx in self._draft_contexts.items()
            if current_time - ctx['timestamp'] > expiry_seconds
        ]
        for draft_id in expired:
            del self._draft_contexts[draft_id]

    async def send_draft_request_with_buttons(
        self,
        chat_id: int,
        user_id: int,
        email_data: Dict[str, Any],
        instruction: str,
        pattern_match: Optional[Dict] = None,
        contact_known: bool = False
    ) -> str:
        """
        Send a draft request message with LLM selection buttons.

        Args:
            chat_id: Telegram chat ID
            user_id: User ID
            email_data: Email data (subject, body, sender_email, sender_name)
            instruction: User's instruction
            pattern_match: Pattern matching result (if any)
            contact_known: Whether sender is in contacts

        Returns:
            Draft ID for tracking
        """
        # Generate draft ID
        draft_id = self._generate_draft_id()

        # Get LLM recommendation
        try:
            from llm_router import route_draft_request
            routing = route_draft_request(
                instruction,
                email_data,
                pattern_match,
                contact_known
            )
            recommendation = routing.get('recommendation_text', 'Choose an LLM')
        except ImportError:
            recommendation = "Choose an LLM"
            routing = {'can_use_ollama': True, 'should_escalate': False}

        # Store context
        self._store_draft_context(
            draft_id=draft_id,
            user_id=user_id,
            chat_id=chat_id,
            email_data=email_data,
            instruction=instruction,
            pattern_match=pattern_match,
            recommendation=recommendation
        )

        # Build message
        subject = email_data.get('subject', '(no subject)')[:50]
        sender = email_data.get('sender_name', email_data.get('sender_email', 'Unknown'))
        body_preview = email_data.get('body', '')[:150].replace('\n', ' ')

        # Escape HTML special characters to prevent parsing errors
        sender_escaped = html.escape(sender)
        subject_escaped = html.escape(subject)
        body_preview_escaped = html.escape(body_preview)
        instruction_escaped = html.escape(instruction)
        recommendation_escaped = html.escape(recommendation)

        message = (
            f"📧 <b>Email Found</b>\n\n"
            f"<b>From:</b> {sender_escaped}\n"
            f"<b>Subject:</b> {subject_escaped}\n"
            f"<b>Preview:</b> {body_preview_escaped}...\n\n"
            f"<b>Your instruction:</b> {instruction_escaped}\n\n"
            f"<b>Recommendation:</b> {recommendation_escaped}\n\n"
            f"Choose LLM for drafting:"
        )

        # Build keyboard
        keyboard = [
            [
                InlineKeyboardButton("⚡ Ollama (Fast)", callback_data=f"draft:ollama:{draft_id}"),
                InlineKeyboardButton("🧠 Claude (Smart)", callback_data=f"draft:claude:{draft_id}")
            ]
        ]

        # Add cancel button
        keyboard.append([
            InlineKeyboardButton("❌ Cancel", callback_data=f"draft:cancel:{draft_id}")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

        return draft_id

    async def _handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button clicks."""
        query = update.callback_query
        user_id = query.from_user.id

        # Always answer the callback to remove loading state
        await query.answer()

        if not self._is_authorized(user_id):
            await query.edit_message_text("Unauthorized.")
            return

        # Parse callback data
        data = query.data
        parts = data.split(':')

        if len(parts) < 2:
            await query.edit_message_text("Invalid callback data.")
            return

        action_type = parts[0]

        if action_type == 'draft':
            await self._handle_draft_callback(query, parts)
        else:
            await query.edit_message_text(f"Unknown action: {action_type}")

    async def _handle_draft_callback(self, query, parts: List[str]):
        """Handle draft-related callbacks."""
        if len(parts) < 3:
            await query.edit_message_text("Invalid draft callback.")
            return

        action = parts[1]
        draft_id = parts[2]

        # Get context
        ctx = self._get_draft_context(draft_id)
        if not ctx:
            await query.edit_message_text(
                "Draft session expired. Please send your request again."
            )
            return

        if action == 'ollama':
            await self._draft_with_ollama(query, draft_id, ctx)
        elif action == 'claude':
            await self._draft_with_claude(query, draft_id, ctx)
        elif action == 'escalate':
            await self._escalate_to_claude(query, draft_id, ctx)
        elif action == 'approve':
            await self._approve_and_save(query, draft_id, ctx)
        elif action == 'edit':
            await self._request_edit(query, draft_id, ctx)
        elif action == 'cancel':
            await self._cancel_draft(query, draft_id, ctx)
        else:
            await query.edit_message_text(f"Unknown draft action: {action}")

    async def _draft_with_ollama(self, query, draft_id: str, ctx: Dict[str, Any]):
        """Generate draft using Ollama."""
        await query.edit_message_text("⏳ Generating draft with Ollama...")

        try:
            from ollama_client import OllamaClient
            ollama = OllamaClient()

            result = ollama.generate_email_draft(
                email_data=ctx['email_data'],
                instruction=ctx['instruction'],
                template=ctx.get('pattern_match', {}).get('template') if ctx.get('pattern_match') else None
            )

            if result.get('success'):
                draft_text = result.get('draft_text', '')
                confidence = result.get('confidence', 0)

                # Update context
                self._update_draft_context(draft_id, {
                    'draft_text': draft_text,
                    'model_used': 'ollama',
                    'confidence': confidence
                })

                # Show draft with action buttons
                await self._show_draft_preview(
                    query, draft_id, draft_text, 'Ollama', confidence
                )
            else:
                error = result.get('error', 'Unknown error')
                await query.edit_message_text(
                    f"❌ Ollama draft failed: {error}\n\n"
                    f"Try Claude instead?"
                )

            del ollama

        except Exception as e:
            logger.error(f"Ollama draft error: {e}")
            await query.edit_message_text(
                f"❌ Error generating draft: {str(e)[:200]}\n\n"
                f"Try Claude instead?"
            )

    async def _draft_with_claude(self, query, draft_id: str, ctx: Dict[str, Any]):
        """Generate draft using Claude."""
        await query.edit_message_text("⏳ Generating draft with Claude...")

        try:
            from claude_client import ClaudeClient
            claude = ClaudeClient()

            if not claude.is_available():
                await query.edit_message_text(
                    "❌ Claude API not configured.\n\n"
                    "Set ANTHROPIC_API_KEY in m1_config.py or environment."
                )
                return

            result = claude.generate_email_draft(
                email_data=ctx['email_data'],
                instruction=ctx['instruction'],
                template=ctx.get('pattern_match', {}).get('template') if ctx.get('pattern_match') else None
            )

            if result.get('success'):
                draft_text = result.get('draft_text', '')

                # Update context
                self._update_draft_context(draft_id, {
                    'draft_text': draft_text,
                    'model_used': 'claude',
                    'confidence': 95  # Claude drafts are high confidence
                })

                # Show draft with action buttons
                await self._show_draft_preview(
                    query, draft_id, draft_text, 'Claude', 95
                )
            else:
                error = result.get('error', 'Unknown error')
                await query.edit_message_text(f"❌ Claude draft failed: {error}")

            del claude

        except Exception as e:
            logger.error(f"Claude draft error: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)[:200]}")

    async def _escalate_to_claude(self, query, draft_id: str, ctx: Dict[str, Any]):
        """Refine Ollama draft with Claude."""
        ollama_draft = ctx.get('draft_text')
        if not ollama_draft:
            await query.edit_message_text("No draft to escalate.")
            return

        await query.edit_message_text("⏳ Refining draft with Claude...")

        try:
            from claude_client import ClaudeClient
            claude = ClaudeClient()

            if not claude.is_available():
                await query.edit_message_text(
                    "❌ Claude API not configured.\n\n"
                    "Set ANTHROPIC_API_KEY in m1_config.py or environment."
                )
                return

            result = claude.refine_draft(
                original_draft=ollama_draft,
                email_data=ctx['email_data'],
                instructions="Improve tone, clarity, and completeness"
            )

            if result.get('success'):
                refined_draft = result.get('draft_text', '')
                changes = result.get('changes_made', [])

                # Update context
                self._update_draft_context(draft_id, {
                    'draft_text': refined_draft,
                    'model_used': 'claude_refined',
                    'original_draft': ollama_draft,
                    'changes_made': changes,
                    'confidence': 95
                })

                # Show refined draft
                changes_text = '\n'.join(f"• {c}" for c in changes[:3]) if changes else "Minor improvements"

                await self._show_draft_preview(
                    query, draft_id, refined_draft, 'Claude (refined)',
                    95, extra_info=f"\n\n<b>Changes:</b>\n{changes_text}"
                )
            else:
                error = result.get('error', 'Unknown error')
                await query.edit_message_text(f"❌ Refinement failed: {error}")

            del claude

        except Exception as e:
            logger.error(f"Claude escalation error: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)[:200]}")

    async def _show_draft_preview(
        self,
        query,
        draft_id: str,
        draft_text: str,
        model: str,
        confidence: int,
        extra_info: str = ""
    ):
        """Show draft preview with action buttons."""
        ctx = self._get_draft_context(draft_id)
        email_data = ctx.get('email_data', {}) if ctx else {}

        # Format preview
        to = email_data.get('sender_email', 'Unknown')
        subject = email_data.get('subject', '(no subject)')
        if not subject.lower().startswith('re:'):
            subject = f"Re: {subject}"

        # Truncate draft for preview
        preview = draft_text[:300]
        if len(draft_text) > 300:
            preview += "..."

        # Escape HTML special characters
        to_escaped = html.escape(to)
        subject_escaped = html.escape(subject[:50])
        preview_escaped = html.escape(preview)
        extra_info_escaped = html.escape(extra_info) if extra_info else ""

        message = (
            f"📝 <b>Draft Preview</b>\n\n"
            f"<b>To:</b> {to_escaped}\n"
            f"<b>Subject:</b> {subject_escaped}\n"
            f"<b>Model:</b> {model} ({confidence}% confidence)\n\n"
            f"<b>Draft:</b>\n{preview_escaped}"
            f"{extra_info_escaped}"
        )

        # Build action buttons
        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"draft:approve:{draft_id}"),
        ]]

        # Add escalate option if Ollama was used
        if model == 'Ollama':
            keyboard[0].append(
                InlineKeyboardButton("🔄 Refine w/ Claude", callback_data=f"draft:escalate:{draft_id}")
            )

        keyboard.append([
            InlineKeyboardButton("❌ Cancel", callback_data=f"draft:cancel:{draft_id}")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def _approve_and_save(self, query, draft_id: str, ctx: Dict[str, Any]):
        """Save approved draft to Gmail."""
        draft_text = ctx.get('draft_text')
        if not draft_text:
            await query.edit_message_text("No draft to save.")
            return

        await query.edit_message_text("⏳ Saving draft to Gmail...")

        try:
            from gmail_client import GmailClient
            gmail = GmailClient()
            gmail.authenticate()

            email_data = ctx.get('email_data', {})

            result = gmail.create_reply_draft(
                email=email_data,
                body=draft_text
            )

            if result.get('success'):
                draft_url = result.get('draft_url', '')

                # Escape HTML special characters
                sender_email = html.escape(email_data.get('sender_email', 'Unknown'))
                subject = html.escape(email_data.get('subject', '')[:40])
                model_used = html.escape(ctx.get('model_used', 'Unknown'))
                draft_url_escaped = html.escape(draft_url)

                message = (
                    f"✅ <b>Draft Saved!</b>\n\n"
                    f"<b>To:</b> {sender_email}\n"
                    f"<b>Subject:</b> Re: {subject}\n"
                    f"<b>Model:</b> {model_used}\n\n"
                    f"<a href=\"{draft_url_escaped}\">Open in Gmail</a>"
                )

                await query.edit_message_text(
                    text=message,
                    parse_mode='HTML'
                )

                # Cleanup context
                if draft_id in self._draft_contexts:
                    del self._draft_contexts[draft_id]
            else:
                error = result.get('error', 'Unknown error')
                await query.edit_message_text(f"❌ Failed to save draft: {error}")

        except Exception as e:
            logger.error(f"Gmail save error: {e}")
            await query.edit_message_text(f"❌ Error saving: {str(e)[:200]}")

    async def _request_edit(self, query, draft_id: str, ctx: Dict[str, Any]):
        """Request user to provide edit instructions."""
        await query.edit_message_text(
            "Send your edit instructions as a new message.\n"
            "Example: 'Make it more formal' or 'Add urgency'\n\n"
            "(This feature is coming soon)"
        )

    async def _cancel_draft(self, query, draft_id: str, ctx: Dict[str, Any]):
        """Cancel draft creation."""
        # Cleanup context
        if draft_id in self._draft_contexts:
            del self._draft_contexts[draft_id]

        await query.edit_message_text("❌ Draft cancelled.")

    # ==================
    # SENDING RESPONSES
    # ==================

    async def send_response(self, chat_id: int, message: str):
        """
        Send a response message to a chat.

        Args:
            chat_id: Telegram chat ID
            message: Message text to send (should have HTML already escaped for dynamic content)
        """
        await self.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='HTML'
        )

    async def send_draft_notification(
        self,
        chat_id: int,
        email_subject: str,
        draft_url: str,
        confidence: int,
        route: str
    ):
        """
        Send a draft creation notification.

        Args:
            chat_id: Telegram chat ID
            email_subject: Subject of the email
            draft_url: URL to the Gmail draft
            confidence: Confidence score
            route: Routing decision
        """
        status_emoji = ""
        if route == 'ollama_only':
            status_emoji = "AI generated"
        elif route == 'ollama_with_review':
            status_emoji = "Needs review"
        else:
            status_emoji = "Escalated"

        # Escape HTML special characters
        email_subject_escaped = html.escape(email_subject[:50])
        draft_url_escaped = html.escape(draft_url)

        message = (
            f"Draft Created\n\n"
            f"Re: {email_subject_escaped}\n"
            f"Confidence: {confidence}%\n"
            f"Status: {status_emoji}\n\n"
            f"<a href=\"{draft_url_escaped}\">Open Draft in Gmail</a>"
        )

        await self.send_response(chat_id, message)

    async def send_error_notification(
        self,
        chat_id: int,
        email_reference: str,
        error: str
    ):
        """Send an error notification."""
        # Escape HTML special characters
        email_reference_escaped = html.escape(email_reference[:50])
        error_escaped = html.escape(error[:200])

        message = (
            f"Error Processing Email\n\n"
            f"Reference: {email_reference_escaped}\n"
            f"Error: {error_escaped}"
        )
        await self.send_response(chat_id, message)

    async def send_escalation_notification(
        self,
        chat_id: int,
        email_subject: str,
        confidence: int,
        reason: str
    ):
        """Send an escalation notification (low confidence)."""
        # Escape HTML special characters
        email_subject_escaped = html.escape(email_subject[:50])
        reason_escaped = html.escape(reason)

        message = (
            f"Escalated to Claude Desktop\n\n"
            f"Re: {email_subject_escaped}\n"
            f"Confidence: {confidence}%\n"
            f"Reason: {reason_escaped}\n\n"
            f"Handle via Claude Desktop when at work laptop."
        )
        await self.send_response(chat_id, message)

    # ==================
    # RUNNING THE BOT
    # ==================

    def run(self, message_callback: Callable = None):
        """
        Start the bot and run until interrupted.

        Args:
            message_callback: Async function to call when a message is received
        """
        self.setup_bot(message_callback)
        logger.info("Starting Telegram bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def run_async(self, message_callback: Callable = None):
        """
        Start the bot asynchronously.

        Args:
            message_callback: Async function to call when a message is received
        """
        self.setup_bot(message_callback)
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop_async(self):
        """Stop the bot asynchronously."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()


# ==================
# TESTING
# ==================

def test_message_parsing():
    """Test message parsing without running the bot."""
    print("Testing Message Parsing...")
    print("=" * 60)

    # Create handler with dummy token
    try:
        handler = TelegramHandler.__new__(TelegramHandler)
        handler.bot_token = "test"
        handler.allowed_users = []

        test_messages = [
            "Re: W9 Request - send W9 and wiring instructions",
            "From john@example.com - confirm payment received",
            "latest from sarah@company.com - schedule meeting",
            "Budget Q4 - approve the numbers",
            "invoice processing quarterly - confirm receipt",
            "/status",
            "/help",
            "just some random text",
        ]

        for msg in test_messages:
            result = handler.parse_message(msg)
            print(f"\nInput: {msg}")
            print(f"  Valid: {result['valid']}")
            print(f"  Reference: {result.get('email_reference', 'N/A')}")
            print(f"  Instruction: {result.get('instruction', 'N/A')}")
            print(f"  Search type: {result.get('search_type', 'N/A')}")
            if 'command' in result:
                print(f"  Command: {result['command']}")

    except TelegramHandlerError as e:
        # Expected if telegram library not installed
        print(f"Note: {e}")


if __name__ == "__main__":
    if not TELEGRAM_AVAILABLE:
        print("Telegram package not installed.")
        print("Run: pip install python-telegram-bot[job-queue]")
    else:
        test_message_parsing()
