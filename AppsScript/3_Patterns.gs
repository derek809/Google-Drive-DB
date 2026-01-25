/**
 * 3_PATTERNS.GS - Pattern Matching & Templates
 * =============================================
 *
 * Handles:
 * - Reading patterns from MCP sheet
 * - Pattern matching against email content
 * - Template retrieval and usage tracking
 * - Contact learning
 */

// ============================================
// PATTERN FUNCTIONS
// ============================================

/**
 * Get all patterns from the MCP sheet (columns J-O)
 * @returns {Array} Array of pattern objects
 */
function getPatternsFromSheet() {
  try {
    var sheet = getMainSheet();

    // Patterns are in columns J-O (10-15), starting at row 2
    var patternNames = sheet.getRange(2, 10, 20, 1).getValues();
    var patternCount = 0;

    for (var i = 0; i < patternNames.length; i++) {
      if (patternNames[i][0]) patternCount++;
      else break;
    }

    if (patternCount === 0) return getHardcodedPatterns();

    var data = sheet.getRange(2, 10, patternCount, 6).getValues();
    var patterns = [];

    data.forEach(function(row) {
      if (row[0]) {
        patterns.push({
          pattern_name: row[0],
          keywords: row[1].split(',').map(function(k) { return k.trim().toLowerCase(); }),
          confidence_boost: row[2] || 0,
          usage_count: row[3] || 0,
          success_rate: row[4] || 0,
          notes: row[5] || ''
        });
      }
    });

    return patterns;

  } catch (e) {
    Logger.log('Error getting patterns: ' + e);
    return getHardcodedPatterns();
  }
}

/**
 * Fallback patterns if sheet read fails
 */
function getHardcodedPatterns() {
  return [
    { pattern_name: 'invoice_processing', keywords: ['invoice', 'fees', 'mgmt', 'q3', 'q4', 'quarterly'], confidence_boost: 15, notes: 'Route to Claude Project or Google Script' },
    { pattern_name: 'w9_wiring_request', keywords: ['w9', 'w-9', 'wiring instructions', 'wire details'], confidence_boost: 20, notes: 'Use w9_response template' },
    { pattern_name: 'payment_confirmation', keywords: ['payment', 'wire', 'received', 'ocs payment'], confidence_boost: 15, notes: 'Check NetSuite for confirmation' },
    { pattern_name: 'producer_statements', keywords: ['producer statements', 'producer report'], confidence_boost: 10, notes: 'Weekly Friday task' },
    { pattern_name: 'delegation_eytan', keywords: ['insufficient info', 'not sure', 'need eytan', 'loop in eytan'], confidence_boost: 0, notes: 'Use delegation_eytan template' },
    { pattern_name: 'turnaround_expectation', keywords: ['how long', 'timeline', 'when', 'deadline'], confidence_boost: 5, notes: 'Use turnaround_time template' },
    { pattern_name: 'journal_entry_reminder', keywords: ['je', 'journal entry', 'partner compensation'], confidence_boost: 0, notes: 'Knowledge base lookup' }
  ];
}

/**
 * Match email content to a pattern
 * @param {Object} emailData - {subject, body, sender}
 * @param {string} instruction - User's instruction/prompt
 * @returns {Object|null} Best matching pattern or null
 */
function matchEmailToPattern(emailData, instruction) {
  var patterns = getPatternsFromSheet();
  var combined = (
    (emailData.subject || '') + ' ' +
    (emailData.body || '') + ' ' +
    (instruction || '')
  ).toLowerCase();

  var bestMatch = null;
  var bestScore = 0;

  patterns.forEach(function(pattern) {
    var matchCount = 0;
    var matchedKeywords = [];

    pattern.keywords.forEach(function(keyword) {
      if (combined.indexOf(keyword) !== -1) {
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
        notes: pattern.notes,
        match_score: matchCount
      };
    }
  });

  if (bestMatch) {
    Logger.log('Pattern match: ' + bestMatch.pattern_name + ' (score: ' + bestMatch.match_score + ')');
  }

  return bestMatch;
}

/**
 * Update pattern usage count in the MCP sheet
 * @param {string} patternName - Name of pattern to update
 */
function updatePatternUsage(patternName) {
  try {
    var sheet = getMainSheet();
    var patternNames = sheet.getRange(2, 10, 20, 1).getValues();

    for (var i = 0; i < patternNames.length; i++) {
      if (patternNames[i][0] === patternName) {
        var currentCount = sheet.getRange(i + 2, 13).getValue() || 0;
        sheet.getRange(i + 2, 13).setValue(currentCount + 1);
        Logger.log('Updated usage for pattern: ' + patternName + ' -> ' + (currentCount + 1));
        return;
      }
    }
  } catch (e) {
    Logger.log('Error updating pattern usage: ' + e);
  }
}

/**
 * Update pattern success rate
 * @param {string} patternName - Name of pattern
 * @param {boolean} wasSuccessful - Whether the response was used without edits
 */
function updatePatternSuccess(patternName, wasSuccessful) {
  try {
    var sheet = getMainSheet();
    var patternNames = sheet.getRange(2, 10, 20, 1).getValues();

    for (var i = 0; i < patternNames.length; i++) {
      if (patternNames[i][0] === patternName) {
        var usage = sheet.getRange(i + 2, 13).getValue() || 1;
        var currentRate = sheet.getRange(i + 2, 14).getValue() || 0;

        // Calculate new success rate
        var successes = Math.round(currentRate * (usage - 1) / 100);
        if (wasSuccessful) successes++;
        var newRate = Math.round((successes / usage) * 100);

        sheet.getRange(i + 2, 14).setValue(newRate);
        Logger.log('Updated success rate for ' + patternName + ': ' + newRate + '%');
        return;
      }
    }
  } catch (e) {
    Logger.log('Error updating pattern success: ' + e);
  }
}

// ============================================
// TEMPLATE FUNCTIONS
// ============================================

/**
 * Get all templates from the Templates sheet
 * @returns {Array} Array of template objects
 */
function getTemplatesFromSheet() {
  try {
    var sheet = getTemplatesSheet();
    if (!sheet) return getHardcodedTemplates();

    var lastRow = sheet.getLastRow();
    if (lastRow <= 1) return getHardcodedTemplates();

    var data = sheet.getRange(2, 1, lastRow - 1, 6).getValues();
    var templates = [];

    data.forEach(function(row) {
      if (row[0]) {
        templates.push({
          template_id: row[0],
          template_name: row[1],
          template_body: row[2],
          variables: row[3] ? row[3].split(',').map(function(v) { return v.trim(); }) : [],
          attachments: row[4] ? row[4].split(',').map(function(a) { return a.trim(); }) : [],
          usage_count: row[5] || 0
        });
      }
    });

    return templates;

  } catch (e) {
    Logger.log('Error getting templates: ' + e);
    return getHardcodedTemplates();
  }
}

/**
 * Fallback templates
 */
function getHardcodedTemplates() {
  return [
    { template_id: 'w9_response', template_name: 'W9 & Wiring Instructions', template_body: 'Hi {name},\n\nHere\'s our W9 form (attached).\n\nOur wiring instructions:\n{wiring_details}\n\nLet me know if you need anything else!\n\nBest,\nDerek', variables: ['name', 'wiring_details'], attachments: ['OldCity_W9.pdf'] },
    { template_id: 'payment_confirmation', template_name: 'Payment Received Confirmation', template_body: 'Hi {name},\n\nConfirmed - we received payment of ${amount} on {date}.\n\nThank you!\n\nBest,\nDerek', variables: ['name', 'amount', 'date'], attachments: [] },
    { template_id: 'delegation_eytan', template_name: 'Loop in Eytan', template_body: 'Hi {name},\n\nLooping in Eytan for his input on this.\n\nEytan - {context}\n\nThanks,\nDerek', variables: ['name', 'context'], attachments: [] },
    { template_id: 'turnaround_time', template_name: 'Turnaround Time Expectation', template_body: 'Hi {name},\n\nOur typical turnaround for {request_type} is {timeline}.\n\nI\'ll have this back to you by {specific_date}.\n\nLet me know if you need it sooner.\n\nBest,\nDerek', variables: ['name', 'request_type', 'timeline', 'specific_date'], attachments: [] }
  ];
}

/**
 * Get a specific template by ID
 * @param {string} templateId - Template ID to find
 * @returns {Object|null} Template object or null
 */
function getTemplate(templateId) {
  var templates = getTemplatesFromSheet();

  for (var i = 0; i < templates.length; i++) {
    if (templates[i].template_id === templateId) {
      return templates[i];
    }
  }

  return null;
}

/**
 * Update template usage count
 * @param {string} templateId - Template ID to update
 */
function updateTemplateUsage(templateId) {
  try {
    var sheet = getTemplatesSheet();
    if (!sheet) return;

    var lastRow = sheet.getLastRow();
    var ids = sheet.getRange(2, 1, lastRow - 1, 1).getValues();

    for (var i = 0; i < ids.length; i++) {
      if (ids[i][0] === templateId) {
        var currentCount = sheet.getRange(i + 2, 6).getValue() || 0;
        sheet.getRange(i + 2, 6).setValue(currentCount + 1);
        Logger.log('Updated usage for template: ' + templateId);
        return;
      }
    }
  } catch (e) {
    Logger.log('Error updating template usage: ' + e);
  }
}

/**
 * Fill template variables with values
 * @param {string} templateBody - Template text with {variables}
 * @param {Object} values - Object with variable values
 * @returns {string} Filled template
 */
function fillTemplate(templateBody, values) {
  var result = templateBody;

  for (var key in values) {
    if (values.hasOwnProperty(key)) {
      var regex = new RegExp('\\{' + key + '\\}', 'g');
      result = result.replace(regex, values[key] || '');
    }
  }

  return result;
}

// ============================================
// CONTACT LEARNING
// ============================================

/**
 * Learn a new contact or update existing
 * @param {string} email - Contact email
 * @param {string} name - Contact name
 * @param {string} relationshipType - Type of relationship
 */
function learnContact(email, name, relationshipType) {
  try {
    var sheet = getContactsSheet();
    if (!sheet) return;

    var lastRow = sheet.getLastRow();

    // Check if contact exists
    if (lastRow > 1) {
      var emails = sheet.getRange(2, 1, lastRow - 1, 1).getValues();

      for (var i = 0; i < emails.length; i++) {
        if (emails[i][0] && emails[i][0].toLowerCase() === email.toLowerCase()) {
          // Update interaction count
          var count = sheet.getRange(i + 2, 6).getValue() || 0;
          sheet.getRange(i + 2, 6).setValue(count + 1);
          sheet.getRange(i + 2, 7).setValue(new Date());
          Logger.log('Updated contact: ' + email + ' (interactions: ' + (count + 1) + ')');
          return;
        }
      }
    }

    // Add new contact
    sheet.appendRow([
      email,
      name || '',
      relationshipType || 'external',
      '',  // preferred tone (learned later)
      '',  // common topics (learned later)
      1,   // interactions
      new Date()
    ]);

    Logger.log('Learned new contact: ' + email);

  } catch (e) {
    Logger.log('Error learning contact: ' + e);
  }
}

/**
 * Check if contact is known
 * @param {string} email - Email to check
 * @returns {boolean} True if contact exists
 */
function isKnownContact(email) {
  try {
    var sheet = getContactsSheet();
    if (!sheet) return false;

    var lastRow = sheet.getLastRow();
    if (lastRow <= 1) return false;

    var emails = sheet.getRange(2, 1, lastRow - 1, 1).getValues();

    for (var i = 0; i < emails.length; i++) {
      if (emails[i][0] && emails[i][0].toLowerCase() === email.toLowerCase()) {
        return true;
      }
    }

    return false;

  } catch (e) {
    Logger.log('Error checking contact: ' + e);
    return false;
  }
}

/**
 * Get contact info
 * @param {string} email - Email to look up
 * @returns {Object|null} Contact info or null
 */
function getContactInfo(email) {
  try {
    var sheet = getContactsSheet();
    if (!sheet) return null;

    var lastRow = sheet.getLastRow();
    if (lastRow <= 1) return null;

    var data = sheet.getRange(2, 1, lastRow - 1, 7).getValues();

    for (var i = 0; i < data.length; i++) {
      if (data[i][0] && data[i][0].toLowerCase() === email.toLowerCase()) {
        return {
          email: data[i][0],
          name: data[i][1],
          relationship: data[i][2],
          preferred_tone: data[i][3],
          common_topics: data[i][4],
          interactions: data[i][5],
          last_contact: data[i][6]
        };
      }
    }

    return null;

  } catch (e) {
    Logger.log('Error getting contact: ' + e);
    return null;
  }
}
