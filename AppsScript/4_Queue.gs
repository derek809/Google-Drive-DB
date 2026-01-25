/**
 * 4_QUEUE.GS - Queue Operations
 * ==============================
 *
 * Handles:
 * - Populating queue from Gmail
 * - Adding manual tasks
 * - Archiving completed items
 */

// ============================================
// EMAIL POPULATION
// ============================================

/**
 * Populate queue from [MCP] labeled emails
 */
function populateQueueFromEmails() {
  var ui = SpreadsheetApp.getUi();

  try {
    var sheet = getMainSheet();
    var existingIds = getExistingEmailIds(sheet);

    // Get Gmail label
    var label = GmailApp.getUserLabelByName(MCP_CONFIG.GMAIL_LABEL);
    if (!label) {
      ui.alert(
        'Error',
        'Gmail label [' + MCP_CONFIG.GMAIL_LABEL + '] not found.\n\nRun Setup first.',
        ui.ButtonSet.OK
      );
      return;
    }

    var threads = label.getThreads();
    Logger.log('Found ' + threads.length + ' threads with [' + MCP_CONFIG.GMAIL_LABEL + '] label');

    var newRows = [];
    var cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - MCP_CONFIG.SEARCH_DAYS);

    threads.forEach(function(thread) {
      var messages = thread.getMessages();
      var firstMessage = messages[0];
      var messageId = firstMessage.getId();
      var messageDate = firstMessage.getDate();
      var subject = firstMessage.getSubject();
      var sender = firstMessage.getFrom();

      // Skip if already in queue
      if (existingIds.has(messageId)) {
        Logger.log('Skipping (already in queue): ' + subject);
        return;
      }

      // Skip if too old
      if (messageDate < cutoffDate) {
        Logger.log('Skipping (too old): ' + subject);
        return;
      }

      // Learn the contact
      var senderEmail = extractEmail(sender);
      var senderName = extractName(sender);
      learnContact(senderEmail, senderName, 'external');

      newRows.push([
        MCP_CONFIG.SOURCE.EMAIL,
        subject,
        '',      // Prompt - user fills in
        false,   // Use Gemini?
        false,   // Ready?
        MCP_CONFIG.STATUS.PENDING,
        messageId,
        new Date()
      ]);

      Logger.log('Added: ' + subject);
    });

    if (newRows.length > 0) {
      var lastRow = findLastQueueRow(sheet);
      sheet.getRange(lastRow + 1, 1, newRows.length, 8).setValues(newRows);

      ui.alert(
        'Queue Updated',
        'Added ' + newRows.length + ' email(s) to queue.\n\n' +
        'Next steps:\n' +
        '1. Fill in Prompt column (C)\n' +
        '2. Check "Gemini?" if data needed (D)\n' +
        '3. Check "Ready?" to process (E)',
        ui.ButtonSet.OK
      );
    } else {
      ui.alert(
        'No New Emails',
        'No new [' + MCP_CONFIG.GMAIL_LABEL + '] labeled emails found.\n\n' +
        'Make sure you have labeled emails in Gmail.',
        ui.ButtonSet.OK
      );
    }

  } catch (error) {
    Logger.log('Error populating queue: ' + error);
    ui.alert('Error', 'Failed to populate queue:\n\n' + error.message, ui.ButtonSet.OK);
  }
}

/**
 * Get existing email IDs from queue to avoid duplicates
 */
function getExistingEmailIds(sheet) {
  var existingIds = new Set();
  var lastRow = findLastQueueRow(sheet);

  if (lastRow > 1) {
    var idColumn = sheet.getRange(2, 7, lastRow - 1, 1).getValues();
    idColumn.forEach(function(row) {
      if (row[0]) existingIds.add(row[0]);
    });
  }

  // Also check history
  try {
    var historySheet = getHistorySheet();
    var historyLastRow = historySheet.getLastRow();
    if (historyLastRow > 1) {
      var historyIds = historySheet.getRange(2, 7, historyLastRow - 1, 1).getValues();
      historyIds.forEach(function(row) {
        if (row[0]) existingIds.add(row[0]);
      });
    }
  } catch (e) {
    // History sheet might not exist yet
  }

  return existingIds;
}

// ============================================
// MANUAL TASK ENTRY
// ============================================

/**
 * Add a manual task to the queue
 */
function addManualTask() {
  var ui = SpreadsheetApp.getUi();

  // Get task description
  var taskResponse = ui.prompt(
    'Add Manual Task',
    'Enter task description:',
    ui.ButtonSet.OK_CANCEL
  );

  if (taskResponse.getSelectedButton() !== ui.Button.OK) return;

  var task = taskResponse.getResponseText().trim();
  if (!task) {
    ui.alert('Error', 'Task description cannot be empty.', ui.ButtonSet.OK);
    return;
  }

  // Get prompt/instruction
  var promptResponse = ui.prompt(
    'Add Instructions',
    'What should Claude do? (optional - can fill in later):',
    ui.ButtonSet.OK_CANCEL
  );

  if (promptResponse.getSelectedButton() !== ui.Button.OK) return;

  var prompt = promptResponse.getResponseText().trim();

  // Ask about Gemini
  var geminiResponse = ui.alert(
    'Use Gemini?',
    'Will this task need Gemini to fetch data from Drive/Sheets?',
    ui.ButtonSet.YES_NO
  );

  var useGemini = (geminiResponse === ui.Button.YES);

  // Add to sheet
  var sheet = getMainSheet();
  var lastRow = findLastQueueRow(sheet);

  var newRow = [
    MCP_CONFIG.SOURCE.MANUAL,
    task,
    prompt,
    useGemini,
    false,  // Ready?
    MCP_CONFIG.STATUS.PENDING,
    '',     // No email ID
    new Date()
  ];

  sheet.getRange(lastRow + 1, 1, 1, 8).setValues([newRow]);

  ui.alert(
    'Task Added',
    'Manual task added to queue at row ' + (lastRow + 1) + '.\n\n' +
    'When ready, check the "Ready?" box to process.',
    ui.ButtonSet.OK
  );

  Logger.log('Added manual task: ' + task);
}

// ============================================
// ARCHIVE FUNCTIONS
// ============================================

/**
 * Archive completed items to History sheet
 */
function archiveCompletedItems() {
  var ui = SpreadsheetApp.getUi();

  try {
    var mainSheet = getMainSheet();
    var historySheet = getHistorySheet();

    var lastRow = findLastQueueRow(mainSheet);
    if (lastRow <= 1) {
      ui.alert('Nothing to Archive', 'Queue is empty.', ui.ButtonSet.OK);
      return;
    }

    // Find completed items
    var data = mainSheet.getRange(2, 1, lastRow - 1, 8).getValues();
    var rowsToArchive = [];
    var rowsToDelete = [];

    data.forEach(function(row, index) {
      if (row[MCP_CONFIG.COL.STATUS] === MCP_CONFIG.STATUS.DONE) {
        rowsToArchive.push(row);
        rowsToDelete.push(index + 2); // +2 for header and 0-index
      }
    });

    if (rowsToArchive.length === 0) {
      ui.alert('Nothing to Archive', 'No completed items found in queue.', ui.ButtonSet.OK);
      return;
    }

    // Confirm
    var response = ui.alert(
      'Archive Completed Items?',
      'Found ' + rowsToArchive.length + ' completed item(s).\n\n' +
      'This will:\n' +
      '- Move them to History sheet\n' +
      '- Remove them from Queue\n\n' +
      'Continue?',
      ui.ButtonSet.YES_NO
    );

    if (response !== ui.Button.YES) return;

    // Copy to history
    var historyLastRow = historySheet.getLastRow();
    historySheet.getRange(historyLastRow + 1, 1, rowsToArchive.length, 8).setValues(rowsToArchive);

    // Delete from queue (reverse order to preserve row numbers)
    rowsToDelete.reverse().forEach(function(rowNum) {
      mainSheet.deleteRow(rowNum);
    });

    ui.alert(
      'Archive Complete',
      'Moved ' + rowsToArchive.length + ' item(s) to History.',
      ui.ButtonSet.OK
    );

    Logger.log('Archived ' + rowsToArchive.length + ' items');

  } catch (error) {
    Logger.log('Archive error: ' + error);
    ui.alert('Error', 'Archive failed:\n\n' + error.message, ui.ButtonSet.OK);
  }
}

/**
 * Update Gmail labels after processing
 * @param {string} messageId - Gmail message ID
 */
function updateGmailLabels(messageId) {
  try {
    if (!messageId) return;

    var message = GmailApp.getMessageById(messageId);
    if (!message) return;

    var thread = message.getThread();

    // Remove MCP label
    var mcpLabel = GmailApp.getUserLabelByName(MCP_CONFIG.GMAIL_LABEL);
    if (mcpLabel) {
      thread.removeLabel(mcpLabel);
    }

    // Add Done label
    var doneLabel = GmailApp.getUserLabelByName(MCP_CONFIG.DONE_LABEL);
    if (doneLabel) {
      thread.addLabel(doneLabel);
    }

    Logger.log('Updated Gmail labels for message: ' + messageId);

  } catch (e) {
    Logger.log('Error updating Gmail labels: ' + e);
  }
}

/**
 * Get email body from Gmail by message ID
 * @param {string} messageId - Gmail message ID
 * @returns {Object} Email data with body
 */
function getEmailFromGmail(messageId) {
  try {
    if (!messageId) return null;

    var message = GmailApp.getMessageById(messageId);
    if (!message) return null;

    return {
      subject: message.getSubject(),
      body: message.getPlainBody(),
      sender: message.getFrom(),
      senderEmail: extractEmail(message.getFrom()),
      senderName: extractName(message.getFrom()),
      date: message.getDate(),
      messageId: messageId
    };

  } catch (e) {
    Logger.log('Error getting email from Gmail: ' + e);
    return null;
  }
}
