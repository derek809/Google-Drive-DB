/**
 * 1_CONFIG.GS - Configuration & Constants
 * ========================================
 *
 * This file must be loaded first (hence the "1_" prefix).
 * Contains all configuration values and helper functions.
 *
 * SHEET STRUCTURE:
 * - "MCP" sheet: Queue (cols A-H) + Patterns (cols J-O)
 * - "Templates" sheet: Email templates
 * - "Contacts" sheet: Learned contacts
 * - "History" sheet: Archived items
 */

// ============================================
// MAIN CONFIGURATION
// ============================================

var MCP_CONFIG = {
  // Sheet names
  MAIN_SHEET_NAME: 'MCP',           // Queue + Patterns combined
  TEMPLATES_SHEET_NAME: 'Templates',
  CONTACTS_SHEET_NAME: 'Contacts',
  HISTORY_SHEET_NAME: 'History',

  // Gmail labels
  GMAIL_LABEL: 'MCP',
  DONE_LABEL: 'MCP-Done',

  // Settings
  SEARCH_DAYS: 7,
  HISTORY_RETENTION: 30,
  GEMINI_MODEL: 'gemini-2.0-flash-exp',
  CLAUDE_MODEL: 'claude-sonnet-4-20250514',

  // Queue columns (A-H) - 0-based index
  COL: {
    SOURCE: 0,      // A
    SUBJECT: 1,     // B
    PROMPT: 2,      // C
    USE_GEMINI: 3,  // D
    READY: 4,       // E
    STATUS: 5,      // F
    EMAIL_ID: 6,    // G (hidden)
    DATE_ADDED: 7   // H
  },

  // Pattern columns (J-O) - column numbers
  PATTERN_COL: {
    START: 10,      // Column J (1-based)
    NAME: 10,       // J
    KEYWORDS: 11,   // K
    CONFIDENCE: 12, // L
    USAGE: 13,      // M
    SUCCESS: 14,    // N
    NOTES: 15       // O
  },

  // Status values
  STATUS: {
    PENDING: 'Pending',
    PROCESSING: 'Processing',
    DONE: 'Done',
    ERROR: 'Error'
  },

  // Source values
  SOURCE: {
    EMAIL: 'Email',
    MANUAL: 'Manual'
  },

  // Colors for conditional formatting
  COLORS: {
    PENDING: '#fff3cd',      // Yellow
    PROCESSING: '#cce5ff',   // Blue
    DONE: '#d4edda',         // Green
    ERROR: '#f8d7da',        // Red
    EMAIL: '#e3f2fd',        // Light blue
    MANUAL: '#f3e5f5',       // Light purple
    PATTERN_HEADER: '#4285f4',
    QUEUE_HEADER: '#34a853',
    TEMPLATE_HEADER: '#34a853',
    CONTACT_HEADER: '#ea4335',
    HISTORY_HEADER: '#6c757d'
  }
};

// ============================================
// SHEET GETTERS
// ============================================

function getMainSheet() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(MCP_CONFIG.MAIN_SHEET_NAME);
  if (!sheet) throw new Error('MCP sheet not found. Run Setup first.');
  return sheet;
}

function getTemplatesSheet() {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(MCP_CONFIG.TEMPLATES_SHEET_NAME);
}

function getContactsSheet() {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(MCP_CONFIG.CONTACTS_SHEET_NAME);
}

function getHistorySheet() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(MCP_CONFIG.HISTORY_SHEET_NAME);
  if (!sheet) throw new Error('History sheet not found. Run Setup first.');
  return sheet;
}

// ============================================
// API KEY MANAGEMENT
// ============================================

function hasClaudeApiKey() {
  return !!PropertiesService.getScriptProperties().getProperty('CLAUDE_API_KEY');
}

function getClaudeApiKey() {
  return PropertiesService.getScriptProperties().getProperty('CLAUDE_API_KEY');
}

function hasGeminiApiKey() {
  return !!PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
}

function getGeminiApiKey() {
  return PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY');
}

function setClaudeApiKey() {
  var ui = SpreadsheetApp.getUi();
  var response = ui.prompt(
    'Set Claude API Key',
    'Enter your Claude API key (starts with sk-ant-):',
    ui.ButtonSet.OK_CANCEL
  );

  if (response.getSelectedButton() === ui.Button.OK) {
    var key = response.getResponseText().trim();
    if (key) {
      PropertiesService.getScriptProperties().setProperty('CLAUDE_API_KEY', key);
      ui.alert('Success', 'Claude API key saved!', ui.ButtonSet.OK);
    }
  }
}

function setGeminiApiKey() {
  var ui = SpreadsheetApp.getUi();
  var response = ui.prompt(
    'Set Gemini API Key',
    'Enter your Gemini API key (starts with AIza):',
    ui.ButtonSet.OK_CANCEL
  );

  if (response.getSelectedButton() === ui.Button.OK) {
    var key = response.getResponseText().trim();
    if (key) {
      PropertiesService.getScriptProperties().setProperty('GEMINI_API_KEY', key);
      ui.alert('Success', 'Gemini API key saved!', ui.ButtonSet.OK);
    }
  }
}

function testConnections() {
  var ui = SpreadsheetApp.getUi();
  var results = [];

  results.push('API KEY STATUS:');
  results.push('');

  if (hasClaudeApiKey()) {
    var key = getClaudeApiKey();
    results.push('Claude: Set (' + key.substring(0, 10) + '...)');
  } else {
    results.push('Claude: NOT SET');
  }

  if (hasGeminiApiKey()) {
    var key = getGeminiApiKey();
    results.push('Gemini: Set (' + key.substring(0, 10) + '...)');
  } else {
    results.push('Gemini: NOT SET');
  }

  ui.alert('Connection Status', results.join('\n'), ui.ButtonSet.OK);
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

function extractEmail(fromString) {
  var match = fromString.match(/<([^>]+)>/);
  return match ? match[1] : fromString;
}

function extractName(fromString) {
  var match = fromString.match(/^([^<]+)/);
  return match ? match[1].trim().replace(/"/g, '') : '';
}

function findLastQueueRow(sheet) {
  // Queue is in columns A-H, find last row with data in column A
  var data = sheet.getRange(2, 1, 200, 1).getValues();
  for (var i = 0; i < data.length; i++) {
    if (!data[i][0]) return i + 1; // Return row number (1-based)
  }
  return data.length + 1;
}
