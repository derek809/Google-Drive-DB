State\&Memory/

Purpose: The persistence layer. It manages the bot’s short-term focus (Current Subject) and long-term conversation progress (State Machine).



Flow

Resolving "it" (Pronoun Resolution)

User: "Send it to Sarah"

&nbsp;  ↓

context\_manager.inject\_context()

&nbsp;  ├─→ Recognizes: Pronoun "it"

&nbsp;  ├─→ Lookup: Find last active entity in Topic Stack

&nbsp;  ├─→ Filter: Check semantic compatibility (Verb: Send -> Type: Email)

&nbsp;  └─→ Action: Injects thread\_id from previous turn into params

Multi-Turn State Recovery

Bot Reboot / Service Restart

&nbsp;  ↓

conversation\_state.get\_state()

&nbsp;  ├─→ Recovery: Pulls last state from SQLite (e.g., AWAITING\_INPUT)

&nbsp;  └─→ Action: Resumes conversation exactly where it stopped

Components

Context Manager (context\_manager.py): Solves the "it" problem using a LIFO topic stack and semantic matching.



Conversation State (conversation\_state.py): A formal state machine (Idle, Executing, Awaiting, etc.) persisted to the database.



Session State (session\_state.py): Short-term memory for numbered lists (e.g., "#1" means "The W9 request") with a 30-minute expiry.

