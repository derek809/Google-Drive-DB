#!/usr/bin/env python3
"""
MCP SQLite API Wrapper
Exposes SQLite database to Google Apps Script via HTTP API
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Allow Apps Script to call this API

# Database path - update this to your actual path
DB_PATH = os.path.join(os.path.dirname(__file__), 'mcp_learning.db')

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def dict_from_row(row):
    """Convert SQLite row to dictionary"""
    return dict(zip(row.keys(), row))

# ============================================
# ENDPOINT: Get all patterns
# ============================================

@app.route('/api/patterns', methods=['GET'])
def get_patterns():
    """Get all pattern hints"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pattern_id, pattern_name, keywords, trigger_subjects, 
                   confidence_boost, usage_count, success_rate, notes
            FROM pattern_hints
            ORDER BY confidence_boost DESC
        """)
        
        patterns = []
        for row in cursor.fetchall():
            pattern = dict_from_row(row)
            # Parse JSON fields
            pattern['keywords'] = json.loads(pattern['keywords']) if pattern['keywords'] else []
            pattern['trigger_subjects'] = json.loads(pattern['trigger_subjects']) if pattern['trigger_subjects'] else []
            patterns.append(pattern)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'patterns': patterns,
            'count': len(patterns)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Get specific pattern
# ============================================

@app.route('/api/patterns/<pattern_name>', methods=['GET'])
def get_pattern(pattern_name):
    """Get specific pattern by name"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pattern_id, pattern_name, keywords, trigger_subjects,
                   confidence_boost, usage_count, success_rate, notes
            FROM pattern_hints
            WHERE pattern_name = ?
        """, (pattern_name,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            pattern = dict_from_row(row)
            pattern['keywords'] = json.loads(pattern['keywords']) if pattern['keywords'] else []
            pattern['trigger_subjects'] = json.loads(pattern['trigger_subjects']) if pattern['trigger_subjects'] else []
            
            return jsonify({
                'success': True,
                'pattern': pattern
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Pattern not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Get all templates
# ============================================

@app.route('/api/templates', methods=['GET'])
def get_templates():
    """Get all templates"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT template_id, template_name, template_body, variables,
                   attachments, usage_count, success_rate
            FROM templates
            ORDER BY usage_count DESC
        """)
        
        templates = []
        for row in cursor.fetchall():
            template = dict_from_row(row)
            template['variables'] = json.loads(template['variables']) if template['variables'] else []
            template['attachments'] = json.loads(template['attachments']) if template['attachments'] else []
            templates.append(template)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'templates': templates,
            'count': len(templates)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Get specific template
# ============================================

@app.route('/api/templates/<template_id>', methods=['GET'])
def get_template(template_id):
    """Get specific template"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT template_id, template_name, template_body, variables,
                   attachments, usage_count, success_rate
            FROM templates
            WHERE template_id = ?
        """, (template_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            template = dict_from_row(row)
            template['variables'] = json.loads(template['variables']) if template['variables'] else []
            template['attachments'] = json.loads(template['attachments']) if template['attachments'] else []
            
            return jsonify({
                'success': True,
                'template': template
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Template not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Get all tools
# ============================================

@app.route('/api/tools', methods=['GET'])
def get_tools():
    """Get all existing tools"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT tool_id, tool_name, tool_type, use_case, trigger_condition,
                   success_count, failure_count, notes
            FROM existing_tools
        """)
        
        tools = []
        for row in cursor.fetchall():
            tools.append(dict_from_row(row))
        
        conn.close()
        
        return jsonify({
            'success': True,
            'tools': tools,
            'count': len(tools)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Match pattern
# ============================================

@app.route('/api/match-pattern', methods=['POST'])
def match_pattern():
    """Match email content to patterns"""
    try:
        data = request.json
        subject = data.get('subject', '')
        body = data.get('body', '')
        instruction = data.get('instruction', '')
        
        combined_text = f"{subject} {body} {instruction}".lower()
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pattern_id, pattern_name, keywords, confidence_boost, notes
            FROM pattern_hints
            ORDER BY confidence_boost DESC
        """)
        
        matches = []
        
        for row in cursor.fetchall():
            pattern = dict_from_row(row)
            keywords = json.loads(pattern['keywords']) if pattern['keywords'] else []
            
            # Check if any keywords match
            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    matched_keywords.append(keyword)
            
            if matched_keywords:
                matches.append({
                    'pattern_name': pattern['pattern_name'],
                    'confidence_boost': pattern['confidence_boost'],
                    'matched_keywords': matched_keywords,
                    'notes': pattern['notes']
                })
        
        conn.close()
        
        # Sort by confidence boost
        matches.sort(key=lambda x: x['confidence_boost'], reverse=True)
        
        return jsonify({
            'success': True,
            'matches': matches,
            'best_match': matches[0] if matches else None
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Get contact patterns
# ============================================

@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    """Get learned contact patterns"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT contact_email, contact_name, relationship_type,
                   preferred_tone, common_topics, interaction_count
            FROM contact_patterns
            ORDER BY interaction_count DESC
        """)
        
        contacts = []
        for row in cursor.fetchall():
            contact = dict_from_row(row)
            contact['common_topics'] = json.loads(contact['common_topics']) if contact['common_topics'] else []
            contacts.append(contact)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'contacts': contacts,
            'count': len(contacts)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Get contact by email
# ============================================

@app.route('/api/contacts/<email>', methods=['GET'])
def get_contact(email):
    """Get specific contact info"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT contact_email, contact_name, relationship_type,
                   preferred_tone, common_topics, interaction_count
            FROM contact_patterns
            WHERE contact_email = ?
        """, (email,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            contact = dict_from_row(row)
            contact['common_topics'] = json.loads(contact['common_topics']) if contact['common_topics'] else []
            
            return jsonify({
                'success': True,
                'contact': contact
            })
        else:
            return jsonify({
                'success': False,
                'contact': None,
                'message': 'Contact not yet learned'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Get writing patterns
# ============================================

@app.route('/api/writing-patterns', methods=['GET'])
def get_writing_patterns():
    """Get learned writing patterns"""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT phrase, context, recipient_type, frequency
            FROM writing_patterns
            ORDER BY frequency DESC
            LIMIT ?
        """, (limit,))
        
        patterns = []
        for row in cursor.fetchall():
            patterns.append(dict_from_row(row))
        
        conn.close()
        
        return jsonify({
            'success': True,
            'patterns': patterns,
            'count': len(patterns)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Get safety overrides
# ============================================

@app.route('/api/overrides', methods=['GET'])
def get_overrides():
    """Get safety override rules"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT rule_type, rule_value, action, reason
            FROM overrides
            WHERE is_active = 1
        """)
        
        overrides = []
        for row in cursor.fetchall():
            overrides.append(dict_from_row(row))
        
        conn.close()
        
        return jsonify({
            'success': True,
            'overrides': overrides,
            'count': len(overrides)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Check safety override
# ============================================

@app.route('/api/check-override', methods=['POST'])
def check_override():
    """Check if email matches any safety overrides"""
    try:
        data = request.json
        subject = data.get('subject', '')
        sender = data.get('sender', '')
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check subject keywords
        cursor.execute("""
            SELECT rule_type, rule_value, action, reason
            FROM overrides
            WHERE is_active = 1 AND rule_type = 'subject_keyword'
        """)
        
        blocked = False
        matched_rule = None
        
        for row in cursor.fetchall():
            rule = dict_from_row(row)
            if rule['rule_value'].lower() in subject.lower():
                blocked = True
                matched_rule = rule
                break
        
        # Check sender overrides
        if not blocked:
            cursor.execute("""
                SELECT rule_type, rule_value, action, reason
                FROM overrides
                WHERE is_active = 1 AND rule_type = 'sender' AND rule_value = ?
            """, (sender,))
            
            row = cursor.fetchone()
            if row:
                blocked = True
                matched_rule = dict_from_row(row)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'blocked': blocked,
            'rule': matched_rule,
            'action': matched_rule['action'] if matched_rule else None
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Update pattern usage
# ============================================

@app.route('/api/patterns/<pattern_name>/use', methods=['POST'])
def update_pattern_usage(pattern_name):
    """Update pattern usage count"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE pattern_hints
            SET usage_count = usage_count + 1,
                last_updated = ?
            WHERE pattern_name = ?
        """, (datetime.now().isoformat(), pattern_name))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Updated usage for {pattern_name}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Update template usage
# ============================================

@app.route('/api/templates/<template_id>/use', methods=['POST'])
def update_template_usage(template_id):
    """Update template usage count"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE templates
            SET usage_count = usage_count + 1,
                last_used = ?
            WHERE template_id = ?
        """, (datetime.now().isoformat(), template_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Updated usage for {template_id}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: Health check
# ============================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pattern_hints")
        pattern_count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'database': 'connected',
            'patterns_loaded': pattern_count,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# ============================================
# ENDPOINT: System stats
# ============================================

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get counts from various tables
        cursor.execute("SELECT COUNT(*) FROM pattern_hints")
        pattern_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM templates")
        template_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM contact_patterns")
        contact_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM writing_patterns")
        writing_pattern_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM responses WHERE sent = 1")
        emails_processed = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(edit_percentage) FROM responses WHERE sent = 1")
        avg_edit_rate = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'patterns': pattern_count,
                'templates': template_count,
                'contacts_learned': contact_count,
                'writing_patterns_learned': writing_pattern_count,
                'emails_processed': emails_processed,
                'average_edit_rate': round(avg_edit_rate, 2)
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# RUN SERVER
# ============================================

if __name__ == '__main__':
    print('=' * 60)
    print('MCP SQLite API Server')
    print('=' * 60)
    print(f'Database: {DB_PATH}')
    print('Starting server on http://localhost:5000')
    print('')
    print('Available endpoints:')
    print('  GET  /api/health - Health check')
    print('  GET  /api/stats - System statistics')
    print('  GET  /api/patterns - All patterns')
    print('  GET  /api/patterns/<name> - Specific pattern')
    print('  GET  /api/templates - All templates')
    print('  GET  /api/templates/<id> - Specific template')
    print('  GET  /api/tools - All tools')
    print('  GET  /api/contacts - All contacts')
    print('  GET  /api/contacts/<email> - Specific contact')
    print('  GET  /api/writing-patterns - Writing patterns')
    print('  GET  /api/overrides - Safety overrides')
    print('  POST /api/match-pattern - Match email to pattern')
    print('  POST /api/check-override - Check safety override')
    print('=' * 60)
    print('')
    
    app.run(host='0.0.0.0', port=5000, debug=True)
