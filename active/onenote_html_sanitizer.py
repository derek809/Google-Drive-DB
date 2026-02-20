"""
OneNote HTML Sanitizer for Graph API.

OneNote's PATCH endpoint is strict about allowed HTML elements.
This module strips unsafe tags and attributes, keeping only the
subset that OneNote reliably renders without returning 400 errors.

Safe tags: p, ul, ol, li, strong, em, b, i, br, h1-h6, pre,
           table, tr, td, th, span, div, a, img
Safe attributes: href (on <a>), src/alt/width/height (on <img>),
                 data-id (on any), style (limited properties)
"""

import re
import logging

logger = logging.getLogger(__name__)

# OneNote-safe tags
SAFE_TAGS = frozenset({
    "p", "ul", "ol", "li", "strong", "em", "b", "i", "br",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "pre", "table", "tr", "td", "th", "thead", "tbody",
    "span", "div", "a", "img",
})

# Allowed attributes per tag ("*" applies to all safe tags)
SAFE_ATTRS = {
    "a": {"href"},
    "img": {"src", "alt", "width", "height"},
    "*": {"data-id", "style"},
}

# Inline CSS properties that OneNote accepts
SAFE_STYLE_PROPS = frozenset({
    "color", "background-color", "font-weight", "font-style",
    "text-decoration", "font-size",
})


def sanitize_html(html: str) -> str:
    """
    Sanitize HTML for OneNote Graph API compatibility.

    Strips disallowed tags (keeping inner text), removes unsafe
    attributes, and filters inline styles to the safe subset.

    Args:
        html: Raw HTML string.

    Returns:
        Sanitized HTML safe for OneNote PATCH requests.
    """
    if not html:
        return ""

    # Remove script/style blocks entirely (content + tags)
    html = re.sub(
        r"<(script|style)[^>]*>.*?</\1>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Process each tag
    tag_pattern = re.compile(
        r"<(/?)(\w+)((?:\s+[^>]*?)?)(\s*/?)>",
        re.IGNORECASE,
    )
    html = tag_pattern.sub(_process_tag, html)

    return html.strip()


def _process_tag(match: re.Match) -> str:
    """Process a single HTML tag, stripping or sanitizing as needed."""
    closing = match.group(1) or ""
    tag_name = match.group(2).lower()
    attrs_str = match.group(3) or ""
    self_close = match.group(4) or ""

    if tag_name not in SAFE_TAGS:
        return ""

    # Filter attributes
    clean_attrs = _filter_attributes(tag_name, attrs_str)

    if self_close.strip() == "/" or tag_name in ("br", "img"):
        return f"<{closing}{tag_name}{clean_attrs} />"
    return f"<{closing}{tag_name}{clean_attrs}>"


def _filter_attributes(tag_name: str, attrs_str: str) -> str:
    """Filter attributes to only those allowed for the tag."""
    if not attrs_str.strip():
        return ""

    allowed = SAFE_ATTRS.get(tag_name, set()) | SAFE_ATTRS.get("*", set())
    if not allowed:
        return ""

    result_attrs = []
    attr_pattern = re.compile(
        r"""(\w[\w-]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|(\S+)))?"""
    )

    for m in attr_pattern.finditer(attrs_str):
        attr_name = m.group(1).lower()
        attr_value = m.group(2) or m.group(3) or m.group(4) or ""

        if attr_name not in allowed:
            continue

        if attr_name == "style":
            attr_value = _filter_style(attr_value)
            if not attr_value:
                continue

        result_attrs.append(f'{attr_name}="{attr_value}"')

    if result_attrs:
        return " " + " ".join(result_attrs)
    return ""


def _filter_style(style: str) -> str:
    """Filter inline style to only OneNote-safe CSS properties."""
    if not style:
        return ""

    safe_parts = []
    for prop in style.split(";"):
        prop = prop.strip()
        if not prop or ":" not in prop:
            continue
        name = prop.split(":")[0].strip().lower()
        if name in SAFE_STYLE_PROPS:
            safe_parts.append(prop)

    return "; ".join(safe_parts)


def build_append_patch(summary_html: str, target: str = "body") -> list:
    """
    Build a OneNote PATCH request body for appending content.

    Uses the PATCH-append pattern instead of fetch-modify-replace.
    The OneNote API accepts an array of patch actions.

    Args:
        summary_html: HTML to append (will be sanitized).
        target: Target element (default "body").

    Returns:
        List of patch action dicts for the OneNote PATCH API.
    """
    clean_html = sanitize_html(summary_html)

    return [
        {
            "target": target,
            "action": "append",
            "position": "after",
            "content": clean_html,
        }
    ]
