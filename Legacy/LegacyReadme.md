\# Legacy/



\*\*Purpose:\*\* This directory serves as the archive for the original MCP project codebase. It contains the logic, schemas, and documentation that defined the system's first iteration before it was consolidated and migrated into the current \*\*Action Registry\*\* system.



---



\## 📜 Historical Context



Initially, this "Legacy" code was the primary production environment. It relied on a combination of manual Python scripts and a separate Google Apps Script batch processor. As the project evolved, any "high-value" components—such as proven email patterns, core database schemas, and refined templates—were extracted and integrated into the new \*\*Action Registry\*\* architecture found in the `core/` folder.



---



\## 🔄 Migration Summary



The following key elements were successfully migrated from this legacy folder to the new main project:



\### 1. The "Proven 7" Patterns



The initial analysis of 97 emails identified 7 recurring patterns (e.g., W9 requests, invoice processing, and payment confirmations). These were migrated from the legacy `pattern\_hints` table into the new `intent\_tree.json` and Sheets-based pattern matcher.



\### 2. Core Templates



The 4 original email templates (W9, Turnaround Time, Payment Confirmation, and Delegation) were ported over to the new system to ensure continuity in Derek's professional "voice."



\### 3. Database Schema



The foundational 13-table SQLite structure defined in `learning\_schema.sql` provided the blueprint for the current persistent memory and session tracking used by the Action Registry.



\### 4. Gemini Data Extraction



The logic for intelligently routing spreadsheet and document analysis tasks to Gemini was refined from the legacy `gemini\_helper.py` and is now a standard part of the multi-step workflow chain.



---



\## 📁 Key Legacy Files



\* \*\*`mcp\_learning.db`\*\*: The original SQLite database that captured initial user edits and writing patterns.

\* \*\*`learning\_schema.sql`\*\*: The original architectural map of the system's memory.

\* \*\*`GoogleAppsScript\_MCP\_Batch.js`\*\*: The first implementation of overnight batch processing.

\* \*\*`learning\_loop.py`\*\*: The initial "self-improvement" engine that compared generated drafts against final sent versions.



---



\## ⚠️ Important Note



Files in this directory are for \*\*reference only\*\*. Active development has moved to the `core/`, `brain/`, and `LLM/` directories. This folder remains to provide an audit trail of the system's learning journey and design evolution.

