\# core/



\*\*Purpose:\*\* The central orchestrator and logic engine for Mode 4. This directory contains the "brains" of the system, managing the transition from raw user input to executed actions across database persistence, intent extraction, and multi-channel notifications.



---



\## Flow



\### Action Registry Execution (e.g., "Draft email to Jason")



```

User message

&nbsp;  ↓

conversation\_manager.handle\_message()

&nbsp;  ├─→ Checks: Is user in an active 'awaiting' state?

&nbsp;  │   └─→ YES: Resolve clarification/confirmation, continue

&nbsp;  │

&nbsp;  └─→ NO: Start new intent classification

&nbsp;      ↓

intent\_tree.classify()

&nbsp;  ├─→ Walks: JSON-configured decision tree

&nbsp;  └─→ Returns: Intent (e.g., EMAIL\_DRAFT) and initial parameters

&nbsp;      ↓

action\_extractor.extract\_params()

&nbsp;  ├─→ Layer 1: Deterministic regex for #N or "Draft to..."

&nbsp;  └─→ Layer 2: LLM fallback for fuzzy phrases ("the big one")

&nbsp;      ↓

context\_manager.inject\_context()

&nbsp;  ├─→ Recognizes: Pronouns like "it" or "that"

&nbsp;  └─→ Lookup: Resolves references using the Session Topic Stack

&nbsp;      ↓

action\_validator.validate()

&nbsp;  ├─→ Checks: Required params present and risk level

&nbsp;  └─→ Action: Triggers "Human Wait" status updates via update\_stream.py

&nbsp;      ↓

mode4\_processor.process\_message()

&nbsp;  ├─→ Action: Final API calls to Gmail, Sheets, or LLMs

&nbsp;  └─→ Result: Draft saved or task updated



```



---



\## Entry Point



\*\*`mode4\_processor.py`\*\*



This is the \*\*Main Orchestrator\*\* for the entire system. It acts as the "Glue" that binds sub-folders together, initializing all lazy-loaded clients (Gmail, Sheets, Ollama, Claude, Kimi) and managing startup recovery for messages sent while the bot was offline.



---



\## Architecture



\### 1. Infrastructure/



\*\*Focus:\*\* Foundations \& Persistence.



\* \*\*`actions.py`\*\*: The formal contract defining every skill, required parameters, and risk levels.

\* \*\*`db\_manager.py`\*\*: Handles local SQLite storage (`mode4.db`) for message queues, tasks, and audit logs.

\* \*\*`observability.py`\*\*: Monitors system health and implements circuit breakers for service failures.

\* \*\*`m1\_config.py`\*\*: Central hub for environment variables, API keys, and feature flags.



\### 2. InputOutput/



\*\*Focus:\*\* Translation \& Feedback.



\* \*\*`intent\_tree.py`\*\*: Evaluates user input against a configurable JSON tree to determine intent.

\* \*\*`action\_extractor.py`\*\*: Extracts specific data points (names, IDs, topics) from raw text.

\* \*\*`action\_validator.py`\*\*: Enforces system safety by requesting confirmation for high-risk actions.

\* \*\*`update\_stream.py`\*\*: Provides live status updates to the user during long-running tasks.



\### 3. State \& Memory/



\*\*Focus:\*\* Context \& Continuity.



\* \*\*`context\_manager.py`\*\*: Solves the "it" problem using a semantic pronoun resolution matrix.

\* \*\*`conversation\_state.py`\*\*: A persistent state machine tracking user status (Idle, Awaiting, etc.).

\* \*\*`session\_state.py`\*\*: Short-term memory for numbered lists and last-viewed entities.



---



\## Internal Dependencies



\* \*\*`\_\_init\_\_.py`\*\*: Universal action registry that handles cross-capability extraction and validation.

\* \*\*SQLite\*\*: Local persistence for state, message queues, and background processing.

\* \*\*LLM Router\*\*: Decides between local Ollama (speed/cost) or high-power Claude/Kimi (reasoning).

