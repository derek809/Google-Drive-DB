# MCP Workspace Integration Guide

**Goal**: Add the MCP Workspace System to your existing Mode4 bot.

This guide assumes you already have:
- ✅ Mode4 bot running (`mode4_processor.py`)
- ✅ Gmail integration working
- ✅ Telegram handler working
- ✅ Database manager (SQLite)

---

## Step 1: Setup Gmail Labels (2 minutes)

### Create Labels in Gmail
1. Go to Gmail
2. Create label: **`mcp`** (all lowercase)
3. Create label: **`mcp done`** (all lowercase, with space)

### Test Labels
Label 2-3 test emails with "mcp" to test sync later.

---

## Step 2: Install New Modules (5 minutes)

### Copy Files
Copy these 3 new files to your `~/mode4/` directory:

```bash
cd ~/mode4

# Copy the modules
cp /path/to/workspace_manager.py .
cp /path/to/proactive_engine.py .
cp /path/to/conversation_memory.py .
```

### Initialize Database
Run once to create workspace tables:

```bash
python3 -c "from workspace_manager import init_workspace_db; init_workspace_db()"
```

Expected output:
```
✅ Workspace database initialized
```

---

## Step 3: Update Telegram Handler (30 minutes)

### Add Imports
At top of `telegram_handler.py`:

```python
from workspace_manager import (
    get_workspace_items,
    get_workspace_item_by_id,
    mark_workspace_done,
    update_workspace_item,
    format_workspace_summary,
    sync_workspace_with_gmail,
)
from conversation_memory import memory
```

### Add New Commands

#### `/workspace` - Show Active Items
```python
async def workspace_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show current workspace items.
    
    Usage:
        /workspace          → all items
        /workspace urgent   → only urgent
        /workspace jason    → filter by name
    """
    args = context.args
    
    # Parse filters
    urgency = None
    keyword = None
    
    if args:
        if args[0].lower() in ['urgent', 'normal', 'low']:
            urgency = args[0].lower()
        else:
            keyword = ' '.join(args)
    
    # Get items
    items = get_workspace_items(urgency=urgency, keyword=keyword)
    
    if not items:
        await update.message.reply_text("✅ Your workspace is empty!")
        return
    
    # Format and send
    summary = format_workspace_summary(items)
    await update.message.reply_text(summary)

# Register command
application.add_handler(CommandHandler("workspace", workspace_command))
```

#### `/done` - Mark Item Complete
```python
async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Mark workspace item as done.
    
    Usage:
        /done 3     → mark item #3 done
        /done       → mark last mentioned item done (uses memory)
    """
    user_id = update.effective_user.id
    args = context.args
    
    item_id = None
    
    if args:
        # /done 3
        try:
            item_id = int(args[0])
        except ValueError:
            await update.message.reply_text("Usage: /done <item_number>")
            return
    else:
        # /done (use memory)
        ctx = memory.recall(user_id)
        if ctx and ctx.last_workspace_item_id:
            item_id = ctx.last_workspace_item_id
        else:
            await update.message.reply_text(
                "Which item? Use: /done <number>\n"
                "Or mention an item first, then say /done"
            )
            return
    
    # Get item
    item = get_workspace_item_by_id(item_id)
    if not item:
        await update.message.reply_text(f"Item #{item_id} not found")
        return
    
    # Mark done
    success = mark_workspace_done(
        item['gmail_thread_id'],
        reason="user_marked_done"
    )
    
    if success:
        await update.message.reply_text(
            f"✅ Done: {item['subject']}\n"
            f"Moved to 'mcp done' label"
        )
    else:
        await update.message.reply_text(f"❌ Failed to mark done")

# Register command
application.add_handler(CommandHandler("done", done_command))
```

#### `/sync` - Force Gmail Sync
```python
async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force workspace sync with Gmail (don't wait 15 min)."""
    await update.message.reply_text("🔄 Syncing with Gmail...")
    
    stats = sync_workspace_with_gmail()
    
    await update.message.reply_text(
        f"✅ Sync complete:\n"
        f"Added: {stats['added']}\n"
        f"Removed: {stats['removed']}\n"
        f"Updated: {stats['updated']}\n"
        f"Total: {stats['total']}"
    )

# Register command
application.add_handler(CommandHandler("sync", sync_command))
```

### Update Message Handler - Add Memory

In your existing `handle_message()` function, add memory tracking:

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # 1. Check if message references context (NEW)
    reference = memory.resolve_reference(user_id, message_text)
    
    if reference:
        if reference['type'] == 'draft_send':
            # User said "send it"
            await send_draft(reference['id'], update, context)
            return
        
        elif reference['type'] == 'draft_edit':
            # User said "make it shorter"
            await revise_draft(reference['id'], reference['instruction'], update, context)
            return
        
        elif reference['type'] == 'workspace_done':
            # User said "mark done"
            await done_command(update, context)
            return
    
    # 2. Otherwise, parse as new request (EXISTING CODE)
    parsed = parse_message_smart(message_text)
    
    # ... rest of your existing message handling ...
    
    # 3. After creating draft, remember it (NEW)
    if draft_created:
        memory.remember(
            user_id,
            last_draft_id=draft_id,
            last_workspace_item_id=workspace_item_id,
            last_action="drafted_email"
        )
```

### Update Draft Approval - Remember Context

In your `draft_approved()` callback:

```python
async def draft_approved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... existing send logic ...
    
    # After sending, update memory (NEW)
    user_id = update.effective_user.id
    memory.remember(
        user_id,
        last_action="sent_email",
        last_workspace_item_id=workspace_item_id
    )
    
    # Ask if should mark done
    await query.message.reply_text(
        "✅ Email sent!\n\n"
        "Mark this workspace item as done? Reply 'yes' or 'done'"
    )
```

---

## Step 4: Start Background Workers (10 minutes)

### Option A: Separate Process (Recommended)

Run proactive engine in separate terminal/screen:

```bash
# Terminal 1: Main bot
python3 mode4_processor.py

# Terminal 2: Proactive engine
python3 proactive_engine.py
```

### Option B: Integrated (Single Process)

In `mode4_processor.py`, add at startup:

```python
import asyncio
from proactive_engine import proactive_worker_loop, schedule_morning_digest

async def main():
    # Start bot
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # ... add handlers ...
    
    # Start background workers (NEW)
    asyncio.create_task(proactive_worker_loop())
    asyncio.create_task(schedule_morning_digest())
    
    # Start polling
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
```

---

## Step 5: Configure Proactive Settings (5 minutes)

### Edit `proactive_engine.py`

Customize these settings at top of file:

```python
# How often to check workspace (default: 2 hours)
CHECK_INTERVAL = 2 * 60 * 60  # seconds

# Max suggestions per item per day
MAX_SUGGESTIONS_PER_DAY = 1

# Follow-up threshold (default: 3 days)
NO_REPLY_DAYS_THRESHOLD = 3

# Morning digest time (edit in schedule_morning_digest)
target = now.replace(hour=7, minute=0, second=0)  # 7am
```

---

## Step 6: Test Everything (15 minutes)

### Test 1: Workspace Sync
```
1. Label 2-3 emails "mcp" in Gmail
2. In Telegram: /sync
3. Verify bot replies with "Added: 3"
4. In Telegram: /workspace
5. Verify items show up
```

### Test 2: Mark Done
```
1. In Telegram: /done 1
2. Check Gmail - email should have "mcp done" label
3. In Telegram: /workspace
4. Verify item #1 is gone
```

### Test 3: Conversational Memory
```
1. Send: "draft invoice to jason"
2. Bot creates draft
3. Send: "make it shorter"
4. Bot revises SAME draft (not asking "which draft?")
5. Send: "send it"
6. Bot sends the draft
```

### Test 4: Proactive Alerts (Wait 15 min)
```
1. Leave an email in workspace for 3+ days (or manually set timestamp)
2. Wait for next proactive check (or restart worker)
3. Verify bot suggests: "Follow up with X?"
```

### Test 5: Morning Digest (Optional - wait until 7am)
```
1. Wait until 7am tomorrow
2. Verify bot sends summary
3. Or manually trigger: await send_morning_digest()
```

---

## Step 7: Monitor & Debug (Ongoing)

### Check Logs

```bash
# Main bot logs
tail -f mode4.log

# Proactive engine logs
tail -f proactive.log
```

### Common Issues

**"mcp label not found"**
- Make sure label exists in Gmail
- Check exact spelling: "mcp" (lowercase)

**"Context expired - can't resolve 'it'"**
- Memory TTL is 10 min
- User needs to be more active in conversation
- Or increase TTL in `conversation_memory.py`

**"Proactive suggestions too frequent"**
- Increase `MAX_SUGGESTIONS_PER_DAY`
- Or increase `CHECK_INTERVAL`

**"Morning digest not sending"**
- Check timezone in `schedule_morning_digest()`
- Verify worker is running (not crashed)

### Database Queries (Debug)

```bash
sqlite3 ~/mode4/data/mode4.db

# Check workspace items
SELECT id, subject, from_name, status, urgency FROM workspace_items;

# Check memory
SELECT user_id, last_draft_id, last_action, expires_at FROM conversation_memory;

# Check suggestions
SELECT workspace_item_id, suggestion_type, suggested_at FROM suggestion_log 
ORDER BY suggested_at DESC LIMIT 10;
```

---

## Step 8: Customize for Your Workflow (Optional)

### Add Custom Proactive Rules

Edit `proactive_engine.py` → `run_all_checks()`:

```python
async def run_all_checks():
    items = get_workspace_items(status='active')
    
    for item in items:
        if should_skip_suggestion(item):
            continue
        
        # Time-based
        await check_no_reply_followup(item)
        await check_urgent_eod(item)
        
        # Event-based
        await check_draft_unsent(item)
        
        # YOUR CUSTOM RULES (add here)
        await check_thursday_invoice_pattern(item)
        await check_compliance_call_prep(item)
```

Example custom rule:

```python
async def check_thursday_invoice_pattern(item: Dict):
    """Your habit: invoice Jason on Thursdays."""
    day = datetime.now().strftime('%A')
    hour = datetime.now().hour
    
    if day == 'Thursday' and 9 <= hour <= 11:
        if 'jason' in item['from_name'].lower():
            if 'invoice' in item['subject'].lower():
                await suggest(
                    item,
                    'pattern_thursday_invoice',
                    f"📊 Thursday invoice time!\n"
                    f"Jason's invoice from {item['days_old']} days ago - draft it now?"
                )
```

### Customize Morning Digest

Edit `proactive_engine.py` → `send_morning_digest()`:

```python
async def send_morning_digest():
    items = get_workspace_items(status='active')
    
    # YOUR custom grouping logic
    compliance = [i for i in items if 'compliance' in i['subject'].lower()]
    invoices = [i for i in items if 'invoice' in i['subject'].lower()]
    mandates = [i for i in items if 'mandate' in i['subject'].lower()]
    
    lines = ["🌅 Good morning Derek!\n"]
    
    if compliance:
        lines.append("⚖️ COMPLIANCE:")
        for item in compliance:
            lines.append(f"• {item['subject']}")
        lines.append("")
    
    # ... etc
```

---

## Quick Reference: New Commands

```
/workspace              Show all active items
/workspace urgent       Show only urgent items
/workspace jason        Filter by keyword

/done 3                 Mark item #3 done
/done                   Mark last mentioned item done

/sync                   Force Gmail sync now

/urgency 2 high         Set item #2 to urgent
/snooze 3 friday        Hide item #3 until Friday
/note 1 waiting on X    Add note to item #1
```

---

## Architecture Diagram

```
┌─────────────────────────┐
│   GMAIL ("mcp" label)   │
│   Your 5-10 emails      │
└───────────┬─────────────┘
            │
            ↓ (every 15 min)
┌─────────────────────────┐
│  workspace_manager.py   │
│  - Syncs labels         │
│  - Detects new activity │
│  - Stores in DB         │
└───────────┬─────────────┘
            │
            ↓
┌─────────────────────────┐
│  mode4.db (SQLite)      │
│  - workspace_items      │
│  - conversation_memory  │
│  - suggestion_log       │
└───────────┬─────────────┘
            │
            ├───────────────────────┐
            │                       │
            ↓                       ↓
┌─────────────────────┐   ┌──────────────────────┐
│  proactive_engine   │   │  telegram_handler    │
│  (background)       │   │  (user commands)     │
│  - Checks triggers  │   │  - /workspace        │
│  - Sends alerts     │   │  - /done             │
│  - Morning digest   │   │  - Natural language  │
└─────────┬───────────┘   └──────────┬───────────┘
          │                          │
          └──────────┬───────────────┘
                     │
                     ↓
          ┌──────────────────────┐
          │  conversation_memory │
          │  - Tracks context    │
          │  - Resolves "it"     │
          │  - 10 min TTL        │
          └──────────────────────┘
                     │
                     ↓
          ┌──────────────────────┐
          │      TELEGRAM        │
          │      (you)           │
          └──────────────────────┘
```

---

## Success Metrics

After 1 week, you should notice:

- ✅ Checking Gmail less (bot tells you what matters)
- ✅ Faster response to important emails (3-day alerts work)
- ✅ Nothing falls through cracks (workspace shows everything)
- ✅ Natural conversation flow (memory makes it smooth)
- ✅ Proactive feels helpful, not annoying (tuned right)

---

## Next Steps

Once this is working well:

1. **Add pattern learning** (Week 2-4 of data)
2. **Customize urgency detection** for your domain
3. **Add more custom rules** for your workflow
4. **Integrate with existing Mode4 features** (tasks, templates, etc.)

---

## Support

If stuck:
1. Check logs (`tail -f mode4.log`)
2. Test each component individually
3. Review this guide's troubleshooting section
4. Check database directly (`sqlite3 mode4.db`)

🚀 **You're ready to go! Start with Step 1.**
