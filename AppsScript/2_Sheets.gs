/**
 * 2_SHEETS.GS - Sheet Creation & Setup
 * =====================================
 *
 * Creates and formats all sheets:
 * - MCP (Queue + Patterns combined)
 * - Templates
 * - Contacts
 * - History
 */

// ============================================
// MAIN SETUP
// ============================================

function onOpen() {
  createMenu();
}

function createMenu() {
  SpreadsheetApp.getUi()
    .createMenu('MCP Queue')
    .addItem('Run Setup', 'setupMCP')
    .addSeparator()
    .addItem('Add Manual Task', 'addManualTask')
    .addItem('Populate from Emails', 'populateQueueFromEmails')
    .addSeparator()
    .addItem('Process Ready Items', 'processReadyItems')
    .addItem('Archive Completed', 'archiveCompletedItems')
    .addSeparator()
    .addItem('Show Stats', 'showStats')
    .addSeparator()
    .addSubMenu(SpreadsheetApp.getUi().createMenu('API Keys')
      .addItem('Set Claude API Key', 'setClaudeApiKey')
      .addItem('Set Gemini API Key', 'setGeminiApiKey')
      .addItem('Test Connections', 'testConnections'))
    .addSubMenu(SpreadsheetApp.getUi().createMenu('History')
      .addItem('View History Stats', 'showHistoryStats')
      .addItem('Clean Old History (30+ days)', 'cleanOldHistory'))
    .addToUi();
}

/**
 * One-time setup - creates all sheets and Gmail labels
 */
function setupMCP() {
  var ui = SpreadsheetApp.getUi();

  Logger.log('Starting MCP Setup...');

  // Create Gmail labels
  createGmailLabels();

  // Create sheets
  createMainSheet();
  createTemplatesSheet();
  createContactsSheet();
  createHistorySheet();

  // Refresh menu
  createMenu();

  ui.alert(
    'Setup Complete',
    'MCP system is ready!\n\n' +
    'Created sheets:\n' +
    '  - MCP (Queue + Patterns)\n' +
    '  - Templates\n' +
    '  - Contacts\n' +
    '  - History\n\n' +
    'Next steps:\n' +
    '1. Set API keys from menu\n' +
    '2. Label emails with [MCP] in Gmail\n' +
    '3. Run "Populate from Emails"',
    ui.ButtonSet.OK
  );
}

function createGmailLabels() {
  var labels = [MCP_CONFIG.GMAIL_LABEL, MCP_CONFIG.DONE_LABEL];

  labels.forEach(function(labelName) {
    try {
      var existing = GmailApp.getUserLabelByName(labelName);
      if (!existing) {
        GmailApp.createLabel(labelName);
        Logger.log('Created Gmail label: ' + labelName);
      } else {
        Logger.log('Gmail label exists: ' + labelName);
      }
    } catch (e) {
      Logger.log('Label error: ' + e);
    }
  });
}

// ============================================
// MAIN SHEET (Queue + Patterns)
// ============================================

function createMainSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var existing = ss.getSheetByName(MCP_CONFIG.MAIN_SHEET_NAME);

  if (existing) {
    Logger.log('MCP sheet already exists');
    return existing;
  }

  var sheet = ss.insertSheet(MCP_CONFIG.MAIN_SHEET_NAME);

  // === QUEUE HEADERS (A-H) ===
  var queueHeaders = ['Source', 'Subject/Task', 'Prompt', 'Gemini?', 'Ready?', 'Status', 'Email ID', 'Date Added'];
  sheet.getRange(1, 1, 1, queueHeaders.length).setValues([queueHeaders]);
  sheet.getRange(1, 1, 1, queueHeaders.length)
    .setFontWeight('bold')
    .setBackground(MCP_CONFIG.COLORS.QUEUE_HEADER)
    .setFontColor('#fff')
    .setHorizontalAlignment('center');

  // === SEPARATOR (Column I) ===
  sheet.getRange(1, 9).setValue('|').setBackground('#cccccc').setFontColor('#cccccc');
  sheet.setColumnWidth(9, 20);

  // === PATTERN HEADERS (J-O) ===
  var patternHeaders = ['Pattern Name', 'Keywords', 'Confidence+', 'Usage', 'Success%', 'Notes'];
  sheet.getRange(1, 10, 1, patternHeaders.length).setValues([patternHeaders]);
  sheet.getRange(1, 10, 1, patternHeaders.length)
    .setFontWeight('bold')
    .setBackground(MCP_CONFIG.COLORS.PATTERN_HEADER)
    .setFontColor('#fff')
    .setHorizontalAlignment('center');

  // === PATTERN DATA (J-O, rows 2-8) ===
  var patterns = getBootstrapPatterns();
  sheet.getRange(2, 10, patterns.length, 6).setValues(patterns);

  // === COLUMN WIDTHS ===
  sheet.setColumnWidth(1, 70);   // Source
  sheet.setColumnWidth(2, 280);  // Subject
  sheet.setColumnWidth(3, 350);  // Prompt
  sheet.setColumnWidth(4, 70);   // Gemini?
  sheet.setColumnWidth(5, 60);   // Ready?
  sheet.setColumnWidth(6, 90);   // Status
  sheet.setColumnWidth(7, 100);  // Email ID
  sheet.setColumnWidth(8, 110);  // Date Added
  sheet.setColumnWidth(10, 160); // Pattern Name
  sheet.setColumnWidth(11, 300); // Keywords
  sheet.setColumnWidth(12, 90);  // Confidence+
  sheet.setColumnWidth(13, 60);  // Usage
  sheet.setColumnWidth(14, 70);  // Success%
  sheet.setColumnWidth(15, 280); // Notes

  // === HIDE EMAIL ID COLUMN ===
  sheet.hideColumns(7);

  // === FREEZE HEADER ROW ===
  sheet.setFrozenRows(1);

  // === DATA VALIDATION ===
  addQueueValidation(sheet);

  // === CONDITIONAL FORMATTING ===
  addConditionalFormatting(sheet);

  Logger.log('Created MCP sheet');
  return sheet;
}

function getBootstrapPatterns() {
  return [
    ['invoice_processing', 'invoice, fees, mgmt, Q3, Q4, quarterly', 15, 0, 0, 'Route to Claude Project or Google Script'],
    ['w9_wiring_request', 'w9, w-9, wiring instructions, wire details', 20, 0, 0, 'Use w9_response template'],
    ['payment_confirmation', 'payment, wire, received, OCS Payment', 15, 0, 0, 'Check NetSuite for confirmation'],
    ['producer_statements', 'producer statements, producer report', 10, 0, 0, 'Weekly Friday task'],
    ['delegation_eytan', 'insufficient info, not sure, need eytan, loop in eytan', 0, 0, 0, 'Use delegation_eytan template'],
    ['turnaround_expectation', 'how long, timeline, when, deadline', 5, 0, 0, 'Use turnaround_time template'],
    ['journal_entry_reminder', 'JE, journal entry, partner compensation', 0, 0, 0, 'Knowledge base lookup']
  ];
}

function addQueueValidation(sheet) {
  // Status dropdown (column F)
  var statusRule = SpreadsheetApp.newDataValidation()
    .requireValueInList([
      MCP_CONFIG.STATUS.PENDING,
      MCP_CONFIG.STATUS.PROCESSING,
      MCP_CONFIG.STATUS.DONE,
      MCP_CONFIG.STATUS.ERROR
    ], true)
    .build();
  sheet.getRange(2, 6, 100, 1).setDataValidation(statusRule);

  // Source dropdown (column A)
  var sourceRule = SpreadsheetApp.newDataValidation()
    .requireValueInList([MCP_CONFIG.SOURCE.EMAIL, MCP_CONFIG.SOURCE.MANUAL], true)
    .build();
  sheet.getRange(2, 1, 100, 1).setDataValidation(sourceRule);

  // Checkboxes for Gemini? (D) and Ready? (E)
  sheet.getRange(2, 4, 100, 1).insertCheckboxes();
  sheet.getRange(2, 5, 100, 1).insertCheckboxes();
}

function addConditionalFormatting(sheet) {
  var rules = [];

  // Status colors (Column F)
  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo(MCP_CONFIG.STATUS.PENDING)
      .setBackground(MCP_CONFIG.COLORS.PENDING)
      .setRanges([sheet.getRange('F2:F100')])
      .build()
  );

  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo(MCP_CONFIG.STATUS.PROCESSING)
      .setBackground(MCP_CONFIG.COLORS.PROCESSING)
      .setRanges([sheet.getRange('F2:F100')])
      .build()
  );

  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo(MCP_CONFIG.STATUS.DONE)
      .setBackground(MCP_CONFIG.COLORS.DONE)
      .setRanges([sheet.getRange('F2:F100')])
      .build()
  );

  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo(MCP_CONFIG.STATUS.ERROR)
      .setBackground(MCP_CONFIG.COLORS.ERROR)
      .setRanges([sheet.getRange('F2:F100')])
      .build()
  );

  // Source colors (Column A)
  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo(MCP_CONFIG.SOURCE.EMAIL)
      .setBackground(MCP_CONFIG.COLORS.EMAIL)
      .setRanges([sheet.getRange('A2:A100')])
      .build()
  );

  rules.push(
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo(MCP_CONFIG.SOURCE.MANUAL)
      .setBackground(MCP_CONFIG.COLORS.MANUAL)
      .setRanges([sheet.getRange('A2:A100')])
      .build()
  );

  sheet.setConditionalFormatRules(rules);
}

// ============================================
// TEMPLATES SHEET
// ============================================

function createTemplatesSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var existing = ss.getSheetByName(MCP_CONFIG.TEMPLATES_SHEET_NAME);

  if (existing) {
    Logger.log('Templates sheet exists');
    return existing;
  }

  var sheet = ss.insertSheet(MCP_CONFIG.TEMPLATES_SHEET_NAME);

  // Headers
  var headers = ['Template ID', 'Template Name', 'Template Body', 'Variables', 'Attachments', 'Usage Count'];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length)
    .setFontWeight('bold')
    .setBackground(MCP_CONFIG.COLORS.TEMPLATE_HEADER)
    .setFontColor('#fff');

  // Template data
  var templates = getBootstrapTemplates();
  sheet.getRange(2, 1, templates.length, 6).setValues(templates);

  // Column widths
  sheet.setColumnWidth(1, 150);
  sheet.setColumnWidth(2, 200);
  sheet.setColumnWidth(3, 450);
  sheet.setColumnWidth(4, 200);
  sheet.setColumnWidth(5, 150);
  sheet.setColumnWidth(6, 100);
  sheet.setFrozenRows(1);

  Logger.log('Created Templates sheet');
  return sheet;
}

function getBootstrapTemplates() {
  return [
    ['w9_response', 'W9 & Wiring Instructions',
     'Hi {name},\n\nHere\'s our W9 form (attached).\n\nOur wiring instructions:\n{wiring_details}\n\nLet me know if you need anything else!\n\nBest,\nDerek',
     'name, wiring_details', 'OldCity_W9.pdf', 0],
    ['payment_confirmation', 'Payment Received Confirmation',
     'Hi {name},\n\nConfirmed - we received payment of ${amount} on {date}.\n\nThank you!\n\nBest,\nDerek',
     'name, amount, date', '', 0],
    ['delegation_eytan', 'Loop in Eytan',
     'Hi {name},\n\nLooping in Eytan for his input on this.\n\nEytan - {context}\n\nThanks,\nDerek',
     'name, context', '', 0],
    ['turnaround_time', 'Turnaround Time Expectation',
     'Hi {name},\n\nOur typical turnaround for {request_type} is {timeline}.\n\nI\'ll have this back to you by {specific_date}.\n\nLet me know if you need it sooner.\n\nBest,\nDerek',
     'name, request_type, timeline, specific_date', '', 0]
  ];
}

// ============================================
// CONTACTS SHEET
// ============================================

function createContactsSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var existing = ss.getSheetByName(MCP_CONFIG.CONTACTS_SHEET_NAME);

  if (existing) {
    Logger.log('Contacts sheet exists');
    return existing;
  }

  var sheet = ss.insertSheet(MCP_CONFIG.CONTACTS_SHEET_NAME);

  // Headers
  var headers = ['Email', 'Name', 'Relationship', 'Preferred Tone', 'Common Topics', 'Interactions', 'Last Contact'];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length)
    .setFontWeight('bold')
    .setBackground(MCP_CONFIG.COLORS.CONTACT_HEADER)
    .setFontColor('#fff');

  // Column widths
  sheet.setColumnWidth(1, 250);
  sheet.setColumnWidth(2, 150);
  sheet.setColumnWidth(3, 120);
  sheet.setColumnWidth(4, 120);
  sheet.setColumnWidth(5, 200);
  sheet.setColumnWidth(6, 100);
  sheet.setColumnWidth(7, 140);
  sheet.setFrozenRows(1);

  Logger.log('Created Contacts sheet');
  return sheet;
}

// ============================================
// HISTORY SHEET
// ============================================

function createHistorySheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var existing = ss.getSheetByName(MCP_CONFIG.HISTORY_SHEET_NAME);

  if (existing) {
    Logger.log('History sheet exists');
    return existing;
  }

  var sheet = ss.insertSheet(MCP_CONFIG.HISTORY_SHEET_NAME);

  // Same headers as queue portion
  var headers = ['Source', 'Subject/Task', 'Prompt', 'Gemini?', 'Ready?', 'Status', 'Email ID', 'Date Added'];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length)
    .setFontWeight('bold')
    .setBackground(MCP_CONFIG.COLORS.HISTORY_HEADER)
    .setFontColor('#fff');

  // Column widths (same as queue)
  sheet.setColumnWidth(1, 70);
  sheet.setColumnWidth(2, 280);
  sheet.setColumnWidth(3, 350);
  sheet.setColumnWidth(4, 70);
  sheet.setColumnWidth(5, 60);
  sheet.setColumnWidth(6, 90);
  sheet.setColumnWidth(7, 100);
  sheet.setColumnWidth(8, 110);
  sheet.hideColumns(7);
  sheet.setFrozenRows(1);

  Logger.log('Created History sheet');
  return sheet;
}
