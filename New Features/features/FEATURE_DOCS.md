# Feature Documentation System

This project uses an automated documentation system to explain how each feature
can be used from the Telegram bot.

## How this works (high level)

- Each feature lives in its own Python file inside the `features/` directory.
- When a new feature file is added, a documentation script is run.
- The script generates:
  1. One Markdown file per feature (human-readable usage guide)
  2. One master file that contains all feature guides combined

This allows any human (or AI) to quickly understand:
- What each feature does
- How it is triggered or called from the Telegram bot
- What parameters or configuration it expects

---

## Rules for Feature Files

To make documentation accurate, each feature file SHOULD:

1. Have a clear filename  
   Example: `email_parser.py`, `error_logger.py`

2. Include a top-level docstring explaining the feature

Example:

```python
"""
Parses incoming emails and extracts structured data.
Triggered from Telegram using the /parse_email command.
"""
```

The docstring is used as input to generate documentation.

---

## How to Generate / Update Documentation

Whenever you add a new feature file:

```bash
python generate_feature_docs.py
```

What happens:
- New features get their own `.md` file
- Existing features are skipped
- The master documentation file is appended (never overwritten)

---

## Output Files

- `feature_guides/<feature_name>.md` → individual feature guide
- `feature_guides/MASTER_FEATURE_GUIDE.md` → full combined guide

This system is safe to run repeatedly.

---

## Integration with Telegram Bot

The generated documentation can be used to:
- Power a `/help` command that dynamically lists all features
- Provide context to Claude when users ask "what can you do?"
- Serve as onboarding material for new team members
- Track feature evolution over time

---

## Future Enhancements

Potential improvements to this system:
- Claude-powered documentation generation (reads function signatures and handlers)
- Automatic change detection (only regenerate docs for modified features)
- Interactive examples embedded in Telegram responses
- Version tracking for feature documentation
