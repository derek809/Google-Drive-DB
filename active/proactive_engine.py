"""
Proactive Engine for Hybrid Operations Backend

Orchestrates workspace synchronization across Microsoft 365 and Google
services. Polls action items, processes threads via legacy Gmail or
Exchange, generates AI summaries, and sends alerts via Telegram.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class ProactiveEngineError(Exception):
    """Raised when the proactive engine encounters an unrecoverable error."""
    pass


class ProactiveEngine:
    """
    Orchestrates hybrid workspace synchronization and proactive intelligence.

    Polls SharePoint action items, processes legacy Gmail and Exchange threads,
    generates AI-powered summaries, and sends operational alerts. Handles
    migration modes (dual, google_only, microsoft_only) for phased rollout.
    """

    def __init__(
        self,
        graph_client,
        gdrive_client,
        onenote_client,
        list_reader,
        telegram_client,
        claude_client,
        config_loader: Callable[[str], Any],
    ) -> None:
        """
        Initialize the proactive engine with all service dependencies.

        Args:
            graph_client: Authenticated Graph API client with get/post/patch
                methods. Handles 401 refresh automatically.
            gdrive_client: Legacy Google Drive client with check_gmail_thread
                and download methods.
            onenote_client: OneNote client for page updates.
            list_reader: SharePoint list reader for action items.
            telegram_client: Alerting interface with send_alert(message,
                priority) method.
            claude_client: LLM interface with generate(prompt, personality)
                method.
            config_loader: Callable that resolves dotted config keys to values.
        """
        self._graph = graph_client
        self._gdrive = gdrive_client
        self._onenote = onenote_client
        self._list_reader = list_reader
        self._telegram = telegram_client
        self._claude = claude_client

        self._migration_mode = config_loader("hybrid.migration_mode") or "dual"
        self._action_items_list = config_loader("microsoft.action_items_list_id")
        self._stale_summary_hours = 24

        logger.info(
            "ProactiveEngine initialized (mode=%s, list=%s)",
            self._migration_mode,
            self._action_items_list,
        )

    def sync_workspace(self) -> None:
        """
        Run a full workspace synchronization cycle.

        Polls action items from SharePoint, processes each item based on
        migration mode, and checks for stale threads needing proactive
        summaries. On critical failure, sends a high-priority Telegram alert.
        """
        logger.info("Starting workspace sync (mode=%s)", self._migration_mode)

        try:
            items = self._list_reader.poll_action_items(
                self._action_items_list
            )
            logger.info("Polled %d actionable items", len(items))

            for item in items:
                try:
                    self._process_item(item)
                except Exception as exc:
                    logger.error(
                        "Failed to process item %s: %s",
                        item.get("id"),
                        exc,
                        exc_info=True,
                    )

            self._check_stale_threads(items)

        except Exception as exc:
            logger.critical(
                "Workspace sync failed: %s", exc, exc_info=True
            )
            try:
                self._telegram.send_alert(
                    f"Workspace sync failure: {exc}", priority="high"
                )
            except Exception as alert_exc:
                logger.error(
                    "Failed to send failure alert: %s", alert_exc
                )

        logger.info("Workspace sync complete")

    def _process_item(self, item: Dict[str, Any]) -> None:
        """
        Process a single action item based on migration mode and item type.

        Routes the item to the appropriate handler depending on whether it
        has a legacy Gmail ThreadID or an Exchange ConversationID, and
        whether the current migration mode supports that source. Claims
        the task first; skips silently if claim fails (another instance won).

        Args:
            item: Action item dict from poll_action_items containing 'id',
                'fields', and 'etag' keys.
        """
        fields = item.get("fields", {})
        item_id = item.get("id", "")
        etag = item.get("etag", "")

        thread_id = fields.get("ThreadID")
        conversation_id = fields.get("ConversationID")

        if not self._list_reader.claim_task(
            self._action_items_list, item_id, etag
        ):
            logger.info("Could not claim item %s, skipping", item_id)
            return

        if thread_id and self._migration_mode in ("dual", "google_only"):
            self._handle_legacy_thread(item, thread_id)
        elif conversation_id and self._migration_mode in (
            "dual",
            "microsoft_only",
        ):
            self._handle_exchange_thread(item, conversation_id)
        else:
            logger.info(
                "Item %s has no actionable thread reference for mode %s",
                item_id,
                self._migration_mode,
            )

    def _handle_legacy_thread(
        self, item: Dict[str, Any], thread_id: str
    ) -> None:
        """
        Handle a legacy Gmail thread via Google Drive client.

        Checks the Gmail thread for updates. If new content is found,
        generates a summary via Claude, appends it to OneNote when a
        page_id exists, sends a Telegram alert, and completes the task.
        If the thread returns 404, marks the task as externally resolved.
        If no updates are found, refreshes the heartbeat.

        Args:
            item: Action item dict.
            thread_id: Gmail thread identifier.
        """
        item_id = item.get("id", "")
        fields = item.get("fields", {})
        page_id = fields.get("OneNotePageID")

        try:
            thread_data = self._gdrive.check_gmail_thread(thread_id)
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(
                getattr(exc, "response", None), "status_code", None
            )
            if status == 404:
                logger.info(
                    "Thread %s not found (404), marking as externally "
                    "resolved",
                    thread_id,
                )
                self._list_reader.complete_task(
                    self._action_items_list,
                    item_id,
                    "Thread resolved externally (404)",
                )
                return

            logger.error("Error checking thread %s: %s", thread_id, exc)
            self._list_reader.update_heartbeat(
                self._action_items_list, item_id
            )
            return

        if not thread_data:
            self._list_reader.update_heartbeat(
                self._action_items_list, item_id
            )
            return

        summary = self._generate_summary(thread_data)

        if page_id:
            try:
                self._onenote.append_state_summary(page_id, summary)
            except Exception as exc:
                logger.error(
                    "Failed to update OneNote page %s: %s", page_id, exc
                )

        self._telegram.send_alert(
            f"Thread update: {fields.get('TaskName', thread_id)}\n{summary}",
            priority="normal",
        )

        self._list_reader.complete_task(
            self._action_items_list,
            item_id,
            f"Summary generated from Gmail thread {thread_id}",
        )

    def _handle_exchange_thread(
        self, item: Dict[str, Any], conversation_id: str
    ) -> None:
        """
        Handle an Exchange thread via Microsoft Graph API.

        Queries for messages by conversationId. If new messages are found,
        generates a summary via Claude, appends it to OneNote when a page_id
        exists, sends a Telegram alert, and completes the task.

        Args:
            item: Action item dict.
            conversation_id: Exchange conversation identifier.
        """
        item_id = item.get("id", "")
        fields = item.get("fields", {})
        page_id = fields.get("OneNotePageID")

        try:
            url = (
                f"{GRAPH_BASE}/me/messages"
                f"?$filter=conversationId eq '{conversation_id}'"
                f"&$orderby=receivedDateTime desc"
                f"&$top=10"
                f"&$select=subject,bodyPreview,from,receivedDateTime"
            )
            resp = self._graph.get(url)
            messages = (
                resp.get("value", []) if isinstance(resp, dict) else []
            )
        except Exception as exc:
            logger.error(
                "Failed to fetch Exchange thread %s: %s",
                conversation_id,
                exc,
            )
            self._list_reader.update_heartbeat(
                self._action_items_list, item_id
            )
            return

        if not messages:
            self._list_reader.update_heartbeat(
                self._action_items_list, item_id
            )
            return

        thread_data = {
            "messages": [
                {
                    "from": (
                        msg.get("from", {})
                        .get("emailAddress", {})
                        .get("address", "")
                    ),
                    "body": msg.get("bodyPreview", ""),
                    "date": msg.get("receivedDateTime", ""),
                    "subject": msg.get("subject", ""),
                }
                for msg in messages
            ]
        }

        summary = self._generate_summary(thread_data)

        if page_id:
            try:
                self._onenote.append_state_summary(page_id, summary)
            except Exception as exc:
                logger.error(
                    "Failed to update OneNote page %s: %s", page_id, exc
                )

        self._telegram.send_alert(
            f"Exchange update: "
            f"{fields.get('TaskName', conversation_id)}\n{summary}",
            priority="normal",
        )

        self._list_reader.complete_task(
            self._action_items_list,
            item_id,
            f"Summary generated from Exchange thread {conversation_id}",
        )

    def _check_stale_threads(
        self, items: List[Dict[str, Any]]
    ) -> None:
        """
        Identify threads that have gone stale and generate proactive summaries.

        Finds items whose LastSummaryDate is older than 24 hours and have
        5 or more messages. Generates a proactive "State of Play" summary
        for each and sends a low-priority Telegram alert.

        Args:
            items: List of action items from the last poll.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self._stale_summary_hours
        )

        for item in items:
            fields = item.get("fields", {})
            message_count = fields.get("MessageCount", 0)
            last_summary = fields.get("LastSummaryDate")
            page_id = fields.get("OneNotePageID")

            if message_count < 5:
                continue

            if last_summary:
                try:
                    last_dt = datetime.fromisoformat(
                        last_summary.replace("Z", "+00:00")
                    )
                    if last_dt >= cutoff:
                        continue
                except (ValueError, TypeError):
                    pass

            item_id = item.get("id", "")
            task_name = fields.get("TaskName", item_id)

            logger.info(
                "Generating proactive summary for stale item %s (%s)",
                item_id,
                task_name,
            )

            try:
                self._generate_proactive_summary(item, page_id)
                self._telegram.send_alert(
                    f"State of Play generated: {task_name}",
                    priority="low",
                )
            except Exception as exc:
                logger.error(
                    "Failed proactive summary for item %s: %s",
                    item_id,
                    exc,
                )

    def _generate_summary(
        self, thread_data: Dict[str, Any]
    ) -> str:
        """
        Generate a thread summary from the last 3 messages using Claude.

        Combines the most recent message contents and prompts Claude for
        a concise, action-oriented summary in Derek's voice.

        Args:
            thread_data: Dict containing a 'messages' list, each with
                'from', 'body', 'date', and optionally 'subject' keys.

        Returns:
            Summary text generated by Claude, or a fallback notice on failure.
        """
        messages = thread_data.get("messages", [])[:3]

        message_texts = []
        for msg in messages:
            sender = msg.get("from", "Unknown")
            body = msg.get("body", "")
            date = msg.get("date", "")
            message_texts.append(f"From: {sender} ({date})\n{body}")

        combined = "\n---\n".join(message_texts)

        prompt = (
            "Summarize this email thread for an operations director. "
            "Focus on action items, decisions made, and what needs "
            "attention. Keep it under 3 sentences.\n\n"
            f"{combined}"
        )

        try:
            result = self._claude.generate(prompt, personality="derek")
            if isinstance(result, dict):
                return result.get(
                    "text", result.get("draft_text", str(result))
                )
            return str(result)
        except Exception as exc:
            logger.error("Claude summary generation failed: %s", exc)
            return (
                f"[Auto-summary unavailable: {len(messages)} messages "
                f"pending review]"
            )

    def _generate_proactive_summary(
        self, item: Dict[str, Any], page_id: Optional[str]
    ) -> None:
        """
        Generate a proactive "State of Play" summary for a stale thread.

        Builds a context dict from the item fields, prompts Claude with
        Derek's persona for a structured summary, and appends the result
        to OneNote with a timestamp header.

        Args:
            item: Action item dict with fields.
            page_id: Optional OneNote page ID for appending the summary.
        """
        fields = item.get("fields", {})

        context = {
            "task_name": fields.get("TaskName", ""),
            "status": fields.get("Status", ""),
            "priority": fields.get("Priority", ""),
            "message_count": fields.get("MessageCount", 0),
            "created_date": fields.get("CreatedDate", ""),
            "source": fields.get("Source", ""),
        }

        prompt = (
            "You are Derek Criollo, Director of Operations at Old City "
            "Capital. Write a brief 'State of Play' for this thread. Use "
            "professional, concise language. No technical jargon.\n\n"
            f"Task: {context['task_name']}\n"
            f"Status: {context['status']}\n"
            f"Priority: {context['priority']}\n"
            f"Messages: {context['message_count']}\n"
            f"Created: {context['created_date']}\n"
            f"Source: {context['source']}\n\n"
            "Format:\n"
            "SITUATION: [1 sentence]\n"
            "KEY UPDATES: [bullet points]\n"
            "NEXT STEPS: [what needs to happen]\n"
            "RISK: [any blockers or concerns]"
        )

        try:
            result = self._claude.generate(prompt, personality="derek")
            if isinstance(result, dict):
                summary_text = result.get(
                    "text", result.get("draft_text", str(result))
                )
            else:
                summary_text = str(result)
        except Exception as exc:
            logger.error("Proactive summary generation failed: %s", exc)
            return

        timestamp = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        summary_html = (
            f"<h2>State of Play &mdash; {timestamp}</h2>"
            f"<pre>{summary_text}</pre>"
        )

        if page_id:
            try:
                self._onenote.append_state_summary(page_id, summary_html)
                logger.info(
                    "Proactive summary appended to page %s", page_id
                )
            except Exception as exc:
                logger.error(
                    "Failed to append proactive summary to page %s: %s",
                    page_id,
                    exc,
                )
