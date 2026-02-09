Based on a review of the system files and existing documentation, here is a comprehensive project README that integrates the core architecture, capabilities, and the advanced features detailed in your \*\*Guides\*\* folder.



---



\# Mode 4: Integrated AI Email \& Operations Assistant



Mode 4 is a privacy-first, local-first operational assistant running on M1 MacBook architecture. It transforms rigid email processing into a natural, conversational experience by combining local LLMs, multi-channel notifications, and persistent state management.



\## 📂 Project Architecture



The system is structured into specialized layers to ensure modularity and scalability:



\### 1. 🧠 Brain (Decision-Making Core)



Located in `brain/`, this layer acts as the reasoning engine.



\* \*\*Intent Classification\*\*: A JSON-configured decision tree in `intent\_tree.json` routes input to actionable categories.

\* \*\*Smart Parsing\*\*: Uses local \*\*Qwen2.5:3b\*\* via Ollama to intelligently extract email references and instructions from natural language.

\* \*\*LLM Routing\*\*: Dynamically selects models (Ollama for speed, Claude for reasoning, Gemini for data) based on task complexity.

\* \*\*Proactive Engine\*\*: Monitors the workspace in the background to identify stale threads, suggest follow-ups, and send morning digests.



\### 2. ⚙️ Core (Execution Orchestrator)



Located in `core/`, this is the system's "glue".



\* \*\*Action Registry\*\*: The formal contract for every skill, defining required parameters and risk levels (Low/Medium/High).

\* \*\*Context Manager\*\*: Resolves pronouns like "it" or "that" using a LIFO topic stack to maintain conversational continuity.

\* \*\*Action Validator\*\*: Enforces safety by requiring explicit user confirmation for high-risk actions (e.g., deleting tasks or sending emails).

\* \*\*State Machine\*\*: Tracks user status (Idle, Awaiting Input, Executing) across restarts using SQLite.



\### 3. 🤖 LLM (Intelligence Layer)



Located in `LLM/`, providing a unified interface for multiple providers.



\* \*\*Claude Client\*\*: Deep reasoning, complex drafting, and thread synthesis.

\* \*\*Gemini Client\*\*: Structured data extraction from sheets/docs and mass context summaries.

\* \*\*Ollama Client\*\*: Zero-cost local inference for intent matching and basic greetings.

\* \*\*Kimi Client\*\*: Alternative high-speed model for creative brainstorming.



\### 4. 📂 Bot\_actions (Capability Modules)



The execution layer containing individual task modules.



\* \*\*Task Manager\*\*: Synchronizes with Google Sheets (`todos\_active`) to track and complete tasks.

\* \*\*Idea Bouncer\*\*: Interactive thinking partner for exploring gaps in new concepts.

\* \*\*File Fetcher\*\*: Search and delivery of Google Drive files via Telegram commands.



---



\## ✨ Key Advanced Features



\* \*\*Workflow Chaining\*\*: Execute multi-step commands like \*"Find the invoice, create a sheet from it, and then email Sarah"\*.

\* \*\*Multi-Channel Output\*\*: Results are routed to Telegram, logged in SQLite, and can update Google Sheets or send Gmail summaries simultaneously.

\* \*\*"Human Wait" UX\*\*: The `UpdateStream` provides real-time status updates (e.g., \*"Analyzing attachments..."\*) during long tasks to prevent user uncertainty.

\* \*\*Auto-Priority Detection\*\*: Automatically flags tasks as high-priority based on keywords like "URGENT" or "ASAP".



---



\## 🚀 Quick Start



1\. \*\*Launch Local Intelligence\*\*:

```bash

ollama serve

ollama pull qwen2.5:3b



```





2\. \*\*Start the Assistant\*\*:

```bash

./start\_mode4.sh



```





3\. \*\*Chat Naturally\*\*: Message your Telegram bot with simple phrases like \*"Draft an email to Jason about the Q4 report"\* or \*"What's on my todo list?"\*.



\## 🛠️ Configuration \& Guides



Detailed operational instructions can be found in the `Guides/` folder:



\* `READY\_TO\_USE.md`: Complete user operational guide.

\* `SKILL\_TEMPLATES.md`: How to add new capabilities to the system.

\* `CONVERSATION\_GUIDE.md`: Mastering the natural language interface.

