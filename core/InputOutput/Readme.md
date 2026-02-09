InputOutput/

Purpose: The communication bridge. It translates messy natural language into structured parameters and routes results back to the user across multiple channels.



Flow

Parameter Extraction \& Validation

User Message

&nbsp;  ↓

intent\_tree.classify()

&nbsp;  ├─→ Logic: Walk decision tree (e.g., Casual vs. Actionable)

&nbsp;  └─→ Result: Intent (e.g., TODO\_COMPLETE)

&nbsp;      ↓

action\_extractor.extract\_params()

&nbsp;  ├─→ Layer 1: Deterministic regex for #N or "Draft to..."

&nbsp;  └─→ Layer 2: LLM fallback for fuzzy phrases ("the big one")

&nbsp;      ↓

action\_validator.validate()

&nbsp;  ├─→ Checks: Are all required parameters present?

&nbsp;  ├─→ Checks: Does risk level require user confirmation?

&nbsp;  └─→ Action: Ask clarification or trigger Update Stream

&nbsp;      ↓

notification\_router.route()

&nbsp;  └─→ Channels: Notify via Telegram, Gmail, or Sheets update

Components

Intent Tree (intent\_tree.py): Evaluates user input against a configurable JSON tree to determine the high-level category.



Action Extractor (action\_extractor.py): Hybrid logic that pulls specific data (names, IDs, topics) from raw text.



Action Validator (action\_validator.py): Ensures system safety by enforcing confirmations for "High Risk" actions.



Update Stream (update\_stream.py): Manages "Human Wait" UX by sending intermediate status updates during long tasks.

