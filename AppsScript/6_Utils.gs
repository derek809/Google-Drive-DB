/**
 * 6_UTILS.GS - Statistics & Utilities
 * =====================================
 *
 * Handles:
 * - Stats display
 * - History management
 * - Testing functions
 */

// ============================================
// STATISTICS
// ============================================

/**
 * Show queue and system statistics
 */
function showStats() {
  var ui = SpreadsheetApp.getUi();

  try {
    var sheet = getMainSheet();
    var lastRow = findLastQueueRow(sheet);
    var queueCount = Math.max(0, lastRow - 1);

    // Count by status and source
    var stats = {
      pending: 0,
      processing: 0,
      done: 0,
      error: 0,
      email: 0,
      manual: 0,
      withGemini: 0,
      ready: 0
    };

    if (queueCount > 0) {
      var data = sheet.getRange(2, 1, queueCount, 8).getValues();

      data.forEach(function(row) {
        var status = (row[MCP_CONFIG.COL.STATUS] || '').toLowerCase();
        var source = row[MCP_CONFIG.COL.SOURCE];
        var useGemini = row[MCP_CONFIG.COL.USE_GEMINI];
        var ready = row[MCP_CONFIG.COL.READY];

        if (stats.hasOwnProperty(status)) stats[status]++;
        if (source === MCP_CONFIG.SOURCE.EMAIL) stats.email++;
        if (source === MCP_CONFIG.SOURCE.MANUAL) stats.manual++;
        if (useGemini) stats.withGemini++;
        if (ready) stats.ready++;
      });
    }

    // Get pattern stats
    var patterns = getPatternsFromSheet();
    var totalPatternUsage = 0;
    patterns.forEach(function(p) {
      totalPatternUsage += p.usage_count || 0;
    });

    // Get contact count
    var contactSheet = getContactsSheet();
    var contactCount = contactSheet ? Math.max(0, contactSheet.getLastRow() - 1) : 0;

    // Get template count
    var templates = getTemplatesFromSheet();
    var totalTemplateUsage = 0;
    templates.forEach(function(t) {
      totalTemplateUsage += t.usage_count || 0;
    });

    // Build message
    var message = '=== MCP QUEUE STATS ===\n\n';

    message += 'QUEUE (' + queueCount + ' items)\n';
    message += '  Email: ' + stats.email + '\n';
    message += '  Manual: ' + stats.manual + '\n';
    message += '  With Gemini: ' + stats.withGemini + '\n';
    message += '  Ready to process: ' + stats.ready + '\n\n';

    message += 'STATUS\n';
    message += '  Pending: ' + stats.pending + '\n';
    message += '  Processing: ' + stats.processing + '\n';
    message += '  Done: ' + stats.done + '\n';
    message += '  Error: ' + stats.error + '\n\n';

    message += 'LEARNING DATA\n';
    message += '  Patterns: ' + patterns.length + ' (used ' + totalPatternUsage + 'x)\n';
    message += '  Templates: ' + templates.length + ' (used ' + totalTemplateUsage + 'x)\n';
    message += '  Contacts learned: ' + contactCount + '\n\n';

    message += 'API KEYS\n';
    message += '  Claude: ' + (hasClaudeApiKey() ? 'Set' : 'NOT SET') + '\n';
    message += '  Gemini: ' + (hasGeminiApiKey() ? 'Set' : 'NOT SET');

    ui.alert('MCP Stats', message, ui.ButtonSet.OK);

  } catch (e) {
    ui.alert('Error', 'Failed to get stats: ' + e.message, ui.ButtonSet.OK);
  }
}

/**
 * Show history statistics
 */
function showHistoryStats() {
  var ui = SpreadsheetApp.getUi();

  try {
    var sheet = getHistorySheet();
    var lastRow = sheet.getLastRow();

    if (lastRow <= 1) {
      ui.alert('History Stats', 'History is empty.', ui.ButtonSet.OK);
      return;
    }

    var count = lastRow - 1;
    var data = sheet.getRange(2, 1, count, 8).getValues();

    var stats = {
      email: 0,
      manual: 0,
      last7days: 0,
      last30days: 0,
      readyToClean: 0
    };

    var now = new Date();

    data.forEach(function(row) {
      var source = row[MCP_CONFIG.COL.SOURCE];
      var dateAdded = new Date(row[MCP_CONFIG.COL.DATE_ADDED]);
      var daysSince = (now - dateAdded) / (1000 * 60 * 60 * 24);

      if (source === MCP_CONFIG.SOURCE.EMAIL) stats.email++;
      if (source === MCP_CONFIG.SOURCE.MANUAL) stats.manual++;
      if (daysSince <= 7) stats.last7days++;
      if (daysSince <= 30) stats.last30days++;
      if (daysSince > MCP_CONFIG.HISTORY_RETENTION) stats.readyToClean++;
    });

    var message = '=== HISTORY STATS ===\n\n';
    message += 'Total archived: ' + count + '\n\n';
    message += 'BY SOURCE\n';
    message += '  Email: ' + stats.email + '\n';
    message += '  Manual: ' + stats.manual + '\n\n';
    message += 'BY AGE\n';
    message += '  Last 7 days: ' + stats.last7days + '\n';
    message += '  Last 30 days: ' + stats.last30days + '\n';
    message += '  Older than 30 days: ' + stats.readyToClean;

    ui.alert('History Stats', message, ui.ButtonSet.OK);

  } catch (e) {
    ui.alert('Error', 'Failed to get history stats: ' + e.message, ui.ButtonSet.OK);
  }
}

/**
 * Clean old items from history (30+ days)
 */
function cleanOldHistory() {
  var ui = SpreadsheetApp.getUi();

  try {
    var sheet = getHistorySheet();
    var lastRow = sheet.getLastRow();

    if (lastRow <= 1) {
      ui.alert('Nothing to Clean', 'History is empty.', ui.ButtonSet.OK);
      return;
    }

    var data = sheet.getRange(2, 1, lastRow - 1, 8).getValues();
    var rowsToDelete = [];
    var now = new Date();

    data.forEach(function(row, index) {
      var dateAdded = new Date(row[MCP_CONFIG.COL.DATE_ADDED]);
      var daysSince = (now - dateAdded) / (1000 * 60 * 60 * 24);

      if (daysSince > MCP_CONFIG.HISTORY_RETENTION) {
        rowsToDelete.push(index + 2);
      }
    });

    if (rowsToDelete.length === 0) {
      ui.alert(
        'Nothing to Clean',
        'No items older than ' + MCP_CONFIG.HISTORY_RETENTION + ' days.',
        ui.ButtonSet.OK
      );
      return;
    }

    var response = ui.alert(
      'Clean Old History?',
      'Found ' + rowsToDelete.length + ' item(s) older than 30 days.\n\n' +
      'This will permanently delete them.\n\nContinue?',
      ui.ButtonSet.YES_NO
    );

    if (response !== ui.Button.YES) return;

    // Delete in reverse order
    rowsToDelete.reverse().forEach(function(rowNum) {
      sheet.deleteRow(rowNum);
    });

    ui.alert(
      'Cleanup Complete',
      'Deleted ' + rowsToDelete.length + ' old item(s) from History.',
      ui.ButtonSet.OK
    );

    Logger.log('Cleaned ' + rowsToDelete.length + ' old items from history');

  } catch (e) {
    ui.alert('Error', 'Cleanup failed: ' + e.message, ui.ButtonSet.OK);
  }
}

// ============================================
// TESTING FUNCTIONS
// ============================================

/**
 * Test pattern matching
 */
function testPatternMatch() {
  var testCases = [
    { subject: 'W9 and wiring instructions needed', body: 'Please send your W9', expected: 'w9_wiring_request' },
    { subject: 'Invoice for Q3 fees', body: 'Attached is the invoice', expected: 'invoice_processing' },
    { subject: 'Payment received', body: 'Wire received today', expected: 'payment_confirmation' },
    { subject: 'When can we expect this?', body: 'What is the timeline?', expected: 'turnaround_expectation' }
  ];

  var results = [];

  testCases.forEach(function(test) {
    var match = matchEmailToPattern({ subject: test.subject, body: test.body }, '');
    var passed = match && match.pattern_name === test.expected;

    results.push({
      subject: test.subject,
      expected: test.expected,
      got: match ? match.pattern_name : 'none',
      passed: passed
    });
  });

  Logger.log('=== Pattern Match Test Results ===');
  results.forEach(function(r) {
    Logger.log((r.passed ? 'PASS' : 'FAIL') + ': "' + r.subject + '" -> ' + r.got + ' (expected: ' + r.expected + ')');
  });

  var passCount = results.filter(function(r) { return r.passed; }).length;
  Logger.log('Passed: ' + passCount + '/' + results.length);

  SpreadsheetApp.getUi().alert(
    'Pattern Test Results',
    'Passed: ' + passCount + '/' + results.length + '\n\nCheck Logs for details.',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

/**
 * Test learning functions
 */
function testLearning() {
  // Test contact learning
  learnContact('test@example.com', 'Test Person', 'vendor');
  Logger.log('Added test contact');

  // Test pattern usage update
  updatePatternUsage('w9_wiring_request');
  Logger.log('Updated pattern usage');

  // Test template usage update
  updateTemplateUsage('w9_response');
  Logger.log('Updated template usage');

  SpreadsheetApp.getUi().alert(
    'Learning Test',
    'Test complete. Check:\n' +
    '- Contacts sheet for test@example.com\n' +
    '- Patterns (col M) for w9_wiring_request usage\n' +
    '- Templates (col F) for w9_response usage',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

/**
 * Test Claude API connection
 */
function testClaudeAPI() {
  var ui = SpreadsheetApp.getUi();

  if (!hasClaudeApiKey()) {
    ui.alert('Error', 'Claude API key not set.', ui.ButtonSet.OK);
    return;
  }

  try {
    var result = processWithClaude(
      { subject: 'Test', body: 'This is a test email.' },
      'Reply with "Claude API working" and nothing else.',
      null,
      null,
      50
    );

    ui.alert('Claude API Test', 'Response:\n\n' + result.output, ui.ButtonSet.OK);

  } catch (e) {
    ui.alert('Error', 'Claude API test failed:\n\n' + e.message, ui.ButtonSet.OK);
  }
}

/**
 * Test Gemini API connection
 */
function testGeminiAPI() {
  var ui = SpreadsheetApp.getUi();

  if (!hasGeminiApiKey()) {
    ui.alert('Error', 'Gemini API key not set.', ui.ButtonSet.OK);
    return;
  }

  try {
    var result = callGeminiForData(
      'Return a simple JSON object with message: "Gemini API working"',
      { subject: 'Test' }
    );

    ui.alert('Gemini API Test', 'Response:\n\n' + JSON.stringify(result, null, 2), ui.ButtonSet.OK);

  } catch (e) {
    ui.alert('Error', 'Gemini API test failed:\n\n' + e.message, ui.ButtonSet.OK);
  }
}

/**
 * Debug: Show all patterns
 */
function debugShowPatterns() {
  var patterns = getPatternsFromSheet();

  Logger.log('=== All Patterns ===');
  patterns.forEach(function(p) {
    Logger.log(p.pattern_name + ': ' + p.keywords.join(', ') + ' (+' + p.confidence_boost + ')');
  });

  SpreadsheetApp.getUi().alert(
    'Patterns Loaded',
    'Found ' + patterns.length + ' patterns.\n\nCheck Logs for details.',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

/**
 * Debug: Show all templates
 */
function debugShowTemplates() {
  var templates = getTemplatesFromSheet();

  Logger.log('=== All Templates ===');
  templates.forEach(function(t) {
    Logger.log(t.template_id + ': ' + t.template_name + ' (used ' + t.usage_count + 'x)');
  });

  SpreadsheetApp.getUi().alert(
    'Templates Loaded',
    'Found ' + templates.length + ' templates.\n\nCheck Logs for details.',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}
