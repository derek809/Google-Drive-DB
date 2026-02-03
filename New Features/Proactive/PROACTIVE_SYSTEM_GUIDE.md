# Proactive System Guide - Alamo Bot Intelligence Layer

## Table of Contents
1. [What is Proactive Mode?](#what-is-proactive-mode)
2. [Why Proactive Matters](#why-proactive-matters)
3. [Architecture Overview](#architecture-overview)
4. [Proactive Triggers](#proactive-triggers)
5. [Integration with Alamo Bot](#integration-with-alamo-bot)
6. [Configuration](#configuration)
7. [Usage Examples](#usage-examples)
8. [Advanced Features](#advanced-features)

---

## What is Proactive Mode?

**Proactive Mode** transforms your bot from a **reactive assistant** (waiting for commands) into an **intelligent partner** that anticipates your needs and suggests actions before you ask.

### Reactive vs. Proactive

| Reactive (Traditional) | Proactive (Intelligent) |
|------------------------|-------------------------|
| Waits for user commands | Monitors context and suggests actions |
| "Tell me when invoice is ready" | "🔔 Mike's invoice is ready - draft it now?" |
| You remember follow-ups | Bot reminds: "Laura hasn't replied in 3 days" |
| Processes when asked | Learns patterns: "You usually process RR onboarding on Mondays" |

**Bottom line**: Proactive Mode means the bot watches your workspace and taps you on the shoulder when something needs attention.

---

## Why Proactive Matters

### For Your Role (Director of Operations)

You manage multiple parallel workflows:
- **RR Onboarding** (1-2 week cycles)
- **Mandate Reviews** (bi-weekly compliance calls)
- **Invoice Generation** (deal-dependent timing)
- **AP Reconciliation** (month-end deadlines)
- **FINRA Compliance** (time-sensitive requests)

**The Problem**: Important items slip through the cracks when you're managing 10+ active tasks.

**The Solution**: Proactive alerts ensure nothing falls through:

```
🔴 URGENT: FINRA document request received 2 days ago
   → Deadline: Tomorrow EOD
   → Action: Pull email archives from Global Relay?

💬 Laura Clarke (RR Onboarding) - no reply in 5 days
   → Last sent: Portal registration link
   → Suggest: Send follow-up check-in?

📊 Pattern Detected: You usually invoice Mike Riskind on Thursdays
   → Ready to draft success fee invoice for ABC Capital deal?
```

### Key Benefits

1. **Never Miss Deadlines**: Urgent items surface automatically
2. **Reduce Mental Load**: Bot remembers what you'd forget
3. **Learn Your Patterns**: Adapts to your workflow habits
4. **Prevent Bottlenecks**: Flags items blocking others
5. **Focus on High-Value Work**: Automate the "what's next?" decision

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    PROACTIVE ENGINE                      │
│                                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────┐│
│  │  TIME-BASED    │  │  EVENT-BASED   │  │  PATTERN   ││
│  │   TRIGGERS     │  │    TRIGGERS    │  │  LEARNING  ││
│  └────────────────┘  └────────────────┘  └────────────┘│
│          ▲                  ▲                   ▲        │
│          └──────────────────┴───────────────────┘        │
│                             │                            │
│                    ┌────────▼────────┐                   │
│                    │  SUGGESTION     │                   │
│                    │    SCORER       │                   │
│                    └────────┬────────┘                   │
│                             │                            │
│                    ┌────────▼────────┐                   │
│                    │  SPAM FILTER    │                   │
│                    │ (Max 1/day/item)│                   │
│                    └────────┬────────┘                   │
└─────────────────────────────┼──────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  TELEGRAM ALERT   │
                    │   "💡 Suggestion"  │
                    └───────────────────┘
```

### Components

1. **Trigger System**: Detects conditions requiring attention
2. **Suggestion Scorer**: Determines if alert is worth sending
3. **Spam Filter**: Prevents overwhelming you with notifications
4. **Telegram Integration**: Delivers actionable suggestions

---

## Proactive Triggers

### 1. Time-Based Triggers

These check **how long** something has been pending:

#### No Reply Follow-up
```python
Condition: Email sent, no reply in 3+ days
Alert: "💬 [Name] hasn't replied in 5 days - send follow-up?"
Use Case: RR onboarding stalls, client ghosting after document request
```

#### End-of-Day Urgent
```python
Condition: Urgent item + late afternoon (3-5pm)
Alert: "⏰ Urgent: [Subject] - tackle before EOD?"
Use Case: FINRA deadline, compliance call prep, critical invoice
```

#### Draft Forgotten
```python
Condition: Draft created but not sent in 2+ days
Alert: "📧 You drafted a reply to [Name] 2 days ago - ready to send?"
Use Case: You write response, get interrupted, forget to send
```

#### Stale Mandate Review
```python
Condition: Mandate in review status for 7+ days
Alert: "📋 Mandate from [RR] pending review for 7 days - schedule compliance call?"
Use Case: Mandate submission sits unreviewed, blocks RR from transacting
```

---

### 2. Event-Based Triggers

These react to **new activity** in your workspace:

#### New Email Reply Received
```python
Condition: Thread you're tracking gets new reply
Alert: "📥 New reply from Laura Clarke on RR Onboarding"
Use Case: Immediate notification when RR responds to your portal setup email
```

#### Deal Closed (Invoice Ready)
```python
Condition: CRM shows deal marked "Closed Won"
Alert: "💰 ABC Capital deal closed - draft success fee invoice?"
Use Case: Mike Riskind's deal closes, you need to invoice within 48 hours
```

#### Mandate Approved
```python
Condition: George approves mandate in compliance call
Alert: "✅ XYZ Fund mandate approved - update Portal and notify RR?"
Use Case: Complete the workflow loop after bi-weekly review
```

#### AP Discrepancy Detected
```python
Condition: Month-end AP Aging doesn't match Balance Sheet
Alert: "🔍 AP discrepancy detected: $5,432 difference - investigate?"
Use Case: Catch accounting errors before month close deadline
```

---

### 3. Pattern-Based Triggers

These **learn your habits** and suggest when it's time for routine tasks:

#### Weekly Invoice Pattern
```python
Learned: You process Mike Riskind invoices every Thursday 9-11am
Alert: "📊 Thursday invoice time - 2 closed deals ready to invoice"
Use Case: Bot learns your workflow rhythm and prompts at optimal time
```

#### Bi-Weekly Compliance Cadence
```python
Learned: Compliance calls with George happen every other Friday 2pm
Alert: "📞 Compliance call tomorrow - 4 mandates ready for review"
Use Case: Prep reminder with actionable data the day before
```

#### Month-End Close Pattern
```python
Learned: You reconcile AP on last business day of month
Alert: "📅 Month-end tomorrow - run AP reconciliation now?"
Use Case: Prevent last-minute scrambling on close day
```

#### RR Onboarding Bottleneck
```python
Learned: RR onboarding averages 10 days; current one at 14 days
Alert: "⚠️ Gennell's onboarding is 4 days behind average - check for blocker?"
Use Case: Detect process delays before they become problems
```

---

## Integration with Alamo Bot

### How Proactive Enhances Alamo Bot

Your existing **Alamo Bot** is a **deterministic decision engine**:
- Classifies intent from user messages
- Validates against refusal conditions
- Executes templated responses

**Proactive Engine** adds the **initiation layer**:
- Bot starts conversations (not just responds)
- Monitors workspace continuously
- Suggests next actions proactively

### Integration Points

```python
# In your alamo_bot.py main():

async def main():
    # Existing: Start reactive message handler
    bot = AlamoBot()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, bot.handle_message))
    
    # NEW: Start proactive background worker
    asyncio.create_task(proactive_worker_loop())
    asyncio.create_task(schedule_morning_digest())
    
    # Run both together
    app.run_polling()
```

### Unified Brain Structure

Add proactive rules to your existing brain structure:

```
brain/operations_assistant/
├── core_directive.txt
├── classification_map.json
├── decision_tree.json
├── response_templates.json
├── refusal_conditions.json
├── confidence_thresholds.json
├── proactive_triggers.json          # NEW
└── pattern_learning.json            # NEW
```

---

## Configuration

### proactive_triggers.json

```json
{
  "time_based": {
    "no_reply_followup": {
      "enabled": true,
      "threshold_days": 3,
      "urgency_boost": 1.5,
      "max_per_week": 2
    },
    "urgent_eod": {
      "enabled": true,
      "start_hour": 15,
      "end_hour": 17,
      "only_weekdays": true
    },
    "draft_forgotten": {
      "enabled": true,
      "threshold_days": 2
    }
  },
  "event_based": {
    "new_reply": {
      "enabled": true,
      "notify_immediately": true
    },
    "deal_closed": {
      "enabled": true,
      "auto_draft_invoice": false
    },
    "mandate_approved": {
      "enabled": true,
      "auto_update_portal": false
    }
  },
  "pattern_based": {
    "enabled": true,
    "min_occurrences": 3,
    "confidence_threshold": 0.7
  }
}
```

### pattern_learning.json

```json
{
  "learned_patterns": [
    {
      "pattern_id": "thursday_invoicing",
      "task_type": "invoice_generation",
      "detected_schedule": {
        "day_of_week": "Thursday",
        "time_range": "09:00-11:00"
      },
      "occurrences": 8,
      "confidence": 0.85,
      "last_occurred": "2026-01-23T09:45:00"
    },
    {
      "pattern_id": "friday_compliance",
      "task_type": "mandate_review",
      "detected_schedule": {
        "day_of_week": "Friday",
        "time_range": "14:00-15:00",
        "frequency": "bi-weekly"
      },
      "occurrences": 12,
      "confidence": 0.92,
      "last_occurred": "2026-01-24T14:00:00"
    }
  ]
}
```

---

## Usage Examples

### Example 1: RR Onboarding Stall

**Scenario**: You sent portal registration link to Gennell 5 days ago. No response.

**Proactive Alert**:
```
💬 Gennell Jefferson (RR Onboarding) hasn't replied in 5 days

Last sent: Portal registration link + credentials
Typical response time: 2 days

Suggested actions:
1. Send follow-up check-in
2. Call directly
3. Mark as "Waiting on RR" (snooze)

Reply: 1, 2, 3, or type custom message
```

**Your Response**: `1`

**Bot Action**:
```
✅ Sending follow-up check-in to Gennell...

📧 Draft created:
Subject: Following up - Portal Registration
Body: Hi Gennell, checking in on the portal registration
I sent last week. Any issues accessing the link?

Reply "send" to send, or edit message
```

---

### Example 2: Invoice Ready

**Scenario**: Mike Riskind marks ABC Capital deal as closed in CRM.

**Proactive Alert**:
```
💰 Deal closed: ABC Capital - Series A Note Raise

Deal Manager: Mike Riskind
Investment Amount: $2,500,000
Fee Rate: 2.0%
Gross Fee: $50,000
Retainer Paid: $10,000
Net Fee Due: $40,000

Draft success fee invoice now?

Reply "yes" to draft, "details" for more info
```

**Your Response**: `yes`

**Bot Action**:
```
✅ Drafting invoice...

Invoice created:
- Invoice #: OCC-2026-0142
- Due date: February 15, 2026
- Supporting docs: Subscription package (attached)

Next steps:
1. Review invoice (Reply "show")
2. Email to Mike for approval (Reply "send")
3. Queue for payment tracking (Reply "track")
```

---

### Example 3: Morning Digest

**Every day at 7:00 AM**:

```
🌅 Good morning! Your MCP workspace:

🔴 URGENT TODAY (2 items):
1. FINRA document request - Delta Securities
   → Deadline: Today 5pm
   → Action: Pull email archives from Global Relay

2. Month-end AP reconciliation
   → Due: Today (January 31)
   → Discrepancy detected: $5,432 difference

🟡 NEEDS ATTENTION (5 items):
3. Laura Clarke - RR onboarding (5 days old)
4. Mandate review - XYZ Fund (George pending)
5. Invoice approval - ABC Capital (Mike)
   ... and 2 more

🟢 LOW PRIORITY (3 items)

Reply with number or tell me what you need!
```

---

### Example 4: Pattern Learning

**After 3+ weeks of data**:

```
📊 Pattern detected!

I've noticed you process RR onboarding tasks in batches
on Monday mornings (9-11am).

Occurrences: 5/5 past Mondays
Confidence: 95%

Current queue:
- Gennell Jefferson (Portal setup)
- Chris Daquiz (U4 filing)

It's Monday 9:15am - tackle these now?

Reply "yes" to batch process, "no" to learn differently
```

---

## Advanced Features

### 1. Smart Spam Prevention

**Problem**: Too many alerts = alert fatigue = you ignore them all.

**Solution**: Multi-layer filtering:

```python
def should_send_suggestion(item, suggestion_type):
    # Layer 1: Max 1 suggestion per item per day
    if suggested_today(item):
        return False
    
    # Layer 2: Respect urgency hierarchy
    if urgency_level(item) < urgency_threshold(suggestion_type):
        return False
    
    # Layer 3: User feedback learning
    if user_dismissed_similar_recently(suggestion_type):
        return False
    
    # Layer 4: Context awareness
    if user_on_vacation() or outside_work_hours():
        return False
    
    return True
```

### 2. Confidence Scoring

Not all suggestions are created equal:

```python
confidence_score = (
    0.4 * time_urgency +      # How overdue is it?
    0.3 * pattern_match +     # Does it fit learned pattern?
    0.2 * business_impact +   # High-value task?
    0.1 * user_acceptance     # Historical acceptance rate
)

if confidence_score > 0.75:
    send_suggestion(item)
elif confidence_score > 0.50:
    queue_for_morning_digest(item)
else:
    log_for_pattern_learning(item)
```

### 3. User Preference Learning

Track how you respond to suggestions:

```python
suggestion_log:
- suggested: "Follow up with Laura"
  user_action: "accepted" ✅
  outcome: "Email sent, RR replied same day"

- suggested: "Invoice Mike (Thursday pattern)"
  user_action: "dismissed" ❌
  reason: "Mike already invoiced separately"

Learning:
→ Increase weight for follow-up suggestions (high acceptance)
→ Decrease weight for Thursday invoice pattern (false positive)
```

### 4. Dependency Chains

Understand task relationships:

```
Task: Draft Invoice
  ↓ (depends on)
Deal Closed in CRM
  ↓ (depends on)
Subscription Package Received
  ↓ (depends on)
Mandate Approved
```

**Proactive Alert**:
```
⚠️ Cannot draft invoice for ABC Capital yet

Blocker: Mandate approval pending
Status: Scheduled for Friday compliance call (tomorrow)

Auto-draft invoice after approval? Reply "yes" to queue
```

---

## Implementation Checklist

### Phase 1: Core Proactive Engine (Week 1)
- [x] `proactive_engine.py` - Main worker loop
- [ ] Database schema for suggestion logging
- [ ] Telegram integration for alerts
- [ ] Basic time-based triggers (no reply, urgent EOD)

### Phase 2: Alamo Bot Integration (Week 2)
- [ ] Add proactive rules to brain structure
- [ ] Integrate with `workspace_manager.py`
- [ ] Test reactive + proactive working together
- [ ] Morning digest functionality

### Phase 3: Pattern Learning (Week 3-4)
- [ ] Track task completion timestamps
- [ ] Pattern detection algorithm
- [ ] Confidence scoring for patterns
- [ ] User feedback loop

### Phase 4: Advanced Features (Month 2)
- [ ] Dependency chain detection
- [ ] Smart spam prevention
- [ ] User preference learning
- [ ] Performance analytics dashboard

---

## Measuring Success

### Key Metrics

1. **Suggestion Acceptance Rate**: % of suggestions you act on
   - Target: >60% acceptance = good signal-to-noise
   - <40% = need better filtering

2. **Time Saved per Week**: Hours recovered from proactive reminders
   - Track: "How many hours would you have spent checking email/CRM manually?"
   - Target: 5+ hours/week

3. **Items Caught Before Deadline**: Urgent items flagged proactively
   - Track: Alerts sent >24 hours before deadline
   - Target: 90%+ caught early

4. **False Positive Rate**: Suggestions that weren't useful
   - Track: Dismissed or ignored suggestions
   - Target: <20%

### Analytics Dashboard (Future)

```
📊 Proactive Engine Performance - Last 30 Days

Suggestions Sent: 142
Accepted: 89 (62.7%) ✅
Dismissed: 31 (21.8%)
Ignored: 22 (15.5%)

Top Performing Triggers:
1. No Reply Follow-up - 78% acceptance
2. Invoice Ready - 92% acceptance
3. Urgent EOD - 45% acceptance

Pattern Learning:
- 4 new patterns detected
- 2 patterns validated (>80% confidence)
- 1 pattern invalidated (user feedback)

Estimated Time Saved: 6.5 hours/week
```

---

## Troubleshooting

### "Too many notifications!"

**Fix**: Adjust thresholds in `proactive_triggers.json`:
```json
{
  "time_based": {
    "no_reply_followup": {
      "threshold_days": 5  // Increase from 3 to 5
    }
  }
}
```

### "Missing important alerts!"

**Fix**: Lower confidence threshold:
```json
{
  "confidence_threshold": 0.6  // Decrease from 0.75
}
```

### "Alerts at wrong times"

**Fix**: Set quiet hours:
```json
{
  "quiet_hours": {
    "enabled": true,
    "weekdays": "19:00-07:00",
    "weekends": "all_day"
  }
}
```

---

## Next Steps

1. **Read `proactive_engine.py`** - Understand existing implementation
2. **Configure triggers** - Customize for your workflow
3. **Test with Alamo Bot** - Run integrated system
4. **Monitor for 1 week** - Track acceptance rates
5. **Tune thresholds** - Optimize signal-to-noise ratio
6. **Enable pattern learning** - Let AI adapt to you

---

## Conclusion

**Proactive Mode** is what transforms your assistant from a tool you use into a partner that watches your back.

The goal isn't to automate everything—it's to ensure **nothing important slips through the cracks** while you focus on high-value work.

Start simple (time-based triggers), then grow into pattern learning as the system proves its value.

**Remember**: Good proactive AI feels like having a great executive assistant—anticipates needs, knows when to interrupt, learns your preferences, and earns your trust over time.
