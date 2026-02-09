"""
Template Manager Capability for Mode 4
Quick-fill templates from Google Sheets.

Commands:
    /template <name> [vars] - Fill and send template
    /templates - List available templates
    /newtemplate <name> - Create new template (interactive)

Usage:
    from template_manager import TemplateManager

    tm = TemplateManager()
    templates = tm.list_templates()
    filled = tm.fill_template("invoice_reminder", {"name": "Jason", "amount": "$500"})
"""

import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class TemplateManagerError(Exception):
    """Custom exception for template manager errors."""
    pass


class TemplateManager:
    """
    Template management capability for Mode 4.

    Templates stored in Google Sheets with variable placeholders.
    Format: {{variable_name}}
    """

    def __init__(self):
        """Initialize template manager."""
        self._sheets = None
        self._ollama = None
        self._cache = {}
        self._cache_time = None

        # Variable pattern: {{variable_name}}
        self.var_pattern = re.compile(r'\{\{(\w+)\}\}')

    def _get_sheets(self):
        """Lazy load Sheets client."""
        if self._sheets is None:
            try:
                from pattern_matcher import PatternMatcher
                matcher = PatternMatcher()
                # Get templates from the same source
                self._sheets = matcher
            except Exception as e:
                logger.warning(f"Could not load Sheets: {e}")
        return self._sheets

    def _get_ollama(self):
        """Lazy load Ollama client."""
        if self._ollama is None:
            try:
                from ollama_client import OllamaClient
                self._ollama = OllamaClient()
            except Exception as e:
                logger.warning(f"Could not load Ollama: {e}")
        return self._ollama

    # ==================
    # TEMPLATE OPERATIONS
    # ==================

    def list_templates(self, refresh: bool = False) -> List[Dict[str, Any]]:
        """
        List available templates.

        Args:
            refresh: Force refresh from Sheets

        Returns:
            List of template metadata dicts
        """
        if self._cache and not refresh and self._cache_time:
            age = (datetime.now() - self._cache_time).seconds
            if age < 300:  # 5 minute cache
                return list(self._cache.values())

        sheets = self._get_sheets()
        if not sheets:
            return []

        templates = []
        try:
            # Get templates from pattern matcher's source
            raw_templates = sheets.get_templates()

            for tmpl in raw_templates:
                template_data = {
                    'id': tmpl.get('id', ''),
                    'name': tmpl.get('name', tmpl.get('id', 'Unnamed')),
                    'category': tmpl.get('category', 'general'),
                    'description': tmpl.get('description', ''),
                    'body': tmpl.get('body', ''),
                    'variables': self._extract_variables(tmpl.get('body', ''))
                }
                templates.append(template_data)
                self._cache[template_data['id']] = template_data

            self._cache_time = datetime.now()

        except Exception as e:
            logger.error(f"Error loading templates: {e}")

        return templates

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific template by ID or name.

        Args:
            template_id: Template ID or name

        Returns:
            Template dict or None
        """
        # Check cache first
        if template_id in self._cache:
            return self._cache[template_id]

        # Search by name
        templates = self.list_templates()
        for tmpl in templates:
            if tmpl['id'].lower() == template_id.lower():
                return tmpl
            if tmpl['name'].lower() == template_id.lower():
                return tmpl

        return None

    def fill_template(
        self,
        template_id: str,
        variables: Dict[str, str],
        use_ai: bool = False
    ) -> Dict[str, Any]:
        """
        Fill a template with variables.

        Args:
            template_id: Template ID or name
            variables: Dict of variable values
            use_ai: Use Ollama to infer missing variables

        Returns:
            Dict with filled template or error
        """
        template = self.get_template(template_id)
        if not template:
            return {
                'success': False,
                'error': f'Template not found: {template_id}'
            }

        body = template['body']
        required_vars = template['variables']
        missing_vars = [v for v in required_vars if v not in variables]

        # Try to infer missing variables with AI
        if missing_vars and use_ai:
            ollama = self._get_ollama()
            if ollama and ollama.is_available():
                inferred = self._infer_variables(body, missing_vars, variables)
                variables.update(inferred)
                missing_vars = [v for v in required_vars if v not in variables]

        if missing_vars:
            return {
                'success': False,
                'error': f'Missing variables: {", ".join(missing_vars)}',
                'missing': missing_vars,
                'template': template
            }

        # Fill template
        filled = body
        for var, value in variables.items():
            filled = filled.replace(f'{{{{{var}}}}}', str(value))

        return {
            'success': True,
            'filled': filled,
            'template_id': template_id,
            'template_name': template['name'],
            'variables_used': variables
        }

    def _extract_variables(self, text: str) -> List[str]:
        """Extract variable names from template text."""
        return list(set(self.var_pattern.findall(text)))

    def _infer_variables(
        self,
        template: str,
        missing: List[str],
        known: Dict[str, str]
    ) -> Dict[str, str]:
        """Use Ollama to infer missing variable values."""
        ollama = self._get_ollama()
        if not ollama:
            return {}

        prompt = f"""Given this email template:
{template}

Known values:
{chr(10).join(f'  {k}: {v}' for k, v in known.items())}

Infer reasonable values for these missing variables:
{chr(10).join(f'  - {v}' for v in missing)}

Respond with ONLY the variable assignments in format:
variable_name: value

Be concise and professional."""

        try:
            response = ollama.generate(prompt)
            inferred = {}

            for line in response.strip().split('\n'):
                if ':' in line:
                    parts = line.split(':', 1)
                    var = parts[0].strip()
                    value = parts[1].strip()
                    if var in missing:
                        inferred[var] = value

            return inferred
        except Exception as e:
            logger.warning(f"Variable inference failed: {e}")
            return {}

    def parse_variables_from_text(self, text: str) -> Dict[str, str]:
        """
        Parse variable assignments from natural text.

        Supports formats:
            - "name=Jason amount=500"
            - "name: Jason, amount: 500"
            - "name Jason amount 500" (positional with template)

        Args:
            text: Variable text

        Returns:
            Dict of parsed variables
        """
        variables = {}

        # Try key=value format
        eq_pattern = re.compile(r'(\w+)\s*=\s*([^\s,]+)')
        for match in eq_pattern.finditer(text):
            variables[match.group(1)] = match.group(2)

        if variables:
            return variables

        # Try key: value format
        colon_pattern = re.compile(r'(\w+)\s*:\s*([^,]+)')
        for match in colon_pattern.finditer(text):
            variables[match.group(1)] = match.group(2).strip()

        return variables

    # ==================
    # COMMAND HANDLERS
    # ==================

    def handle_command(self, command: str, args: str, user_id: int) -> str:
        """
        Handle template command and return response text.

        Args:
            command: Command name (/template, /templates)
            args: Command arguments
            user_id: Telegram user ID

        Returns:
            Response message text
        """
        try:
            if command == '/templates':
                return self._cmd_list_templates()
            elif command == '/template':
                return self._cmd_fill_template(args)
            elif command == '/newtemplate':
                return self._cmd_new_template(args)
            else:
                return f"Unknown command: {command}"
        except Exception as e:
            logger.error(f"Template command error: {e}")
            return f"Error: {str(e)}"

    def _cmd_list_templates(self) -> str:
        """Handle /templates command."""
        templates = self.list_templates(refresh=True)

        if not templates:
            return (
                "No templates found.\n\n"
                "Templates are loaded from Google Sheets.\n"
                "Check your MCP Email Templates sheet."
            )

        lines = ["Available Templates:\n"]
        by_category = {}

        for tmpl in templates:
            cat = tmpl.get('category', 'general')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(tmpl)

        for category, tmpls in sorted(by_category.items()):
            lines.append(f"\n{category.upper()}:")
            for tmpl in tmpls:
                vars_str = ', '.join(tmpl['variables'][:3])
                if len(tmpl['variables']) > 3:
                    vars_str += '...'
                lines.append(f"  /{tmpl['id']} - {tmpl['name']}")
                if vars_str:
                    lines.append(f"    Variables: {vars_str}")

        lines.append("\nUsage: /template <name> var1=value1 var2=value2")
        return '\n'.join(lines)

    def _cmd_fill_template(self, args: str) -> str:
        """Handle /template command."""
        if not args.strip():
            return (
                "Template Quick-Fill\n\n"
                "Usage: /template <name> [variables]\n"
                "Example: /template invoice_reminder name=Jason amount=$500\n\n"
                "Use /templates to see available templates."
            )

        parts = args.strip().split(maxsplit=1)
        template_id = parts[0]
        var_text = parts[1] if len(parts) > 1 else ''

        # Get template first
        template = self.get_template(template_id)
        if not template:
            # Try fuzzy match
            templates = self.list_templates()
            matches = [t for t in templates if template_id.lower() in t['id'].lower() or
                      template_id.lower() in t['name'].lower()]
            if matches:
                suggestions = ', '.join(t['id'] for t in matches[:3])
                return f"Template '{template_id}' not found. Did you mean: {suggestions}?"
            return f"Template '{template_id}' not found. Use /templates to see available."

        # Parse variables
        variables = self.parse_variables_from_text(var_text) if var_text else {}

        # Check for missing
        required = template['variables']
        missing = [v for v in required if v not in variables]

        if missing:
            return (
                f"Template: {template['name']}\n\n"
                f"Missing variables: {', '.join(missing)}\n\n"
                f"Usage: /template {template_id} {' '.join(f'{v}=<value>' for v in missing)}\n\n"
                f"Or use /template {template_id} ai=yes to auto-fill"
            )

        # Fill template
        use_ai = variables.pop('ai', '').lower() in ('yes', 'true', '1')
        result = self.fill_template(template_id, variables, use_ai=use_ai)

        if not result['success']:
            return f"Error: {result['error']}"

        return (
            f"Template: {result['template_name']}\n\n"
            f"---\n"
            f"{result['filled']}\n"
            f"---\n\n"
            "Reply 'send' to use this as a draft, or edit as needed."
        )

    def _cmd_new_template(self, args: str) -> str:
        """Handle /newtemplate command."""
        return (
            "Creating new templates:\n\n"
            "Templates are managed in Google Sheets.\n"
            "1. Open your MCP Email Templates sheet\n"
            "2. Add a new row with:\n"
            "   - ID (unique identifier)\n"
            "   - Name (display name)\n"
            "   - Category (for organization)\n"
            "   - Body (use {{variable}} for placeholders)\n\n"
            "Example body:\n"
            "  Hi {{name}},\n"
            "  This is a reminder about invoice #{{invoice_num}}.\n"
            "  Amount due: {{amount}}\n"
            "  Best regards"
        )

    def cleanup(self):
        """Cleanup resources."""
        if self._sheets:
            del self._sheets
            self._sheets = None
        if self._ollama:
            del self._ollama
            self._ollama = None
        self._cache.clear()


# ==================
# TESTING
# ==================

def test_template_manager():
    """Test template manager."""
    print("Testing Template Manager...")
    print("=" * 60)

    tm = TemplateManager()

    # Test variable extraction
    print("\nTesting variable extraction...")
    test_body = "Hi {{name}}, your invoice #{{invoice_num}} for {{amount}} is due."
    vars_found = tm._extract_variables(test_body)
    print(f"  Template: {test_body}")
    print(f"  Variables: {vars_found}")

    # Test variable parsing
    print("\nTesting variable parsing...")
    test_inputs = [
        "name=Jason amount=$500",
        "name: Jason, amount: $500",
    ]
    for inp in test_inputs:
        parsed = tm.parse_variables_from_text(inp)
        print(f"  Input: '{inp}' -> {parsed}")

    # Test filling (mock)
    print("\nTesting template filling...")
    tm._cache['test'] = {
        'id': 'test',
        'name': 'Test Template',
        'category': 'testing',
        'body': 'Hello {{name}}, your amount is {{amount}}.',
        'variables': ['name', 'amount']
    }

    result = tm.fill_template('test', {'name': 'Jason', 'amount': '$500'})
    if result['success']:
        print(f"  Filled: {result['filled']}")
    else:
        print(f"  Error: {result['error']}")

    # Test missing variable
    result = tm.fill_template('test', {'name': 'Jason'})
    print(f"  Missing var result: {result.get('error', result)}")

    tm.cleanup()
    print("\nTemplate manager test complete!")


if __name__ == "__main__":
    test_template_manager()
