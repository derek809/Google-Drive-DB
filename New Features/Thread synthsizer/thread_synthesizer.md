🧠 MCP Thread Synthesizer Design
Purpose: To provide Claude with a comprehensive "State of Play" for an entire email thread before drafting a response, preventing redundant questions and ensuring historical context is maintained.

🏗️ Core Logic
The Thread Synthesizer will pull all messages associated with a thread_id from the SQLite database and generate a structured summary.

Key Responsibilities

Chronological Assembly: Sort all messages in a thread by received_at.

Fact Extraction: Identify confirmed data points (e.g., agreed-upon dates, specific amounts, or attached documents).

Action Tracking: List "Open Questions" and "Completed Tasks" mentioned throughout the thread.

Stakeholder Mapping: Identify all participants and their roles/concerns based on their previous messages.