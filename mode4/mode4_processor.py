"""
Mode 4 Processor - Main Orchestrator
Connects Telegram, Gmail, Sheets, and Ollama for email processing.

Usage:
    python mode4_processor.py

This is the main entry point for Mode 4. It:
1. Receives Telegram messages
2. Searches for matching emails in Gmail
3. Loads patterns/templates from Google Sheets
4. Uses Ollama for triage and draft generation
5. Creates Gmail drafts
6. Updates status in Google Sheets
7. Sends responses back to Telegram
"""

import os
import sys
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import html
from datetime import datetime
from typing import Dict, Any, Optional

# Set up logging with rotation to prevent unbounded log growth
_base_dir = os.path.dirname(os.path.abspath(__file__))
_log_fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

_console = logging.StreamHandler(sys.stdout)
_console.setFormatter(_log_fmt)

_file = RotatingFileHandler(
    os.path.join(_base_dir, 'mode4.log'),
    maxBytes=2 * 1024 * 1024,  # 2 MB
    backupCount=3,
    encoding='utf-8'
)
_file.setFormatter(_log_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_console, _file])

# Suppress noisy httpx polling logs (one line every ~10 seconds)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Mode 4 components
from gmail_client import GmailClient, GmailClientError
from ollama_client import OllamaClient, OllamaClientError
from pattern_matcher import PatternMatcher, PatternMatcherError
from telegram_handler import TelegramHandler, TelegramHandlerError
from llm_router import LLMRouter, route_draft_request
from queue_processor import QueueProcessor
from db_manager import DatabaseManager
from claude_client import ClaudeClient, ClaudeClientError
from kimi_client import KimiClient, KimiClientError

# Import new features
from smart_parser import SmartParser, SmartParserError
from thread_synthesizer import ThreadSynthesizer, ThreadSynthesizerError
from proactive_engine import ProactiveEngine, ProactiveEngineError

# Import Sheets client from parent
from sheets_client import GoogleSheetsClient, SheetsClientError


class Mode4Processor:
    """
    Main orchestrator for Mode 4 email processing.

    Coordinates all components to process emails based on Telegram commands.
    """

    def __init__(self):
        """Initialize the processor with all components."""
        logger.info("Initializing Mode 4 Processor...")

        # Load configuration
        try:
            from m1_config import (
                SPREADSHEET_ID, SHEETS_CREDENTIALS_PATH,
                OLLAMA_ONLY_THRESHOLD, OLLAMA_REVIEW_THRESHOLD,
                M1_STATUS_COLUMNS, MCP_QUEUE_SHEET
            )
            self.spreadsheet_id = SPREADSHEET_ID
            self.sheets_credentials = SHEETS_CREDENTIALS_PATH
            self.ollama_only_threshold = OLLAMA_ONLY_THRESHOLD
            self.ollama_review_threshold = OLLAMA_REVIEW_THRESHOLD
            self.status_columns = M1_STATUS_COLUMNS
            self.queue_sheet = MCP_QUEUE_SHEET
        except ImportError as e:
            logger.error(f"Configuration error: {e}")
            raise

        # Initialize components (lazy loading)
        self._gmail: Optional[GmailClient] = None
        self._ollama: Optional[OllamaClient] = None
        self._pattern_matcher: Optional[PatternMatcher] = None
        self._sheets: Optional[GoogleSheetsClient] = None
        self._telegram: Optional[TelegramHandler] = None
        self._queue_processor: Optional[QueueProcessor] = None
        self._db_manager: Optional[DatabaseManager] = None
        self._llm_router: Optional[LLMRouter] = None

        # New features (lazy loading)
        self._smart_parser: Optional[SmartParser] = None
        self._thread_synthesizer: Optional[ThreadSynthesizer] = None
        self._proactive_engine: Optional[ProactiveEngine] = None
        self._claude: Optional[ClaudeClient] = None
        self._kimi: Optional[KimiClient] = None

        # Background task tracking for graceful shutdown
        self._background_tasks: list = []

        # State tracking
        self.last_error: Optional[str] = None
        self.processed_count = 0

        # Feature flags
        self.use_inline_buttons = True  # Use new inline button flow

    @property
    def gmail(self) -> GmailClient:
        """Lazy-load Gmail client."""
        if self._gmail is None:
            self._gmail = GmailClient()
            self._gmail.authenticate()
            logger.info("Gmail client initialized")
        return self._gmail

    @property
    def ollama(self) -> OllamaClient:
        """Lazy-load Ollama client."""
        if self._ollama is None:
            self._ollama = OllamaClient()
            if not self._ollama.is_available():
                raise OllamaClientError("Ollama model not available. Run: ollama pull llama3.2")
            logger.info("Ollama client initialized")
        return self._ollama

    @property
    def pattern_matcher(self) -> PatternMatcher:
        """Lazy-load pattern matcher."""
        if self._pattern_matcher is None:
            self._pattern_matcher = PatternMatcher()
            self._pattern_matcher.load_data()
            logger.info(f"Pattern matcher initialized with {len(self._pattern_matcher.patterns)} patterns")
        return self._pattern_matcher

    @property
    def sheets(self) -> GoogleSheetsClient:
        """Lazy-load Sheets client."""
        if self._sheets is None:
            self._sheets = GoogleSheetsClient(self.sheets_credentials)
            self._sheets.connect()
            logger.info("Sheets client initialized")
        return self._sheets

    @property
    def telegram(self) -> TelegramHandler:
        """Lazy-load Telegram handler."""
        if self._telegram is None:
            self._telegram = TelegramHandler()
            # Give telegram handler reference to processor for SmartParser access
            self._telegram.processor = self
            # Set processor reference for conversation manager
            self._telegram.set_conversation_processor(self)
            logger.info("Telegram handler initialized")
        return self._telegram

    @property
    def queue_processor(self) -> QueueProcessor:
        """Lazy-load queue processor."""
        if self._queue_processor is None:
            self._queue_processor = QueueProcessor()
            logger.info("Queue processor initialized")
        return self._queue_processor

    @property
    def db_manager(self) -> DatabaseManager:
        """Lazy-load database manager."""
        if self._db_manager is None:
            self._db_manager = DatabaseManager()
            logger.info("Database manager initialized")
        return self._db_manager

    @property
    def llm_router(self) -> LLMRouter:
        """Lazy-load LLM router."""
        if self._llm_router is None:
            self._llm_router = LLMRouter()
            logger.info("LLM router initialized")
        return self._llm_router

    @property
    def smart_parser(self) -> SmartParser:
        """Lazy-load Smart Parser."""
        if self._smart_parser is None:
            from m1_config import SMART_PARSER_MODEL
            self._smart_parser = SmartParser(model=SMART_PARSER_MODEL)
            if self._smart_parser.available:
                logger.info(f"Smart Parser initialized with LLM model: {SMART_PARSER_MODEL}")
            else:
                logger.info("Smart Parser initialized (regex-only mode)")
        return self._smart_parser

    @property
    def thread_synthesizer(self) -> ThreadSynthesizer:
        """Lazy-load Thread Synthesizer."""
        if self._thread_synthesizer is None:
            from m1_config import MODE4_DB_PATH
            self._thread_synthesizer = ThreadSynthesizer(db_path=MODE4_DB_PATH)
            logger.info("Thread Synthesizer initialized")
        return self._thread_synthesizer

    @property
    def proactive_engine(self) -> ProactiveEngine:
        """Lazy-load Proactive Engine."""
        if self._proactive_engine is None:
            self._proactive_engine = ProactiveEngine(
                processor=self,
                telegram_handler=self.telegram
            )
            logger.info("Proactive Engine initialized")
        return self._proactive_engine

    @property
    def claude(self) -> ClaudeClient:
        """Lazy-load Claude client."""
        if self._claude is None:
            self._claude = ClaudeClient()
            logger.info("Claude client initialized")
        return self._claude

    @property
    def kimi(self) -> KimiClient:
        """Lazy-load Kimi K2 client."""
        if self._kimi is None:
            self._kimi = KimiClient()
            logger.info("Kimi K2 client initialized")
        return self._kimi

    async def start_proactive_engine(self):
        """Start proactive engine background worker."""
        from m1_config import PROACTIVE_ENGINE_ENABLED

        if not PROACTIVE_ENGINE_ENABLED:
            logger.info("Proactive Engine disabled by config")
            return

        logger.info("Starting Proactive Engine background workers...")

        # Start worker loops and store references for graceful shutdown
        task1 = asyncio.create_task(self.proactive_engine.worker_loop())
        task2 = asyncio.create_task(self.proactive_engine.schedule_morning_digest())
        self._background_tasks.extend([task1, task2])

    # ==================
    # MAIN PROCESSING
    # ==================

    async def process_message(
        self,
        parsed_message: Dict[str, Any],
        chat_id: int,
        user_id: int
    ):
        """
        Process a parsed Telegram message.

        This is the main entry point called by the Telegram handler.

        Args:
            parsed_message: Output from TelegramHandler.parse_message()
            chat_id: Telegram chat ID for responses
            user_id: Telegram user ID
        """
        logger.info(f"Processing message from user {user_id}: {parsed_message.get('email_reference', '')[:50]}")

        # Handle commands
        if 'command' in parsed_message:
            # Commands are handled by TelegramHandler
            return

        email_reference = parsed_message.get('email_reference', '')
        instruction = parsed_message.get('instruction', '')
        search_type = parsed_message.get('search_type', 'keyword')

        try:
            # Step 1: Search for email
            await self.telegram.send_typing(chat_id)
            email_reference_escaped = html.escape(email_reference[:50])
            await self.telegram.send_response(
                chat_id,
                f"🔍 Searching for email: {email_reference_escaped}..."
            )

            email = self.gmail.search_email(
                email_reference,
                search_type=search_type,
                max_results=1
            )

            if not email:
                await self.telegram.send_error_notification(
                    chat_id,
                    email_reference,
                    f"No email found matching '{email_reference}'"
                )
                return

            logger.info(f"Found email: {email.get('subject', '')[:50]}")

            # Step 2: Load patterns and check contact
            patterns = self.pattern_matcher.patterns
            sender_known = self.pattern_matcher.is_known_sender(email.get('sender_email', ''))
            contact_info = self.pattern_matcher.get_contact_info(email.get('sender_email', ''))

            # Step 3: Get pattern match
            pattern_match = self.pattern_matcher.match_pattern(
                email_content=email.get('body', ''),
                subject=email.get('subject', '')
            )

            # Step 4: Use new inline button flow OR legacy flow
            if self.use_inline_buttons:
                # NEW FLOW: Show email with LLM selection buttons
                await self.telegram.send_draft_request_with_buttons(
                    chat_id=chat_id,
                    user_id=user_id,
                    email_data=email,
                    instruction=instruction,
                    pattern_match=pattern_match,
                    contact_known=sender_known
                )
                logger.info("Sent draft request with inline buttons")
            else:
                # LEGACY FLOW: Automatic triage and generation
                # Wrap blocking Ollama call in executor to prevent heartbeat timeout
                loop = asyncio.get_event_loop()
                triage_result = await loop.run_in_executor(
                    None,
                    lambda: self.ollama.triage(
                        email,
                        patterns,
                        list(self.pattern_matcher.contacts.values())
                    )
                )

                confidence = triage_result.get('confidence', 50)
                route = triage_result.get('route', 'escalate_to_claude')
                pattern_name = triage_result.get('pattern_name')

                logger.info(f"Triage result: confidence={confidence}, route={route}, pattern={pattern_name}")

                if route == 'escalate_to_claude':
                    await self._handle_low_confidence(
                        chat_id, email, triage_result, instruction
                    )
                else:
                    await self._handle_draft_generation(
                        chat_id, email, triage_result, instruction,
                        contact_info, route
                    )

            self.processed_count += 1

        except GmailClientError as e:
            logger.error(f"Gmail error: {e}")
            await self.telegram.send_error_notification(
                chat_id, email_reference, f"Gmail error: {str(e)}"
            )

        except OllamaClientError as e:
            logger.error(f"Ollama error: {e}")
            await self.telegram.send_error_notification(
                chat_id, email_reference, f"Ollama error: {str(e)}"
            )

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            await self.telegram.send_error_notification(
                chat_id, email_reference, f"Error: {str(e)}"
            )

    async def _handle_low_confidence(
        self,
        chat_id: int,
        email: Dict[str, Any],
        triage_result: Dict[str, Any],
        instruction: str
    ):
        """Handle low confidence emails - flag for Claude Desktop."""
        confidence = triage_result.get('confidence', 0)
        reasoning = triage_result.get('reasoning', [])

        logger.info(f"Escalating to Claude Desktop: confidence={confidence}")

        # Update Sheets status
        try:
            self._update_sheets_status(
                email.get('thread_id', ''),
                email.get('subject', ''),
                m1_status='escalated_to_claude',
                confidence=confidence,
                processed_by='escalated',
                notes=f"Low confidence ({confidence}%): {'; '.join(reasoning[:2])}"
            )
        except Exception as e:
            logger.error(f"Failed to update Sheets: {e}")

        # Send notification
        await self.telegram.send_escalation_notification(
            chat_id,
            email.get('subject', 'Unknown'),
            confidence,
            '; '.join(reasoning[:2]) if reasoning else 'Low confidence'
        )

    async def _handle_draft_generation(
        self,
        chat_id: int,
        email: Dict[str, Any],
        triage_result: Dict[str, Any],
        instruction: str,
        contact_info: Optional[Dict],
        route: str
    ):
        """Handle draft generation for medium/high confidence emails."""
        confidence = triage_result.get('confidence', 50)
        pattern_name = triage_result.get('pattern_name')

        # Get template if pattern matched
        template = None
        if pattern_name:
            template = self.pattern_matcher.get_template_for_pattern(pattern_name)

        # Get preferred tone from contact
        contact_tone = None
        if contact_info:
            contact_tone = contact_info.get('preferred_tone')

        # Generate draft
        logger.info(f"Generating draft: pattern={pattern_name}, template={template is not None}")

        # Wrap blocking Ollama call in executor to prevent heartbeat timeout
        loop = asyncio.get_event_loop()
        draft_result = await loop.run_in_executor(
            None,
            lambda: self.ollama.generate_draft(
                email,
                instruction,
                template=template,
                contact_tone=contact_tone
            )
        )

        if not draft_result.get('success'):
            await self.telegram.send_error_notification(
                chat_id,
                email.get('subject', ''),
                f"Failed to generate draft: {draft_result.get('error', 'Unknown error')}"
            )
            return

        draft_text = draft_result.get('draft_text', '')

        # Create Gmail draft
        logger.info("Creating Gmail draft...")

        gmail_draft = self.gmail.create_reply_draft(email, draft_text)

        if not gmail_draft.get('success'):
            await self.telegram.send_error_notification(
                chat_id,
                email.get('subject', ''),
                f"Failed to create Gmail draft: {gmail_draft.get('error', 'Unknown error')}"
            )
            return

        draft_url = gmail_draft.get('draft_url', '')

        # Update Sheets status
        status = 'done' if route == 'ollama_only' else 'needs_review'
        processed_by = 'ollama' if route == 'ollama_only' else 'ollama+review'

        try:
            self._update_sheets_status(
                email.get('thread_id', ''),
                email.get('subject', ''),
                m1_status=status,
                confidence=confidence,
                processed_by=processed_by,
                draft_url=draft_url,
                notes=f"Pattern: {pattern_name or 'none'}, Template: {template.get('template_id', 'none') if template else 'none'}"
            )
        except Exception as e:
            logger.error(f"Failed to update Sheets: {e}")

        # Send notification
        await self.telegram.send_draft_notification(
            chat_id,
            email.get('subject', 'Unknown'),
            draft_url,
            confidence,
            route
        )

    def _update_sheets_status(
        self,
        thread_id: str,
        subject: str,
        m1_status: str,
        confidence: int,
        processed_by: str,
        draft_url: str = '',
        notes: str = ''
    ):
        """Update status in Google Sheets."""
        # For now, just log the update
        # TODO: Implement proper row lookup and update
        logger.info(
            f"Sheets update: thread_id={thread_id}, status={m1_status}, "
            f"confidence={confidence}, processed_by={processed_by}"
        )

        # Append to a Mode 4 log sheet
        try:
            values = [[
                datetime.now().isoformat(),
                thread_id,
                subject[:50],
                m1_status,
                confidence,
                processed_by,
                draft_url,
                notes
            ]]

            self.sheets.append_rows(
                self.spreadsheet_id,
                'Mode4_Log!A:H',
                values
            )
        except Exception as e:
            logger.warning(f"Could not append to Mode4_Log sheet: {e}")

    # ==================
    # RUN METHODS
    # ==================

    def run(self):
        """Run the Mode 4 processor (blocking)."""
        logger.info("Starting Mode 4 Processor...")

        # Validate configuration
        errors = self._validate_config()
        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            sys.exit(1)

        # Initialize database
        try:
            self.db_manager.initialize()
            logger.info("Database initialized")
        except Exception as e:
            logger.warning(f"Database initialization warning: {e}")

        # Process any queued messages from when bot was offline
        try:
            asyncio.run(self._process_startup_queue())
        except Exception as e:
            logger.warning(f"Queue processing warning: {e}")

        # Set up Telegram with our callback
        self.telegram.run(message_callback=self.process_message)

    async def run_async(self):
        """Run the processor asynchronously."""
        logger.info("Starting Mode 4 Processor (async)...")

        errors = self._validate_config()
        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            return

        # Initialize database
        try:
            self.db_manager.initialize()
            logger.info("Database initialized")
        except Exception as e:
            logger.warning(f"Database initialization warning: {e}")

        # Process any queued messages
        await self._process_startup_queue()

        await self.telegram.run_async(message_callback=self.process_message)

    async def _process_startup_queue(self):
        """Process any messages queued while bot was offline."""
        logger.info("Checking for queued messages...")

        try:
            status = self.queue_processor.get_queue_status()
            pending = status.get('pending_count', 0)

            if pending > 0:
                logger.info(f"Found {pending} pending messages in queue")

                async def progress_callback(msg_id, status, details):
                    logger.info(f"Queue message {msg_id}: {status}")

                results = await self.queue_processor.process_queue(
                    progress_callback=progress_callback,
                    telegram_handler=self.telegram
                )

                logger.info(
                    f"Queue processing complete: {results['successful']} successful, "
                    f"{results['failed']} failed"
                )
            else:
                logger.info("No pending messages in queue")

        except Exception as e:
            logger.error(f"Error processing startup queue: {e}")

    def _validate_config(self) -> list:
        """Validate configuration before starting."""
        errors = []

        try:
            from m1_config import validate_config
            errors = validate_config()
        except ImportError:
            errors.append("m1_config.py not found")

        return errors

    def cleanup(self):
        """Clean up resources."""
        # Cancel background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled background task: {task.get_name()}")
        self._background_tasks.clear()

        if self._sheets:
            self._sheets.close()
        if self._pattern_matcher:
            self._pattern_matcher.close()
        if self._queue_processor:
            self._queue_processor.cleanup()
        if self._db_manager:
            del self._db_manager
            self._db_manager = None


# ==================
# MAIN ENTRY POINT
# ==================

def main():
    """Main entry point."""
    print()
    print("=" * 60)
    print("  MODE 4 PROCESSOR - MCP Email System")
    print("  M1 + Clawdbot via Telegram")
    print("=" * 60)
    print()

    try:
        processor = Mode4Processor()
        processor.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\nFatal error: {e}")
        sys.exit(1)
    finally:
        if 'processor' in locals():
            processor.cleanup()


if __name__ == "__main__":
    main()
