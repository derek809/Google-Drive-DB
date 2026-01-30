/**
 * 5_PROCESSING.GS - AI Processing (Claude & Gemini)
 * ==================================================
 *
 * Handles:
 * - Processing queue items
 * - Claude API calls
 * - Gemini API calls (for data fetching)
 * - Confidence calculation
 */

// ============================================
// MAIN PROCESSING
// ============================================

/**
 * Process all ready items in the queue
 */
function processReadyItems() {
  var ui = SpreadsheetApp.getUi();

  // Check API key
  if (!hasClaudeApiKey()) {
    ui.alert(
      'API Key Required',
      'Claude API key not set.\n\nSet it from menu: MCP Queue > API Keys > Set Claude API Key',
      ui.ButtonSet.OK
    );
    return;
  }

  var sheet = getMainSheet();
  var lastRow = findLastQueueRow(sheet);

  if (lastRow <= 1) {
    ui.alert('Empty Queue', 'No items in queue to process.', ui.ButtonSet.OK);
    return;
  }

  var data = sheet.getRange(2, 1, lastRow - 1, 8).getValues();
  var processed = 0;
  var errors = 0;
  var results = [];

  data.forEach(function(row, index) {
    var rowNum = index + 2;
    var ready = row[MCP_CONFIG.COL.READY];
    var status = row[MCP_CONFIG.COL.STATUS];

    if (ready && status === MCP_CONFIG.STATUS.PENDING) {
      Logger.log('Processing row ' + rowNum + ': ' + row[MCP_CONFIG.COL.SUBJECT]);

      // Mark as processing
      sheet.getRange(rowNum, MCP_CONFIG.COL.STATUS + 1).setValue(MCP_CONFIG.STATUS.PROCESSING);
      SpreadsheetApp.flush();

      try {
        // Get email data
        var emailId = row[MCP_CONFIG.COL.EMAIL_ID];
        var emailData = emailId ? getEmailFromGmail(emailId) : {
          subject: row[MCP_CONFIG.COL.SUBJECT],
          body: '',
          sender: '',
          senderEmail: ''
        };

        if (!emailData) {
          emailData = {
            subject: row[MCP_CONFIG.COL.SUBJECT],
            body: '',
            sender: ''
          };
        }

        var instruction = row[MCP_CONFIG.COL.PROMPT];
        var useGemini = row[MCP_CONFIG.COL.USE_GEMINI];

        // Match pattern
        var patternMatch = matchEmailToPattern(emailData, instruction);
        if (patternMatch) {
          updatePatternUsage(patternMatch.pattern_name);
        }

        // Get Gemini data if needed
        var geminiData = null;
        if (useGemini && hasGeminiApiKey()) {
          geminiData = callGeminiForData(instruction, emailData);
        }

        // Calculate confidence
        var confidence = calculateConfidence(emailData, patternMatch, geminiData);

        // Process with Claude
        var result = processWithClaude(emailData, instruction, patternMatch, geminiData, confidence);

        // Store result in prompt cell note (will be updated with draft info below)
        var noteContent = 'RESULT:\n' + result.output + '\n\n' +
          'Confidence: ' + result.confidence + '%\n' +
          'Pattern: ' + (patternMatch ? patternMatch.pattern_name : 'none');

        // Create Gmail draft if this is an email item
        var draftInfo = null;
        if (emailId && emailData.senderEmail) {
          draftInfo = createGmailDraft(emailId, emailData, result.output);
          if (draftInfo && draftInfo.success) {
            Logger.log('Created Gmail draft: ' + draftInfo.draftId);
            noteContent += '\n\nDraft URL: ' + draftInfo.draftUrl;
          } else if (draftInfo && draftInfo.error) {
            noteContent += '\n\nDraft creation failed: ' + draftInfo.error;
          }
        }

        // Now set the note with all info
        sheet.getRange(rowNum, MCP_CONFIG.COL.PROMPT + 1).setNote(noteContent);

        // Update Gmail labels if email
        if (emailId) {
          updateGmailLabels(emailId);
        }

        // Mark as done
        sheet.getRange(rowNum, MCP_CONFIG.COL.STATUS + 1).setValue(MCP_CONFIG.STATUS.DONE);
        processed++;

        results.push({
          row: rowNum,
          subject: emailData.subject,
          confidence: result.confidence,
          pattern: patternMatch ? patternMatch.pattern_name : 'none',
          draftCreated: draftInfo ? draftInfo.success : false,
          draftUrl: draftInfo ? draftInfo.draftUrl : null
        });

      } catch (error) {
        Logger.log('Error processing row ' + rowNum + ': ' + error);
        sheet.getRange(rowNum, MCP_CONFIG.COL.STATUS + 1).setValue(MCP_CONFIG.STATUS.ERROR);
        sheet.getRange(rowNum, MCP_CONFIG.COL.PROMPT + 1).setNote('ERROR: ' + error.message);
        errors++;
      }

      // Rate limiting
      Utilities.sleep(1500);
    }
  });

  // Show results
  if (processed > 0 || errors > 0) {
    var message = 'Processing Complete\n\n';
    message += 'Processed: ' + processed + '\n';
    message += 'Errors: ' + errors + '\n\n';

    if (results.length > 0) {
      message += 'Results:\n';
      results.forEach(function(r) {
        var draftStatus = r.draftCreated ? ' [Draft created]' : '';
        message += '- Row ' + r.row + ': ' + r.confidence + '% (' + r.pattern + ')' + draftStatus + '\n';
      });
    }

    message += '\nDrafts created in Gmail Drafts folder.\nCheck cell notes (right-click Prompt cells) for full output.';

    ui.alert('Done', message, ui.ButtonSet.OK);
  } else {
    ui.alert(
      'No Ready Items',
      'No items with "Ready?" checked and Pending status.\n\n' +
      'Check the Ready? checkbox for items you want to process.',
      ui.ButtonSet.OK
    );
  }
}

// ============================================
// CLAUDE API
// ============================================

/**
 * Process item with Claude API
 */
function processWithClaude(emailData, instruction, patternMatch, geminiData, confidence) {
  var apiKey = getClaudeApiKey();

  // Build prompt
  var prompt = buildClaudePrompt(emailData, instruction, patternMatch, geminiData);

  var payload = {
    model: MCP_CONFIG.CLAUDE_MODEL,
    max_tokens: 2000,
    messages: [{
      role: 'user',
      content: prompt
    }]
  };

  var options = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  var response = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', options);
  var responseCode = response.getResponseCode();

  if (responseCode !== 200) {
    var errorText = response.getContentText();
    Logger.log('Claude API error: ' + errorText);
    throw new Error('Claude API error: ' + responseCode);
  }

  var data = JSON.parse(response.getContentText());

  return {
    output: data.content[0].text,
    confidence: confidence
  };
}

/**
 * Build prompt for Claude
 */
function buildClaudePrompt(emailData, instruction, patternMatch, geminiData) {
  var prompt = 'You are MCP, Derek\'s email processing assistant at Old City Capital.\n\n';

  // Add pattern context
  if (patternMatch) {
    prompt += '=== PATTERN MATCH ===\n';
    prompt += 'Pattern: ' + patternMatch.pattern_name + '\n';
    prompt += 'Confidence boost: +' + patternMatch.confidence_boost + '%\n';
    prompt += 'Keywords matched: ' + patternMatch.matched_keywords.join(', ') + '\n';
    prompt += 'Notes: ' + patternMatch.notes + '\n\n';
  }

  // Add Gemini data if available
  if (geminiData && !geminiData.error) {
    prompt += '=== PRE-FETCHED DATA (from Gemini) ===\n';
    prompt += JSON.stringify(geminiData, null, 2) + '\n';
    prompt += 'Use this data to inform your response. Do not just repeat it.\n\n';
  }

  // Add instruction
  prompt += '=== DEREK\'S INSTRUCTION ===\n';
  prompt += instruction + '\n\n';

  // Add email
  prompt += '=== EMAIL ===\n';
  prompt += 'Subject: ' + (emailData.subject || 'N/A') + '\n';
  if (emailData.sender) {
    prompt += 'From: ' + emailData.sender + '\n';
  }
  if (emailData.date) {
    prompt += 'Date: ' + emailData.date + '\n';
  }
  prompt += '\n';
  if (emailData.body) {
    prompt += emailData.body + '\n\n';
  }

  prompt += '=== YOUR TASK ===\n';
  prompt += 'Process this according to Derek\'s instruction. Be concise and professional.\n';
  prompt += 'Sign as Derek unless instructed otherwise.';

  return prompt;
}

// ============================================
// GEMINI API
// ============================================

/**
 * Call Gemini for data fetching
 */
function callGeminiForData(instruction, emailData) {
  if (!hasGeminiApiKey()) {
    return { error: 'Gemini API key not set' };
  }

  var apiKey = getGeminiApiKey();

  // Build Gemini prompt
  var prompt = buildGeminiPrompt(instruction, emailData);

  var url = 'https://generativelanguage.googleapis.com/v1beta/models/' +
            MCP_CONFIG.GEMINI_MODEL + ':generateContent?key=' + apiKey;

  var payload = {
    contents: [{
      parts: [{
        text: prompt
      }]
    }],
    generationConfig: {
      temperature: 0.1,
      maxOutputTokens: 4000
    }
  };

  var options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  try {
    var response = UrlFetchApp.fetch(url, options);
    var responseCode = response.getResponseCode();

    if (responseCode !== 200) {
      Logger.log('Gemini API error: ' + response.getContentText());
      return { error: 'Gemini API error: ' + responseCode };
    }

    var data = JSON.parse(response.getContentText());

    if (data.candidates && data.candidates[0] && data.candidates[0].content) {
      var text = data.candidates[0].content.parts[0].text;

      // Try to parse as JSON
      try {
        // Remove markdown code blocks if present
        text = text.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
        return JSON.parse(text);
      } catch (e) {
        return { raw_response: text };
      }
    }

    return { error: 'No response from Gemini' };

  } catch (e) {
    Logger.log('Gemini error: ' + e);
    return { error: e.message };
  }
}

/**
 * Build prompt for Gemini data fetching
 */
function buildGeminiPrompt(instruction, emailData) {
  var prompt = 'You are a data extraction assistant. Your job is to fetch and structure data.\n\n';

  prompt += 'TASK: ' + instruction + '\n\n';

  if (emailData.subject) {
    prompt += 'CONTEXT (email subject): ' + emailData.subject + '\n\n';
  }

  prompt += 'INSTRUCTIONS:\n';
  prompt += '1. Identify what data is needed\n';
  prompt += '2. Return structured JSON with the data\n';
  prompt += '3. Include source information if possible\n';
  prompt += '4. Do NOT make recommendations - just return data\n\n';

  prompt += 'Return JSON in this format:\n';
  prompt += '{\n';
  prompt += '  "data_found": true/false,\n';
  prompt += '  "data_type": "spreadsheet|document|email|other",\n';
  prompt += '  "extracted_data": { ... },\n';
  prompt += '  "source_info": { "name": "...", "location": "..." },\n';
  prompt += '  "notes": "any relevant context"\n';
  prompt += '}';

  return prompt;
}

// ============================================
// CONFIDENCE CALCULATION
// ============================================

/**
 * Calculate confidence score
 */
function calculateConfidence(emailData, patternMatch, geminiData) {
  var confidence = 50; // Base confidence

  // Pattern match bonus
  if (patternMatch) {
    confidence += patternMatch.confidence_boost;
  }

  // Known contact bonus
  if (emailData.senderEmail && isKnownContact(emailData.senderEmail)) {
    confidence += 10;
  }

  // Unknown sender penalty
  if (emailData.senderEmail && !isKnownContact(emailData.senderEmail)) {
    confidence -= 10;
  }

  // Gemini data bonus
  if (geminiData && geminiData.data_found) {
    confidence += 15;
  }

  // Clamp to 0-100
  return Math.max(0, Math.min(100, confidence));
}

// ============================================
// GMAIL DRAFT CREATION
// ============================================

/**
 * Create a Gmail draft from the Claude response
 * @param {string} messageId - Original email message ID
 * @param {Object} emailData - Email data object
 * @param {string} draftBody - The draft body text from Claude
 * @returns {Object} Draft info with success status and draft ID
 */
function createGmailDraft(messageId, emailData, draftBody) {
  try {
    if (!messageId || !draftBody) {
      return { success: false, error: 'Missing messageId or draftBody' };
    }

    var originalMessage = GmailApp.getMessageById(messageId);
    if (!originalMessage) {
      return { success: false, error: 'Original message not found' };
    }

    var thread = originalMessage.getThread();
    var recipientEmail = emailData.senderEmail || extractEmail(originalMessage.getFrom());
    var replySubject = 'Re: ' + (emailData.subject || originalMessage.getSubject());

    // Create the draft as a reply in the same thread
    var draft = GmailApp.createDraft(
      recipientEmail,
      replySubject,
      draftBody,
      {
        replyTo: recipientEmail
      }
    );

    var draftId = draft.getId();
    var draftUrl = 'https://mail.google.com/mail/u/0/#drafts?compose=' + draftId;

    Logger.log('Created Gmail draft for: ' + replySubject);
    Logger.log('Draft URL: ' + draftUrl);

    return {
      success: true,
      draftId: draftId,
      draftUrl: draftUrl,
      recipient: recipientEmail,
      subject: replySubject
    };

  } catch (error) {
    Logger.log('Error creating Gmail draft: ' + error);
    return { success: false, error: error.message };
  }
}

/**
 * Process a single item by row number (for testing)
 */
function processSingleRow(rowNum) {
  var sheet = getMainSheet();
  var row = sheet.getRange(rowNum, 1, 1, 8).getValues()[0];

  var emailId = row[MCP_CONFIG.COL.EMAIL_ID];
  var emailData = emailId ? getEmailFromGmail(emailId) : {
    subject: row[MCP_CONFIG.COL.SUBJECT],
    body: '',
    sender: ''
  };

  var instruction = row[MCP_CONFIG.COL.PROMPT];
  var patternMatch = matchEmailToPattern(emailData, instruction);
  var confidence = calculateConfidence(emailData, patternMatch, null);

  var result = processWithClaude(emailData, instruction, patternMatch, null, confidence);

  Logger.log('Result for row ' + rowNum + ':');
  Logger.log('Confidence: ' + result.confidence + '%');
  Logger.log('Output: ' + result.output);

  return result;
}
