cat << 'EOF' > generate_feature_docs.py
#!/usr/bin/env python3
"""
Feature Documentation Generator

Automatically generates Markdown documentation for each feature file
in the features/ directory. Creates both individual feature guides and
a master guide containing all features.

Usage:
    python generate_feature_docs.py
"""

import os

FEATURES_DIR = "features"
DOCS_DIR = "feature_guides"
MASTER_DOC = os.path.join(DOCS_DIR, "MASTER_FEATURE_GUIDE.md")

# Create docs directory if it doesn't exist
os.makedirs(DOCS_DIR, exist_ok=True)

# Load existing master doc
if os.path.exists(MASTER_DOC):
    with open(MASTER_DOC, "r") as f:
        master_content = f.read()
else:
    master_content = "# Master Telegram Bot Feature Guide\n\n"
    master_content += "This document contains all feature documentation for the Telegram bot.\n\n"
    master_content += "---\n\n"

# Detect already-documented features
documented = set()
for line in master_content.splitlines():
    if line.startswith("## "):
        documented.add(line.replace("## ", "").strip())


def extract_docstring(path):
    """Extracts the top-level docstring from a Python file."""
    with open(path, "r") as f:
        lines = f.readlines()

    doc = []
    in_doc = False

    for line in lines[:30]:  # Check first 30 lines
        stripped = line.strip()
        if stripped.startswith(('"""', "'''")):
            if in_doc:
                break
            in_doc = True
            continue
        if in_doc:
            doc.append(stripped)

    return " ".join(doc) if doc else "No description provided."


def generate_markdown(feature_name, description):
    """Generates Markdown documentation for a feature."""
    return f"""## {feature_name}

**What it does**
{description}

**How to call from Telegram**
Describe the command or trigger used to invoke this feature from the bot.

**Parameters / Inputs**
List expected arguments or configuration.

**Example**