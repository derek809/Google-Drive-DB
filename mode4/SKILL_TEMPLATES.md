# How to Add New Skill Types

This guide lets you add new skill types (intents) to the bot without needing external help.

## Quick Reference

The system uses **intent-based routing** in `conversation_manager.py`:
1. User sends message
2. `classify_intent()` matches trigger phrases → returns an `Intent`
3. `route_to_capability()` calls the appropriate handler
4. Handler processes and responds

---

## Step-by-Step: Adding a New Skill

### 1. Add the Intent Enum

Open `conversation_manager.py` and find the `Intent` enum (around line 26):

```python
class Intent(Enum):
    # ... existing intents ...

    # Add your new intent here
    MY_NEW_SKILL = "my_skill_name"
```

### 2. Add Trigger Phrase Detection

In `classify_intent()` (around line 290), add your trigger phrases:

```python
# === MY NEW SKILL ===
my_skill_phrases = ['trigger phrase 1', 'trigger phrase 2', 'another trigger']
if any(phrase in text_lower for phrase in my_skill_phrases):
    return Intent.MY_NEW_SKILL
```

**Tips:**
- Put more specific patterns BEFORE general ones
- Use `text_lower.startswith()` for prefix matching
- Combine conditions: `if 'word1' in text_lower and 'word2' in text_lower:`

### 3. Add Route Handler

In `route_to_capability()` (around line 480), add your route:

```python
elif intent == Intent.MY_NEW_SKILL:
    return await self._handle_my_new_skill(text, user_id, chat_id)
```

### 4. Create the Handler Method

Add your handler method (around line 1170):

```python
async def _handle_my_new_skill(self, text: str, user_id: int, chat_id: int) -> Dict[str, Any]:
    """Handle my new skill - describe what it does."""
    try:
        # Your logic here
        # Example: Call an external service, process data, etc.

        response = "Your response to the user"
        await self.telegram.send_response(chat_id, response)

        return {'handled': True, 'routed_to': 'my_new_skill'}

    except Exception as e:
        logger.error(f"Error in my_new_skill: {e}", exc_info=True)
        await self.telegram.send_response(
            chat_id,
            f"Sorry, something went wrong. Error: {str(e)}"
        )
        return {'handled': True, 'routed_to': 'my_new_skill', 'error': str(e)}
```

---

## Existing Skills Reference

| Intent | Trigger Phrases | Handler | What It Does |
|--------|-----------------|---------|--------------|
| `GREETING` | "hi", "hello", "hey" | `_generate_greeting()` | Friendly greeting |
| `HELP_REQUEST` | "help", "what can you do" | `_generate_help_message()` | Shows capabilities |
| `EMAIL_DRAFT` | "draft email to...", "write email" | → `email_processor` | Creates email drafts |
| `TODO_ADD` | "add task", "remind me" | `_handle_todo_add()` | Adds tasks |
| `TODO_LIST` | "show my todos", "my tasks" | `_handle_todo_list()` | Lists tasks |
| `IDEA_BOUNCE` | "help me think", "brainstorm" | `_handle_idea_bounce()` | Starts idea exploration |
| `SKILL_FINALIZE` | "finalize", "save this idea" | `_handle_skill_finalize()` | Saves to Master Doc |
| `SKILL_QUICK` | "Idea: ...", "Note: ..." | `_handle_skill_quick()` | Quick capture |
| `SKILL_LIST` | "show my skills", "recent ideas" | `_handle_skill_list()` | Lists skills |

---

## Pattern Matching Tips

### 1. Order Matters
Put specific patterns before generic ones:
```python
# CORRECT - specific first
if 'help me think' in text_lower:  # Specific → IDEA_BOUNCE
    return Intent.IDEA_BOUNCE
if 'help' in text_lower:  # Generic → HELP_REQUEST
    return Intent.HELP_REQUEST

# WRONG - generic catches everything
if 'help' in text_lower:
    return Intent.HELP_REQUEST  # This catches "help me think" too!
```

### 2. Use Exclusions
Prevent false positives:
```python
if 'draft' in text_lower and 'email' in text_lower:
    if 'todo' not in text_lower:  # Make sure it's not a todo
        return Intent.EMAIL_DRAFT
```

### 3. Prefix Matching
For structured input:
```python
if text_lower.startswith(('idea:', 'note:', 'task:')):
    return Intent.SKILL_QUICK
```

### 4. Multiple Conditions
For precision:
```python
if any(word in text_lower for word in ['add', 'create', 'new']) and \
   any(word in text_lower for word in ['todo', 'task', 'reminder']):
    return Intent.TODO_ADD
```

---

## Testing Your Changes

### Quick Test in Python
```python
from conversation_manager import ConversationManager, Intent

cm = ConversationManager()
intent = cm.classify_intent("your test message here")
print(f"Intent: {intent}")
```

### Full Test via Telegram
1. Restart the bot: `python mode4_processor.py`
2. Send your trigger message
3. Check logs for: `Classified intent: your_intent_name`

---

## Adding to the Help Message

Update `_generate_help_message()` to include your new skill:

```python
def _generate_help_message(self) -> str:
    return """I can help you with:

<b>Email Management</b>
• Draft emails - "draft email to Jason about the invoice"

<b>Your New Category</b>
• Your feature - "trigger phrase example"
...
"""
```

---

## Common Patterns

### Skill That Calls an External Service
```python
async def _handle_weather(self, text: str, user_id: int, chat_id: int):
    # Extract city from text
    city = text.replace('weather in', '').strip()

    # Call external API (you'd add a weather_client.py)
    from weather_client import get_weather
    weather = get_weather(city)

    response = f"Weather in {city}: {weather['temp']}, {weather['condition']}"
    await self.telegram.send_response(chat_id, response)
    return {'handled': True, 'routed_to': 'weather'}
```

### Skill That Uses LLM
```python
async def _handle_summarize(self, text: str, user_id: int, chat_id: int):
    from ollama_client import OllamaClient

    ollama = OllamaClient()
    content = text.replace('summarize', '').strip()

    summary = ollama.generate(f"Summarize this: {content}")

    await self.telegram.send_response(chat_id, summary)
    return {'handled': True, 'routed_to': 'summarizer'}
```

### Skill That Saves to Database
```python
async def _handle_bookmark(self, text: str, user_id: int, chat_id: int):
    from db_manager import DatabaseManager

    db = DatabaseManager()
    url = text.replace('bookmark', '').strip()

    # You'd add a bookmarks table to db_manager.py
    db.add_bookmark(user_id, url)

    await self.telegram.send_response(chat_id, f"Bookmarked: {url}")
    return {'handled': True, 'routed_to': 'bookmark'}
```

---

## Checklist

Before deploying your new skill:

- [ ] Intent enum added
- [ ] Trigger phrases added (specific before generic)
- [ ] Route handler added
- [ ] Handler method implemented
- [ ] Error handling included
- [ ] Help message updated
- [ ] Tested via Telegram

---

## Need More Help?

Look at these files for reference:
- `conversation_manager.py` - All routing logic
- `skill_manager.py` - Example of a complete skill
- `todo_manager.py` - Example of database operations
- `idea_bouncer.py` - Example of multi-turn conversation
