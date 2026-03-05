"""Utility functions for data processing and conversion."""

from datetime import datetime
from typing import Any
from bs4 import BeautifulSoup


def parse_datetime(dt_str: str | None, format: str = "%Y-%m-%d") -> str | None:
    """
    Parse ISO datetime string and format it.

    Args:
        dt_str: ISO format datetime string
        format: Output format string

    Returns:
        Formatted date string or None
    """
    if not dt_str:
        return None

    try:
        # Parse ISO format (e.g., "2024-03-05T14:30:22.123+0000")
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime(format)
    except (ValueError, AttributeError):
        return dt_str


def html_to_text(html: str | None, max_length: int | None = None) -> str:
    """
    Convert HTML to plain text.

    Args:
        html: HTML string
        max_length: Maximum length to truncate (None = no limit)

    Returns:
        Plain text string
    """
    if not html:
        return ""

    try:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        if max_length and len(text) > max_length:
            return text[:max_length] + "..."

        return text
    except Exception:
        # If parsing fails, return original text
        return html[:max_length] if max_length else html


def adf_to_text(adf_node: dict | None, max_length: int | None = None) -> str:
    """
    Convert Atlassian Document Format (ADF) to plain text.

    Args:
        adf_node: ADF JSON node
        max_length: Maximum length to truncate (None = no limit)

    Returns:
        Plain text string
    """
    if not adf_node:
        return ""

    def extract_text(node: dict) -> str:
        """Recursively extract text from ADF nodes."""
        if not isinstance(node, dict):
            return ""

        # If node has text, return it
        if node.get("type") == "text":
            return node.get("text", "")

        # If node has content, recurse
        if "content" in node and isinstance(node["content"], list):
            texts = [extract_text(child) for child in node["content"]]
            return " ".join(texts)

        return ""

    try:
        text = extract_text(adf_node)
        text = " ".join(text.split())  # Normalize whitespace

        if max_length and len(text) > max_length:
            return text[:max_length] + "..."

        return text
    except Exception:
        return ""


def safe_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary value.

    Args:
        data: Dictionary to access
        *keys: Sequence of keys to traverse
        default: Default value if key not found

    Returns:
        Value at the key path or default

    Example:
        safe_get(data, "fields", "assignee", "displayName", default="Unassigned")
    """
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def truncate_text(text: str | None, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def join_list(items: list[Any], separator: str = "; ") -> str:
    """
    Join list items into a string.

    Args:
        items: List of items to join
        separator: Separator string

    Returns:
        Joined string
    """
    if not items:
        return ""

    # Filter out None values and convert to strings
    str_items = [str(item) for item in items if item is not None]
    return separator.join(str_items)
