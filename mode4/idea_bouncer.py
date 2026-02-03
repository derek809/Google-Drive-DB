"""
Idea Bouncer Capability for Mode 4
Gap-finding conversation agent via Telegram.

A thinking partner that helps explore ideas by finding gaps,
asking probing questions, and deepening understanding.

Commands:
    /idea <topic> - Start idea exploration
    /deepidea <topic> - Deep dive with more questions
    /answer <response> - Continue conversation
    /summarize - Get session summary

Usage:
    from idea_bouncer import IdeaBouncer

    bouncer = IdeaBouncer()
    response = bouncer.start_session("startup idea for B2B invoicing", user_id)
    follow_up = bouncer.continue_session("it's for small businesses", user_id)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)


class IdeaBouncerError(Exception):
    """Custom exception for idea bouncer errors."""
    pass


class IdeaBouncer:
    """
    Idea exploration agent capability for Mode 4.

    Uses Ollama to:
    - Identify gaps in thinking
    - Ask probing questions
    - Challenge assumptions
    - Help refine ideas
    """

    def __init__(self):
        """Initialize idea bouncer."""
        self._ollama = None
        self._claude = None
        self._db = None

        # Session config
        self.max_session_age = timedelta(hours=24)
        self.max_exchanges = 20

        # Modes
        self.modes = {
            'explore': {
                'name': 'Exploration',
                'system': """You are a thoughtful thinking partner helping explore an idea.
Your role is to:
1. Identify gaps in the thinking
2. Ask 2-3 probing questions
3. Offer one alternative perspective
4. Be concise but insightful

Format your response as:
GAP: [One key gap you notice]
QUESTIONS:
- [Question 1]
- [Question 2]
PERSPECTIVE: [Brief alternative view]"""
            },
            'deep': {
                'name': 'Deep Dive',
                'system': """You are a rigorous thinking partner for deep analysis.
Your role is to:
1. Challenge assumptions
2. Explore edge cases
3. Ask 3-4 deep questions
4. Suggest frameworks or models
5. Identify blind spots

Be thorough but focused. Push for clarity."""
            },
            'refine': {
                'name': 'Refinement',
                'system': """You are helping refine and strengthen an idea.
Based on the conversation so far:
1. Summarize the core idea
2. List resolved questions
3. Identify remaining gaps
4. Suggest concrete next steps

Be constructive and actionable."""
            }
        }

    def _get_ollama(self):
        """Lazy load Ollama client."""
        if self._ollama is None:
            try:
                from ollama_client import OllamaClient
                self._ollama = OllamaClient()
            except Exception as e:
                logger.warning(f"Could not load Ollama: {e}")
        return self._ollama

    def _get_claude(self):
        """Lazy load Claude client for complex analysis."""
        if self._claude is None:
            try:
                from claude_client import ClaudeClient
                self._claude = ClaudeClient()
            except Exception as e:
                logger.warning(f"Could not load Claude: {e}")
        return self._claude

    def _get_db(self):
        """Lazy load database manager."""
        if self._db is None:
            from db_manager import DatabaseManager
            self._db = DatabaseManager()
        return self._db

    # ==================
    # SESSION MANAGEMENT
    # ==================

    def start_session(
        self,
        topic: str,
        user_id: int,
        mode: str = 'explore'
    ) -> Dict[str, Any]:
        """
        Start a new idea exploration session.

        Args:
            topic: Initial idea/topic
            user_id: Telegram user ID
            mode: 'explore' or 'deep'

        Returns:
            Dict with session info and initial response
        """
        db = self._get_db()

        # Create session
        session_id = f"idea_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        session_data = {
            'topic': topic,
            'mode': mode,
            'exchanges': [],
            'started_at': datetime.now().isoformat()
        }

        # Save session
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO idea_sessions
                    (session_id, user_id, topic, mode, context_json, created_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'active')
                """, (
                    session_id, user_id, topic, mode,
                    json.dumps(session_data), datetime.now()
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error creating session: {e}")

        # Generate initial response
        response = self._generate_response(topic, session_data, mode)

        # Update session with exchange
        session_data['exchanges'].append({
            'user': topic,
            'assistant': response,
            'timestamp': datetime.now().isoformat()
        })

        self._save_session(session_id, session_data)

        return {
            'session_id': session_id,
            'response': response,
            'mode': self.modes[mode]['name'],
            'exchange_count': 1
        }

    def continue_session(
        self,
        message: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Continue an existing idea session.

        Args:
            message: User's response/answer
            user_id: Telegram user ID

        Returns:
            Dict with response and session info
        """
        # Get active session
        session = self._get_active_session(user_id)

        if not session:
            return {
                'error': 'No active idea session. Start one with /idea <topic>'
            }

        session_id = session['session_id']
        session_data = json.loads(session['context_json'])

        # Check exchange limit
        if len(session_data['exchanges']) >= self.max_exchanges:
            return {
                'response': self._generate_summary(session_data),
                'session_id': session_id,
                'status': 'completed',
                'reason': 'max_exchanges'
            }

        # Build context from history
        context = self._build_context(session_data)

        # Generate response
        response = self._generate_response(
            message, session_data,
            session_data.get('mode', 'explore'),
            context=context
        )

        # Update session
        session_data['exchanges'].append({
            'user': message,
            'assistant': response,
            'timestamp': datetime.now().isoformat()
        })

        self._save_session(session_id, session_data)

        return {
            'session_id': session_id,
            'response': response,
            'exchange_count': len(session_data['exchanges'])
        }

    def get_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Get summary of active session.

        Args:
            user_id: Telegram user ID

        Returns:
            Dict with summary
        """
        session = self._get_active_session(user_id)

        if not session:
            return {'error': 'No active session'}

        session_data = json.loads(session['context_json'])
        summary = self._generate_summary(session_data)

        return {
            'session_id': session['session_id'],
            'topic': session_data['topic'],
            'summary': summary,
            'exchange_count': len(session_data['exchanges'])
        }

    def end_session(self, user_id: int) -> Dict[str, Any]:
        """End the active session."""
        session = self._get_active_session(user_id)

        if not session:
            return {'error': 'No active session'}

        session_data = json.loads(session['context_json'])
        summary = self._generate_summary(session_data)

        # Mark as completed
        db = self._get_db()
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE idea_sessions
                    SET status = 'completed', completed_at = ?
                    WHERE session_id = ?
                """, (datetime.now(), session['session_id']))
                conn.commit()
        except Exception as e:
            logger.error(f"Error ending session: {e}")

        return {
            'session_id': session['session_id'],
            'summary': summary,
            'status': 'completed'
        }

    # ==================
    # INTERNAL METHODS
    # ==================

    def _get_active_session(self, user_id: int) -> Optional[Dict]:
        """Get user's active session."""
        db = self._get_db()

        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM idea_sessions
                    WHERE user_id = ? AND status = 'active'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (user_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None

    def _save_session(self, session_id: str, session_data: Dict):
        """Save session data."""
        db = self._get_db()

        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE idea_sessions
                    SET context_json = ?, updated_at = ?
                    WHERE session_id = ?
                """, (json.dumps(session_data), datetime.now(), session_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving session: {e}")

    def _build_context(self, session_data: Dict) -> str:
        """Build context string from session history."""
        lines = [f"Topic: {session_data['topic']}\n"]

        for i, ex in enumerate(session_data['exchanges'][-5:], 1):  # Last 5
            lines.append(f"Exchange {i}:")
            lines.append(f"User: {ex['user'][:200]}")
            lines.append(f"Response: {ex['assistant'][:300]}")
            lines.append("")

        return '\n'.join(lines)

    def _generate_response(
        self,
        message: str,
        session_data: Dict,
        mode: str,
        context: str = None
    ) -> str:
        """Generate AI response using Ollama."""
        ollama = self._get_ollama()
        if not ollama or not ollama.is_available():
            return "AI unavailable. Please try again later."

        system_prompt = self.modes.get(mode, self.modes['explore'])['system']

        if context:
            prompt = f"""Previous context:
{context}

User's latest message: {message}

{system_prompt}"""
        else:
            prompt = f"""Topic to explore: {message}

{system_prompt}"""

        try:
            response = ollama.generate(prompt)
            return response
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return "Sorry, I couldn't generate a response. Please try again."

    def _generate_summary(self, session_data: Dict) -> str:
        """Generate session summary."""
        ollama = self._get_ollama()
        if not ollama or not ollama.is_available():
            return self._basic_summary(session_data)

        context = self._build_context(session_data)

        prompt = f"""Summarize this idea exploration session:

{context}

Provide:
1. CORE IDEA: One sentence summary
2. KEY INSIGHTS: 2-3 bullet points
3. OPEN QUESTIONS: Remaining unknowns
4. NEXT STEPS: 2-3 actionable items

Be concise and actionable."""

        try:
            return ollama.generate(prompt)
        except Exception as e:
            logger.error(f"Summary error: {e}")
            return self._basic_summary(session_data)

    def _basic_summary(self, session_data: Dict) -> str:
        """Basic summary without AI."""
        exchanges = session_data.get('exchanges', [])
        return (
            f"Topic: {session_data.get('topic', 'Unknown')}\n"
            f"Exchanges: {len(exchanges)}\n"
            f"Started: {session_data.get('started_at', 'Unknown')}"
        )

    # ==================
    # COMMAND HANDLERS
    # ==================

    def handle_command(self, command: str, args: str, user_id: int) -> str:
        """
        Handle idea bouncer command.

        Args:
            command: Command name
            args: Command arguments
            user_id: Telegram user ID

        Returns:
            Response message text
        """
        try:
            if command == '/idea':
                return self._cmd_idea(args, user_id, mode='explore')
            elif command == '/deepidea':
                return self._cmd_idea(args, user_id, mode='deep')
            elif command == '/answer':
                return self._cmd_answer(args, user_id)
            elif command == '/summarize':
                return self._cmd_summarize(user_id)
            elif command == '/endidea':
                return self._cmd_end(user_id)
            else:
                return f"Unknown command: {command}"
        except Exception as e:
            logger.error(f"Idea bouncer error: {e}")
            return f"Error: {str(e)}"

    def _cmd_idea(self, args: str, user_id: int, mode: str) -> str:
        """Handle /idea or /deepidea command."""
        if not args.strip():
            return (
                "Idea Bouncer - Your Thinking Partner\n\n"
                "Usage: /idea <your idea or question>\n"
                "Example: /idea startup for B2B invoicing automation\n\n"
                "For deeper analysis: /deepidea <topic>\n"
                "Continue with: /answer <your response>\n"
                "Get summary: /summarize"
            )

        result = self.start_session(args.strip(), user_id, mode=mode)

        mode_name = self.modes[mode]['name']
        return (
            f"Starting {mode_name} Mode\n"
            f"Topic: {args.strip()[:50]}...\n\n"
            f"{result['response']}\n\n"
            f"Reply with /answer <your response>"
        )

    def _cmd_answer(self, args: str, user_id: int) -> str:
        """Handle /answer command."""
        if not args.strip():
            return "Usage: /answer <your response to the questions>"

        result = self.continue_session(args.strip(), user_id)

        if result.get('error'):
            return result['error']

        response = result['response']
        count = result.get('exchange_count', 0)

        return (
            f"{response}\n\n"
            f"[Exchange {count}] Reply: /answer <response> | Summary: /summarize"
        )

    def _cmd_summarize(self, user_id: int) -> str:
        """Handle /summarize command."""
        result = self.get_summary(user_id)

        if result.get('error'):
            return result['error']

        return (
            f"Session Summary\n"
            f"Topic: {result['topic']}\n"
            f"Exchanges: {result['exchange_count']}\n\n"
            f"{result['summary']}\n\n"
            f"End session: /endidea"
        )

    def _cmd_end(self, user_id: int) -> str:
        """Handle /endidea command."""
        result = self.end_session(user_id)

        if result.get('error'):
            return result['error']

        return (
            f"Session Ended\n\n"
            f"Final Summary:\n{result['summary']}\n\n"
            f"Start new session: /idea <topic>"
        )

    def cleanup(self):
        """Cleanup resources."""
        if self._ollama:
            del self._ollama
            self._ollama = None
        if self._claude:
            del self._claude
            self._claude = None
        if self._db:
            del self._db
            self._db = None


# ==================
# TESTING
# ==================

def test_idea_bouncer():
    """Test idea bouncer."""
    print("Testing Idea Bouncer...")
    print("=" * 60)

    bouncer = IdeaBouncer()

    # Test modes
    print("\nAvailable modes:")
    for mode_id, mode_info in bouncer.modes.items():
        print(f"  {mode_id}: {mode_info['name']}")

    # Note: Full testing requires Ollama and database
    print("\nTo test idea bouncer:")
    print("  1. Ensure Ollama is running")
    print("  2. Ensure mode4.db has idea_sessions table")
    print("  3. Run: bouncer.start_session('your idea', user_id)")

    bouncer.cleanup()
    print("\nIdea bouncer test complete!")


if __name__ == "__main__":
    test_idea_bouncer()
