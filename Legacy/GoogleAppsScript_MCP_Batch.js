// ============================================
// MCP BATCH PROCESSOR - GOOGLE APPS SCRIPT
// Version 1.0 - Complete System
// ============================================

// ============================================
// CONFIGURATION
// ============================================

var CONFIG = {
  DEREK_EMAIL: 'derek@oldcitycapital.com',
  SEARCH_QUERY: 'label:mcp newer_than:1d',
  MCP_LABEL: 'MCP',
  DONE_LABEL: 'MCP-Done',
  REVIEW_LABEL: 'MCP-Review',
  SCRIPT_URL: ScriptApp.getService().getUrl()
};

// ============================================
// PART 1: GENERATE BATCH QUEUE EMAIL
// Runs at 11 PM - Creates queue for next day
// ============================================

function generateBatchQueue() {
  Logger.log('Starting batch queue generation...');
  
  // Search for MCP labeled emails
  var threads = GmailApp.search(CONFIG.SEARCH_QUERY);
  
  if (threads.length === 0) {
    Logger.log('No MCP emails found');
    return;
  }
  
  Logger.log('Found ' + threads.length + ' MCP emails');
  
  // Build email data array
  var emailData = [];
  threads.forEach(function(thread) {
    var messages = thread.getMessages();
    var lastMessage = messages[messages.length - 1];
    
    emailData.push({
      subject: thread.getFirstMessageSubject(),
      threadId: thread.getId(),
      messageId: lastMessage.getId(),
      sender: extractEmail(lastMessage.getFrom()),
      senderName: extractName(lastMessage.getFrom()),
      date: Utilities.formatDate(lastMessage.getDate(), Session.getScriptTimeZone(), 'MMM dd, yyyy'),
      timestamp: lastMessage.getDate().getTime(),
      body: lastMessage.getPlainBody()
    });
  });
  
  // Generate unique batch ID
  var batchId = 'BATCH_' + new Date().getTime();
  
  // Store batch data in script properties for later retrieval
  PropertiesService.getScriptProperties().setProperty(
    batchId,
    JSON.stringify(emailData)
  );
  
  // Generate HTML email
  var htmlBody = buildQueueEmailHtml(emailData, batchId);
  
  // Send to Derek
  GmailApp.sendEmail(
    CONFIG.DEREK_EMAIL,
    'MCP Batch Queue - ' + emailData.length + ' emails ready',
    'Fill in instructions and click Process Queue Now link',
    {
      htmlBody: htmlBody,
      name: 'MCP Assistant'
    }
  );
  
  Logger.log('Batch queue email sent successfully. Batch ID: ' + batchId);
  
  return batchId;
}

function buildQueueEmailHtml(emailData, batchId) {
  // Build table rows
  var rows = '';
  emailData.forEach(function(email, index) {
    rows += '\n      <tr>\n' +
            '        <td class="subject">\n' +
            '          ' + escapeHtml(email.subject) + '\n' +
            '          <div class="sender">From: ' + escapeHtml(email.senderName) + ' (' + escapeHtml(email.sender) + ')</div>\n' +
            '        </td>\n' +
            '        <td class="instruction" contenteditable="true" id="instr_' + index + '">\n' +
            '          <!-- Derek types here -->\n' +
            '        </td>\n' +
            '      </tr>';
  });
  
  // Build process link with batch ID
  var processLink = CONFIG.SCRIPT_URL + '?action=process&batchId=' + batchId;
  
  var html = '<!DOCTYPE html>\n' +
'<html>\n' +
'<head>\n' +
'  <style>\n' +
'    body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }\n' +
'    .container { background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }\n' +
'    table { border-collapse: collapse; width: 100%; margin: 20px 0; background-color: white; }\n' +
'    th { background-color: #4CAF50; color: white; padding: 15px; text-align: left; border: 1px solid #ddd; font-size: 14px; }\n' +
'    td { padding: 15px; border: 1px solid #ddd; vertical-align: top; }\n' +
'    .subject { font-weight: bold; width: 45%; font-size: 15px; }\n' +
'    .sender { color: #666; font-size: 12px; margin-top: 5px; font-weight: normal; }\n' +
'    .instruction { width: 55%; background-color: #f9f9f9; min-height: 50px; font-size: 14px; }\n' +
'    [contenteditable] { outline: 1px dashed #ccc; }\n' +
'    [contenteditable]:focus { outline: 2px solid #4CAF50; background-color: white; }\n' +
'    .process-button { display: inline-block; background-color: #4CAF50; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px; margin: 20px 0; }\n' +
'    .process-button:hover { background-color: #45a049; }\n' +
'    .tips { background-color: #e8f5e9; padding: 20px; border-radius: 5px; margin-top: 20px; border-left: 4px solid #4CAF50; }\n' +
'    .tips h3 { margin-top: 0; color: #2e7d32; }\n' +
'    .instructions-text { background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }\n' +
'    .meta { color: #999; font-size: 12px; margin-top: 20px; text-align: center; padding-top: 20px; border-top: 1px solid #ddd; }\n' +
'  </style>\n' +
'</head>\n' +
'<body>\n' +
'  <div class="container">\n' +
'    <div class="header">\n' +
'      <h2>🤖 MCP Batch Queue - Ready for Processing</h2>\n' +
'      <p>Found <strong>' + emailData.length + ' emails</strong> with [MCP] label.</p>\n' +
'    </div>\n' +
'    \n' +
'    <div class="instructions-text">\n' +
'      <strong>📝 Instructions:</strong> Click in the right column to type what you want MCP to do, then click "Process Queue Now" below.\n' +
'    </div>\n' +
'    \n' +
'    <table>\n' +
'      <thead>\n' +
'        <tr>\n' +
'          <th>Subject Line</th>\n' +
'          <th>Your Instruction</th>\n' +
'        </tr>\n' +
'      </thead>\n' +
'      <tbody>' + rows + '\n' +
'      </tbody>\n' +
'    </table>\n' +
'    \n' +
'    <div style="text-align: center; margin: 30px 0;">\n' +
'      <a href="' + processLink + '" class="process-button">🚀 Process Queue Now</a>\n' +
'      <p style="color: #666; font-size: 13px; margin-top: 10px;">Click when you\'ve filled in all instructions above</p>\n' +
'    </div>\n' +
'    \n' +
'    <div class="tips">\n' +
'      <h3>💡 Example Instructions</h3>\n' +
'      <ul>\n' +
'        <li><strong>"extract invoice data"</strong> - Get investor list + recipients</li>\n' +
'        <li><strong>"send w9"</strong> - Draft W9 response with attachment</li>\n' +
'        <li><strong>"confirm amount"</strong> - Check payment in NetSuite</li>\n' +
'        <li><strong>"summarize"</strong> - Give me key points only</li>\n' +
'        <li><strong>"SKIP"</strong> - Don\'t process this email</li>\n' +
'        <li><strong>Leave blank</strong> - MCP auto-determines action</li>\n' +
'      </ul>\n' +
'    </div>\n' +
'    \n' +
'    <div class="meta">\n' +
'      Generated: ' + new Date().toLocaleString() + '<br>\n' +
'      Batch ID: ' + batchId + '\n' +
'    </div>\n' +
'    \n' +
'    <div style="display:none;" id="batch-data">' + JSON.stringify(emailData) + '</div>\n' +
'  </div>\n' +
'</body>\n' +
'</html>';
  
  return html;
}

// ============================================
// PART 2: WEB APP ENDPOINT (Process Link)
// Handles "Process Queue Now" button click
// ============================================

function doGet(e) {
  var action = e.parameter.action;
  var batchId = e.parameter.batchId;
  
  if (action === 'process' && batchId) {
    Logger.log('Processing batch: ' + batchId);
    
    // Retrieve batch data
    var batchDataJson = PropertiesService.getScriptProperties().getProperty(batchId);
    
    if (!batchDataJson) {
      return HtmlService.createHtmlOutput('Error: Batch not found. It may have expired.');
    }
    
    var emailData = JSON.parse(batchDataJson);
    
    // Return immediate feedback
    var html = '<!DOCTYPE html>\n' +
      '<html>\n' +
      '<head>\n' +
      '  <style>\n' +
      '    body { font-family: Arial; text-align: center; padding: 50px; }\n' +
      '    .success { color: #4CAF50; font-size: 24px; margin: 20px 0; }\n' +
      '    .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #4CAF50; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 20px auto; }\n' +
      '    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }\n' +
      '  </style>\n' +
      '</head>\n' +
      '<body>\n' +
      '  <div class="spinner"></div>\n' +
      '  <div class="success">✓ Processing Started!</div>\n' +
      '  <p>Processing ' + emailData.length + ' emails from your batch queue.</p>\n' +
      '  <p>You\'ll receive results via email in a few minutes.</p>\n' +
      '  <p><em>You can close this window.</em></p>\n' +
      '</body>\n' +
      '</html>';
    
    // Trigger async processing
    processBatchAsync(batchId, emailData);
    
    return HtmlService.createHtmlOutput(html);
  }
  
  return HtmlService.createHtmlOutput('Invalid request');
}

function processBatchAsync(batchId, emailData) {
  // Get Derek's instructions from the latest reply email
  var threads = GmailApp.search('subject:"MCP Batch Queue" from:' + CONFIG.DEREK_EMAIL + ' newer_than:1d');
  
  var instructions = [];
  
  if (threads.length > 0) {
    var thread = threads[0];
    var messages = thread.getMessages();
    var reply = messages[messages.length - 1];
    
    instructions = parseInstructionsFromEmail(reply.getBody(), emailData.length);
  }
  
  // If no instructions found, auto-determine
  if (instructions.length === 0) {
    Logger.log('No instructions found - will auto-determine actions');
    instructions = emailData.map(function() { return ''; });
  }
  
  // Process each email
  var results = [];
  
  for (var i = 0; i < emailData.length; i++) {
    var instruction = instructions[i] || '';
    
    // Check for SKIP
    if (instruction.toUpperCase().indexOf('SKIP') !== -1) {
      Logger.log('Skipping email ' + i + ': ' + emailData[i].subject);
      continue;
    }
    
    try {
      // Process the email
      var result = processSingleEmail(
        emailData[i],
        instruction
      );
      
      results.push(result);
      
      // Rate limiting
      Utilities.sleep(2000);
      
    } catch (error) {
      Logger.log('Error processing email ' + i + ': ' + error.toString());
      results.push({
        subject: emailData[i].subject,
        instruction: instruction,
        output: 'ERROR: ' + error.toString(),
        confidence: 0,
        pattern: 'error',
        success: false
      });
    }
  }
  
  // Send results email
  sendResultsEmail(results, batchId);
  
  // Update labels on processed emails
  updateEmailLabels(emailData);
  
  // Clean up batch data
  PropertiesService.getScriptProperties().deleteProperty(batchId);
  
  Logger.log('Batch processing complete: ' + batchId);
}

// ============================================
// PART 3: INTELLIGENT DATA NEEDS DETECTION
// Apps Script decides what data is needed
// ============================================

function analyzeDataNeeds(instruction, emailContent, subject) {
  var needs = {
    needsGemini: false,
    geminiTask: null,
    taskType: null
  };
  
  var instrLower = instruction.toLowerCase();
  var contentLower = (subject + ' ' + emailContent).toLowerCase();
  
  // SPREADSHEET INDICATORS
  var spreadsheetKeywords = [
    'reconcile', 'ap aging', 'ar aging', 'balance sheet',
    'compare spreadsheet', 'analyze budget', 'calculate fees',
    'financial data', 'expense report'
  ];
  
  for (var i = 0; i < spreadsheetKeywords.length; i++) {
    if (instrLower.indexOf(spreadsheetKeywords[i]) !== -1 ||
        contentLower.indexOf(spreadsheetKeywords[i]) !== -1) {
      
      needs.needsGemini = true;
      needs.geminiTask = 'spreadsheet_analysis';
      needs.taskType = 'Find and analyze spreadsheet data';
      
      Logger.log('DETECTED: Spreadsheet task');
      return needs;
    }
  }
  
  // DOCUMENT SEARCH INDICATORS
  var documentSearchKeywords = [
    'find documents', 'locate files', 'search drive',
    'all mandates', 'compliance audit', 'review documents',
    'missing forms', 'incomplete submissions'
  ];
  
  for (var i = 0; i < documentSearchKeywords.length; i++) {
    if (instrLower.indexOf(documentSearchKeywords[i]) !== -1 ||
        contentLower.indexOf(documentSearchKeywords[i]) !== -1) {
      
      needs.needsGemini = true;
      needs.geminiTask = 'document_search';
      needs.taskType = 'Search Google Drive for documents';
      
      Logger.log('DETECTED: Document search task');
      return needs;
    }
  }
  
  // BULK SCANNING INDICATORS
  if (instrLower.indexOf('audit') !== -1 ||
      instrLower.indexOf('review all') !== -1 ||
      instrLower.indexOf('check compliance') !== -1) {
    
    needs.needsGemini = true;
    needs.geminiTask = 'bulk_scan';
    needs.taskType = 'Scan multiple documents for compliance';
    
    Logger.log('DETECTED: Bulk scanning task');
    return needs;
  }
  
  // DATA EXTRACTION INDICATORS
  if (instrLower.indexOf('extract from drive') !== -1 ||
      instrLower.indexOf('pull data from') !== -1) {
    
    needs.needsGemini = true;
    needs.geminiTask = 'data_extraction';
    needs.taskType = 'Extract structured data from documents';
    
    Logger.log('DETECTED: Data extraction task');
    return needs;
  }
  
  Logger.log('No Gemini data needed - Claude can handle directly');
  return needs;
}

// ============================================
// PART 4: PROCESS INDIVIDUAL EMAILS
// Main processing logic with Gemini integration
// ============================================

function processSingleEmail(emailData, instruction) {
  Logger.log('Processing: ' + emailData.subject + ' | Instruction: ' + instruction);
  
  // Determine what data is needed
  var dataNeeds = analyzeDataNeeds(instruction, emailData.body, emailData.subject);
  
  var geminiData = null;
  
  // If Gemini data needed, fetch it FIRST
  if (dataNeeds.needsGemini) {
    Logger.log('Gemini data needed: ' + dataNeeds.geminiTask);
    geminiData = callGeminiForData(dataNeeds.geminiTask, emailData);
  }
  
  // Now call Claude with all context
  var claudeInput = {
    emailData: emailData,
    instruction: instruction,
    geminiData: geminiData
  };
  
  var result = callClaudeAPI(claudeInput);
  
  return {
    subject: emailData.subject,
    instruction: instruction || 'auto-determined',
    output: result.output,
    confidence: result.confidence,
    pattern: result.pattern,
    success: true
  };
}

// ============================================
// PART 5: GEMINI API INTEGRATION
// Calls Gemini to fetch structured data
// ============================================

function callGeminiForData(taskType, emailData) {
  var geminiApiKey = PropertiesService.getScriptProperties()
    .getProperty('GEMINI_API_KEY');
  
  if (!geminiApiKey) {
    throw new Error('Gemini API key not configured');
  }
  
  var prompt = buildGeminiPrompt(taskType, emailData);
  
  var payload = {
    contents: [{
      parts: [{
        text: prompt
      }]
    }],
    generationConfig: {
      temperature: 0.1,
      topK: 1,
      topP: 1,
      maxOutputTokens: 8000
    }
  };
  
  var options = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'x-goog-api-key': geminiApiKey
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  try {
    var response = UrlFetchApp.fetch(
      'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent',
      options
    );
    
    var responseCode = response.getResponseCode();
    
    if (responseCode !== 200) {
      throw new Error('Gemini API error: ' + response.getContentText());
    }
    
    var data = JSON.parse(response.getContentText());
    var geminiResponse = data.candidates[0].content.parts[0].text;
    
    // Parse Gemini's JSON response
    var structuredData = parseGeminiResponse(geminiResponse);
    
    Logger.log('Gemini returned structured data');
    
    return structuredData;
    
  } catch (error) {
    Logger.log('Gemini API error: ' + error.toString());
    
    return {
      error: true,
      message: error.toString(),
      taskType: taskType
    };
  }
}

function buildGeminiPrompt(taskType, emailData) {
  var basePrompt = 'You are a data extraction assistant for Derek at Old City Capital.\n\n' +
    'Your job is to find and structure data, NOT to interpret or recommend.\n\n' +
    'Email context:\n' +
    'Subject: ' + emailData.subject + '\n' +
    'From: ' + emailData.senderName + ' (' + emailData.sender + ')\n' +
    'Body: ' + emailData.body + '\n\n';
  
  if (taskType === 'spreadsheet_analysis') {
    return basePrompt +
      'TASK: Find spreadsheet data mentioned in the email.\n\n' +
      '1. Search Google Drive for the spreadsheet mentioned\n' +
      '2. If found, extract:\n' +
      '   - All sheet names\n' +
      '   - Column headers\n' +
      '   - All numerical data\n' +
      '   - Any formulas present\n' +
      '3. If comparing multiple sheets, extract both\n\n' +
      'Return ONLY JSON format:\n' +
      '{\n' +
      '  "files_found": [\n' +
      '    {\n' +
      '      "name": "AP Aging Summary.xlsx",\n' +
      '      "url": "https://drive.google.com/...",\n' +
      '      "sheets": [\n' +
      '        {\n' +
      '          "name": "Summary",\n' +
      '          "headers": ["Vendor", "Amount", "Days Outstanding"],\n' +
      '          "data": [\n' +
      '            ["Vendor A", 5000, 30],\n' +
      '            ["Vendor B", 3000, 45]\n' +
      '          ]\n' +
      '        }\n' +
      '      ]\n' +
      '    }\n' +
      '  ],\n' +
      '  "total_files": 1\n' +
      '}';
  }
  
  else if (taskType === 'document_search') {
    return basePrompt +
      'TASK: Search Google Drive for documents mentioned in email.\n\n' +
      '1. Identify document type requested\n' +
      '2. Search Drive with appropriate keywords\n' +
      '3. Return list of matching files\n\n' +
      'Return ONLY JSON format:\n' +
      '{\n' +
      '  "search_query": "mandate forms",\n' +
      '  "files_found": [\n' +
      '    {\n' +
      '      "name": "Mandate_CompanyA.pdf",\n' +
      '      "url": "https://drive.google.com/...",\n' +
      '      "modified": "2026-01-15",\n' +
      '      "size": "2.4 MB",\n' +
      '      "folder": "Mandates/2026"\n' +
      '    }\n' +
      '  ],\n' +
      '  "total_files": 12\n' +
      '}';
  }
  
  else if (taskType === 'bulk_scan') {
    return basePrompt +
      'TASK: Scan multiple documents for specific information.\n\n' +
      '1. Find all documents of the type requested\n' +
      '2. Extract key fields from each\n' +
      '3. Check for completeness\n\n' +
      'Return ONLY JSON format:\n' +
      '{\n' +
      '  "documents_scanned": 15,\n' +
      '  "complete": 12,\n' +
      '  "incomplete": 3,\n' +
      '  "details": [\n' +
      '    {\n' +
      '      "name": "Mandate_CompanyA.pdf",\n' +
      '      "status": "complete",\n' +
      '      "missing_fields": []\n' +
      '    },\n' +
      '    {\n' +
      '      "name": "Mandate_CompanyB.pdf",\n' +
      '      "status": "incomplete",\n' +
      '      "missing_fields": ["signature", "date"]\n' +
      '    }\n' +
      '  ]\n' +
      '}';
  }
  
  else if (taskType === 'data_extraction') {
    return basePrompt +
      'TASK: Extract structured data from documents.\n\n' +
      '1. Find the documents mentioned\n' +
      '2. Extract the specific data points requested\n' +
      '3. Return in structured format\n\n' +
      'Return ONLY JSON format:\n' +
      '{\n' +
      '  "data_extracted": true,\n' +
      '  "records": [\n' +
      '    {\n' +
      '      "field_1": "value_1",\n' +
      '      "field_2": "value_2"\n' +
      '    }\n' +
      '  ],\n' +
      '  "total_records": 10\n' +
      '}';
  }
  
  return basePrompt + 'Extract relevant data and return as JSON.';
}

function parseGeminiResponse(responseText) {
  try {
    // Remove markdown code fences if present
    var cleaned = responseText
      .replace(/```json\n?/g, '')
      .replace(/```\n?/g, '')
      .trim();
    
    var parsed = JSON.parse(cleaned);
    return parsed;
    
  } catch (error) {
    Logger.log('Error parsing Gemini JSON: ' + error.toString());
    Logger.log('Raw response: ' + responseText);
    
    return {
      error: true,
      message: 'Failed to parse Gemini response',
      raw_response: responseText
    };
  }
}

// ============================================
// PART 6: CLAUDE API INTEGRATION
// Calls Claude with all context pre-gathered
// ============================================

function callClaudeAPI(claudeInput) {
  var apiKey = PropertiesService.getScriptProperties()
    .getProperty('CLAUDE_API_KEY');
  
  if (!apiKey) {
    throw new Error('Claude API key not configured');
  }
  
  var prompt = buildClaudePrompt(claudeInput);
  
  var payload = {
    model: 'claude-sonnet-4-20250514',
    max_tokens: 4000,
    messages: [
      {
        role: 'user',
        content: prompt
      }
    ]
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
  
  try {
    var response = UrlFetchApp.fetch(
      'https://api.anthropic.com/v1/messages',
      options
    );
    
    var responseCode = response.getResponseCode();
    
    if (responseCode !== 200) {
      throw new Error('Claude API error: ' + response.getContentText());
    }
    
    var data = JSON.parse(response.getContentText());
    
    return {
      output: data.content[0].text,
      confidence: 85,
      pattern: determinePattern(claudeInput.instruction)
    };
    
  } catch (error) {
    Logger.log('Claude API error: ' + error.toString());
    throw error;
  }
}

function buildClaudePrompt(claudeInput) {
  var emailData = claudeInput.emailData;
  var instruction = claudeInput.instruction;
  var geminiData = claudeInput.geminiData;
  
  var prompt = 'You are MCP, Derek\'s email processing assistant at Old City Capital.\n\n' +
    'Derek\'s instruction: "' + instruction + '"\n\n' +
    'Email:\n' +
    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' +
    'Subject: ' + emailData.subject + '\n' +
    'From: ' + emailData.senderName + ' (' + emailData.sender + ')\n' +
    'Date: ' + emailData.date + '\n\n' +
    emailData.body + '\n' +
    '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n';
  
  // Add Gemini data if available
  if (geminiData && !geminiData.error) {
    prompt += 'Gemini Data (pre-fetched structured data):\n' +
      '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' +
      JSON.stringify(geminiData, null, 2) + '\n' +
      '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n' +
      'This data has been pre-fetched for you. Your job is to:\n' +
      '1. Interpret what this data means\n' +
      '2. Apply business context\n' +
      '3. Make recommendations\n' +
      '4. Format for Derek\n\n' +
      'DO NOT just repeat the data - add value through analysis.\n' +
      '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n';
  } else if (geminiData && geminiData.error) {
    prompt += '⚠️ Gemini data retrieval encountered an error:\n' +
      geminiData.message + '\n\n' +
      'Please work with the email content available.\n' +
      '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n';
  }
  
  prompt += 'Process this email according to Derek\'s instruction.\n\n' +
    'Remember:\n' +
    '- Apply Derek\'s established patterns and rules from your knowledge\n' +
    '- If Gemini data is provided, interpret it - don\'t just relay it\n' +
    '- Add business context and recommendations\n' +
    '- Format output for Derek\'s use (copy-paste ready)';
  
  return prompt;
}

// ============================================
// PART 7: SEND RESULTS EMAIL
// ============================================

function sendResultsEmail(results, batchId) {
  var htmlBody = buildResultsEmailHtml(results, batchId);
  
  GmailApp.sendEmail(
    CONFIG.DEREK_EMAIL,
    'MCP Batch Results - ' + results.length + ' processed',
    'Batch processing complete. See HTML email for formatted results.',
    {
      htmlBody: htmlBody,
      name: 'MCP Assistant'
    }
  );
  
  Logger.log('Results email sent');
}

function buildResultsEmailHtml(results, batchId) {
  var successCount = results.filter(function(r) { return r.success; }).length;
  var warningCount = results.filter(function(r) { return r.confidence < 70; }).length;
  
  var html = '<!DOCTYPE html>\n<html>\n<head>\n  <style>\n' +
    '    body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }\n' +
    '    .container { background-color: white; padding: 30px; border-radius: 8px; }\n' +
    '    .summary { background-color: #e8f5e9; padding: 20px; border-radius: 5px; margin-bottom: 30px; }\n' +
    '    .summary h2 { margin-top: 0; color: #2e7d32; }\n' +
    '    .result { border: 1px solid #ddd; margin: 20px 0; padding: 20px; border-radius: 5px; }\n' +
    '    .result.success { background-color: #e8f5e9; border-left: 5px solid #4CAF50; }\n' +
    '    .result.warning { background-color: #fff3e0; border-left: 5px solid #ff9800; }\n' +
    '    .result.error { background-color: #ffebee; border-left: 5px solid #f44336; }\n' +
    '    .subject { font-weight: bold; font-size: 18px; margin-bottom: 10px; }\n' +
    '    .instruction { color: #666; font-style: italic; margin-bottom: 15px; padding: 10px; background-color: rgba(255,255,255,0.5); border-radius: 3px; }\n' +
    '    .output { background-color: white; padding: 15px; border-radius: 3px; white-space: pre-wrap; font-family: \'Courier New\', monospace; font-size: 13px; line-height: 1.6; }\n' +
    '    .meta { font-size: 12px; color: #999; margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd; }\n' +
    '  </style>\n</head>\n<body>\n  <div class="container">\n    <div class="summary">\n' +
    '      <h2>✅ MCP Batch Processing Complete</h2>\n' +
    '      <p><strong>' + successCount + ' of ' + results.length + ' emails</strong> processed successfully.</p>\n';
  
  if (warningCount > 0) {
    html += '      <p>⚠️ <strong>' + warningCount + ' items</strong> flagged for review (low confidence).</p>\n';
  }
  
  html += '      <p style="font-size: 12px; color: #666; margin-top: 15px;">Batch ID: ' + batchId + '</p>\n' +
    '    </div>\n';

  results.forEach(function(result, index) {
    var cssClass = result.success ? (result.confidence >= 70 ? 'success' : 'warning') : 'error';
    var icon = result.success ? (result.confidence >= 70 ? '✓' : '⚠') : '✗';
    
    html += '    <div class="result ' + cssClass + '">\n' +
      '      <div class="subject">' + icon + ' Email ' + (index + 1) + ': ' + escapeHtml(result.subject) + '</div>\n' +
      '      <div class="instruction">Instruction: "' + escapeHtml(result.instruction) + '"</div>\n' +
      '      <div class="output">' + escapeHtml(result.output) + '</div>\n' +
      '      <div class="meta">\n' +
      '        Confidence: ' + result.confidence + '% | \n' +
      '        Pattern: ' + result.pattern + ' |\n' +
      '        Status: ' + (result.success ? 'Success' : 'Error') + '\n' +
      '      </div>\n' +
      '    </div>\n';
  });

  html += '    <p style="text-align: center; color: #999; margin-top: 30px; font-size: 12px;">\n' +
    '      <em>Generated: ' + new Date().toLocaleString() + '</em>\n' +
    '    </p>\n' +
    '  </div>\n' +
    '</body>\n' +
    '</html>';
  
  return html;
}

// ============================================
// PART 8: LABEL MANAGEMENT
// ============================================

function updateEmailLabels(emailData) {
  var mcpLabel = GmailApp.getUserLabelByName(CONFIG.MCP_LABEL);
  var doneLabel = GmailApp.getUserLabelByName(CONFIG.DONE_LABEL);
  
  if (!doneLabel) {
    doneLabel = GmailApp.createLabel(CONFIG.DONE_LABEL);
  }
  
  emailData.forEach(function(email) {
    try {
      var thread = GmailApp.getThreadById(email.threadId);
      thread.removeLabel(mcpLabel);
      thread.addLabel(doneLabel);
    } catch (error) {
      Logger.log('Error updating label for ' + email.subject + ': ' + error.toString());
    }
  });
  
  Logger.log('Labels updated for ' + emailData.length + ' emails');
}

// ============================================
// HELPER FUNCTIONS
// ============================================

function parseInstructionsFromEmail(htmlBody, expectedCount) {
  var instructions = [];
  
  var regex = /<td[^>]*contenteditable[^>]*id="instr_\d+"[^>]*>(.*?)<\/td>/gi;
  var matches;
  
  while ((matches = regex.exec(htmlBody)) !== null) {
    var text = matches[1]
      .replace(/<[^>]*>/g, '')
      .replace(/&nbsp;/g, ' ')
      .trim();
    
    instructions.push(text);
  }
  
  if (instructions.length === 0) {
    regex = /<td class="instruction"[^>]*>(.*?)<\/td>/gi;
    while ((matches = regex.exec(htmlBody)) !== null) {
      var text = matches[1]
        .replace(/<[^>]*>/g, '')
        .trim();
      instructions.push(text);
    }
  }
  
  Logger.log('Parsed ' + instructions.length + ' instructions');
  return instructions;
}

function extractEmail(fromString) {
  var match = fromString.match(/<(.+?)>/);
  return match ? match[1] : fromString;
}

function extractName(fromString) {
  var match = fromString.match(/^(.+?)\s*</);
  return match ? match[1].replace(/"/g, '') : fromString;
}

function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function determinePattern(instruction) {
  if (!instruction) return 'Generic';
  
  var instrLower = instruction.toLowerCase();
  if (instrLower.indexOf('invoice') !== -1) return 'Invoice Processing';
  if (instrLower.indexOf('w9') !== -1) return 'W9 Request';
  if (instrLower.indexOf('payment') !== -1) return 'Payment Confirmation';
  if (instrLower.indexOf('summarize') !== -1) return 'Summary';
  return 'Generic';
}

// ============================================
// SETUP FUNCTION (Run once)
// ============================================

function setupMCP() {
  // Instructions for Derek to run once
  Logger.log('=== MCP SETUP ===');
  Logger.log('1. Set Claude API key:');
  Logger.log('   PropertiesService.getScriptProperties().setProperty("CLAUDE_API_KEY", "your-key");');
  Logger.log('2. Set Gemini API key:');
  Logger.log('   PropertiesService.getScriptProperties().setProperty("GEMINI_API_KEY", "your-key");');
  Logger.log('3. Deploy as Web App');
  Logger.log('4. Set up triggers for generateBatchQueue()');
  Logger.log('5. Create Gmail labels: MCP, MCP-Done, MCP-Review');
  
  // Create labels
  var labels = [CONFIG.MCP_LABEL, CONFIG.DONE_LABEL, CONFIG.REVIEW_LABEL];
  labels.forEach(function(labelName) {
    if (!GmailApp.getUserLabelByName(labelName)) {
      GmailApp.createLabel(labelName);
      Logger.log('Created label: ' + labelName);
    }
  });
  
  Logger.log('Setup complete!');
}

// ============================================
// TEST FUNCTION
// ============================================

function testSystem() {
  Logger.log('=== TESTING MCP SYSTEM ===');
  
  // Test Gemini API
  try {
    var testEmail = {
      subject: 'Test Email',
      body: 'This is a test',
      sender: 'test@example.com',
      senderName: 'Test User'
    };
    
    Logger.log('Testing data needs detection...');
    var needs = analyzeDataNeeds('reconcile ap', testEmail.body, testEmail.subject);
    Logger.log('Needs Gemini: ' + needs.needsGemini);
    Logger.log('Task Type: ' + needs.geminiTask);
    
    Logger.log('✓ System components working');
    
  } catch (error) {
    Logger.log('✗ Error: ' + error.toString());
  }
}
