"""Format a selection payload into a prompt prefix block.

Selection payload comes from the element picker in the React shell. The agent
gets the prefix prepended invisibly to the user's prompt.
"""

from __future__ import annotations

from typing import Any


_FIELD_ORDER = ("source", "component", "selector", "text", "html")
_HEADER = "[Selected element from preview — edit this in code]"


def format_selection_block(selection: dict[str, Any] | None) -> str:
    """Return the prefix block, or empty string if nothing to format."""
    if not selection:
        return ""

    lines = [_HEADER]
    for key in _FIELD_ORDER:
        value = selection.get(key)
        if value:
            lines.append(f"{key}: {value}")

    if len(lines) == 1:
        # Nothing useful in the payload (only summary maybe).
        return ""
    return "\n".join(lines)


def prepend_selection(prompt: str, selection: dict[str, Any] | None) -> str:
    """Prepend the selection block to a user prompt (with blank line)."""
    block = format_selection_block(selection)
    if not block:
        return prompt
    return f"{block}\n\n{prompt}"


def format_selections_block(selections: list[dict[str, Any]] | None) -> str:
    """Format multiple selection payloads into stacked blocks separated by blank lines."""
    if not selections:
        return ""
    blocks: list[str] = []
    for sel in selections:
        block = format_selection_block(sel)
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)


def prepend_selections(prompt: str, selections: list[dict[str, Any]] | None) -> str:
    """Prepend all selection blocks to a user prompt (with blank line)."""
    block = format_selections_block(selections)
    if not block:
        return prompt
    return f"{block}\n\n{prompt}"
