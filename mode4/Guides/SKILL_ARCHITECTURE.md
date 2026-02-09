# Mode4 Skill Architecture Guide

## How Skills (Intents) Work

The system routes user messages through **intent classification** in `conversation_manager.py`.

```
User Message
     ↓
┌─────────────────────────────────┐
│   classify_intent()             │
│   (Pattern matching + LLM)      │
└─────────────────────────────────┘
     ↓
Intent (EMAIL_DRAFT, TODO_ADD, etc.)
     ↓
┌─────────────────────────────────┐
│   route_to_capability()         │
│   (Sends to handler)            │
└─────────────────────────────────┘
     ↓
Response to user
```

---

## Email Draft Flow (Detailed Example)

### Step 1: User sends message
```
"draft email to Jason about the invoice"
```

### Step 2: Intent Classification (`classify_intent()` line ~151)

The function checks patterns **in order** (first match wins):

```python
# Line ~241-245 - Email detection
if 'draft' in text_lower or 'write' in text_lower or 'compose' in text_lower:
    if 'email' in text_lower or '@' in text or 'to ' in text_lower:
        if 'todo' not in text_lower and 'task' not in text_lower:
            return Intent.EMAIL_DRAFT
```

**Result**: `Intent.EMAIL_DRAFT`

### Step 3: Routing (`route_to_capability()` line ~346)

```python
# Line ~391-387
elif intent in [Intent.EMAIL_DRAFT, Intent.EMAIL_SEARCH]:
    return {
        'handled': False,  # Let email processor handle it
        'routed_to': 'email_processor',
        'reason': intent.value
    }
```

**Result**: Message goes to `mode4_processor.py`

### Step 4: Email Processing (`mode4_processor.py`)

1. `process_message()` receives the parsed message
2. Searches Gmail for matching emails
3. Shows LLM selection buttons: [Ollama] [Kimi K2] [Claude]
4. User clicks a button
5. Selected LLM generates draft
6. Draft saved to Gmail

---

## How to Add/Modify a Skill

### 1. Define the Intent (if new)

In `conversation_manager.py` around line 26:

```python
class Intent(Enum):
    # ... existing intents ...
    MY_NEW_SKILL = "my_skill"  # Add your new intent
```

### 2. Add Detection Pattern

In `classify_intent()` - **ORDER MATTERS!**

```python
# Add BEFORE less specific patterns
# Example: Add "quick note" skill
if any(phrase in text_lower for phrase in ['quick note', 'jot down', 'note to self']):
    return Intent.MY_NEW_SKILL
```

### 3. Add Route Handler

In `route_to_capability()`:

```python
elif intent == Intent.MY_NEW_SKILL:
    return await self._handle_my_new_skill(text, user_id, chat_id)
```

### 4. Create Handler Method

```python
async def _handle_my_new_skill(self, text: str, user_id: int, chat_id: int) -> Dict[str, Any]:
    """Handle my new skill."""
    try:
        # Your logic here
        response = "Skill executed!"
        await self.telegram.send_response(chat_id, response)
        return {'handled': True, 'routed_to': 'my_new_skill'}
    except Exception as e:
        await self.telegram.send_response(chat_id, f"Error: {str(e)}")
        return {'handled': True, 'error': str(e)}
```

---

## Current Skills Reference

| Intent | Trigger Phrases | Handler |
|--------|-----------------|---------|
| `GREETING` | hi, hello, hey, morning | `_generate_greeting()` |
| `HELP_REQUEST` | help, what can you do | `_generate_help_message()` |
| `CASUAL_CHAT` | how are you, thanks, ok | `_generate_casual_response()` |
| `EMAIL_DRAFT` | draft email, write email to | → `email_processor` |
| `EMAIL_SEARCH` | find email, search email | → `email_processor` |
| `TODO_ADD` | add task, add to todo | `_handle_todo_add()` |
| `TODO_LIST` | show todos, my tasks | `_handle_todo_list()` |
| `INFO_DIGEST` | morning brief, digest | `_handle_digest()` |
| `INFO_STATUS` | status | → `command_handler` |
| `IDEA_BOUNCE` | help me think, brainstorm | `_handle_idea_bounce()` |
| `COMMAND` | /anything | → `command_handler` |
| `UNCLEAR` | (fallback) | `_generate_unclear_response()` |

---

## Pattern Matching Tips

1. **Order matters** - Put specific patterns before generic ones
   - "help me think" must come BEFORE "help"

2. **Use `in` for contains, `startswith` for begins with**
   ```python
   if 'draft' in text_lower:  # Contains "draft"
   if text_lower.startswith('hi'):  # Starts with "hi"
   ```

3. **Combine conditions for precision**
   ```python
   if 'draft' in text_lower and 'email' in text_lower:
   ```

4. **Exclude false positives**
   ```python
   if 'todo' not in text_lower:  # Make sure it's not a todo
   ```

---

## Testing Your Changes

Quick test in Python:
```python
from conversation_manager import ConversationManager, Intent

cm = ConversationManager()
intent = cm.classify_intent("your test message here")
print(f"Intent: {intent}")
```
