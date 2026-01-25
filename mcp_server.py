#!/usr/bin/env python3
"""
MCP Server for Claude Desktop
Exposes email processing tools to Claude via Model Context Protocol

This server runs locally on your machine (FREE - no additional API costs).
Claude Desktop connects to it and can directly query your learning database.

Tools exposed:
- process_email: Process an email with MCP system
- get_patterns: List all learned patterns
- get_templates: List available email templates
- record_edit: Record your edits for learning
- get_contacts: Get learned contact preferences
- get_stats: Get system statistics
"""

import asyncio
import json
import os
import sqlite3
from datetime import datetime
from typing import Any

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP SDK not installed. Run: pip install mcp")
    print("Or: pip install anthropic[mcp]")
    exit(1)

# Get database path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "mcp_learning.db")

# Create server instance
server = Server("mcp-email-processor")


# ============================================
# DATABASE HELPERS
# ============================================

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dict_from_row(row):
    """Convert SQLite row to dictionary."""
    return dict(zip(row.keys(), row)) if row else None


# ============================================
# TOOL DEFINITIONS
# ============================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="process_email",
            description="Process an email through the MCP system. Matches patterns, calculates confidence, and routes to appropriate template or action.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "Email subject line"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content"
                    },
                    "sender_email": {
                        "type": "string",
                        "description": "Sender's email address"
                    },
                    "sender_name": {
                        "type": "string",
                        "description": "Sender's name (optional)"
                    },
                    "instruction": {
                        "type": "string",
                        "description": "What you want done with this email (e.g., 'send w9', 'draft reply', 'extract info')"
                    }
                },
                "required": ["subject", "body", "sender_email", "instruction"]
            }
        ),
        Tool(
            name="get_patterns",
            description="Get all learned email patterns from the database. Shows keywords, confidence boosts, and success rates.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_templates",
            description="Get all available email templates. Use these for quick responses to common email types.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_template",
            description="Get a specific email template by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "template_id": {
                        "type": "string",
                        "description": "Template ID (e.g., 'w9_response', 'payment_confirmation')"
                    }
                },
                "required": ["template_id"]
            }
        ),
        Tool(
            name="record_edit",
            description="Record your edits to a draft for learning. Compares what MCP generated vs what you actually sent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "response_id": {
                        "type": "integer",
                        "description": "Response ID from previous process_email call"
                    },
                    "final_text": {
                        "type": "string",
                        "description": "The actual text you sent (after your edits)"
                    },
                    "was_sent": {
                        "type": "boolean",
                        "description": "True if you sent it, False if you deleted/discarded it",
                        "default": True
                    }
                },
                "required": ["response_id", "final_text"]
            }
        ),
        Tool(
            name="get_contacts",
            description="Get learned contact preferences. Shows preferred tone, common topics, and interaction history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Contact email to look up (optional - omit to get all contacts)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_stats",
            description="Get MCP system statistics: patterns, templates, contacts learned, emails processed, success rates.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="learn_contact",
            description="Add or update a contact's preferences in the learning database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "Contact's email address"
                    },
                    "name": {
                        "type": "string",
                        "description": "Contact's name"
                    },
                    "preferred_tone": {
                        "type": "string",
                        "description": "How to address them: 'formal', 'casual', 'professional'",
                        "enum": ["formal", "casual", "professional"]
                    },
                    "notes": {
                        "type": "string",
                        "description": "Any notes about this contact"
                    }
                },
                "required": ["email", "name"]
            }
        )
    ]


# ============================================
# TOOL IMPLEMENTATIONS
# ============================================

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    if name == "process_email":
        return await process_email_tool(arguments)
    elif name == "get_patterns":
        return await get_patterns_tool()
    elif name == "get_templates":
        return await get_templates_tool()
    elif name == "get_template":
        return await get_template_tool(arguments)
    elif name == "record_edit":
        return await record_edit_tool(arguments)
    elif name == "get_contacts":
        return await get_contacts_tool(arguments)
    elif name == "get_stats":
        return await get_stats_tool()
    elif name == "learn_contact":
        return await learn_contact_tool(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def process_email_tool(args: dict) -> list[TextContent]:
    """Process an email through MCP system."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        subject = args.get("subject", "")
        body = args.get("body", "")
        sender_email = args.get("sender_email", "")
        sender_name = args.get("sender_name", "")
        instruction = args.get("instruction", "")

        result = {
            "status": "processed",
            "confidence": 50,
            "pattern_match": None,
            "sender_known": False,
            "routing": None,
            "reasoning": ["Base confidence: 50"]
        }

        # 1. Check for safety overrides
        cursor.execute("""
            SELECT rule_type, rule_value, action, reason
            FROM overrides WHERE is_active = 1
        """)
        for override in cursor.fetchall():
            rule_value = override["rule_value"].lower()
            if override["rule_type"] == "subject_keyword" and rule_value in subject.lower():
                conn.close()
                return [TextContent(type="text", text=json.dumps({
                    "status": "BLOCKED",
                    "reason": override["reason"],
                    "action": override["action"]
                }, indent=2))]

        # 2. Match patterns
        cursor.execute("""
            SELECT pattern_name, keywords, confidence_boost, notes
            FROM pattern_hints ORDER BY confidence_boost DESC
        """)
        combined_text = f"{subject.lower()} {body.lower()}"

        for pattern in cursor.fetchall():
            keywords = json.loads(pattern["keywords"]) if pattern["keywords"] else []
            matches = sum(1 for kw in keywords if kw.lower() in combined_text)
            if matches > 0:
                result["pattern_match"] = {
                    "name": pattern["pattern_name"],
                    "confidence_boost": pattern["confidence_boost"],
                    "keyword_matches": matches,
                    "notes": pattern["notes"]
                }
                result["confidence"] += pattern["confidence_boost"]
                result["reasoning"].append(
                    f"Pattern '{pattern['pattern_name']}' matched: +{pattern['confidence_boost']}"
                )
                break

        # 3. Check if sender is known
        cursor.execute(
            "SELECT id, contact_name, preferred_tone FROM contact_patterns WHERE contact_email = ?",
            (sender_email,)
        )
        contact = cursor.fetchone()
        if contact:
            result["sender_known"] = True
            result["contact_info"] = dict_from_row(contact)
            result["confidence"] += 10
            result["reasoning"].append("Known sender: +10")
        else:
            result["confidence"] -= 20
            result["reasoning"].append("Unknown sender: -20")

        # 4. Determine routing
        pattern_name = result["pattern_match"]["name"] if result["pattern_match"] else None
        template_mapping = {
            "w9_wiring_request": "w9_response",
            "payment_confirmation": "payment_confirmation",
            "delegation_eytan": "delegation_eytan",
            "turnaround_expectation": "turnaround_time"
        }

        if pattern_name in template_mapping:
            template_id = template_mapping[pattern_name]
            cursor.execute(
                "SELECT template_body, variables FROM templates WHERE template_id = ?",
                (template_id,)
            )
            template = cursor.fetchone()
            if template:
                result["routing"] = {
                    "destination": "template",
                    "template_id": template_id,
                    "template_body": template["template_body"],
                    "variables": json.loads(template["variables"]) if template["variables"] else []
                }
                result["status"] = "template_ready"
        else:
            result["routing"] = {
                "destination": "claude_reasoning",
                "reason": "No template match - Claude should draft response"
            }
            result["status"] = "needs_reasoning"

        # 5. Clamp confidence
        result["confidence"] = max(0, min(100, result["confidence"]))

        # 6. Log to database
        cursor.execute("""
            INSERT INTO threads (gmail_thread_id, subject, mcp_prompt, status)
            VALUES (?, ?, ?, 'processing')
        """, (f"mcp_{datetime.now().timestamp()}", subject, instruction))
        thread_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO responses (thread_id, draft_text, confidence_score, model_used)
            VALUES (?, ?, ?, 'mcp_server')
        """, (thread_id, json.dumps(result), result["confidence"]))
        response_id = cursor.lastrowid

        conn.commit()
        conn.close()

        result["response_id"] = response_id
        result["thread_id"] = thread_id

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def get_patterns_tool() -> list[TextContent]:
    """Get all patterns from database."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT pattern_name, keywords, confidence_boost, usage_count,
                   success_rate, notes, last_updated
            FROM pattern_hints
            ORDER BY confidence_boost DESC
        """)

        patterns = []
        for row in cursor.fetchall():
            patterns.append({
                "name": row["pattern_name"],
                "keywords": json.loads(row["keywords"]) if row["keywords"] else [],
                "confidence_boost": row["confidence_boost"],
                "usage_count": row["usage_count"] or 0,
                "success_rate": f"{(row['success_rate'] or 0) * 100:.1f}%",
                "notes": row["notes"],
                "last_updated": row["last_updated"]
            })

        conn.close()

        return [TextContent(type="text", text=json.dumps({
            "count": len(patterns),
            "patterns": patterns
        }, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def get_templates_tool() -> list[TextContent]:
    """Get all templates from database."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT template_id, template_name, template_body, variables,
                   usage_count, success_rate
            FROM templates
            ORDER BY usage_count DESC
        """)

        templates = []
        for row in cursor.fetchall():
            templates.append({
                "id": row["template_id"],
                "name": row["template_name"],
                "body_preview": row["template_body"][:100] + "..." if len(row["template_body"] or "") > 100 else row["template_body"],
                "variables": json.loads(row["variables"]) if row["variables"] else [],
                "usage_count": row["usage_count"] or 0,
                "success_rate": f"{(row['success_rate'] or 0) * 100:.1f}%"
            })

        conn.close()

        return [TextContent(type="text", text=json.dumps({
            "count": len(templates),
            "templates": templates
        }, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def get_template_tool(args: dict) -> list[TextContent]:
    """Get a specific template by ID."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        template_id = args.get("template_id")

        cursor.execute("""
            SELECT template_id, template_name, template_body, variables, attachments
            FROM templates WHERE template_id = ?
        """, (template_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return [TextContent(type="text", text=json.dumps({
                "id": row["template_id"],
                "name": row["template_name"],
                "body": row["template_body"],
                "variables": json.loads(row["variables"]) if row["variables"] else [],
                "attachments": json.loads(row["attachments"]) if row["attachments"] else []
            }, indent=2))]
        else:
            return [TextContent(type="text", text=f"Template not found: {template_id}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def record_edit_tool(args: dict) -> list[TextContent]:
    """Record edits for learning."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        response_id = args.get("response_id")
        final_text = args.get("final_text")
        was_sent = args.get("was_sent", True)

        # Get original draft
        cursor.execute("""
            SELECT draft_text, confidence_score FROM responses WHERE id = ?
        """, (response_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return [TextContent(type="text", text=f"Response not found: {response_id}")]

        draft_text = row["draft_text"]

        # Calculate edit percentage
        if draft_text and final_text:
            draft_words = set(draft_text.lower().split())
            final_words = set(final_text.lower().split())
            added = final_words - draft_words
            removed = draft_words - final_words
            changed = len(added) + len(removed)
            total = max(len(draft_words), len(final_words))
            edit_pct = (changed / total * 100) if total > 0 else 0
        else:
            edit_pct = 100.0

        # Classify outcome
        if not was_sent:
            outcome = "deleted"
        elif edit_pct < 10:
            outcome = "success"
        elif edit_pct < 30:
            outcome = "good"
        elif edit_pct < 50:
            outcome = "needs_work"
        else:
            outcome = "failure"

        # Update response
        cursor.execute("""
            UPDATE responses
            SET final_text = ?, sent = ?, user_edited = 1,
                edit_percentage = ?, sent_at = ?
            WHERE id = ?
        """, (final_text, 1 if was_sent else 0, edit_pct,
              datetime.now().isoformat(), response_id))

        conn.commit()
        conn.close()

        return [TextContent(type="text", text=json.dumps({
            "status": "recorded",
            "outcome": outcome,
            "edit_percentage": f"{edit_pct:.1f}%",
            "was_sent": was_sent,
            "learning_impact": "System will use this to improve future drafts"
        }, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def get_contacts_tool(args: dict) -> list[TextContent]:
    """Get contact preferences."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        email = args.get("email")

        if email:
            cursor.execute("""
                SELECT contact_email, contact_name, preferred_tone,
                       common_topics, interaction_count, last_interaction
                FROM contact_patterns WHERE contact_email = ?
            """, (email,))
        else:
            cursor.execute("""
                SELECT contact_email, contact_name, preferred_tone,
                       common_topics, interaction_count, last_interaction
                FROM contact_patterns
                ORDER BY interaction_count DESC
                LIMIT 50
            """)

        contacts = []
        for row in cursor.fetchall():
            contacts.append({
                "email": row["contact_email"],
                "name": row["contact_name"],
                "preferred_tone": row["preferred_tone"],
                "common_topics": json.loads(row["common_topics"]) if row["common_topics"] else [],
                "interaction_count": row["interaction_count"] or 0,
                "last_interaction": row["last_interaction"]
            })

        conn.close()

        return [TextContent(type="text", text=json.dumps({
            "count": len(contacts),
            "contacts": contacts
        }, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def get_stats_tool() -> list[TextContent]:
    """Get system statistics."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        stats = {}

        cursor.execute("SELECT COUNT(*) FROM pattern_hints")
        stats["patterns"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM templates")
        stats["templates"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM contact_patterns")
        stats["contacts_learned"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM writing_patterns")
        stats["writing_patterns"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM responses WHERE sent = 1")
        stats["emails_processed"] = cursor.fetchone()[0]

        cursor.execute("""
            SELECT AVG(edit_percentage) FROM responses
            WHERE sent = 1 AND edit_percentage IS NOT NULL
        """)
        avg_edit = cursor.fetchone()[0]
        stats["avg_edit_rate"] = f"{avg_edit:.1f}%" if avg_edit else "N/A"

        cursor.execute("""
            SELECT COUNT(*) FROM responses
            WHERE sent = 1 AND edit_percentage < 10
        """)
        success_count = cursor.fetchone()[0]
        stats["successful_drafts"] = success_count

        conn.close()

        return [TextContent(type="text", text=json.dumps({
            "mcp_system_stats": stats,
            "database_path": DB_PATH
        }, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def learn_contact_tool(args: dict) -> list[TextContent]:
    """Add or update a contact."""
    try:
        conn = get_db()
        cursor = conn.cursor()

        email = args.get("email")
        name = args.get("name")
        tone = args.get("preferred_tone", "professional")
        notes = args.get("notes", "")

        # Check if contact exists
        cursor.execute(
            "SELECT id FROM contact_patterns WHERE contact_email = ?",
            (email,)
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE contact_patterns
                SET contact_name = ?, preferred_tone = ?,
                    last_interaction = ?, interaction_count = interaction_count + 1
                WHERE contact_email = ?
            """, (name, tone, datetime.now().isoformat(), email))
            action = "updated"
        else:
            cursor.execute("""
                INSERT INTO contact_patterns
                (contact_email, contact_name, preferred_tone, interaction_count, last_interaction)
                VALUES (?, ?, ?, 1, ?)
            """, (email, name, tone, datetime.now().isoformat()))
            action = "added"

        conn.commit()
        conn.close()

        return [TextContent(type="text", text=json.dumps({
            "status": "success",
            "action": action,
            "contact": {
                "email": email,
                "name": name,
                "preferred_tone": tone
            }
        }, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# ============================================
# MAIN
# ============================================

async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    print(f"Starting MCP Email Processor Server...")
    print(f"Database: {DB_PATH}")
    asyncio.run(main())
