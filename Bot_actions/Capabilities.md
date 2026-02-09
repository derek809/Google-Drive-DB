\# Capabilities/



\*\*Purpose:\*\* The execution layer. This directory contains the individual "Capability" modules that carry out specific tasks once the system has determined the user's intent and validated the parameters.



---



\## Flow



\### Capability Execution (e.g., "Add 'Buy milk' to my todo list")



```

Validated Request from InputOutput/

\&nbsp;   ↓

skill\_manager.execute\_capability()

\&nbsp;   ├─→ Action: Identifies the correct module (todo\_manager.py)

\&nbsp;   ├─→ Action: Passes extracted parameters (Task: "Buy milk")

\&nbsp;   └─→ Action: Calls specific function (add\_todo)

\&nbsp;       ↓

todo\_manager.py

\&nbsp;   ├─→ Action: Connects to sheets\_client.py

\&nbsp;   ├─→ Action: Appends row to the "Todo" Google Sheet

\&nbsp;   └─→ Returns: Success message + Row ID

\&nbsp;       ↓

skill\_manager

\&nbsp;   └─→ Routes result to notification\_router.py for user feedback



```



---



\## Core Capabilities



\### 1. Task \& Information Management



\* \*\*`todo\_manager.py`\*\*: Handles the lifecycle of tasks, including adding, listing, completing, and clearing items from the Google Sheets todo list.

\* \*\*`quick\_capture.py`\*\*: A high-speed entry point for saving raw notes, links, or fleeting thoughts into a "Capture" sheet for later processing.

\* \*\*`idea\_bouncer.py`\*\*: Uses an LLM to "bounce" ideas back to the user, providing critiques, expansions, or structured feedback on new concepts.



\### 2. Email \& Communication



\* \*\*`template\_manager.py`\*\*: Retrieves and formats pre-written email responses (like W9 requests or project updates) to ensure consistency.

\* \*\*`daily\_digest.py` / `on\_demand\_digest.py\*\*`: Scans the workspace to generate summaries of unread emails, pending tasks, and recent bot actions.



\### 3. Workflow \& Orchestration



\* \*\*`workflow\_manager.py`\*\*: Manages "Chained Actions" where one request triggers multiple capabilities (e.g., "Process invoice" might trigger a file fetch, a sheet update, and an email draft).

\* \*\*`skill\_manager.py`\*\*: The central registry that discovers and invokes the modules above, ensuring they have the correct credentials and context.

\* \*\*`queue\_processor.py`\*\*: Processes background tasks and "Human-in-the-loop" confirmations stored in the local database.



---



\## Entry Point



\*\*`skill\_manager.py`\*\*



This is the primary interface used by the `core/` orchestrator. It ensures that every capability follows the same execution pattern, handles errors gracefully, and logs performance metrics to the observability layer.



---



\## Internal Dependencies



\* \*\*Connections\*\*: Most capabilities rely on client connectors (Gmail, Sheets, Claude) to interact with external services.

\* \*\*Infrastructure\*\*: All actions are logged and validated against the central `actions.py` registry.

\* \*\*File Fetcher (`file\_fetcher.py`)\*\*: A utility capability used across workflows to retrieve attachments or document contents for AI analysis.

