// ============================================
// MCP BATCH PROCESSOR - WITH SYNC ENDPOINT
// Version 3.0 - Receives updates from Python sync script
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
// WEB APP ENDPOINT - Receives Pattern Updates
// ============================================

function doPost(e) {
  /**
   * Receives pattern updates from Python sync script
   * Stores in Script Properties for fast access during batch processing
   */
  
  try {
    // Parse incoming data
    var data = JSON.parse(e.postData.contents);
    
    if (data.action !== 'update_patterns') {
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        message: 'Unknown action: ' + data.action
      })).setMimeType(ContentService.MimeType.JSON);
    }
    
    // Store patterns in Script Properties (fast cache)
    var props = PropertiesService.getScriptProperties();
    
    props.setProperties({
      'patterns': JSON.stringify(data.patterns),
      'templates': JSON.stringify(data.templates),
      'stats': JSON.stringify(data.stats),
      'last_sync': data.timestamp || new Date().toISOString()
    });
    
    Logger.log('✓ Patterns updated: ' + data.patterns.length + ' patterns');
    Logger.log('✓ Templates updated: ' + data.templates.length + ' templates');
    Logger.log('✓ Last sync: ' + data.timestamp);
    
    return ContentService.createTextOutput(JSON.stringify({
      success: true,
      message: 'Patterns updated successfully',
      patterns_count: data.patterns.length,
      templates_count: data.templates.length,
      timestamp: new Date().toISOString()
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (error) {
    Logger.log('Error in doPost: ' + error.toString());
    
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      message: 'Error: ' + error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  /**
   * Simple GET endpoint for testing
   */
  
  var props = PropertiesService.getScriptProperties();
  var lastSync = props.getProperty('last_sync') || 'Never';
  
  var html = '<h1>MCP Apps Script Endpoint</h1>' +
             '<p>Status: <strong>Active</strong></p>' +
             '<p>Last Sync: <strong>' + lastSync + '</strong></p>' +
             '<p>Use POST to update patterns</p>';
  
  return HtmlService.createHtmlOutput(html);
}

// ============================================
// GET PATTERNS FROM SCRIPT PROPERTIES
// ============================================

function getPatterns() {
  /**
   * Get patterns from Script Properties (cached from sync)
   * Falls back to hardcoded patterns if none cached
   */
  
  var props = PropertiesService.getScriptProperties();
  var patternsJson = props.getProperty('patterns');
  
  if (patternsJson) {
    try {
      var patterns = JSON.parse(patternsJson);
      Logger.log('✓ Loaded ' + patterns.length + ' patterns from cache');
      return patterns;
    } catch (error) {
      Logger.log('Error parsing cached patterns: ' + error.toString());
      Logger.log('Falling back to hardcoded patterns');
    }
  } else {
    Logger.log('No cached patterns found - using hardcoded fallback');
  }
  
  // Fallback to hardcoded patterns
  return getHardcodedPatterns();
}

function getTemplates() {
  /**
   * Get templates from Script Properties (cached from sync)
   * Falls back to hardcoded templates if none cached
   */
  
  var props = PropertiesService.getScriptProperties();
  var templatesJson = props.getProperty('templates');
  
  if (templatesJson) {
    try {
      var templates = JSON.parse(templatesJson);
      Logger.log('✓ Loaded ' + templates.length + ' templates from cache');
      return templates;
    } catch (error) {
      Logger.log('Error parsing cached templates: ' + error.toString());
      Logger.log('Falling back to hardcoded templates');
    }
  } else {
    Logger.log('No cached templates found - using hardcoded fallback');
  }
  
  // Fallback to hardcoded templates
  return getHardcodedTemplates();
}

function getStats() {
  /**
   * Get stats from Script Properties
   */
  
  var props = PropertiesService.getScriptProperties();
  var statsJson = props.getProperty('stats');
  
  if (statsJson) {
    try {
      return JSON.parse(statsJson);
    } catch (error) {
      Logger.log('Error parsing stats: ' + error.toString());
    }
  }
  
  return null;
}

// ============================================
// HARDCODED FALLBACK PATTERNS
// ============================================

function getHardcodedPatterns() {
  /**
   * Fallback patterns - used only if sync hasn't run yet
   * These will be replaced by cached patterns after first sync
   */
  return [
    {
      pattern_name: 'invoice_processing',
      keywords: ['invoice', 'fees', 'mgmt', 'Q3', 'Q4', 'quarterly'],
      confidence_boost: 15,
      usage_count: 0,
      success_rate: 0.0,
      notes: 'Route to Claude Project or Google Script'
    },
    {
      pattern_name: 'w9_wiring_request',
      keywords: ['w9', 'w-9', 'wiring instructions', 'wire details'],
      confidence_boost: 20,
      usage_count: 0,
      success_rate: 0.0,
      notes: 'Use w9_response template'
    },
    {
      pattern_name: 'payment_confirmation',
      keywords: ['payment', 'wire', 'received', 'OCS Payment'],
      confidence_boost: 15,
      usage_count: 0,
      success_rate: 0.0,
      notes: 'Check NetSuite for confirmation'
    },
    {
      pattern_name: 'producer_statements',
      keywords: ['producer statements', 'producer report'],
      confidence_boost: 10,
      usage_count: 0,
      success_rate: 0.0,
      notes: 'Weekly Friday task'
    },
    {
      pattern_name: 'delegation_eytan',
      keywords: ['insufficient info', 'not sure', 'need eytan', 'loop in eytan'],
      confidence_boost: 0,
      usage_count: 0,
      success_rate: 0.0,
      notes: 'Use delegation_eytan template'
    },
    {
      pattern_name: 'turnaround_expectation',
      keywords: ['how long', 'timeline', 'when', 'deadline'],
      confidence_boost: 5,
      usage_count: 0,
      success_rate: 0.0,
      notes: 'Use turnaround_time template'
    },
    {
      pattern_name: 'journal_entry_reminder',
      keywords: ['JE', 'journal entry', 'partner compensation'],
      confidence_boost: 0,
      usage_count: 0,
      success_rate: 0.0,
      notes: 'Knowledge base lookup'
    }
  ];
}

function getHardcodedTemplates() {
  /**
   * Fallback templates - used only if sync hasn't run yet
   */
  return [
    {
      template_id: 'w9_response',
      template_name: 'W9 & Wiring Instructions',
      template_body: 'Hi {name},\n\nHere\'s our W9 form (attached).\n\nOur wiring instructions:\n{wiring_details}\n\nLet me know if you need anything else!\n\nBest,\nDerek',
      variables: ['name', 'wiring_details'],
      attachments: ['OldCity_W9.pdf'],
      usage_count: 0,
      success_rate: 0.0
    },
    {
      template_id: 'payment_confirmation',
      template_name: 'Payment Received Confirmation',
      template_body: 'Hi {name},\n\nConfirmed - we received payment of ${amount} on {date}.\n\nThank you!\n\nBest,\nDerek',
      variables: ['name', 'amount', 'date'],
      attachments: [],
      usage_count: 0,
      success_rate: 0.0
    },
    {
      template_id: 'delegation_eytan',
      template_name: 'Loop in Eytan',
      template_body: 'Hi {name},\n\nLooping in Eytan for his input on this.\n\nEytan - {context}\n\nThanks,\nDerek',
      variables: ['name', 'context'],
      attachments: [],
      usage_count: 0,
      success_rate: 0.0
    },
    {
      template_id: 'turnaround_time',
      template_name: 'Turnaround Time Expectation',
      template_body: 'Hi {name},\n\nOur typical turnaround for {request_type} is {timeline}.\n\nI\'ll have this back to you by {specific_date}.\n\nLet me know if you need it sooner.\n\nBest,\nDerek',
      variables: ['name', 'request_type', 'timeline', 'specific_date'],
      attachments: [],
      usage_count: 0,
      success_rate: 0.0
    }
  ];
}

// ============================================
// PATTERN MATCHING WITH CACHED DATA
// ============================================

function matchEmailToPattern(emailData, instruction) {
  /**
   * Match email to pattern using cached data from sync
   */
  
  var patterns = getPatterns();
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
  
  if (bestMatch) {
    Logger.log('Pattern matched: ' + bestMatch.pattern_name);
    Logger.log('  Confidence boost: +' + bestMatch.confidence_boost);
    Logger.log('  Matched keywords: ' + bestMatch.matched_keywords.join(', '));
  }
  
  return bestMatch;
}

// ============================================
// TEST FUNCTIONS
// ============================================

function testCachedPatterns() {
  /**
   * Test reading patterns from cache
   */
  Logger.log('Testing cached patterns...');
  
  var patterns = getPatterns();
  Logger.log('✓ Loaded ' + patterns.length + ' patterns');
  
  patterns.forEach(function(pattern) {
    Logger.log('  - ' + pattern.pattern_name + ' (+' + pattern.confidence_boost + ')');
  });
  
  var props = PropertiesService.getScriptProperties();
  var lastSync = props.getProperty('last_sync') || 'Never';
  Logger.log('Last sync: ' + lastSync);
}

function testPatternMatch() {
  /**
   * Test pattern matching with cached data
   */
  Logger.log('Testing pattern matching...');
  
  var testEmail = {
    subject: 'W9 Request',
    body: 'Hi Derek, please send your W9 and wiring instructions',
    sender: 'test@example.com'
  };
  
  var match = matchEmailToPattern(testEmail, 'send w9');
  
  if (match) {
    Logger.log('✓ Matched: ' + match.pattern_name);
    Logger.log('  Confidence: +' + match.confidence_boost);
    Logger.log('  Keywords: ' + match.matched_keywords.join(', '));
  } else {
    Logger.log('✗ No match found');
  }
}

function showSyncStatus() {
  /**
   * Show current sync status and statistics
   */
  var props = PropertiesService.getScriptProperties();
  
  Logger.log('=' * 60);
  Logger.log('MCP APPS SCRIPT STATUS');
  Logger.log('=' * 60);
  
  var lastSync = props.getProperty('last_sync');
  if (lastSync) {
    Logger.log('Last Sync: ' + lastSync);
    
    var stats = getStats();
    if (stats) {
      Logger.log('');
      Logger.log('Statistics:');
      Logger.log('  Total Patterns: ' + stats.total_patterns);
      Logger.log('  Total Templates: ' + stats.total_templates);
      Logger.log('  Contacts Learned: ' + stats.contacts_learned);
      Logger.log('  Writing Patterns: ' + stats.writing_patterns);
      Logger.log('  Emails Processed: ' + stats.emails_processed);
      Logger.log('  Average Edit Rate: ' + stats.avg_edit_rate + '%');
    }
    
    Logger.log('');
    Logger.log('Cached Patterns: ' + getPatterns().length);
    Logger.log('Cached Templates: ' + getTemplates().length);
    Logger.log('');
    Logger.log('✓ System ready for batch processing');
  } else {
    Logger.log('⚠️  No sync data found');
    Logger.log('');
    Logger.log('Run the sync script to update patterns:');
    Logger.log('  1. Double-click "Sync MCP to Apps Script.bat"');
    Logger.log('  2. Or run: python sync_to_apps_script.py');
    Logger.log('');
    Logger.log('Using hardcoded fallback patterns until sync runs.');
  }
  
  Logger.log('=' * 60);
}

function clearCache() {
  /**
   * Clear cached patterns (for testing)
   */
  var props = PropertiesService.getScriptProperties();
  props.deleteProperty('patterns');
  props.deleteProperty('templates');
  props.deleteProperty('stats');
  props.deleteProperty('last_sync');
  
  Logger.log('✓ Cache cleared');
  Logger.log('Run sync script to repopulate');
}

// ============================================
// SETUP FUNCTION
// ============================================

function setupSyncEndpoint() {
  /**
   * Setup instructions for the sync endpoint
   */
  
  Logger.log('=' * 60);
  Logger.log('MCP SYNC ENDPOINT SETUP');
  Logger.log('=' * 60);
  Logger.log('');
  Logger.log('1. Deploy this Apps Script as a Web App:');
  Logger.log('   - Click Deploy > New deployment');
  Logger.log('   - Type: Web app');
  Logger.log('   - Execute as: Me');
  Logger.log('   - Who has access: Anyone');
  Logger.log('   - Click Deploy');
  Logger.log('   - Copy the Web App URL');
  Logger.log('');
  Logger.log('2. Update sync_to_apps_script.py:');
  Logger.log('   - Edit the Python file');
  Logger.log('   - Update APPS_SCRIPT_WEB_APP_URL');
  Logger.log('   - Paste your Web App URL');
  Logger.log('');
  Logger.log('3. Run the sync script:');
  Logger.log('   - Double-click "Sync MCP to Apps Script.bat"');
  Logger.log('   - Or run: python sync_to_apps_script.py');
  Logger.log('');
  Logger.log('4. Verify it worked:');
  Logger.log('   - Run showSyncStatus() in this script');
  Logger.log('   - Should show "Last Sync" timestamp');
  Logger.log('');
  Logger.log('=' * 60);
}
