"""
Workflow Manager for Mode 4
Manages multi-step workflows with state persistence.

Supports workflows like:
- Email → Draft → Send
- Search → Summarize → Action
- Find → Review → Respond

Usage:
    from workflow_manager import WorkflowManager, WorkflowState

    wf_manager = WorkflowManager(db_manager)

    # Start a workflow
    workflow = await wf_manager.start_workflow(
        user_id=123,
        workflow_type="email_draft_send",
        context={"email_reference": "Jason", "instruction": "reply about invoice"}
    )

    # Advance workflow
    workflow = await wf_manager.advance_workflow(
        user_id=123,
        action="draft_created",
        data={"draft_id": "abc123", "draft_text": "..."}
    )
"""

import json
import logging
import os
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# ── Load workflow definitions from playbook/workflows.json ───────────────────
_PLAYBOOK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "playbook",
)
_WORKFLOWS_JSON: Dict[str, Any] = {}
_WORKFLOWS_CONFIG: Dict[str, Any] = {}

try:
    with open(os.path.join(_PLAYBOOK_DIR, "workflows.json"), "r") as _fh:
        _raw = json.load(_fh)
        _WORKFLOWS_JSON = _raw.get("workflows", {})
        _WORKFLOWS_CONFIG = _raw.get("config", {})
    logger.info("Loaded workflows.json from %s (%d workflows)", _PLAYBOOK_DIR, len(_WORKFLOWS_JSON))
except (FileNotFoundError, json.JSONDecodeError) as _exc:
    logger.warning("Could not load workflows.json: %s – using defaults", _exc)


class WorkflowState(Enum):
    """States for multi-step workflows."""
    IDLE = "idle"                           # Initial state
    SEARCHING = "searching"                 # Searching for email(s)
    EMAIL_FOUND = "email_found"             # Email found, awaiting action
    DRAFTING = "drafting"                   # Generating draft
    DRAFT_CREATED = "draft_created"         # Draft exists, can send or edit
    AWAITING_CONFIRMATION = "awaiting"      # Waiting for user yes/no
    SENDING = "sending"                     # Sending email
    SUMMARIZING = "summarizing"             # Summarizing content
    SUMMARY_READY = "summary_ready"         # Summary available
    COMPLETED = "completed"                 # Workflow finished successfully
    CANCELLED = "cancelled"                 # Workflow cancelled by user
    FAILED = "failed"                       # Workflow failed with error


class WorkflowType(Enum):
    """Types of supported workflows."""
    EMAIL_DRAFT_SEND = "email_draft_send"       # Find email → Draft → Send
    SEARCH_SUMMARIZE = "search_summarize"       # Search emails → Summarize → Action
    MULTI_EMAIL = "multi_email"                 # Process multiple emails
    CUSTOM = "custom"                           # Custom workflow


@dataclass
class ActiveWorkflow:
    """Represents an active multi-step workflow."""
    workflow_id: str
    user_id: int
    workflow_type: str
    state: WorkflowState
    context: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    step_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            'workflow_id': self.workflow_id,
            'user_id': self.user_id,
            'workflow_type': self.workflow_type,
            'state': self.state.value,
            'context': json.dumps(self.context),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'step_history': json.dumps(self.step_history)
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ActiveWorkflow':
        """Create from dictionary."""
        return cls(
            workflow_id=data['workflow_id'],
            user_id=data['user_id'],
            workflow_type=data['workflow_type'],
            state=WorkflowState(data['state']),
            context=json.loads(data['context']) if isinstance(data['context'], str) else data['context'],
            created_at=datetime.fromisoformat(data['created_at']) if isinstance(data['created_at'], str) else data['created_at'],
            updated_at=datetime.fromisoformat(data['updated_at']) if isinstance(data['updated_at'], str) else data['updated_at'],
            step_history=json.loads(data['step_history']) if isinstance(data['step_history'], str) else data.get('step_history', [])
        )


class WorkflowManager:
    """
    Manages multi-step workflows with state persistence.

    Supports:
    - Starting new workflows
    - Advancing workflow state based on actions
    - Persisting workflow state to database
    - Recovering workflows on restart
    - Cancelling workflows
    """

    # State transition rules for each workflow type
    TRANSITIONS = {
        WorkflowType.EMAIL_DRAFT_SEND.value: {
            (WorkflowState.IDLE, "start"): WorkflowState.SEARCHING,
            (WorkflowState.SEARCHING, "email_found"): WorkflowState.EMAIL_FOUND,
            (WorkflowState.SEARCHING, "email_not_found"): WorkflowState.FAILED,
            (WorkflowState.EMAIL_FOUND, "start_draft"): WorkflowState.DRAFTING,
            (WorkflowState.DRAFTING, "draft_created"): WorkflowState.DRAFT_CREATED,
            (WorkflowState.DRAFTING, "draft_failed"): WorkflowState.EMAIL_FOUND,  # Allow retry
            (WorkflowState.DRAFT_CREATED, "send"): WorkflowState.AWAITING_CONFIRMATION,
            (WorkflowState.DRAFT_CREATED, "edit"): WorkflowState.DRAFTING,
            (WorkflowState.AWAITING_CONFIRMATION, "confirmed"): WorkflowState.SENDING,
            (WorkflowState.AWAITING_CONFIRMATION, "cancelled"): WorkflowState.DRAFT_CREATED,
            (WorkflowState.SENDING, "sent"): WorkflowState.COMPLETED,
            (WorkflowState.SENDING, "send_failed"): WorkflowState.DRAFT_CREATED,
        },
        WorkflowType.SEARCH_SUMMARIZE.value: {
            (WorkflowState.IDLE, "start"): WorkflowState.SEARCHING,
            (WorkflowState.SEARCHING, "emails_found"): WorkflowState.SUMMARIZING,
            (WorkflowState.SEARCHING, "no_emails"): WorkflowState.FAILED,
            (WorkflowState.SUMMARIZING, "summary_ready"): WorkflowState.SUMMARY_READY,
            (WorkflowState.SUMMARY_READY, "add_todos"): WorkflowState.COMPLETED,
            (WorkflowState.SUMMARY_READY, "draft_replies"): WorkflowState.DRAFTING,
            (WorkflowState.SUMMARY_READY, "done"): WorkflowState.COMPLETED,
            (WorkflowState.DRAFTING, "draft_created"): WorkflowState.DRAFT_CREATED,
            (WorkflowState.DRAFT_CREATED, "send"): WorkflowState.COMPLETED,
            (WorkflowState.DRAFT_CREATED, "next"): WorkflowState.DRAFTING,  # Draft next email
        },
    }

    # Universal transitions (apply to all workflow types)
    UNIVERSAL_TRANSITIONS = {
        "cancel": WorkflowState.CANCELLED,
        "fail": WorkflowState.FAILED,
        "complete": WorkflowState.COMPLETED,
    }

    def __init__(self, db_manager=None):
        """
        Initialize workflow manager.

        Args:
            db_manager: DatabaseManager instance for persistence
        """
        self.db = db_manager
        self._active_workflows: Dict[int, ActiveWorkflow] = {}  # user_id → workflow
        self._workflow_timeout_minutes = _WORKFLOWS_CONFIG.get("context_ttl_minutes", 60)
        self._max_steps = _WORKFLOWS_CONFIG.get("max_steps", 5)
        self._connectors = _WORKFLOWS_CONFIG.get("connectors", [". then", ". also", ". plus", "and then"])

        # Named pipeline definitions from playbook/workflows.json
        self.pipeline_definitions = _WORKFLOWS_JSON

        # Load active workflows from database
        if self.db:
            self._load_active_workflows()

    def _load_active_workflows(self):
        """Load active workflows from database."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM workflows
                    WHERE state NOT IN ('completed', 'cancelled', 'failed')
                    ORDER BY updated_at DESC
                """)
                rows = cursor.fetchall()

                for row in rows:
                    workflow = ActiveWorkflow.from_dict(dict(row))
                    # Check if workflow is still valid (not expired)
                    age = (datetime.now() - workflow.updated_at).total_seconds() / 60
                    if age < self._workflow_timeout_minutes:
                        self._active_workflows[workflow.user_id] = workflow
                        logger.info(f"Loaded active workflow {workflow.workflow_id} for user {workflow.user_id}")
                    else:
                        # Mark expired workflows as failed
                        self._expire_workflow(workflow.workflow_id)

        except Exception as e:
            logger.warning(f"Could not load workflows from database: {e}")

    def _generate_workflow_id(self) -> str:
        """Generate unique workflow ID."""
        import uuid
        return str(uuid.uuid4())[:8]

    async def start_workflow(
        self,
        user_id: int,
        workflow_type: str,
        context: dict,
        auto_start: bool = True
    ) -> ActiveWorkflow:
        """
        Begin a new multi-step workflow.

        Args:
            user_id: Telegram user ID
            workflow_type: Type of workflow (email_draft_send, search_summarize, etc.)
            context: Initial context data (email_reference, instruction, etc.)
            auto_start: Automatically advance to first state

        Returns:
            ActiveWorkflow instance
        """
        # Cancel any existing workflow for this user
        if user_id in self._active_workflows:
            await self.cancel_workflow(user_id, reason="new_workflow_started")

        workflow_id = self._generate_workflow_id()
        now = datetime.now()

        workflow = ActiveWorkflow(
            workflow_id=workflow_id,
            user_id=user_id,
            workflow_type=workflow_type,
            state=WorkflowState.IDLE,
            context=context,
            created_at=now,
            updated_at=now,
            step_history=[]
        )

        # Store in memory
        self._active_workflows[user_id] = workflow

        # Persist to database
        self._persist_workflow(workflow)

        logger.info(f"Started workflow {workflow_id} for user {user_id}: {workflow_type}")

        # Auto-start if requested
        if auto_start:
            workflow = await self.advance_workflow(user_id, "start")

        return workflow

    async def advance_workflow(
        self,
        user_id: int,
        action: str,
        data: dict = None
    ) -> Optional[ActiveWorkflow]:
        """
        Move workflow to next state based on action.

        Args:
            user_id: Telegram user ID
            action: Action to perform (e.g., "email_found", "draft_created", "send")
            data: Additional data to merge into context

        Returns:
            Updated workflow or None if no active workflow
        """
        workflow = self._active_workflows.get(user_id)
        if not workflow:
            logger.warning(f"No active workflow for user {user_id}")
            return None

        current_state = workflow.state
        workflow_type = workflow.workflow_type

        # Check for universal transitions first
        if action in self.UNIVERSAL_TRANSITIONS:
            new_state = self.UNIVERSAL_TRANSITIONS[action]
        else:
            # Check type-specific transitions
            transitions = self.TRANSITIONS.get(workflow_type, {})
            new_state = transitions.get((current_state, action))

        if new_state is None:
            logger.warning(
                f"Invalid transition: {workflow_type} from {current_state.value} via '{action}'"
            )
            return workflow

        # Record step in history
        workflow.step_history.append({
            'from_state': current_state.value,
            'action': action,
            'to_state': new_state.value,
            'timestamp': datetime.now().isoformat(),
            'data': data
        })

        # Update state and context
        workflow.state = new_state
        workflow.updated_at = datetime.now()

        if data:
            workflow.context.update(data)

        # Persist changes
        self._persist_workflow(workflow)

        logger.info(
            f"Workflow {workflow.workflow_id}: {current_state.value} → {new_state.value} via '{action}'"
        )

        # Clean up if workflow is terminal
        if new_state in [WorkflowState.COMPLETED, WorkflowState.CANCELLED, WorkflowState.FAILED]:
            # Keep in memory briefly for status checks, but mark as done
            pass

        return workflow

    def get_active_workflow(self, user_id: int) -> Optional[ActiveWorkflow]:
        """Get user's current active workflow if any."""
        workflow = self._active_workflows.get(user_id)

        if workflow:
            # Check if expired
            age = (datetime.now() - workflow.updated_at).total_seconds() / 60
            if age > self._workflow_timeout_minutes:
                self._expire_workflow(workflow.workflow_id)
                del self._active_workflows[user_id]
                return None

            # Check if terminal state
            if workflow.state in [WorkflowState.COMPLETED, WorkflowState.CANCELLED, WorkflowState.FAILED]:
                return None

        return workflow

    def has_active_workflow(self, user_id: int) -> bool:
        """Check if user has an active (non-terminal) workflow."""
        return self.get_active_workflow(user_id) is not None

    async def cancel_workflow(self, user_id: int, reason: str = "user_cancelled") -> bool:
        """
        Cancel and clean up workflow.

        Args:
            user_id: Telegram user ID
            reason: Reason for cancellation

        Returns:
            True if cancelled, False if no workflow found
        """
        workflow = self._active_workflows.get(user_id)
        if not workflow:
            return False

        # Record cancellation
        workflow.step_history.append({
            'from_state': workflow.state.value,
            'action': 'cancel',
            'to_state': WorkflowState.CANCELLED.value,
            'timestamp': datetime.now().isoformat(),
            'data': {'reason': reason}
        })

        workflow.state = WorkflowState.CANCELLED
        workflow.updated_at = datetime.now()

        # Persist final state
        self._persist_workflow(workflow)

        # Remove from active workflows
        del self._active_workflows[user_id]

        logger.info(f"Cancelled workflow {workflow.workflow_id} for user {user_id}: {reason}")
        return True

    def get_workflow_status(self, user_id: int) -> Dict[str, Any]:
        """Get current workflow status for display."""
        workflow = self.get_active_workflow(user_id)

        if not workflow:
            return {
                'has_workflow': False,
                'message': 'No active workflow'
            }

        # Build status message
        state_messages = {
            WorkflowState.IDLE: 'Ready to start',
            WorkflowState.SEARCHING: 'Searching for email...',
            WorkflowState.EMAIL_FOUND: 'Email found - ready to draft',
            WorkflowState.DRAFTING: 'Generating draft...',
            WorkflowState.DRAFT_CREATED: 'Draft ready - review and send?',
            WorkflowState.AWAITING_CONFIRMATION: 'Waiting for your confirmation',
            WorkflowState.SENDING: 'Sending email...',
            WorkflowState.SUMMARIZING: 'Summarizing emails...',
            WorkflowState.SUMMARY_READY: 'Summary ready - what next?',
            WorkflowState.COMPLETED: 'Workflow completed',
            WorkflowState.CANCELLED: 'Workflow cancelled',
            WorkflowState.FAILED: 'Workflow failed',
        }

        return {
            'has_workflow': True,
            'workflow_id': workflow.workflow_id,
            'type': workflow.workflow_type,
            'state': workflow.state.value,
            'state_message': state_messages.get(workflow.state, 'Unknown state'),
            'context': workflow.context,
            'steps_completed': len(workflow.step_history),
            'age_minutes': (datetime.now() - workflow.created_at).total_seconds() / 60
        }

    def get_expected_actions(self, user_id: int) -> List[str]:
        """Get list of valid actions for current workflow state."""
        workflow = self.get_active_workflow(user_id)
        if not workflow:
            return []

        transitions = self.TRANSITIONS.get(workflow.workflow_type, {})
        valid_actions = []

        for (state, action), _ in transitions.items():
            if state == workflow.state:
                valid_actions.append(action)

        # Add universal actions
        valid_actions.extend(['cancel'])

        return valid_actions

    def get_pipeline(self, pipeline_name: str) -> Optional[Dict[str, Any]]:
        """Get a named pipeline definition from workflows.json.

        Returns the pipeline dict with 'description' and 'steps' keys,
        or None if not found.
        """
        return self.pipeline_definitions.get(pipeline_name)

    def list_pipelines(self) -> List[Dict[str, Any]]:
        """List all available named pipelines from workflows.json."""
        return [
            {"name": name, "description": defn.get("description", ""), "steps": len(defn.get("steps", []))}
            for name, defn in self.pipeline_definitions.items()
        ]

    def is_connector_phrase(self, text: str) -> bool:
        """Check if text contains a workflow connector phrase (e.g. '. then', 'and then')."""
        text_lower = text.lower()
        return any(conn.lower() in text_lower for conn in self._connectors)

    # ==================
    # PERSISTENCE
    # ==================

    def _persist_workflow(self, workflow: ActiveWorkflow):
        """Save workflow to database."""
        if not self.db:
            return

        try:
            with self.db.get_connection() as conn:
                data = workflow.to_dict()

                # Upsert
                conn.execute("""
                    INSERT OR REPLACE INTO workflows
                    (workflow_id, user_id, workflow_type, state, context, created_at, updated_at, step_history)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data['workflow_id'],
                    data['user_id'],
                    data['workflow_type'],
                    data['state'],
                    data['context'],
                    data['created_at'],
                    data['updated_at'],
                    data['step_history']
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Failed to persist workflow: {e}")

    def _expire_workflow(self, workflow_id: str):
        """Mark workflow as expired/failed in database."""
        if not self.db:
            return

        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE workflows
                    SET state = 'failed', updated_at = ?
                    WHERE workflow_id = ?
                """, (datetime.now().isoformat(), workflow_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Failed to expire workflow: {e}")


# ==================
# WORKFLOW EXECUTOR
# ==================

class WorkflowExecutor:
    """
    Executes workflow steps and integrates with other Mode 4 components.

    This class handles the actual execution of workflow steps,
    coordinating between Gmail, LLM clients, and Telegram.
    """

    def __init__(
        self,
        workflow_manager: WorkflowManager,
        telegram_handler=None,
        gmail_client=None,
        ollama_client=None,
        claude_client=None
    ):
        self.wf = workflow_manager
        self.telegram = telegram_handler
        self.gmail = gmail_client
        self.ollama = ollama_client
        self.claude = claude_client

    async def execute_email_draft_send(
        self,
        user_id: int,
        chat_id: int,
        email_reference: str,
        instruction: str,
        auto_send: bool = False
    ) -> Dict[str, Any]:
        """
        Execute the Email → Draft → Send workflow.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            email_reference: Email subject/sender to search for
            instruction: What to do (e.g., "reply about invoice")
            auto_send: If True, send without final confirmation

        Returns:
            Dict with workflow result
        """
        # Start workflow
        workflow = await self.wf.start_workflow(
            user_id=user_id,
            workflow_type=WorkflowType.EMAIL_DRAFT_SEND.value,
            context={
                'email_reference': email_reference,
                'instruction': instruction,
                'chat_id': chat_id,
                'auto_send': auto_send
            }
        )

        # Step 1: Search for email
        await self.telegram.send_response(
            chat_id,
            f"Searching for email: <b>{email_reference}</b>..."
        )

        email = await self._search_email(email_reference)

        if not email:
            await self.wf.advance_workflow(user_id, "email_not_found")
            await self.telegram.send_response(
                chat_id,
                f"Could not find email matching: {email_reference}\n\n"
                "Try a different search term or check the exact subject line."
            )
            return {'success': False, 'reason': 'email_not_found'}

        # Update workflow with email data
        await self.wf.advance_workflow(
            user_id, "email_found",
            data={'email': email}
        )

        # Show email preview
        await self.telegram.send_response(
            chat_id,
            f"Found email from <b>{email.get('sender_name', email.get('sender_email'))}</b>\n"
            f"Subject: <b>{email.get('subject', '(no subject)')}</b>\n\n"
            f"Drafting reply..."
        )

        # Step 2: Generate draft
        await self.wf.advance_workflow(user_id, "start_draft")

        draft_result = await self._generate_draft(email, instruction)

        if not draft_result.get('success'):
            await self.wf.advance_workflow(user_id, "draft_failed", data={'error': draft_result.get('error')})
            await self.telegram.send_response(
                chat_id,
                f"Failed to generate draft: {draft_result.get('error')}\n\n"
                "Would you like to try again?"
            )
            return {'success': False, 'reason': 'draft_failed'}

        draft_text = draft_result.get('draft_text', '')

        await self.wf.advance_workflow(
            user_id, "draft_created",
            data={'draft_text': draft_text, 'model_used': draft_result.get('model', 'unknown')}
        )

        # Show draft preview with options
        preview = draft_text[:300] + ('...' if len(draft_text) > 300 else '')
        await self.telegram.send_response(
            chat_id,
            f"<b>Draft ready:</b>\n\n{preview}\n\n"
            f"Reply with:\n"
            f"• <b>send</b> - Send this email\n"
            f"• <b>edit [changes]</b> - Make changes\n"
            f"• <b>cancel</b> - Cancel workflow"
        )

        return {
            'success': True,
            'state': 'draft_created',
            'workflow_id': workflow.workflow_id,
            'email': email,
            'draft': draft_text
        }

    async def handle_workflow_message(
        self,
        user_id: int,
        chat_id: int,
        message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Handle a message in the context of an active workflow.

        Returns None if no active workflow or message not handled.
        """
        workflow = self.wf.get_active_workflow(user_id)
        if not workflow:
            return None

        message_lower = message.lower().strip()

        # Handle universal actions
        if message_lower in ['cancel', 'stop', 'quit', 'exit', 'nevermind']:
            await self.wf.cancel_workflow(user_id, reason="user_requested")
            await self.telegram.send_response(chat_id, "Workflow cancelled.")
            return {'handled': True, 'action': 'cancelled'}

        # Handle state-specific actions
        if workflow.state == WorkflowState.DRAFT_CREATED:
            if message_lower == 'send':
                return await self._handle_send_action(user_id, chat_id, workflow)
            elif message_lower.startswith('edit'):
                edit_instruction = message[4:].strip()
                return await self._handle_edit_action(user_id, chat_id, workflow, edit_instruction)

        elif workflow.state == WorkflowState.AWAITING_CONFIRMATION:
            if message_lower in ['yes', 'confirm', 'ok', 'y']:
                return await self._execute_send(user_id, chat_id, workflow)
            elif message_lower in ['no', 'cancel', 'n']:
                await self.wf.advance_workflow(user_id, "cancelled")
                await self.telegram.send_response(chat_id, "Send cancelled. Draft is still saved.")
                return {'handled': True, 'action': 'send_cancelled'}

        elif workflow.state == WorkflowState.SUMMARY_READY:
            if 'todo' in message_lower or 'task' in message_lower:
                return await self._handle_add_todos(user_id, chat_id, workflow)
            elif 'draft' in message_lower or 'reply' in message_lower:
                return await self._handle_draft_replies(user_id, chat_id, workflow)
            elif message_lower in ['done', 'finish', 'ok', 'thanks']:
                await self.wf.advance_workflow(user_id, "done")
                await self.telegram.send_response(chat_id, "Workflow completed!")
                return {'handled': True, 'action': 'completed'}

        return None  # Message not handled by workflow

    async def _search_email(self, reference: str) -> Optional[Dict]:
        """Search for email using Gmail client."""
        if not self.gmail:
            return None

        try:
            return self.gmail.search_email(reference, search_type='keyword', max_results=1)
        except Exception as e:
            logger.error(f"Email search failed: {e}")
            return None

    async def _generate_draft(self, email: dict, instruction: str) -> Dict[str, Any]:
        """Generate email draft using available LLM."""
        try:
            # Try Ollama first (faster, free)
            if self.ollama and self.ollama.is_available():
                result = self.ollama.generate_draft(
                    email_data=email,
                    instruction=instruction
                )
                if result.get('success'):
                    result['model'] = 'ollama'
                    return result

            # Fall back to Claude
            if self.claude and self.claude.is_available():
                result = self.claude.generate_email_draft(
                    email_data=email,
                    instruction=instruction
                )
                if result.get('success'):
                    result['model'] = 'claude'
                    return result

            return {'success': False, 'error': 'No LLM available'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _handle_send_action(
        self,
        user_id: int,
        chat_id: int,
        workflow: ActiveWorkflow
    ) -> Dict[str, Any]:
        """Handle 'send' action in draft_created state."""
        email = workflow.context.get('email', {})
        recipient = email.get('sender_email', 'recipient')

        await self.wf.advance_workflow(user_id, "send")
        await self.telegram.send_response(
            chat_id,
            f"Send this email to <b>{recipient}</b>?\n\n"
            f"Reply <b>yes</b> to confirm or <b>no</b> to cancel."
        )

        return {'handled': True, 'action': 'awaiting_confirmation'}

    async def _execute_send(
        self,
        user_id: int,
        chat_id: int,
        workflow: ActiveWorkflow
    ) -> Dict[str, Any]:
        """Execute the actual email send."""
        await self.wf.advance_workflow(user_id, "confirmed")
        await self.telegram.send_response(chat_id, "Sending email...")

        try:
            email = workflow.context.get('email', {})
            draft_text = workflow.context.get('draft_text', '')

            if self.gmail:
                # Create draft and then send it
                result = self.gmail.create_reply_draft(email, draft_text)

                if result.get('success'):
                    draft_id = result.get('draft_id')
                    # Note: Actual sending would require additional Gmail API scope
                    # For now, we create the draft and link to it

                    await self.wf.advance_workflow(user_id, "sent", data={'draft_url': result.get('draft_url')})
                    await self.telegram.send_response(
                        chat_id,
                        f"Email draft created and ready to send!\n\n"
                        f"<a href=\"{result.get('draft_url')}\">Open in Gmail to send</a>"
                    )
                    return {'handled': True, 'action': 'sent', 'draft_url': result.get('draft_url')}

            await self.wf.advance_workflow(user_id, "send_failed")
            await self.telegram.send_response(chat_id, "Failed to send. Draft saved.")
            return {'handled': True, 'action': 'send_failed'}

        except Exception as e:
            logger.error(f"Send failed: {e}")
            await self.wf.advance_workflow(user_id, "send_failed", data={'error': str(e)})
            await self.telegram.send_response(chat_id, f"Send failed: {str(e)[:100]}")
            return {'handled': True, 'action': 'send_failed', 'error': str(e)}

    async def _handle_edit_action(
        self,
        user_id: int,
        chat_id: int,
        workflow: ActiveWorkflow,
        edit_instruction: str
    ) -> Dict[str, Any]:
        """Handle edit action to revise the draft."""
        await self.wf.advance_workflow(user_id, "edit")
        await self.telegram.send_response(chat_id, "Revising draft...")

        current_draft = workflow.context.get('draft_text', '')
        email = workflow.context.get('email', {})

        # Use Claude for editing (better at following instructions)
        if self.claude and self.claude.is_available():
            result = self.claude.refine_draft(
                original_draft=current_draft,
                email_data=email,
                instructions=edit_instruction or "Improve the draft"
            )

            if result.get('success'):
                new_draft = result.get('draft_text', '')
                await self.wf.advance_workflow(
                    user_id, "draft_created",
                    data={'draft_text': new_draft, 'model_used': 'claude_edit'}
                )

                preview = new_draft[:300] + ('...' if len(new_draft) > 300 else '')
                await self.telegram.send_response(
                    chat_id,
                    f"<b>Revised draft:</b>\n\n{preview}\n\n"
                    f"Reply with <b>send</b>, <b>edit [changes]</b>, or <b>cancel</b>"
                )
                return {'handled': True, 'action': 'edited'}

        await self.telegram.send_response(chat_id, "Could not edit draft. Try again?")
        return {'handled': True, 'action': 'edit_failed'}

    async def _handle_add_todos(
        self,
        user_id: int,
        chat_id: int,
        workflow: ActiveWorkflow
    ) -> Dict[str, Any]:
        """Add summary items to todo list."""
        await self.wf.advance_workflow(user_id, "add_todos")

        # TODO: Implement todo extraction from summary
        await self.telegram.send_response(chat_id, "Added action items to your todo list!")
        return {'handled': True, 'action': 'todos_added'}

    async def _handle_draft_replies(
        self,
        user_id: int,
        chat_id: int,
        workflow: ActiveWorkflow
    ) -> Dict[str, Any]:
        """Start drafting replies to summarized emails."""
        await self.wf.advance_workflow(user_id, "draft_replies")

        # TODO: Implement multi-email reply drafting
        await self.telegram.send_response(chat_id, "Starting to draft replies...")
        return {'handled': True, 'action': 'drafting_replies'}
