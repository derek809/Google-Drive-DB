\# brain/



\*\*Purpose:\*\* The decision-making core. Routes user messages through parsing → memory lookup → AI model selection → execution.



---



\## Flow



\### Simple Request (e.g., "Draft email to Jason")

```

User message

&nbsp;   ↓

conversation\_manager.handle\_message()

&nbsp;   ├─→ Checks: Is this a command? (/start, /help)

&nbsp;   │   └─→ YES: Route to command handler, done

&nbsp;   │

&nbsp;   └─→ NO: Continue to workflow

&nbsp;       ↓

smart\_parser.parse()

&nbsp;   ├─→ Tries: Local LLM (Qwen) to extract intent

&nbsp;   ├─→ Fallback: Regex patterns if LLM fails

&nbsp;   └─→ Returns: {action: 'draft\_email', recipient: 'Jason', context: {...}}

&nbsp;       ↓

pattern\_matcher.find\_relevant()

&nbsp;   ├─→ Searches: Google Sheets for Jason's past emails

&nbsp;   ├─→ Searches: SQLite for email templates

&nbsp;   └─→ Returns: Template ID, preferred tone, past subjects

&nbsp;       ↓

llm\_router.select\_model()

&nbsp;   ├─→ Evaluates: Task complexity (simple draft vs. complex reasoning)

&nbsp;   ├─→ Evaluates: Cost constraints (budget for this user/task)

&nbsp;   └─→ Decides: "Use Ollama" (fast, cheap, good enough)

&nbsp;       ↓

llm\_router.generate()

&nbsp;   ├─→ Calls: Ollama API with template + context

&nbsp;   └─→ Returns: Draft email text

&nbsp;       ↓

conversation\_manager

&nbsp;   └─→ Sends draft back to user via Telegram

```



\### Complex Request (e.g., "Summarize my email thread with Mike about the ABC deal")

```

User message

&nbsp;   ↓

conversation\_manager.handle\_message()

&nbsp;   ↓

smart\_parser.parse()

&nbsp;   └─→ {action: 'summarize\_thread', contact: 'Mike', topic: 'ABC deal'}

&nbsp;       ↓

thread\_synthesizer.fetch\_thread()

&nbsp;   ├─→ Calls: Gmail API to get full email history with Mike

&nbsp;   ├─→ Filters: Only emails mentioning "ABC deal"

&nbsp;   └─→ Returns: 47 emails spanning 3 months

&nbsp;       ↓

llm\_router.select\_model()

&nbsp;   └─→ Decides: "Use Smart LLM" (needs deep reasoning, long context)

&nbsp;       ↓

thread\_synthesizer.synthesize()

&nbsp;   ├─→ Sends all 47 emails to Smart LLM

&nbsp;   ├─→ Asks: "What's the current state? What's pending? What's the next step?"

&nbsp;   └─→ Returns: 3-paragraph summary

&nbsp;       ↓

conversation\_manager

&nbsp;   └─→ Sends summary to user

```



\### Proactive Alert (no user request)

```

proactive\_engine.run() \[runs every 15 minutes]

&nbsp;   ↓

Scans workspace state:

&nbsp;   ├─→ Checks: Gmail for threads idle >3 days

&nbsp;   ├─→ Checks: Telegram for unsent draft messages

&nbsp;   ├─→ Checks: CRM for overdue follow-ups

&nbsp;   └─→ Finds: Email from investor waiting 4 days

&nbsp;       ↓

llm\_router.select\_model()

&nbsp;   └─→ "Use Ollama" (simple alert generation)

&nbsp;       ↓

Generates alert:

&nbsp;   "⚠️ Thread with John (XYZ Fund) has been idle for 4 days.

&nbsp;    Last message: He asked for updated financials.

&nbsp;    Suggested action: Send Q4 audit or follow up."

&nbsp;       ↓

conversation\_manager

&nbsp;   └─→ Pushes alert to Telegram (doesn't wait for user to ask)

```



---



\## Entry Point



\*\*`conversation\_manager.handle\_message(user\_text, user\_id, chat\_id)`\*\*



This function is called by the Telegram bot handler whenever a message arrives.



---



\## External Dependencies



\- \*\*Ollama (local)\*\* - Fast, cheap inference

\- \*\*Smart LLM\*\* - Complex reasoning, deep analysis (Claude, Kimi, etc.)

\- \*\*Gemini API\*\* - Structured data extraction

\- \*\*SQLite\*\* - Pattern storage

\- \*\*Google Sheets\*\* - Template storage



---



\## How Decisions Are Made



\### When to use which AI model?

\- \*\*Ollama:\*\* Simple drafts, basic questions, templates we've used before

\- \*\*Smart LLM:\*\* Complex reasoning, novel situations, multi-step logic, long context

\- \*\*Gemini:\*\* Extracting structured data from messy sources (invoices, forms)



\### When to search memory vs. generate fresh?

\- `pattern\_matcher` runs \*\*first\*\*

\- If confidence score >80%: Use existing template

\- If confidence score <80%: Generate fresh with AI



\### When to be proactive vs. reactive?

\- `proactive\_engine` runs on schedule (every 15 min)

\- Doesn't need user permission to surface important info

\- Only alerts if issue severity >threshold (configurable)

