// ============================================
// MCP BATCH PROCESSOR WITH SQLITE INTEGRATION
// Version 2.0 - Connects to Python API
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
  SCRIPT_URL: ScriptApp.getService().getUrl(),
  
  // Python API configuration
  PYTHON_API_URL: 'http://localhost:5000/api',  // Update this if API is remote
  USE_PYTHON_API: true  // Set to false to use local patterns only
};

// ============================================
// PYTHON API CLIENT
// ============================================

function callPythonAPI(endpoint, method, data) {
  /**
   * Call Python SQLite API
   * @param {string} endpoint - API endpoint (e.g., '/patterns')
   * @param {string} method - HTTP method ('GET' or 'POST')
   * @param {object} data - Data to send (for POST requests)
   */
  
  if (!CONFIG.USE_PYTHON_API) {
    Logger.log('Python API disabled - using local fallback');
    return null;
  }
  
  var url = CONFIG.PYTHON_API_URL + endpoint;
  
  var options = {
    method: method.toLowerCase(),
    contentType: 'application/json',
    muteHttpExceptions: true
  };
  
  if (method === 'POST' && data) {
    options.payload = JSON.stringify(data);
  }
  
  try {
    Logger.log('Calling Python API: ' + method + ' ' + url);
    var response = UrlFetchApp.fetch(url, options);
    var responseCode = response.getResponseCode();
    
    if (responseCode === 200) {
      var result = JSON.parse(response.getContentText());
      if (result.success) {
        Logger.log('✓ Python API call successful');
        return result;
      } else {
        Logger.log('Python API returned error: ' + result.error);
        return null;
      }
    } else {
      Logger.log('Python API returned status ' + responseCode);
      return null;
    }
    
  } catch (error) {
    Logger.log('Python API error: ' + error.toString());
    Logger.log('Falling back to local patterns');
    return null;
  }
}

// ============================================
// GET PATTERNS FROM SQLITE
// ============================================

function getSQLitePatterns() {
  /**
   * Get patterns from SQLite via Python API
   * Falls back to local patterns if API unavailable
   */
  
  var result = callPythonAPI('/patterns', 'GET');
  
  if (result && result.patterns) {
    Logger.log('Loaded ' + result.count + ' patterns from SQLite');
    return result.patterns;
  }
  
  // Fallback: Local patterns (copied from SQLite)
  Logger.log('Using local fallback patterns');
  return getLocalPatterns();
}

function getLocalPatterns() {
  /**
   * Fallback patterns (manually synced from SQLite)
   * These are copies of your SQLite bootstrap data
   */
  return [
    {
      pattern_name: 'invoice_processing',
      keywords: ['invoice', 'fees', 'mgmt', 'Q3', 'Q4', 'quarterly'],
      confidence_boost: 15,
      notes: 'Route to Claude Project or Google Script'
    },
    {
      pattern_name: 'w9_wiring_request',
      keywords: ['w9', 'w-9', 'wiring instructions', 'wire details'],
      confidence_boost: 20,
      notes: 'Use w9_response template'
    },
    {
      pattern_name: 'payment_confirmation',
      keywords: ['payment', 'wire', 'received', 'OCS Payment'],
      confidence_boost: 15,
      notes: 'Check NetSuite for confirmation'
    },
    {
      pattern_name: 'producer_statements',
      keywords: ['producer statements', 'producer report'],
      confidence_boost: 10,
      notes: 'Weekly Friday task'
    },
    {
      pattern_name: 'delegation_eytan',
      keywords: ['insufficient info', 'not sure', 'need eytan', 'loop in eytan'],
      confidence_boost: 0,
      notes: 'Use delegation_eytan template'
    },
    {
      pattern_name: 'turnaround_expectation',
      keywords: ['how long', 'timeline', 'when', 'deadline'],
      confidence_boost: 5,
      notes: 'Use turnaround_time template'
    },
    {
      pattern_name: 'journal_entry_reminder',
      keywords: ['JE', 'journal entry', 'partner compensation'],
      confidence_boost: 0,
      notes: 'Knowledge base lookup'
    }
  ];
}

// ============================================
// GET TEMPLATES FROM SQLITE
// ============================================

function getSQLiteTemplates() {
  /**
   * Get templates from SQLite via Python API
   * Falls back to local templates if API unavailable
   */
  
  var result = callPythonAPI('/templates', 'GET');
  
  if (result && result.templates) {
    Logger.log('Loaded ' + result.count + ' templates from SQLite');
    return result.templates;
  }
  
  // Fallback: Local templates
  Logger.log('Using local fallback templates');
  return getLocalTemplates();
}

function getLocalTemplates() {
  /**
   * Fallback templates (manually synced from SQLite)
   */
  return [
    {
      template_id: 'w9_response',
      template_name: 'W9 & Wiring Instructions',
      template_body: 'Hi {name},\n\nHere\'s our W9 form (attached).\n\nOur wiring instructions:\n{wiring_details}\n\nLet me know if you need anything else!\n\nBest,\nDerek',
      variables: ['name', 'wiring_details'],
      attachments: ['OldCity_W9.pdf']
    },
    {
      template_id: 'payment_confirmation',
      template_name: 'Payment Received Confirmation',
      template_body: 'Hi {name},\n\nConfirmed - we received payment of ${amount} on {date}.\n\nThank you!\n\nBest,\nDerek',
      variables: ['name', 'amount', 'date'],
      attachments: []
    },
    {
      template_id: 'delegation_eytan',
      template_name: 'Loop in Eytan',
      template_body: 'Hi {name},\n\nLooping in Eytan for his input on this.\n\nEytan - {context}\n\nThanks,\nDerek',
      variables: ['name', 'context'],
      attachments: []
    },
    {
      template_id: 'turnaround_time',
      template_name: 'Turnaround Time Expectation',
      template_body: 'Hi {name},\n\nOur typical turnaround for {request_type} is {timeline}.\n\nI\'ll have this back to you by {specific_date}.\n\nLet me know if you need it sooner.\n\nBest,\nDerek',
      variables: ['name', 'request_type', 'timeline', 'specific_date'],
      attachments: []
    }
  ];
}

// ============================================
// MATCH EMAIL TO PATTERN (Using SQLite)
// ============================================

function matchEmailToPattern(emailData, instruction) {
  /**
   * Match email to pattern using SQLite data
   * Can use Python API for intelligent matching
   */
  
  // Try Python API pattern matching
  var result = callPythonAPI('/match-pattern', 'POST', {
    subject: emailData.subject,
    body: emailData.body,
    instruction: instruction
  });
  
  if (result && result.best_match) {
    Logger.log('SQLite pattern match: ' + result.best_match.pattern_name);
    Logger.log('  Confidence boost: +' + result.best_match.confidence_boost);
    Logger.log('  Matched keywords: ' + result.best_match.matched_keywords.join(', '));
    return result.best_match;
  }
  
  // Fallback: Local matching
  Logger.log('Using local pattern matching');
  return matchEmailToPatternLocal(emailData, instruction);
}

function matchEmailToPatternLocal(emailData, instruction) {
  /**
   * Local pattern matching (fallback)
   */
  var patterns = getLocalPatterns();
  var combined = (emailData.subject + ' ' + emailData.body + ' ' + instruction).toLowerCase();
  
  var bestMatch = null;
  var bestScore = 0;
  
  patterns.forEach(function(pattern) {
    var matchCount = 0;
    var matchedKeywords = [];
    
    pattern.keywords.forEach(function(keyword) {
      if (combined.indexOf(keyword.toLowerCase()) !== -1) {
        matchCount++;
        matchedKeywords.push(keyword);
      }
    });
    
    if (matchCount > bestScore) {
      bestScore = matchCount;
      bestMatch = {
        pattern_name: pattern.pattern_name,
        confidence_boost: pattern.confidence_boost,
        matched_keywords: matchedKeywords,
        notes: pattern.notes
      };
    }
  });
  
  return bestMatch;
}

// ============================================
// CHECK SAFETY OVERRIDES (Using SQLite)
// ============================================

function checkSafetyOverride(emailData) {
  /**
   * Check if email matches any safety overrides in SQLite
   */
  
  var result = callPythonAPI('/check-override', 'POST', {
    subject: emailData.subject,
    sender: emailData.sender
  });
  
  if (result) {
    if (result.blocked) {
      Logger.log('⚠️  Email blocked by safety rule');
      Logger.log('   Rule: ' + result.rule.rule_value);
      Logger.log('   Action: ' + result.rule.action);
      Logger.log('   Reason: ' + result.rule.reason);
      return result;
    }
  }
  
  // Fallback: Local safety check
  return checkSafetyOverrideLocal(emailData);
}

function checkSafetyOverrideLocal(emailData) {
  /**
   * Local safety override check (fallback)
   */
  var dangerousKeywords = ['FINRA audit', 'SEC investigation', 'compliance violation'];
  var subject = emailData.subject.toLowerCase();
  
  for (var i = 0; i < dangerousKeywords.length; i++) {
    if (subject.indexOf(dangerousKeywords[i].toLowerCase()) !== -1) {
      return {
        blocked: true,
        rule: {
          rule_value: dangerousKeywords[i],
          action: 'never_draft',
          reason: 'Compliance/regulatory risk'
        }
      };
    }
  }
  
  return { blocked: false };
}

// ============================================
// GET CONTACT INFO (Using SQLite)
// ============================================

function getContactInfo(email) {
  /**
   * Get contact info from SQLite
   */
  
  var result = callPythonAPI('/contacts/' + encodeURIComponent(email), 'GET');
  
  if (result && result.contact) {
    Logger.log('Found contact info for: ' + email);
    Logger.log('  Preferred tone: ' + (result.contact.preferred_tone || 'not learned'));
    Logger.log('  Interactions: ' + result.contact.interaction_count);
    return result.contact;
  }
  
  Logger.log('No contact info found for: ' + email);
  return null;
}

// ============================================
// UPDATE USAGE STATS (Using SQLite)
// ============================================

function updatePatternUsage(patternName) {
  /**
   * Update pattern usage count in SQLite
   */
  
  var result = callPythonAPI('/patterns/' + encodeURIComponent(patternName) + '/use', 'POST');
  
  if (result) {
    Logger.log('✓ Updated usage for pattern: ' + patternName);
  }
}

function updateTemplateUsage(templateId) {
  /**
   * Update template usage count in SQLite
   */
  
  var result = callPythonAPI('/templates/' + encodeURIComponent(templateId) + '/use', 'POST');
  
  if (result) {
    Logger.log('✓ Updated usage for template: ' + templateId);
  }
}

// ============================================
// ENHANCED PROCESSING WITH SQLITE DATA
// ============================================

function processSingleEmailWithSQLite(emailData, instruction) {
  /**
   * Process email using SQLite patterns and templates
   */
  
  Logger.log('Processing with SQLite integration: ' + emailData.subject);
  Logger.log('Instruction: ' + instruction);
  
  // 1. Check safety overrides
  var safetyCheck = checkSafetyOverride(emailData);
  if (safetyCheck.blocked) {
    return {
      subject: emailData.subject,
      instruction: instruction,
      output: '⚠️  BLOCKED: ' + safetyCheck.rule.reason + '\n\nThis email requires human review.',
      confidence: 0,
      pattern: 'safety_override',
      success: false
    };
  }
  
  // 2. Get contact info (for personalization)
  var contactInfo = getContactInfo(emailData.sender);
  
  // 3. Match to pattern
  var patternMatch = matchEmailToPattern(emailData, instruction);
  
  if (patternMatch) {
    // Update usage stats
    updatePatternUsage(patternMatch.pattern_name);
    
    Logger.log('Pattern matched: ' + patternMatch.pattern_name);
    Logger.log('Pattern notes: ' + patternMatch.notes);
  }
  
  // 4. Determine data needs
  var dataNeeds = analyzeDataNeeds(instruction, emailData.body, emailData.subject);
  
  var geminiData = null;
  
  // 5. Call Gemini if needed
  if (dataNeeds.needsGemini) {
    Logger.log('Gemini data needed: ' + dataNeeds.geminiTask);
    geminiData = callGeminiForData(dataNeeds.geminiTask, emailData);
  }
  
  // 6. Build enhanced Claude input with SQLite context
  var claudeInput = {
    emailData: emailData,
    instruction: instruction,
    geminiData: geminiData,
    patternMatch: patternMatch,
    contactInfo: contactInfo,
    sqliteContext: {
      patterns: patternMatch ? [patternMatch] : [],
      contact_known: contactInfo !== null
    }
  };
  
  // 7. Call Claude with full context
  var result = callClaudeAPIWithSQLiteContext(claudeInput);
  
  return {
    subject: emailData.subject,
    instruction: instruction || 'auto-determined',
    output: result.output,
    confidence: result.confidence,
    pattern: patternMatch ? patternMatch.pattern_name : 'generic',
    success: true
  };
}

// ============================================
// CLAUDE API WITH SQLITE CONTEXT
// ============================================

function callClaudeAPIWithSQLiteContext(claudeInput) {
  /**
   * Call Claude API with SQLite context included
   */
  
  var apiKey = PropertiesService.getScriptProperties().getProperty('CLAUDE_API_KEY');
  
  if (!apiKey) {
    throw new Error('Claude API key not configured');
  }
  
  var prompt = buildEnhancedClaudePrompt(claudeInput);
  
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
    var response = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', options);
    var responseCode = response.getResponseCode();
    
    if (responseCode !== 200) {
      throw new Error('Claude API error: ' + response.getContentText());
    }
    
    var data = JSON.parse(response.getContentText());
    
    // Determine confidence based on pattern match
    var confidence = 50; // base
    if (claudeInput.patternMatch) {
      confidence += claudeInput.patternMatch.confidence_boost;
    }
    if (claudeInput.contactInfo) {
      confidence += 10; // known contact bonus
    }
    
    return {
      output: data.content[0].text,
      confidence: Math.min(100, confidence),
      pattern: claudeInput.patternMatch ? claudeInput.patternMatch.pattern_name : 'generic'
    };
    
  } catch (error) {
    Logger.log('Claude API error: ' + error.toString());
    throw error;
  }
}

function buildEnhancedClaudePrompt(claudeInput) {
  /**
   * Build Claude prompt with SQLite context
   */
  
  var emailData = claudeInput.emailData;
  var instruction = claudeInput.instruction;
  var geminiData = claudeInput.geminiData;
  var patternMatch = claudeInput.patternMatch;
  var contactInfo = claudeInput.contactInfo;
  
  var prompt = 'You are MCP, Derek\'s email processing assistant at Old City Capital.\n\n';
  
  // Add pattern context if available
  if (patternMatch) {
    prompt += '📋 PATTERN MATCH FROM DEREK\'S DATABASE:\n';
    prompt += 'Pattern: ' + patternMatch.pattern_name + '\n';
    prompt += 'Confidence boost: +' + patternMatch.confidence_boost + '%\n';
    prompt += 'Notes: ' + patternMatch.notes + '\n';
    prompt += 'Matched keywords: ' + patternMatch.matched_keywords.join(', ') + '\n\n';
  }
  
  // Add contact context if available
  if (contactInfo) {
    prompt += '👤 CONTACT INFO FROM DEREK\'S DATABASE:\n';
    prompt += 'Name: ' + contactInfo.contact_name + '\n';
    if (contactInfo.preferred_tone) {
      prompt += 'Preferred tone: ' + contactInfo.preferred_tone + '\n';
    }
    prompt += 'Previous interactions: ' + contactInfo.interaction_count + '\n\n';
  }
  
  prompt += 'Derek\'s instruction: "' + instruction + '"\n\n';
  
  prompt += 'Email:\n';
  prompt += '━'.repeat(60) + '\n';
  prompt += 'Subject: ' + emailData.subject + '\n';
  prompt += 'From: ' + emailData.senderName + ' (' + emailData.sender + ')\n';
  prompt += 'Date: ' + emailData.date + '\n\n';
  prompt += emailData.body + '\n';
  prompt += '━'.repeat(60) + '\n\n';
  
  // Add Gemini data if available
  if (geminiData && !geminiData.error) {
    prompt += 'Gemini Data (pre-fetched):\n';
    prompt += '━'.repeat(60) + '\n';
    prompt += JSON.stringify(geminiData, null, 2) + '\n';
    prompt += '━'.repeat(60) + '\n\n';
    prompt += 'This data has been pre-fetched. Interpret it and add business context.\n\n';
  }
  
  prompt += 'Process this email according to Derek\'s instruction.\n';
  prompt += 'Use the pattern and contact context from Derek\'s database to guide your response.';
  
  return prompt;
}

// ============================================
// TEST API CONNECTION
// ============================================

function testPythonAPIConnection() {
  /**
   * Test connection to Python SQLite API
   */
  
  Logger.log('Testing Python API connection...');
  Logger.log('API URL: ' + CONFIG.PYTHON_API_URL);
  
  // Test health endpoint
  var result = callPythonAPI('/health', 'GET');
  
  if (result) {
    Logger.log('✓ API is healthy');
    Logger.log('  Database: ' + result.database);
    Logger.log('  Patterns loaded: ' + result.patterns_loaded);
    Logger.log('  Timestamp: ' + result.timestamp);
    return true;
  } else {
    Logger.log('❌ API connection failed');
    Logger.log('  Make sure Python API server is running');
    Logger.log('  Command: python mcp_api_server.py');
    return false;
  }
}

function testPythonAPIStats() {
  /**
   * Get stats from Python API
   */
  
  var result = callPythonAPI('/stats', 'GET');
  
  if (result && result.stats) {
    Logger.log('SQLite Database Stats:');
    Logger.log('  Patterns: ' + result.stats.patterns);
    Logger.log('  Templates: ' + result.stats.templates);
    Logger.log('  Contacts learned: ' + result.stats.contacts_learned);
    Logger.log('  Writing patterns: ' + result.stats.writing_patterns_learned);
    Logger.log('  Emails processed: ' + result.stats.emails_processed);
    Logger.log('  Average edit rate: ' + result.stats.average_edit_rate + '%');
  } else {
    Logger.log('Could not fetch stats from API');
  }
}
