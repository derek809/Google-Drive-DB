\# llm/



\*\*Purpose:\*\* The intelligence layer. Acts as the system's "reasoning engine" by providing a unified interface for multiple LLM providers, allowing the bot to switch models based on task complexity, cost, and speed.



---



\## Flow



\### Model Selection \& Generation (e.g., "Summarize this long thread")



```

Request from mode4\_processor

\&nbsp;   ↓

llm\_router.select\_model()

\&nbsp;   ├─→ Evaluates: Task complexity (Summarization vs. Simple Greeting)

\&nbsp;   ├─→ Evaluates: Input size (Context length of the email thread)

\&nbsp;   ├─→ Evaluates: Cost constraints (Budget-friendly vs. High-power)

\&nbsp;   └─→ Decides: "Use Claude" (High reasoning, long context)

\&nbsp;       ↓

llm\_router.generate()

\&nbsp;   ├─→ Action: Retrieves specific prompt template from prompts.json

\&nbsp;   ├─→ Action: Routes to specific provider client (e.g., claude\_client.py)

\&nbsp;   └─→ Returns: Structured JSON or Natural Language response

\&nbsp;       ↓

mode4\_processor

\&nbsp;   └─→ Passes result to the next stage (Extraction or Output)



```



---



\## Components



\### 1. Model Router (`llm\_router.py`)



\* \*\*The Gatekeeper:\*\* Analyzes every incoming request to determine the most efficient model to use.

\* \*\*Unified Interface:\*\* Provides a single `.generate()` method that hides the complexity of different API formats (Ollama vs. Anthropic vs. Google).

\* \*\*Fallback Logic:\*\* If a primary model (like Claude) fails, the router automatically attempts a fallback to a secondary model (like Gemini) to ensure zero downtime.



\### 2. Provider Clients (`/connections/`)



\* \*\*Claude Client:\*\* Leveraged for deep reasoning, complex drafting, and long-form synthesis.

\* \*\*Gemini Client:\*\* Optimized for structured data extraction and rapid processing of messy inputs.

\* \*\*Ollama Client:\*\* Used for local, privacy-focused, and cost-free inference on simpler tasks like intent classification.

\* \*\*Kimi Client:\*\* Utilized for high-speed, efficient processing in specific regional or task-specific contexts.



---



\## Decision Logic



\### When to use which AI model?



| Model | Use Case | Strength |

| --- | --- | --- |

| \*\*Ollama (Local)\*\* | Intent matching, simple greetings, basic classification | $0 cost, high privacy, low latency |

| \*\*Claude\*\* | Complex email drafting, multi-step reasoning, nuances | Superior "human-like" writing and logic |

| \*\*Gemini\*\* | Extracting data from tables/sheets, long context summaries | Massively long context window \& structured output |

| \*\*Kimi\*\* | High-speed processing, efficient simple requests | Performance vs. cost balance |



---



\## External Dependencies



\* \*\*Prompts Configuration (`prompts.json`):\*\* Centralized storage for system instructions and few-shot examples.

\* \*\*Model Credentials:\*\* API keys managed via `Infrastructure/m1\_config.py`.

\* \*\*Performance Metrics:\*\* Reports latency and success rates to `Infrastructure/observability.py`.

