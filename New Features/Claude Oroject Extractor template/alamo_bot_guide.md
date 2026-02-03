# Alamo Bot - Complete Implementation Guide

## Table of Contents
1. [What You're Building](#what-youre-building)
2. [Architecture Overview](#architecture-overview)
3. [Migration Phase](#migration-phase)
4. [Runtime Phase](#runtime-phase)
5. [Configuration](#configuration)
6. [Quick Start](#quick-start)

---

## What You're Building
A **deterministic Telegram bot** that acts as an operational assistant by:
1. **Converting Claude Projects into Rules**: Extracts structured JSON/TXT files from Claude.
2. **Local Execution**: Runs on cheap local models (Ollama) like `llama3.1:8b`.
3. **Strict Boundaries**: Prevents hallucinations by using a deterministic decision engine.



## Architecture Overview
The bot operates in two distinct phases:

### Migration Phase (One-time per project)
* **Extract**: Use the `extract.md` prompt in Claude.
* **Structure**: Save outputs into the `/brain` directory.
* **Validate**: Ensure rules are bot-safe.

### Runtime Phase (24/7 Operation)
1. **Intent Classifier**: Maps messages to specific tasks (e.g., RR Onboarding).
2. **Decision Engine**: Checks refusal conditions and system constraints.
3. **LLM Wrapper**: Generates the final text using local hardware.
4. **Confidence Scorer**: Determines if the bot should act automatically or ask for help.

---

## Configuration
### Telegram Config (`config/telegram_config.json`)
```json
{
  "bot_token": "YOUR_TOKEN",
  "authorized_user_ids": [123456789],
  "admin_email": "derek@oldcitycapital.com"
}