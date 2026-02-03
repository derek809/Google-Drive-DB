"""
Queue Processor for Mode 4
Processes queued messages from the database with fresh context per message.

Key principle: Each message gets isolated context - no token bloat.

Usage:
    from queue_processor import QueueProcessor

    processor = QueueProcessor()

    # Process all pending messages
    await processor.process_queue()

    # Process with progress callback
    async def on_progress(msg_id, status, details):
        print(f"Message {msg_id}: {status}")

    await processor.process_queue(progress_callback=on_progress)
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class QueueProcessorError(Exception):
    """Custom exception for queue processor errors."""
    pass


class QueueProcessor:
    """
    Processes queued Telegram messages with fresh context per message.

    Uses the database manager to fetch pending messages and process
    them one at a time, ensuring no context leaks between messages.
    """

    def __init__(self, db_path: str = None):
        """
        Initialize queue processor.

        Args:
            db_path: Path to mode4.db (optional, uses default)
        """
        self.db_path = db_path
        self._db_manager = None

    def _get_db_manager(self):
        """Lazy load database manager."""
        if self._db_manager is None:
            from db_manager import DatabaseManager
            self._db_manager = DatabaseManager(self.db_path)
        return self._db_manager

    async def process_queue(
        self,
        progress_callback: Optional[Callable] = None,
        max_messages: int = 50,
        telegram_handler = None
    ) -> Dict[str, Any]:
        """
        Process all pending messages in the queue.

        Args:
            progress_callback: Async function called for each message
                              Signature: async callback(msg_id, status, details)
            max_messages: Maximum messages to process in one batch
            telegram_handler: TelegramHandler instance for sending updates

        Returns:
            Dict with processing summary
        """
        db = self._get_db_manager()
        results = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        # Get pending messages
        pending = db.get_pending_queue_messages(limit=max_messages)

        if not pending:
            logger.info("No pending messages in queue")
            return results

        logger.info(f"Processing {len(pending)} queued messages")

        for msg in pending:
            msg_id = msg['id']
            telegram_msg_id = msg['telegram_message_id']

            try:
                # Mark as processing
                db.update_queue_status(msg_id, 'processing')

                if progress_callback:
                    await progress_callback(msg_id, 'processing', {'message': msg})

                # Process with fresh context
                result = await self._process_single_message(
                    msg, telegram_handler
                )

                if result.get('success'):
                    db.update_queue_status(
                        msg_id, 'completed',
                        draft_id=result.get('draft_id'),
                        gmail_draft_id=result.get('gmail_draft_id'),
                        confidence_score=result.get('confidence'),
                        model_used=result.get('model_used')
                    )
                    results['successful'] += 1

                    if progress_callback:
                        await progress_callback(msg_id, 'completed', result)
                else:
                    error = result.get('error', 'Unknown error')
                    db.update_queue_status(msg_id, 'failed', error_message=error)
                    results['failed'] += 1
                    results['errors'].append({
                        'msg_id': msg_id,
                        'error': error
                    })

                    if progress_callback:
                        await progress_callback(msg_id, 'failed', {'error': error})

                results['processed'] += 1

            except Exception as e:
                logger.error(f"Error processing message {msg_id}: {e}")
                db.update_queue_status(msg_id, 'failed', error_message=str(e))
                results['failed'] += 1
                results['errors'].append({
                    'msg_id': msg_id,
                    'error': str(e)
                })

            # Small delay between messages to prevent overload
            await asyncio.sleep(0.5)

        logger.info(
            f"Queue processing complete: {results['processed']} processed, "
            f"{results['successful']} successful, {results['failed']} failed"
        )

        return results

    async def _process_single_message(
        self,
        msg: Dict[str, Any],
        telegram_handler = None
    ) -> Dict[str, Any]:
        """
        Process a single queued message with fresh context.

        Args:
            msg: Message data from queue
            telegram_handler: TelegramHandler for sending updates

        Returns:
            Dict with processing result
        """
        message_text = msg.get('message_text', '')
        user_id = msg.get('user_id')
        chat_id = msg.get('chat_id')
        llm_choice = msg.get('llm_choice', 'ollama')

        # Parse message - use fresh TelegramHandler instance
        from telegram_handler import TelegramHandler
        temp_handler = TelegramHandler.__new__(TelegramHandler)
        temp_handler.bot_token = "temp"
        temp_handler.allowed_users = []
        parsed = temp_handler.parse_message(message_text)
        del temp_handler

        if not parsed.get('valid'):
            return {
                'success': False,
                'error': 'Could not parse message'
            }

        # Search for email - use fresh GmailClient instance
        email_data = None
        try:
            from gmail_client import GmailClient
            gmail = GmailClient()
            gmail.authenticate()

            email_data = gmail.search_email(
                reference=parsed.get('email_reference', ''),
                search_type=parsed.get('search_type', 'keyword'),
                max_results=1
            )

            del gmail  # Cleanup
        except Exception as e:
            return {
                'success': False,
                'error': f'Gmail search failed: {str(e)}'
            }

        if not email_data:
            return {
                'success': False,
                'error': f"No email found for: {parsed.get('email_reference', '')}"
            }

        # Check pattern match - use fresh PatternMatcher instance
        pattern_match = None
        contact_known = False
        try:
            from pattern_matcher import PatternMatcher
            matcher = PatternMatcher()
            pattern_match = matcher.match(
                subject=email_data.get('subject', ''),
                body=email_data.get('body', ''),
                sender=email_data.get('sender_email', '')
            )
            contact_known = matcher.is_contact_known(email_data.get('sender_email', ''))
            del matcher
        except Exception as e:
            logger.warning(f"Pattern matching failed: {e}")

        # Generate draft based on LLM choice
        draft_result = None
        model_used = llm_choice

        if llm_choice == 'claude':
            draft_result = await self._generate_with_claude(
                email_data, parsed.get('instruction', ''), pattern_match
            )
            model_used = 'claude'
        else:
            # Default to Ollama
            draft_result = await self._generate_with_ollama(
                email_data, parsed.get('instruction', ''), pattern_match
            )
            model_used = 'ollama'

        if not draft_result or not draft_result.get('success'):
            return {
                'success': False,
                'error': draft_result.get('error', 'Draft generation failed')
            }

        # Save to Gmail drafts
        draft_text = draft_result.get('draft_text', '')
        gmail_result = None

        try:
            from gmail_client import GmailClient
            gmail = GmailClient()
            gmail.authenticate()

            gmail_result = gmail.create_reply_draft(
                email=email_data,
                body=draft_text
            )

            del gmail
        except Exception as e:
            return {
                'success': False,
                'error': f'Gmail draft creation failed: {str(e)}'
            }

        if not gmail_result or not gmail_result.get('success'):
            return {
                'success': False,
                'error': gmail_result.get('error', 'Draft save failed')
            }

        # Send notification if handler available
        if telegram_handler and chat_id:
            try:
                await telegram_handler.send_draft_notification(
                    chat_id=chat_id,
                    email_subject=email_data.get('subject', ''),
                    draft_url=gmail_result.get('draft_url', ''),
                    confidence=draft_result.get('confidence', 0),
                    route=model_used
                )
            except Exception as e:
                logger.warning(f"Failed to send notification: {e}")

        return {
            'success': True,
            'draft_id': gmail_result.get('draft_id'),
            'gmail_draft_id': gmail_result.get('message_id'),
            'draft_url': gmail_result.get('draft_url'),
            'confidence': draft_result.get('confidence', 0),
            'model_used': model_used
        }

    async def _generate_with_ollama(
        self,
        email_data: Dict[str, Any],
        instruction: str,
        pattern_match: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate draft with Ollama (fresh instance)."""
        try:
            from ollama_client import OllamaClient
            ollama = OllamaClient()

            template = pattern_match.get('template') if pattern_match else None

            result = ollama.generate_draft(
                email_data=email_data,
                instruction=instruction,
                template=template
            )

            del ollama  # Cleanup
            return result

        except Exception as e:
            return {
                'success': False,
                'error': f'Ollama error: {str(e)}'
            }

    async def _generate_with_claude(
        self,
        email_data: Dict[str, Any],
        instruction: str,
        pattern_match: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate draft with Claude (fresh instance)."""
        try:
            from claude_client import ClaudeClient
            claude = ClaudeClient()

            if not claude.is_available():
                del claude
                return {
                    'success': False,
                    'error': 'Claude API not configured'
                }

            template = pattern_match.get('template') if pattern_match else None

            result = claude.generate_email_draft(
                email_data=email_data,
                instruction=instruction,
                template=template
            )

            del claude  # Cleanup
            return result

        except Exception as e:
            return {
                'success': False,
                'error': f'Claude error: {str(e)}'
            }

    def queue_message(
        self,
        telegram_message_id: str,
        user_id: int,
        chat_id: int,
        message_text: str,
        llm_choice: str = 'user_pending'
    ) -> int:
        """
        Add a message to the processing queue.

        Args:
            telegram_message_id: Telegram message ID
            user_id: User ID
            chat_id: Chat ID
            message_text: Message text
            llm_choice: LLM choice ('ollama', 'claude', or 'user_pending')

        Returns:
            Queue entry ID
        """
        db = self._get_db_manager()
        return db.add_to_queue(
            telegram_message_id=telegram_message_id,
            user_id=user_id,
            chat_id=chat_id,
            message_text=message_text,
            llm_choice=llm_choice
        )

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        db = self._get_db_manager()

        pending = db.get_pending_queue_messages(limit=100)
        processing = db.get_queue_messages_by_status('processing', limit=100)

        return {
            'pending_count': len(pending),
            'processing_count': len(processing),
            'pending_messages': pending[:10],  # First 10
            'processing_messages': processing[:10]
        }

    def retry_failed(self, msg_id: int) -> bool:
        """
        Retry a failed message.

        Args:
            msg_id: Queue message ID

        Returns:
            True if reset successful
        """
        db = self._get_db_manager()
        return db.update_queue_status(msg_id, 'pending', error_message=None)

    def cleanup(self):
        """Cleanup resources."""
        if self._db_manager:
            del self._db_manager
            self._db_manager = None


# ==================
# TESTING
# ==================

async def test_queue_processor():
    """Test the queue processor."""
    print("Testing Queue Processor...")
    print("=" * 60)

    processor = QueueProcessor()

    # Check status
    status = processor.get_queue_status()
    print(f"\nQueue Status:")
    print(f"  Pending: {status['pending_count']}")
    print(f"  Processing: {status['processing_count']}")

    # Test queueing a message
    print("\nTesting message queueing...")
    try:
        msg_id = processor.queue_message(
            telegram_message_id="test_123",
            user_id=12345,
            chat_id=12345,
            message_text="Re: Test Subject - send confirmation",
            llm_choice='ollama'
        )
        print(f"  Queued message with ID: {msg_id}")
    except Exception as e:
        print(f"  Error queueing: {e}")

    # Check status again
    status = processor.get_queue_status()
    print(f"\nUpdated Queue Status:")
    print(f"  Pending: {status['pending_count']}")

    # Cleanup
    processor.cleanup()
    print("\nQueue processor test complete!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_queue_processor())
