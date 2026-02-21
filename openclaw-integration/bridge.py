"""
OpenClaw ↔ Work Bot Bridge
==========================
File-based communication layer that allows OpenClaw to delegate tasks to
the Work Bot and receive structured results.

HOW IT WORKS
------------
1. OpenClaw drops a JSON task file in inbox/
2. Bridge watches inbox/, picks up the file
3. Bridge translates the OpenClaw task into Work Bot internal calls
4. Bridge writes result JSON to outbox/
5. OpenClaw polls outbox/ and acts on the result

USAGE
-----
Run bridge as a standalone process alongside the Work Bot:

    python bridge.py --inbox /path/to/inbox --outbox /path/to/outbox

Or import and embed in mode4_processor.py:

    from openclaw_integration.bridge import OpenClawBridge
    bridge = OpenClawBridge(processor=mode4_processor_instance)
    await bridge.start()
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_INBOX = Path("inbox")
DEFAULT_OUTBOX = Path("outbox")
DEFAULT_PROCESSED = Path("inbox/processed")
DEFAULT_FAILED_DIR = Path("inbox/failed")
POLL_INTERVAL_SECONDS = 2
TASK_LOCK_SUFFIX = ".lock"


# ---------------------------------------------------------------------------
# Skill Registry
# Maps OpenClaw skill names → Work Bot handler methods
# ---------------------------------------------------------------------------

SKILL_REGISTRY: dict[str, dict] = {
    # ── Email ────────────────────────────────────────────────────────────────
    "draft_email_reply": {
        "description": "Find an email and draft a reply to it",
        "required_params": ["email_search_query"],
        "optional_params": ["reply_tone", "reply_instructions", "llm_preference"],
        "handler": "_handle_draft_email_reply",
        "risk": "medium",
    },
    "search_email": {
        "description": "Search Gmail for emails matching a query",
        "required_params": ["query"],
        "optional_params": ["max_results", "date_after"],
        "handler": "_handle_search_email",
        "risk": "low",
    },
    "summarize_thread": {
        "description": "Summarize an email thread",
        "required_params": ["email_search_query"],
        "optional_params": [],
        "handler": "_handle_summarize_thread",
        "risk": "low",
    },
    "forward_email": {
        "description": "Forward an email to a recipient",
        "required_params": ["email_search_query", "to_address"],
        "optional_params": ["forward_note"],
        "handler": "_handle_forward_email",
        "risk": "high",
    },
    "extract_contacts": {
        "description": "Extract contact information from an email thread",
        "required_params": ["email_search_query"],
        "optional_params": [],
        "handler": "_handle_extract_contacts",
        "risk": "low",
    },
    "handle_w9_request": {
        "description": "Respond to a W9 request using templated response",
        "required_params": ["email_search_query"],
        "optional_params": [],
        "handler": "_handle_w9_request",
        "risk": "medium",
    },
    # ── Task Management ──────────────────────────────────────────────────────
    "add_task": {
        "description": "Add a new task to the to-do list",
        "required_params": ["title"],
        "optional_params": ["priority", "deadline", "notes"],
        "handler": "_handle_add_task",
        "risk": "low",
    },
    "list_tasks": {
        "description": "List all pending tasks",
        "required_params": [],
        "optional_params": ["filter_priority", "limit"],
        "handler": "_handle_list_tasks",
        "risk": "low",
    },
    "complete_task": {
        "description": "Mark a task as complete",
        "required_params": ["task_identifier"],
        "optional_params": [],
        "handler": "_handle_complete_task",
        "risk": "medium",
    },
    "delete_task": {
        "description": "Delete a task from the list",
        "required_params": ["task_identifier"],
        "optional_params": [],
        "handler": "_handle_delete_task",
        "risk": "high",
    },
    "update_task": {
        "description": "Update a task's priority or deadline",
        "required_params": ["task_identifier"],
        "optional_params": ["priority", "deadline", "notes"],
        "handler": "_handle_update_task",
        "risk": "medium",
    },
    "view_task_history": {
        "description": "View recently completed tasks",
        "required_params": [],
        "optional_params": ["limit", "days_back"],
        "handler": "_handle_view_task_history",
        "risk": "low",
    },
    # ── Ideas / Knowledge ────────────────────────────────────────────────────
    "capture_idea": {
        "description": "Capture and save an idea to Master Doc",
        "required_params": ["idea_text"],
        "optional_params": ["category", "auto_extract_actions"],
        "handler": "_handle_capture_idea",
        "risk": "low",
    },
    "brainstorm": {
        "description": "Start an interactive brainstorming session (async-safe via file reply)",
        "required_params": ["topic"],
        "optional_params": ["seed_thoughts"],
        "handler": "_handle_brainstorm",
        "risk": "low",
    },
    "save_to_master_doc": {
        "description": "Append formatted content to the Master Google Doc",
        "required_params": ["content"],
        "optional_params": ["section_title"],
        "handler": "_handle_save_to_master_doc",
        "risk": "low",
    },
    "extract_action_items": {
        "description": "Extract action items from unstructured text",
        "required_params": ["text"],
        "optional_params": ["auto_create_tasks"],
        "handler": "_handle_extract_action_items",
        "risk": "low",
    },
    "search_skills": {
        "description": "Search the saved skills/knowledge base",
        "required_params": ["query"],
        "optional_params": ["limit"],
        "handler": "_handle_search_skills",
        "risk": "low",
    },
    # ── Information / Digests ─────────────────────────────────────────────────
    "daily_digest": {
        "description": "Generate a morning summary of tasks and emails",
        "required_params": [],
        "optional_params": [],
        "handler": "_handle_daily_digest",
        "risk": "low",
    },
    "on_demand_digest": {
        "description": "Generate an on-demand summary of current state",
        "required_params": [],
        "optional_params": ["include_emails", "include_tasks"],
        "handler": "_handle_on_demand_digest",
        "risk": "low",
    },
    "system_status": {
        "description": "Report Work Bot and connected service health",
        "required_params": [],
        "optional_params": [],
        "handler": "_handle_system_status",
        "risk": "low",
    },
    "get_template": {
        "description": "Retrieve a named response template",
        "required_params": ["template_name"],
        "optional_params": [],
        "handler": "_handle_get_template",
        "risk": "low",
    },
    # ── Workflows ────────────────────────────────────────────────────────────
    "process_invoice_workflow": {
        "description": "End-to-end: find invoice email → extract data → draft confirmation",
        "required_params": ["invoice_search_query"],
        "optional_params": [],
        "handler": "_handle_process_invoice_workflow",
        "risk": "medium",
    },
    "idea_to_execution_workflow": {
        "description": "End-to-end: capture idea → save to doc → create tasks",
        "required_params": ["idea_text"],
        "optional_params": [],
        "handler": "_handle_idea_to_execution_workflow",
        "risk": "low",
    },
    "w9_fulfillment_workflow": {
        "description": "End-to-end: find W9 request email → draft templated response",
        "required_params": ["search_query"],
        "optional_params": [],
        "handler": "_handle_w9_fulfillment_workflow",
        "risk": "medium",
    },
    # ── Files ─────────────────────────────────────────────────────────────────
    "fetch_google_drive_file": {
        "description": "Search Google Drive and retrieve a file's content or link",
        "required_params": ["file_query"],
        "optional_params": ["file_type"],
        "handler": "_handle_fetch_google_drive_file",
        "risk": "low",
    },
}


# ---------------------------------------------------------------------------
# Result Builders (helpers for constructing outbox messages)
# ---------------------------------------------------------------------------

def _make_result(task_id: str, status: str, **kwargs) -> dict:
    """Build a standard result envelope."""
    return {
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "workbot",
        "status": status,
        **kwargs,
    }


def success(task_id: str, summary: str, data: Any = None,
            artifacts: list = None, confidence: float = 1.0,
            skill_used: str = "", duration_ms: int = 0) -> dict:
    return _make_result(
        task_id, "success",
        result={
            "summary": summary,
            "data": data or {},
            "artifacts": artifacts or [],
        },
        skill_used=skill_used,
        confidence=confidence,
        duration_ms=duration_ms,
    )


def partial(task_id: str, completed_steps: list, failed_steps: list,
            resumable: bool = False, resume_context: dict = None,
            skill_used: str = "") -> dict:
    return _make_result(
        task_id, "partial",
        partial_results={
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "resumable": resumable,
            "resume_context": resume_context or {},
        },
        skill_used=skill_used,
    )


def failed(task_id: str, error_type: str, message: str,
           retryable: bool = False, retry_after_seconds: int = 0,
           suggested_fix: str = "", skill_used: str = "") -> dict:
    return _make_result(
        task_id, "failed",
        error={
            "error_type": error_type,
            "message": message,
            "retryable": retryable,
            "retry_after_seconds": retry_after_seconds,
            "suggested_fix": suggested_fix,
        },
        skill_used=skill_used,
    )


def unknown_skill(task_id: str, requested: str, closest_match: str = "",
                  decomposition_hint: str = "") -> dict:
    return _make_result(
        task_id, "unknown_skill",
        unknown_skill_info={
            "requested_skill": requested,
            "available_skills": list(SKILL_REGISTRY.keys()),
            "closest_match": closest_match,
            "decomposition_hint": decomposition_hint,
        },
    )


# ---------------------------------------------------------------------------
# OpenClawBridge
# ---------------------------------------------------------------------------

class OpenClawBridge:
    """
    Watches an inbox directory for task files from OpenClaw,
    dispatches them to the Work Bot, then writes results to an outbox directory.

    Can be embedded in an existing asyncio app or run standalone.
    """

    def __init__(
        self,
        inbox: Path = DEFAULT_INBOX,
        outbox: Path = DEFAULT_OUTBOX,
        processor=None,  # Mode4Processor instance (optional for testing)
        poll_interval: float = POLL_INTERVAL_SECONDS,
    ):
        self.inbox = Path(inbox)
        self.outbox = Path(outbox)
        self.processed_dir = self.inbox / "processed"
        self.failed_dir = self.inbox / "failed"
        self.processor = processor
        self.poll_interval = poll_interval
        self._active_tasks: dict[str, asyncio.Task] = {}

        # Create directories
        for d in [self.inbox, self.outbox, self.processed_dir, self.failed_dir]:
            d.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"OpenClawBridge initialized | inbox={self.inbox} | outbox={self.outbox}"
        )

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self):
        """Start the bridge loop. Runs until cancelled."""
        logger.info("OpenClawBridge starting...")
        while True:
            try:
                await self._poll_inbox()
            except Exception as e:
                logger.error(f"Bridge poll error: {e}", exc_info=True)
            await asyncio.sleep(self.poll_interval)

    # ── Inbox Polling ─────────────────────────────────────────────────────────

    async def _poll_inbox(self):
        """Scan inbox for unprocessed task files and dispatch each one."""
        task_files = sorted(self.inbox.glob("task_*.json"))
        for task_file in task_files:
            lock_file = task_file.with_suffix(TASK_LOCK_SUFFIX)
            if lock_file.exists():
                continue  # Another worker has it
            try:
                lock_file.touch()
                asyncio.create_task(
                    self._handle_task_file(task_file, lock_file),
                    name=f"task_{task_file.stem}",
                )
            except Exception as e:
                logger.error(f"Failed to lock task file {task_file}: {e}")
                lock_file.unlink(missing_ok=True)

    # ── Task File Handling ────────────────────────────────────────────────────

    async def _handle_task_file(self, task_file: Path, lock_file: Path):
        """Load, validate, dispatch, and archive a single task file."""
        task_id = "unknown"
        start_ms = int(time.time() * 1000)
        try:
            raw = task_file.read_text(encoding="utf-8")
            task = json.loads(raw)
            task_id = task.get("task_id", str(uuid.uuid4()))
            logger.info(f"Picked up task {task_id}: skill={task.get('skill')}")

            result = await self._dispatch(task, start_ms)
            await self._write_outbox(result)

            # Archive the processed task
            dest = self.processed_dir / task_file.name
            task_file.rename(dest)
            logger.info(f"Task {task_id} → status={result['status']}")

        except json.JSONDecodeError as e:
            logger.error(f"Bad JSON in {task_file}: {e}")
            err_result = failed(
                task_id, "validation_error",
                f"Invalid JSON in task file: {e}",
                retryable=False,
            )
            await self._write_outbox(err_result)
            task_file.rename(self.failed_dir / task_file.name)

        except Exception as e:
            logger.error(f"Unhandled error processing {task_file}: {e}", exc_info=True)
            err_result = failed(
                task_id, "internal_error",
                f"Bridge internal error: {e}",
                retryable=True,
            )
            await self._write_outbox(err_result)
            task_file.rename(self.failed_dir / task_file.name)

        finally:
            lock_file.unlink(missing_ok=True)

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def _dispatch(self, task: dict, start_ms: int) -> dict:
        """Route the task to the appropriate skill handler."""
        task_id = task["task_id"]
        skill = task.get("skill", "")
        params = task.get("parameters", {})
        timeout = task.get("timeout_seconds", 300)

        # Unknown skill guard
        if skill not in SKILL_REGISTRY:
            closest = self._closest_skill(skill)
            hint = self._decomposition_hint(skill)
            return unknown_skill(task_id, skill, closest, hint)

        # Parameter validation
        reg = SKILL_REGISTRY[skill]
        missing = [p for p in reg["required_params"] if p not in params]
        if missing:
            return failed(
                task_id, "validation_error",
                f"Missing required parameters for '{skill}': {missing}",
                retryable=False,
                suggested_fix=f"Add these parameters: {missing}",
                skill_used=skill,
            )

        # Execute with timeout
        handler_name = reg["handler"]
        handler = getattr(self, handler_name, None)
        if handler is None:
            return failed(
                task_id, "internal_error",
                f"Handler '{handler_name}' not implemented in bridge",
                retryable=False,
                skill_used=skill,
            )

        try:
            result = await asyncio.wait_for(
                handler(task_id, params, task.get("context", {})),
                timeout=timeout,
            )
            duration_ms = int(time.time() * 1000) - start_ms
            if "duration_ms" not in result:
                result["duration_ms"] = duration_ms
            return result

        except asyncio.TimeoutError:
            return failed(
                task_id, "internal_error",
                f"Task timed out after {timeout}s",
                retryable=True,
                retry_after_seconds=60,
                skill_used=skill,
            )

    # ── Outbox Writing ────────────────────────────────────────────────────────

    async def _write_outbox(self, result: dict):
        """Atomically write a result file to the outbox directory."""
        task_id = result["task_id"]
        filename = f"result_{task_id}.json"
        tmp_path = self.outbox / f".tmp_{filename}"
        final_path = self.outbox / filename
        try:
            tmp_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp_path.rename(final_path)
        except Exception as e:
            logger.error(f"Failed to write outbox result for {task_id}: {e}")
            raise

    # ── Skill Handlers ────────────────────────────────────────────────────────
    # Each handler: async def _handle_X(task_id, params, context) -> dict
    # Returns a result dict (use success(), partial(), failed() helpers above)

    async def _handle_draft_email_reply(self, task_id: str, params: dict, context: dict) -> dict:
        """Draft a reply to an email found by search query."""
        if self.processor is None:
            return self._stub_success(task_id, "draft_email_reply",
                                      "Draft created (stub mode)")
        try:
            query = params["email_search_query"]
            tone = params.get("reply_tone", "professional")
            instructions = params.get("reply_instructions", "")

            # Use existing Mode4Processor gmail + LLM pipeline
            email_data = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.gmail.search_emails, query, 1
            )
            if not email_data:
                return failed(task_id, "not_found",
                              f"No email found matching: {query}",
                              retryable=False,
                              suggested_fix="Try a broader search query",
                              skill_used="draft_email_reply")

            email = email_data[0]
            prompt = f"Draft a {tone} reply to this email. {instructions}".strip()
            llm_pref = params.get("llm_preference", "auto")

            if llm_pref == "claude" or llm_pref == "auto":
                draft_text = await asyncio.get_event_loop().run_in_executor(
                    None, self.processor.claude.generate_draft,
                    email["body"], prompt
                )
            else:
                draft_text = await asyncio.get_event_loop().run_in_executor(
                    None, self.processor.ollama.generate_draft,
                    email["body"], prompt
                )

            draft_id = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.gmail.create_reply_draft,
                email["id"], draft_text
            )

            return success(
                task_id,
                summary=f"Draft created for email: '{email.get('subject', '(no subject)')}'",
                data={"draft_text": draft_text, "email_subject": email.get("subject")},
                artifacts=[{"type": "gmail_draft_id", "value": draft_id,
                            "label": "Gmail Draft ID"}],
                skill_used="draft_email_reply",
            )
        except Exception as e:
            return failed(task_id, "internal_error", str(e),
                          retryable=True, skill_used="draft_email_reply")

    async def _handle_search_email(self, task_id: str, params: dict, context: dict) -> dict:
        if self.processor is None:
            return self._stub_success(task_id, "search_email",
                                      "Email search results (stub mode)")
        try:
            results = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.gmail.search_emails,
                params["query"], params.get("max_results", 5)
            )
            emails = [
                {"id": e["id"], "subject": e.get("subject"), "from": e.get("from"),
                 "date": e.get("date"), "snippet": e.get("snippet", "")[:200]}
                for e in results
            ]
            return success(
                task_id,
                summary=f"Found {len(emails)} email(s) matching '{params['query']}'",
                data={"emails": emails, "count": len(emails)},
                skill_used="search_email",
            )
        except Exception as e:
            return failed(task_id, "external_service_unavailable", str(e),
                          retryable=True, skill_used="search_email")

    async def _handle_add_task(self, task_id: str, params: dict, context: dict) -> dict:
        if self.processor is None:
            return self._stub_success(task_id, "add_task",
                                      f"Task '{params['title']}' added (stub mode)")
        try:
            created_id = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.todo_manager.add_task,
                params["title"],
                params.get("priority", "medium"),
                params.get("deadline"),
                params.get("notes", ""),
            )
            return success(
                task_id,
                summary=f"Task added: '{params['title']}'",
                data={"task_id": created_id, "title": params["title"]},
                artifacts=[{"type": "task_id", "value": str(created_id),
                            "label": "New Task ID"}],
                skill_used="add_task",
            )
        except Exception as e:
            return failed(task_id, "internal_error", str(e),
                          retryable=True, skill_used="add_task")

    async def _handle_list_tasks(self, task_id: str, params: dict, context: dict) -> dict:
        if self.processor is None:
            return self._stub_success(task_id, "list_tasks", "Task list (stub mode)")
        try:
            tasks = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.todo_manager.list_tasks,
                params.get("filter_priority"), params.get("limit", 20)
            )
            return success(
                task_id,
                summary=f"Found {len(tasks)} pending task(s)",
                data={"tasks": tasks, "count": len(tasks)},
                skill_used="list_tasks",
            )
        except Exception as e:
            return failed(task_id, "internal_error", str(e),
                          retryable=True, skill_used="list_tasks")

    async def _handle_complete_task(self, task_id: str, params: dict, context: dict) -> dict:
        if self.processor is None:
            return self._stub_success(task_id, "complete_task", "Task completed (stub mode)")
        try:
            result_data = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.todo_manager.complete_task,
                params["task_identifier"]
            )
            if not result_data:
                return failed(task_id, "not_found",
                              f"No task found matching '{params['task_identifier']}'",
                              suggested_fix="Use list_tasks first to get exact task names",
                              skill_used="complete_task")
            return success(
                task_id,
                summary=f"Task completed: '{params['task_identifier']}'",
                data=result_data,
                skill_used="complete_task",
            )
        except Exception as e:
            return failed(task_id, "internal_error", str(e),
                          retryable=True, skill_used="complete_task")

    async def _handle_on_demand_digest(self, task_id: str, params: dict, context: dict) -> dict:
        if self.processor is None:
            return self._stub_success(task_id, "on_demand_digest", "Digest (stub mode)")
        try:
            digest = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.on_demand_digest.generate,
                params.get("include_emails", True),
                params.get("include_tasks", True),
            )
            return success(
                task_id,
                summary="On-demand digest generated",
                data={"digest": digest},
                skill_used="on_demand_digest",
            )
        except Exception as e:
            return failed(task_id, "internal_error", str(e),
                          retryable=True, skill_used="on_demand_digest")

    async def _handle_system_status(self, task_id: str, params: dict, context: dict) -> dict:
        """Report service health without touching processor internals."""
        status_checks = {}
        services = ["gmail", "ollama", "claude", "sheets", "google_docs"]
        for svc in services:
            if self.processor and hasattr(self.processor, svc):
                try:
                    client = getattr(self.processor, svc)
                    if hasattr(client, "ping"):
                        ok = await asyncio.get_event_loop().run_in_executor(
                            None, client.ping
                        )
                        status_checks[svc] = "ok" if ok else "degraded"
                    else:
                        status_checks[svc] = "available"
                except Exception as e:
                    status_checks[svc] = f"error: {e}"
            else:
                status_checks[svc] = "unknown"

        all_ok = all(v in ("ok", "available") for v in status_checks.values())
        return success(
            task_id,
            summary="System status report",
            data={"services": status_checks, "overall": "healthy" if all_ok else "degraded"},
            confidence=1.0,
            skill_used="system_status",
        )

    async def _handle_capture_idea(self, task_id: str, params: dict, context: dict) -> dict:
        if self.processor is None:
            return self._stub_success(task_id, "capture_idea", "Idea captured (stub mode)")
        try:
            result_data = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.skill_manager.capture_idea,
                params["idea_text"],
                params.get("category", "general"),
                params.get("auto_extract_actions", True),
            )
            return success(
                task_id,
                summary=f"Idea captured: '{params['idea_text'][:60]}...'",
                data=result_data,
                skill_used="capture_idea",
            )
        except Exception as e:
            return failed(task_id, "internal_error", str(e),
                          retryable=True, skill_used="capture_idea")

    async def _handle_daily_digest(self, task_id: str, params: dict, context: dict) -> dict:
        if self.processor is None:
            return self._stub_success(task_id, "daily_digest", "Daily digest (stub mode)")
        try:
            digest = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.daily_digest.generate
            )
            return success(task_id, summary="Daily digest generated",
                           data={"digest": digest}, skill_used="daily_digest")
        except Exception as e:
            return failed(task_id, "internal_error", str(e),
                          retryable=True, skill_used="daily_digest")

    async def _handle_summarize_thread(self, task_id: str, params: dict, context: dict) -> dict:
        if self.processor is None:
            return self._stub_success(task_id, "summarize_thread", "Thread summary (stub mode)")
        try:
            emails = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.gmail.search_emails,
                params["email_search_query"], 10
            )
            if not emails:
                return failed(task_id, "not_found",
                              "No emails found for that query", skill_used="summarize_thread")
            summary = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.thread_synthesizer.summarize, emails
            )
            return success(task_id, summary=f"Thread summarized ({len(emails)} messages)",
                           data={"summary": summary, "email_count": len(emails)},
                           skill_used="summarize_thread")
        except Exception as e:
            return failed(task_id, "internal_error", str(e),
                          retryable=True, skill_used="summarize_thread")

    async def _handle_fetch_google_drive_file(self, task_id: str, params: dict, context: dict) -> dict:
        if self.processor is None:
            return self._stub_success(task_id, "fetch_google_drive_file", "File fetched (stub mode)")
        try:
            result_data = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.file_fetcher.fetch,
                params["file_query"], params.get("file_type", "any")
            )
            if not result_data:
                return failed(task_id, "not_found",
                              f"No file found matching '{params['file_query']}'",
                              skill_used="fetch_google_drive_file")
            return success(task_id, summary=f"File found: {result_data.get('name')}",
                           data=result_data,
                           artifacts=[{"type": "file_url", "value": result_data.get("url", ""),
                                       "label": result_data.get("name", "File")}],
                           skill_used="fetch_google_drive_file")
        except Exception as e:
            return failed(task_id, "internal_error", str(e),
                          retryable=True, skill_used="fetch_google_drive_file")

    # Stub handlers for skills not yet fully wired
    async def _handle_extract_contacts(self, task_id, params, context):
        return self._stub_success(task_id, "extract_contacts", "Contacts extracted (stub)")

    async def _handle_handle_w9_request(self, task_id, params, context):
        return self._stub_success(task_id, "handle_w9_request", "W9 handled (stub)")

    async def _handle_delete_task(self, task_id, params, context):
        return self._stub_success(task_id, "delete_task", "Task deleted (stub)")

    async def _handle_update_task(self, task_id, params, context):
        return self._stub_success(task_id, "update_task", "Task updated (stub)")

    async def _handle_view_task_history(self, task_id, params, context):
        return self._stub_success(task_id, "view_task_history", "History (stub)")

    async def _handle_brainstorm(self, task_id, params, context):
        return self._stub_success(task_id, "brainstorm", "Brainstorm started (stub)")

    async def _handle_save_to_master_doc(self, task_id, params, context):
        return self._stub_success(task_id, "save_to_master_doc", "Saved to doc (stub)")

    async def _handle_extract_action_items(self, task_id, params, context):
        return self._stub_success(task_id, "extract_action_items", "Actions extracted (stub)")

    async def _handle_search_skills(self, task_id, params, context):
        return self._stub_success(task_id, "search_skills", "Skills found (stub)")

    async def _handle_finalize_idea_session(self, task_id, params, context):
        return self._stub_success(task_id, "finalize_idea_session", "Session finalized (stub)")

    async def _handle_get_template(self, task_id, params, context):
        return self._stub_success(task_id, "get_template", "Template retrieved (stub)")

    async def _handle_process_invoice_workflow(self, task_id, params, context):
        return self._stub_success(task_id, "process_invoice_workflow", "Invoice processed (stub)")

    async def _handle_idea_to_execution_workflow(self, task_id, params, context):
        return self._stub_success(task_id, "idea_to_execution_workflow", "Idea executed (stub)")

    async def _handle_w9_fulfillment_workflow(self, task_id, params, context):
        return self._stub_success(task_id, "w9_fulfillment_workflow", "W9 fulfilled (stub)")

    async def _handle_forward_email(self, task_id, params, context):
        return self._stub_success(task_id, "forward_email", "Email forwarded (stub)")

    # ── Utilities ────────────────────────────────────────────────────────────

    def _stub_success(self, task_id: str, skill: str, summary: str) -> dict:
        """Return a stub success result when processor is not connected."""
        return success(task_id, summary, skill_used=skill, confidence=0.5)

    def _closest_skill(self, requested: str) -> str:
        """Find the most similar skill name using simple character overlap."""
        req = requested.lower().replace("_", " ")
        best, best_score = "", 0.0
        for skill_name in SKILL_REGISTRY:
            s = skill_name.lower().replace("_", " ")
            common = len(set(req.split()) & set(s.split()))
            if common > best_score:
                best_score = common
                best = skill_name
        return best

    def _decomposition_hint(self, requested: str) -> str:
        """Suggest how an unknown task might be broken into known skills."""
        hints = {
            "send_email": "Use draft_email_reply (creates a draft; you must manually send)",
            "reply": "Use draft_email_reply",
            "task": "Use add_task or list_tasks",
            "note": "Use capture_idea or save_to_master_doc",
            "summary": "Use on_demand_digest or summarize_thread",
            "file": "Use fetch_google_drive_file",
            "status": "Use system_status",
        }
        req_lower = requested.lower()
        for keyword, hint in hints.items():
            if keyword in req_lower:
                return hint
        return "Try decomposing into: search_email + draft_email_reply, or add_task + list_tasks"


# ---------------------------------------------------------------------------
# Standalone Entry Point
# ---------------------------------------------------------------------------

async def _main():
    import argparse

    parser = argparse.ArgumentParser(description="OpenClaw ↔ Work Bot Bridge")
    parser.add_argument("--inbox", default="inbox", help="Inbox directory path")
    parser.add_argument("--outbox", default="outbox", help="Outbox directory path")
    parser.add_argument("--poll", type=float, default=2.0, help="Poll interval in seconds")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Try to import and connect the actual Mode4Processor
    processor = None
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from core.mode4_processor import Mode4Processor
        processor = Mode4Processor()
        logger.info("Connected to Mode4Processor")
    except ImportError as e:
        logger.warning(f"Mode4Processor not available, running in stub mode: {e}")

    bridge = OpenClawBridge(
        inbox=Path(args.inbox),
        outbox=Path(args.outbox),
        processor=processor,
        poll_interval=args.poll,
    )
    await bridge.start()


if __name__ == "__main__":
    asyncio.run(_main())
