Here is a structured overview you can add to your `README.md` or `MIGRATION.md` file. This content illustrates the core purpose of your hybrid system and the transition from Google to Microsoft 365.

---

# Hybrid MCP System: Project Overview

This project implements a **Hybrid Model Context Protocol (MCP)** system. Its primary goal is to automate the bridge between incoming communications (Gmail) and a structured productivity suite (Microsoft 365), using a local Python-based "Brain" for intelligent processing.

## The Mission

The system is designed to act as an automated executive assistant that:

* **Captures** incoming tasks and attachments from Gmail.
* **Organizes** metadata into a centralized command center using Microsoft Lists.
* **Processes** content using local AI (Ollama) to extract insights, gaps, and action items.
* **Documents** deep-dive ideas and brainstorms into a persistent, human-readable OneNote notebook.

## Architectural Shift

Following the migration from a Google-only stack, the system now utilizes a hybrid architecture to leverage the best of both platforms:

| Feature | Legacy State (Google) | Hybrid State (Microsoft 365) |
| --- | --- | --- |
| **Email Trigger** | Gmail [MCP] Label | Gmail [MCP] Label (Unchanged) |
| **Task Database** | Google Sheets | **Microsoft Lists** (Action_Items, Idea_Board) |
| **Documentation** | Google Docs | **OneNote** (Automated Page Provisioning) |
| **File Storage** | Google Drive | **SharePoint** (Primary) / Drive (Fallback) |
| **Automation** | Apps Script | **Power Automate** |

## Core Workflows

### 1. Email Onboarding & Offboarding (Flows A & B)

When an email is labeled `[MCP]`, Power Automate extracts attachments to SharePoint and creates a tracking item in the `Action_Items` list. When the label is removed, the system performs a cleanup of staging files and list items.

### 2. The Idea Board → OneNote Bridge (Flow C)

This is the heart of the documentation engine. Adding a new entry to the `Idea_Board` list triggers the creation of a dedicated OneNote page. The Python bot then uses the **Microsoft Graph API** to read the user's manual notes and append AI-generated state summaries or "Idea Bouncer" analysis directly into the document.

### 3. Proactive Maintenance (Flow D)

A "60-Day Reaper" daily routine ensures the SharePoint environment remains clean by purging temporary staging files and garbage folders older than two months.

## Technical Components

* **`graph_client.py`**: Manages MSAL authentication and direct communication with Microsoft services.
* **`onenote_client.py`**: Handles HTML-based page updates with optimistic concurrency control to prevent overwriting human edits.
* **`mode4_processor.py`**: The main execution loop that polls Microsoft Lists for pending work and orchestrates AI responses.
