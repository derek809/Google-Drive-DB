-- MCP Email Processing System - Learning-First Database Schema
-- Version 2.0 - Starts with MINIMAL bootstrap, learns from use
-- Created: January 22, 2026
-- 
-- PHILOSOPHY: 
-- - Start with only proven patterns from 97-email analysis
-- - Start with templates Derek explicitly requested
-- - Everything else starts EMPTY and learns from actual use
-- - Recent examples weighted higher than old ones

-- ====================
-- CORE WORKFLOW TABLES
-- ====================

CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_thread_id TEXT UNIQUE NOT NULL,
    subject TEXT,
    participants TEXT,  -- JSON array of email addresses
    status TEXT CHECK(status IN ('queue', 'processing', 'resolved', 'needs_review', 'error')) DEFAULT 'queue',
    priority TEXT CHECK(priority IN ('high', 'normal', 'low')) DEFAULT 'normal',
    needs_escalation INTEGER DEFAULT 0,
    mcp_prompt TEXT,  -- Derek's instruction
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,
    gmail_message_id TEXT UNIQUE NOT NULL,
    sender_email TEXT NOT NULL,
    sender_name TEXT,
    body TEXT,
    attachments TEXT,  -- JSON array of attachment metadata
    received_at TIMESTAMP NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES threads(id)
);

CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,
    template_id TEXT,
    model_used TEXT CHECK(model_used IN ('Claude', 'Gemini', 'Claude_Project')) DEFAULT 'Claude',
    draft_text TEXT,
    confidence_score REAL,
    user_edited INTEGER DEFAULT 0,
    edit_percentage REAL,  -- How much Derek changed
    sent INTEGER DEFAULT 0,
    final_text TEXT,  -- What Derek actually sent (for learning)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,
    FOREIGN KEY (thread_id) REFERENCES threads(id),
    FOREIGN KEY (template_id) REFERENCES templates(template_id)
);

-- ====================
-- BOOTSTRAP PATTERN TABLES
-- (START WITH DAY 1 DATA - proven patterns only)
-- ====================

CREATE TABLE IF NOT EXISTS pattern_hints (
    pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_name TEXT UNIQUE NOT NULL,
    keywords TEXT,  -- JSON array: ["invoice", "fees", "mgmt"]
    trigger_subjects TEXT,  -- JSON array
    confidence_boost INTEGER DEFAULT 0,
    usage_count INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS templates (
    template_id TEXT PRIMARY KEY,
    template_name TEXT NOT NULL,
    template_body TEXT NOT NULL,
    variables TEXT,  -- JSON array: ["name", "amount"]
    attachments TEXT,  -- JSON array: ["OldCity_W9.pdf"]
    usage_count INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP
);

CREATE TABLE IF NOT EXISTS existing_tools (
    tool_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT NOT NULL,
    tool_type TEXT,  -- 'claude_project', 'script', 'api', 'manual'
    use_case TEXT,
    trigger_condition TEXT,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    notes TEXT
);

-- ====================
-- LEARNING TABLES
-- (START EMPTY - build from Derek's actual usage)
-- ====================

-- Institutional knowledge - learns from Derek's responses
CREATE TABLE IF NOT EXISTS knowledge_base (
    kb_id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    question TEXT,
    answer TEXT,
    source_thread_id INTEGER,  -- Links to thread where this was learned
    confidence REAL DEFAULT 0.5,
    usage_count INTEGER DEFAULT 0,
    times_reinforced INTEGER DEFAULT 1,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_thread_id) REFERENCES threads(id)
);

-- Contact-specific patterns - learns Derek's relationship with each person
CREATE TABLE IF NOT EXISTS contact_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_email TEXT UNIQUE NOT NULL,
    contact_name TEXT,
    relationship_type TEXT,  -- 'rr', 'deal_manager', 'managing_partner', 'compliance_officer'
    preferred_tone TEXT,  -- Learned from Derek's actual emails to them
    response_time_preference TEXT,  -- 'urgent', 'normal', 'low_priority'
    common_topics TEXT,  -- JSON array - learned from email subjects/content
    interaction_count INTEGER DEFAULT 0,
    last_interaction TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Derek's writing patterns - learns his phrases and style
CREATE TABLE IF NOT EXISTS writing_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phrase TEXT NOT NULL,
    context TEXT,  -- When this phrase is typically used
    recipient_type TEXT,  -- Which type of contact this works for
    frequency INTEGER DEFAULT 1,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Discovered patterns - learns new email types organically
CREATE TABLE IF NOT EXISTS learning_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER,
    pattern_type TEXT,  -- 'phrasing', 'decision', 'action_sequence', 'escalation_trigger'
    pattern_text TEXT,
    context TEXT,  -- JSON with situation details
    confidence REAL DEFAULT 0.5,
    times_reinforced INTEGER DEFAULT 1,
    last_reinforced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (thread_id) REFERENCES threads(id)
);

-- Observed actions - learns what Derek does after certain email types
CREATE TABLE IF NOT EXISTS observed_actions (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_pattern TEXT,
    action_taken TEXT,  -- 'created_calendar_event', 'updated_spreadsheet', 'forwarded_to_X'
    action_details TEXT,  -- JSON with specifics
    frequency INTEGER DEFAULT 1,
    last_observed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ====================
-- SAFETY & CONTROL TABLES
-- ====================

-- Safety overrides - hard rules that never change
CREATE TABLE IF NOT EXISTS overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type TEXT,  -- 'sender', 'subject_keyword', 'thread_id'
    rule_value TEXT,
    action TEXT,  -- 'never_draft', 'always_escalate', 'require_high_confidence'
    reason TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Confidence rules - starts minimal, adjusts based on outcomes
CREATE TABLE IF NOT EXISTS confidence_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL,
    condition_type TEXT,  -- 'sender_in_contacts', 'subject_contains', 'body_contains'
    condition_value TEXT,
    score_modifier INTEGER,  -- Positive or negative adjustment
    priority INTEGER DEFAULT 50,
    is_active INTEGER DEFAULT 1,
    times_applied INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ====================
-- DAY 1 BOOTSTRAP DATA
-- (Only proven patterns from 97-email analysis)
-- ====================

-- 7 proven patterns from Derek's actual email volume
INSERT INTO pattern_hints (pattern_name, keywords, confidence_boost, notes) VALUES
('invoice_processing', '["invoice", "fees", "mgmt", "Q3", "Q4", "quarterly"]', 15, '28% of emails - route to Claude Project or Google Script'),
('w9_wiring_request', '["w9", "w-9", "wiring instructions", "wire details"]', 20, 'Use w9_response template'),
('payment_confirmation', '["payment", "wire", "received", "OCS Payment"]', 15, 'Check NetSuite for confirmation'),
('producer_statements', '["producer statements", "producer report"]', 10, 'Weekly Friday task'),
('delegation_eytan', '["insufficient info", "not sure", "need eytan", "loop in eytan"]', 0, 'Use delegation_eytan template'),
('turnaround_expectation', '["how long", "timeline", "when", "deadline"]', 5, 'Use turnaround_time template'),
('journal_entry_reminder', '["JE", "journal entry", "partner compensation"]', 0, 'Knowledge base lookup');

-- 4 templates Derek explicitly requested
INSERT INTO templates (template_id, template_name, template_body, variables, attachments) VALUES
('w9_response', 'W9 & Wiring Instructions', 
'Hi {name},

Here''s our W9 form (attached).

Our wiring instructions:
{wiring_details}

Let me know if you need anything else!

Best,
Derek', 
'["name", "wiring_details"]',
'["OldCity_W9.pdf"]'),

('turnaround_time', 'Turnaround Time Expectation',
'Hi {name},

Our typical turnaround for {request_type} is {timeline}.

I''ll have this back to you by {specific_date}.

Let me know if you need it sooner.

Best,
Derek',
'["name", "request_type", "timeline", "specific_date"]',
'[]'),

('payment_confirmation', 'Payment Received Confirmation',
'Hi {name},

Confirmed - we received payment of ${amount} on {date}.

Thank you!

Best,
Derek',
'["name", "amount", "date"]',
'[]'),

('delegation_eytan', 'Loop in Eytan',
'Hi {name},

Looping in Eytan for his input on this.

Eytan - {context}

Thanks,
Derek',
'["name", "context"]',
'[]');

-- 3 existing automation tools Derek references
INSERT INTO existing_tools (tool_name, tool_type, use_case, trigger_condition, notes) VALUES
('Claude Project - Invoice Generator', 'claude_project', 'Invoice generation from email body text', 'invoice request AND body contains deal details', 'Primary tool for invoices - 14 uses with 95% success'),
('Google Script - Invoice CSV', 'script', 'Invoice generation from CSV attachment', 'invoice request AND CSV attachment present', 'Secondary tool - 11 uses with 90% success'),
('NetSuite Export', 'manual', 'Producer statements weekly report', 'producer statements AND friday', 'Manual trigger weekly - should automate send');

-- Minimal safety rules (compliance requirements)
INSERT INTO overrides (rule_type, rule_value, action, reason) VALUES
('subject_keyword', 'FINRA audit', 'never_draft', 'Compliance risk - human only'),
('subject_keyword', 'SEC', 'always_escalate', 'Regulatory matter - requires review'),
('subject_keyword', 'compliance violation', 'never_draft', 'Legal risk - human only');

-- Minimal confidence rules (will learn more over time)
INSERT INTO confidence_rules (rule_name, condition_type, condition_value, score_modifier, priority) VALUES
('Unknown Sender Penalty', 'sender_not_in_contacts', '1', -20, 100),
('Known Contact Bonus', 'sender_in_contacts', '1', 10, 10);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_threads_status ON threads(status);
CREATE INDEX IF NOT EXISTS idx_threads_gmail_id ON threads(gmail_thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_gmail_id ON messages(gmail_message_id);
CREATE INDEX IF NOT EXISTS idx_responses_thread ON responses(thread_id);
CREATE INDEX IF NOT EXISTS idx_responses_sent ON responses(sent);
CREATE INDEX IF NOT EXISTS idx_contact_patterns_email ON contact_patterns(contact_email);
CREATE INDEX IF NOT EXISTS idx_pattern_hints_name ON pattern_hints(pattern_name);
CREATE INDEX IF NOT EXISTS idx_knowledge_base_topic ON knowledge_base(topic);
CREATE INDEX IF NOT EXISTS idx_writing_patterns_phrase ON writing_patterns(phrase);

-- ====================
-- LEARNING VIEWS
-- (Helpful queries for understanding what's been learned)
-- ====================

-- View: Recent successful responses (for learning)
CREATE VIEW IF NOT EXISTS v_successful_responses AS
SELECT 
    r.id,
    r.thread_id,
    t.subject,
    t.mcp_prompt,
    r.draft_text,
    r.final_text,
    r.edit_percentage,
    r.confidence_score,
    r.created_at,
    r.sent_at
FROM responses r
JOIN threads t ON r.thread_id = t.id
WHERE r.sent = 1 
  AND r.edit_percentage < 20  -- Less than 20% edits = success
ORDER BY r.sent_at DESC;

-- View: Patterns to improve (high edit rates)
CREATE VIEW IF NOT EXISTS v_patterns_needing_work AS
SELECT 
    ph.pattern_name,
    ph.confidence_boost,
    COUNT(r.id) as usage_count,
    AVG(r.edit_percentage) as avg_edit_percentage,
    ph.success_rate
FROM pattern_hints ph
LEFT JOIN threads t ON t.subject LIKE '%' || json_extract(ph.keywords, '$[0]') || '%'
LEFT JOIN responses r ON r.thread_id = t.id AND r.sent = 1
GROUP BY ph.pattern_id
HAVING COUNT(r.id) > 0
ORDER BY avg_edit_percentage DESC;

-- View: Contact interaction summary
CREATE VIEW IF NOT EXISTS v_contact_summary AS
SELECT 
    cp.contact_email,
    cp.contact_name,
    cp.relationship_type,
    cp.interaction_count,
    cp.last_interaction,
    COUNT(DISTINCT t.id) as email_threads,
    AVG(r.edit_percentage) as avg_edit_rate
FROM contact_patterns cp
LEFT JOIN messages m ON m.sender_email = cp.contact_email
LEFT JOIN threads t ON t.id = m.thread_id
LEFT JOIN responses r ON r.thread_id = t.id AND r.sent = 1
GROUP BY cp.id
ORDER BY cp.interaction_count DESC;

-- ====================
-- NOTES ON DATA RETENTION
-- ====================

-- Keep FOREVER (learning data):
--   - pattern_hints (pattern matches)
--   - templates (usage stats)
--   - knowledge_base (institutional knowledge)
--   - contact_patterns (relationship learnings)
--   - writing_patterns (Derek's phrases)
--   - learning_patterns (discovered patterns)

-- Keep 90 DAYS (operational):
--   - threads (email threads being processed)
--   - messages (email content)
--   - responses (drafts and outcomes)
--   - observed_actions (recent action sequences)

-- Keep 30 DAYS (debugging):
--   - Logs would go here if we add logging table

-- Cleanup query (run periodically):
-- DELETE FROM threads WHERE last_updated < datetime('now', '-90 days');
-- DELETE FROM messages WHERE received_at < datetime('now', '-90 days');
-- DELETE FROM responses WHERE created_at < datetime('now', '-90 days');
-- DELETE FROM observed_actions WHERE last_observed < datetime('now', '-90 days');
