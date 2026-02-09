"""
Skill Manager - Central coordinator for skill lifecycle.
Orchestrates: idea finalization -> Master Doc storage -> Sheets sync -> task creation.

Usage:
    from skill_manager import SkillManager

    mgr = SkillManager()

    # Finalize an active idea session
    result = await mgr.finalize_skill(user_id, chat_id)

    # Quick capture without session
    result = await mgr.capture_quick(user_id, "Idea: automate RR onboarding")

    # Process inbox entries from Master Doc
    results = await mgr.process_inbox()
"""

import re
import json
import logging
import random
import string
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class SkillManagerError(Exception):
    """Custom exception for skill manager errors."""
    pass


class SkillManager:
    """
    Orchestrates skill capture -> storage -> task creation -> retrieval.

    Flow:
    1. Get idea content (from session, quick capture, or inbox)
    2. Generate unique slug
    3. Extract metadata via LLM (Type, Tags, Action Items)
    4. Format for Master Doc
    5. Append to Google Doc
    6. Sync to Google Sheets
    7. Store in SQLite for fast retrieval
    """

    def __init__(self):
        """Initialize skill manager with lazy-loaded dependencies."""
        self._db = None
        self._docs_client = None
        self._sheets_client = None
        self._ollama = None
        self._telegram = None

    # ==================
    # LAZY LOADERS
    # ==================

    def _get_db(self):
        """Lazy load database manager."""
        if self._db is None:
            from db_manager import DatabaseManager
            self._db = DatabaseManager()
        return self._db

    def _get_docs_client(self):
        """Lazy load Google Docs client."""
        if self._docs_client is None:
            from google_docs_client import GoogleDocsClient
            self._docs_client = GoogleDocsClient()
            self._docs_client.authenticate()
        return self._docs_client

    def _get_sheets_client(self):
        """Lazy load Google Sheets client."""
        if self._sheets_client is None:
            try:
                # Use existing sheets client from mode4
                from mode4_processor import Mode4Processor
                processor = Mode4Processor()
                self._sheets_client = processor.sheets
            except Exception as e:
                logger.warning(f"Could not load sheets client: {e}")
        return self._sheets_client

    def _get_ollama(self):
        """Lazy load Ollama client for LLM operations."""
        if self._ollama is None:
            try:
                from ollama_client import OllamaClient
                self._ollama = OllamaClient()
            except Exception as e:
                logger.warning(f"Could not load Ollama: {e}")
        return self._ollama

    # ==================
    # CORE OPERATIONS
    # ==================

    async def finalize_skill(self, user_id: int, chat_id: int = None) -> Dict[str, Any]:
        """
        Finalize the active idea session into a skill.

        This is the main entry point when user says "finalize" or "/finalize".

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID (for sending responses)

        Returns:
            Dict with skill info and status
        """
        db = self._get_db()

        # Get active idea session
        session = db.get_active_idea_session(user_id)

        if not session:
            return {
                "success": False,
                "error": "No active idea session found. Start one with /idea <topic>"
            }

        # Build content from session
        idea_content = self._build_content_from_session(session)

        # Process into skill
        result = await self._process_skill(
            user_id=user_id,
            raw_content=idea_content,
            idea_session_id=session.get('id')
        )

        if result.get('success'):
            # Mark idea session as completed
            db.update_idea_session(session['id'], status='completed')

        return result

    async def capture_quick(self, user_id: int, raw_text: str) -> Dict[str, Any]:
        """
        Quick capture of an idea without going through a session.

        Triggered by: "Idea: ...", "Note: ...", "Task: ...", etc.

        Args:
            user_id: Telegram user ID
            raw_text: Raw input text (with prefix like "Idea:")

        Returns:
            Dict with skill info and status
        """
        # Remove the prefix to get clean content
        content = re.sub(r'^(idea|note|task|brainstorm):\s*', '', raw_text, flags=re.IGNORECASE)

        return await self._process_skill(
            user_id=user_id,
            raw_content=content.strip()
        )

    async def process_inbox(self) -> List[Dict[str, Any]]:
        """
        Process entries from the ## INBOX section of Master Doc.

        Reads inbox, processes each entry, clears inbox when done.

        Returns:
            List of results for each processed entry
        """
        docs = self._get_docs_client()

        try:
            from m1_config import MASTER_DOC_ID
        except ImportError:
            return [{"success": False, "error": "MASTER_DOC_ID not configured"}]

        if not MASTER_DOC_ID:
            return [{"success": False, "error": "MASTER_DOC_ID is empty"}]

        # Read inbox
        inbox_result = docs.read_inbox(MASTER_DOC_ID)

        if not inbox_result.get('success'):
            return [{"success": False, "error": inbox_result.get('error')}]

        if not inbox_result.get('has_content'):
            return [{"success": True, "message": "Inbox is empty", "processed": 0}]

        inbox_content = inbox_result['content']

        # Split into separate entries (by blank lines or ---)
        entries = re.split(r'\n{2,}|---', inbox_content)
        entries = [e.strip() for e in entries if e.strip()]

        results = []
        for entry in entries:
            # Process each entry (use a default user_id for inbox processing)
            result = await self._process_skill(
                user_id=0,  # System-processed
                raw_content=entry
            )
            results.append(result)

        # Clear inbox after processing
        if results:
            docs.clear_inbox(MASTER_DOC_ID)

        return results

    async def _process_skill(
        self,
        user_id: int,
        raw_content: str,
        idea_session_id: str = None
    ) -> Dict[str, Any]:
        """
        Internal method to process content into a skill.

        Args:
            user_id: User ID
            raw_content: The raw idea/note content
            idea_session_id: Optional link to idea session

        Returns:
            Dict with skill info
        """
        try:
            # Step 1: Extract metadata via LLM
            metadata = await self._extract_metadata(raw_content)

            # Step 2: Generate unique slug
            slug = self._generate_slug(
                skill_type=metadata.get('type', 'Note'),
                keywords=metadata.get('keywords', [])
            )

            # Step 3: Format for Master Doc
            formatted_entry = self._format_for_doc(
                slug=slug,
                metadata=metadata,
                body=raw_content
            )

            # Step 4: Append to Google Doc
            doc_result = await self._append_to_doc(formatted_entry)

            # Step 5: Sync to Google Sheets
            sheet_row_ids = await self._sync_to_sheets(slug, metadata, raw_content)

            # Step 6: Store in SQLite
            db = self._get_db()
            db.create_skill(
                slug=slug,
                user_id=user_id,
                skill_type=metadata.get('type', 'Note'),
                title=metadata.get('title', slug),
                body=raw_content,
                context=metadata.get('context'),
                action_items=metadata.get('action_items'),
                tags=metadata.get('tags'),
                doc_position=doc_result.get('insert_index'),
                sheet_row_ids=sheet_row_ids,
                idea_session_id=idea_session_id
            )

            # Step 7: Create tasks from action items (if enabled)
            tasks_created = []
            try:
                from m1_config import SKILL_AUTO_CREATE_TASKS
                if SKILL_AUTO_CREATE_TASKS and metadata.get('action_items'):
                    tasks_created = await self._create_tasks_from_actions(
                        slug=slug,
                        action_items=metadata['action_items'],
                        context=metadata.get('context')
                    )
            except ImportError:
                pass

            logger.info(f"Created skill: {slug}")

            return {
                "success": True,
                "slug": slug,
                "type": metadata.get('type'),
                "title": metadata.get('title'),
                "action_items_count": len(metadata.get('action_items', [])),
                "tasks_created": len(tasks_created),
                "doc_updated": doc_result.get('success', False),
                "sheets_updated": len(sheet_row_ids) > 0
            }

        except Exception as e:
            logger.error(f"Error processing skill: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    # ==================
    # RETRIEVAL
    # ==================

    def get_skill(self, slug: str) -> Optional[Dict]:
        """Get a skill by slug from SQLite."""
        db = self._get_db()
        return db.get_skill(slug)

    def list_skills(
        self,
        user_id: int = None,
        status: str = None,
        skill_type: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """List skills with optional filters."""
        db = self._get_db()
        return db.list_skills(user_id, status, skill_type, limit)

    def search_skills(self, query: str, user_id: int = None, limit: int = 20) -> List[Dict]:
        """Search skills by keyword."""
        db = self._get_db()
        return db.search_skills(query, user_id, limit)

    # ==================
    # INTERNAL HELPERS
    # ==================

    def _generate_slug(self, skill_type: str, keywords: List[str] = None) -> str:
        """
        Generate a unique slug for the skill.

        Format: {type}_{keyword}_{YYYYMMDD}_{HHMM}_{random}

        Args:
            skill_type: Type of skill (Task, Note, etc.)
            keywords: Optional keywords to include

        Returns:
            Unique slug string
        """
        now = datetime.now()
        date_part = now.strftime('%Y%m%d')
        time_part = now.strftime('%H%M')

        # Clean type for slug
        type_clean = skill_type.lower().replace(' ', '_').replace('-', '_')

        # Build keyword part
        if keywords:
            # Take first 2-3 keywords, clean them
            keyword_part = '_'.join(
                re.sub(r'[^a-z0-9]', '', kw.lower())
                for kw in keywords[:3]
                if kw
            )
        else:
            keyword_part = 'item'

        # Add random suffix for uniqueness
        random_suffix = ''.join(random.choices(string.digits, k=4))

        slug = f"{type_clean}_{keyword_part}_{date_part}_{time_part}_{random_suffix}"

        # Ensure valid slug (no double underscores, reasonable length)
        slug = re.sub(r'_+', '_', slug)
        slug = slug[:80]  # Max length

        return slug

    async def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """
        Extract metadata from content using LLM.

        Args:
            content: Raw content to analyze

        Returns:
            Dict with type, title, tags, action_items, keywords, context
        """
        ollama = self._get_ollama()

        if not ollama or not ollama.is_available():
            # Fallback: basic extraction without LLM
            return self._extract_metadata_basic(content)

        prompt = f"""Analyze this idea/note and extract structured metadata.

Content:
{content}

Return a JSON object with these fields:
- type: One of "Task", "Email Draft", "Note", "Brainstorm"
- title: A short title (max 50 chars)
- context: A context tag if applicable (e.g., "RR_onboarding", "mandate_billing")
- tags: Array of 2-4 relevant tags
- keywords: Array of 2-3 main keywords from the content
- action_items: Array of action items if any are mentioned (max 5)

Return ONLY valid JSON, no other text."""

        try:
            response = ollama.generate(prompt)

            # Try to parse JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")

        # Fallback to basic extraction
        return self._extract_metadata_basic(content)

    def _extract_metadata_basic(self, content: str) -> Dict[str, Any]:
        """Basic metadata extraction without LLM."""
        # Determine type from keywords
        content_lower = content.lower()

        if any(word in content_lower for word in ['email', 'draft', 'send to', 'reply']):
            skill_type = 'Email Draft'
        elif any(word in content_lower for word in ['todo', 'task', 'need to', 'must', 'should']):
            skill_type = 'Task'
        elif any(word in content_lower for word in ['brainstorm', 'idea', 'what if', 'explore']):
            skill_type = 'Brainstorm'
        else:
            skill_type = 'Note'

        # Extract title from first line
        first_line = content.split('\n')[0][:50]

        # Extract potential action items (lines starting with - or *)
        action_items = re.findall(r'^[\-\*]\s*(.+)$', content, re.MULTILINE)

        # Extract keywords (simple word frequency)
        words = re.findall(r'\b[a-z]{4,}\b', content_lower)
        # Filter common words
        stopwords = {'this', 'that', 'with', 'from', 'have', 'will', 'about', 'would', 'could', 'should'}
        keywords = [w for w in words if w not in stopwords][:3]

        return {
            'type': skill_type,
            'title': first_line,
            'context': None,
            'tags': [],
            'keywords': keywords,
            'action_items': action_items[:5]
        }

    def _format_for_doc(self, slug: str, metadata: Dict, body: str) -> str:
        """
        Format skill data for Master Doc entry.

        Args:
            slug: The unique slug
            metadata: Extracted metadata
            body: The main body content

        Returns:
            Formatted string ready for doc insertion
        """
        lines = [f"# {slug}"]

        # Type
        lines.append(f"Type: {metadata.get('type', 'Note')}")

        # Context (if present)
        if metadata.get('context'):
            lines.append(f"Context: {metadata['context']}")

        # Status
        lines.append("Status: Pending")

        # Tags
        if metadata.get('tags'):
            tags_str = ', '.join(metadata['tags'])
            lines.append(f"Tags: {tags_str}")

        # Empty line before body
        lines.append("")

        # Body
        lines.append(body.strip())

        # Action items (if present)
        if metadata.get('action_items'):
            lines.append("")
            lines.append("Action Items:")
            for item in metadata['action_items']:
                lines.append(f"- {item}")

        # Delimiter
        lines.append("")

        return '\n'.join(lines)

    async def _append_to_doc(self, formatted_entry: str) -> Dict[str, Any]:
        """Append formatted entry to Master Doc."""
        try:
            from m1_config import MASTER_DOC_ID
        except ImportError:
            return {"success": False, "error": "MASTER_DOC_ID not configured"}

        if not MASTER_DOC_ID:
            return {"success": False, "error": "MASTER_DOC_ID is empty"}

        docs = self._get_docs_client()
        return docs.append_to_storage(MASTER_DOC_ID, formatted_entry)

    async def _sync_to_sheets(
        self,
        slug: str,
        metadata: Dict,
        body: str
    ) -> List[str]:
        """
        Sync skill to Google Sheets.

        Creates a row in Skills Log sheet, and optionally in Todo List for action items.

        Returns:
            List of created row IDs
        """
        row_ids = []

        try:
            from m1_config import SPREADSHEET_ID
            sheets = self._get_sheets_client()

            if not sheets:
                logger.warning("Sheets client not available, skipping sync")
                return row_ids

            # Add to Skills Log sheet
            # Columns: Slug | Type | Title | Status | Action Items | Tags | Created
            skills_row = [
                slug,
                metadata.get('type', 'Note'),
                metadata.get('title', '')[:100],
                'Pending',
                json.dumps(metadata.get('action_items', [])),
                ', '.join(metadata.get('tags', [])),
                datetime.now().strftime('%Y-%m-%d %H:%M')
            ]

            try:
                result = sheets.append_rows(
                    SPREADSHEET_ID,
                    'Skills Log!A:G',
                    [skills_row]
                )
                if result.get('success'):
                    row_ids.append(result.get('updated_range', ''))
            except Exception as e:
                logger.warning(f"Could not write to Skills Log: {e}")

            # Add action items to Todo List (if any)
            if metadata.get('action_items'):
                for item in metadata['action_items']:
                    # Columns: Source | Subject/Task | Context | Status | Created | Due Date
                    todo_row = [
                        slug,  # Source = skill slug
                        item,
                        metadata.get('context', ''),
                        'Pending',
                        datetime.now().strftime('%Y-%m-%d'),
                        ''  # No due date by default
                    ]
                    try:
                        result = sheets.append_rows(
                            SPREADSHEET_ID,
                            'Todo List!A:F',
                            [todo_row]
                        )
                        if result.get('success'):
                            row_ids.append(result.get('updated_range', ''))
                    except Exception as e:
                        logger.warning(f"Could not write to Todo List: {e}")

        except Exception as e:
            logger.warning(f"Sheets sync failed: {e}")

        return row_ids

    async def _create_tasks_from_actions(
        self,
        slug: str,
        action_items: List[str],
        context: str = None
    ) -> List[int]:
        """
        Create SQLite tasks from action items.

        Args:
            slug: The parent skill slug
            action_items: List of action item strings
            context: Optional context

        Returns:
            List of created task IDs
        """
        db = self._get_db()
        task_ids = []

        for item in action_items:
            try:
                task_id = db.add_task(
                    title=item,
                    priority='medium',
                    notes=f"From skill: {slug}",
                    skill_slug=slug
                )
                task_ids.append(task_id)
            except Exception as e:
                logger.warning(f"Could not create task: {e}")

        return task_ids

    def _build_content_from_session(self, session: Dict) -> str:
        """Build content string from idea session data."""
        lines = [f"Topic: {session.get('idea', 'Unknown topic')}"]

        # Add exchanges if available
        if session.get('context_json'):
            try:
                context = json.loads(session['context_json'])
                if context.get('exchanges'):
                    lines.append("\nConversation:")
                    for ex in context['exchanges'][-5:]:  # Last 5 exchanges
                        if ex.get('user'):
                            lines.append(f"User: {ex['user'][:200]}")
                        if ex.get('assistant'):
                            lines.append(f"Assistant: {ex['assistant'][:300]}")
            except json.JSONDecodeError:
                pass

        # Add Q&A if available
        questions = session.get('questions', [])
        answers = session.get('answers', [])
        if questions:
            lines.append("\nQuestions & Answers:")
            for i, (q, a) in enumerate(zip(questions, answers), 1):
                lines.append(f"Q{i}: {q}")
                lines.append(f"A{i}: {a}")

        # Add gameplan if available
        if session.get('gameplan'):
            lines.append(f"\nGameplan:\n{session['gameplan']}")

        return '\n'.join(lines)

    def cleanup(self):
        """Cleanup resources."""
        self._db = None
        self._docs_client = None
        self._sheets_client = None
        self._ollama = None


# ==================
# TESTING
# ==================

def test_skill_manager():
    """Test skill manager."""
    print("Testing Skill Manager...")
    print("=" * 60)

    mgr = SkillManager()

    # Test slug generation
    print("\nTesting slug generation...")
    slug1 = mgr._generate_slug("Task", ["RR", "onboarding"])
    print(f"  Generated: {slug1}")

    slug2 = mgr._generate_slug("Email Draft", ["Mike", "invoice"])
    print(f"  Generated: {slug2}")

    # Test basic metadata extraction
    print("\nTesting metadata extraction...")
    content = """
    Need to automate RR onboarding process.
    - Create checklist template
    - Set up U4 filing reminders
    - Document compliance requirements
    """
    metadata = mgr._extract_metadata_basic(content)
    print(f"  Type: {metadata['type']}")
    print(f"  Action items: {len(metadata['action_items'])}")

    # Test formatting
    print("\nTesting doc formatting...")
    formatted = mgr._format_for_doc("test_slug_20250205_1430_1234", metadata, content)
    print(f"  Formatted length: {len(formatted)} chars")
    print(f"  First 200 chars:\n{formatted[:200]}")

    print("\n" + "=" * 60)
    print("Skill manager test complete!")
    print("\nNote: Full testing requires running bot with active connections.")


if __name__ == "__main__":
    test_skill_manager()
