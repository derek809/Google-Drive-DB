-- Database Migration for New Features
-- Adds tables for ProactiveEngine workspace tracking
-- Run this after upgrading to the new features

-- ============================================================================
-- WORKSPACE ITEMS TABLE
-- ============================================================================
-- Track workspace items (emails being tracked for proactive suggestions)
CREATE TABLE IF NOT EXISTS workspace_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,               -- Gmail thread ID
    subject TEXT NOT NULL,                  -- Email subject
    from_name TEXT NOT NULL,                -- Sender name
    from_email TEXT NOT NULL,               -- Sender email
    received_at TEXT NOT NULL,              -- When email was received
    last_gmail_activity TEXT,               -- Last activity timestamp in Gmail
    urgency TEXT DEFAULT 'normal',          -- urgent, normal, low
    status TEXT DEFAULT 'active',           -- active, completed, archived
    days_old INTEGER DEFAULT 0,             -- Days since received
    related_draft_id TEXT,                  -- Associated draft ID if created
    last_bot_suggestion TEXT,               -- When bot last suggested action
    suggestion_count INTEGER DEFAULT 0,     -- Number of suggestions made
    chat_id INTEGER,                        -- Telegram chat ID for notifications
    added_to_workspace TEXT DEFAULT CURRENT_TIMESTAMP,  -- When added to workspace

    -- Indexes for performance
    UNIQUE(thread_id)
);

CREATE INDEX IF NOT EXISTS idx_workspace_status ON workspace_items(status);
CREATE INDEX IF NOT EXISTS idx_workspace_urgency ON workspace_items(urgency);
CREATE INDEX IF NOT EXISTS idx_workspace_days_old ON workspace_items(days_old);


-- ============================================================================
-- SUGGESTION LOG TABLE
-- ============================================================================
-- Track suggestions made by ProactiveEngine
CREATE TABLE IF NOT EXISTS suggestion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_item_id INTEGER NOT NULL,    -- Reference to workspace_items
    suggestion_type TEXT NOT NULL,          -- follow_up, urgent_eod, draft_unsent, new_reply, etc.
    suggested_at TEXT DEFAULT CURRENT_TIMESTAMP,  -- When suggestion was sent
    user_action TEXT,                       -- accepted, dismissed, ignored

    FOREIGN KEY (workspace_item_id) REFERENCES workspace_items(id)
);

CREATE INDEX IF NOT EXISTS idx_suggestion_workspace ON suggestion_log(workspace_item_id);
CREATE INDEX IF NOT EXISTS idx_suggestion_type ON suggestion_log(suggestion_type);
CREATE INDEX IF NOT EXISTS idx_suggestion_date ON suggestion_log(suggested_at);


-- ============================================================================
-- MIGRATION INFO
-- ============================================================================
-- Track migrations applied
CREATE TABLE IF NOT EXISTS db_migrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration_name TEXT NOT NULL,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Record this migration
INSERT INTO db_migrations (migration_name) VALUES ('add_proactive_engine_tables');
