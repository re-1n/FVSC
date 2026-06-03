"""Markdown format adapter — AST-level extraction preserving structural signals.

Uses mistune to parse Markdown into tokens, then converts them to text chunks
that preserve the semantic relationships between: headings and their content,
table columns and rows, and nested list items.

The output is plain text chunks optimized for the FVSC co-occurrence parser:
concepts that are structurally related appear together in the same chunk,
making them discoverable by the sliding-window co-occurrence algorithm.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from mistune import create_markdown
from mistune.plugins.table import table as table_plugin


_md = create_markdown(renderer=None, plugins=[table_plugin])


# ── public API ───────────────────────────────────────────────────

def parse_markdown_to_chunks(text: str) -> List[str]:
    """Convert Markdown text to FVSC-ready text chunks.

    Each chunk is a self-contained text segment where structurally
    related concepts appear together:

    - Headings prepend context to subsequent paragraphs
    - Table rows become sentences with column labels
    - List items preserve nesting through indentation
    - Blockquotes are treated as paragraphs
    - Code blocks and HTML are skipped

    Returns list of text strings, each >= 20 chars after cleaning.
    """
    _, state = _md.parse(text)
    tokens: Sequence[dict] = state.tokens
    chunks: List[str] = []
    current_section: Optional[str] = None

    for tok in tokens:
        t = tok["type"]

        if t == "heading":
            text = _extract_inline_text(tok.get("children", []))
            if not text:
                continue
            current_section = text
            chunks.append(text)

        elif t == "paragraph":
            text = _extract_inline_text(tok.get("children", []))
            if not text:
                continue
            if current_section:
                text = f"{current_section}: {text}"
            chunks.append(text)
            current_section = None

        elif t == "table":
            rows = _table_to_rows(tok)
            chunks.extend(rows)
            current_section = None

        elif t == "list":
            items = _list_to_items(tok)
            chunks.extend(items)
            current_section = None

        elif t == "block_quote":
            text = _extract_text_from_children(tok.get("children", []))
            if text:
                chunks.append(text)
            current_section = None

        elif t in ("block_code", "block_html", "thematic_break", "blank_line"):
            if t == "blank_line":
                current_section = None  # paragraph break resets section
            continue

    return [c.strip() for c in chunks if len(c.strip()) >= 20]


# ── inline text extraction ──────────────────────────────────────

def _extract_inline_text(children: Sequence[dict]) -> str:
    """Recursively extract text from inline tokens."""
    parts: List[str] = []
    for child in children:
        t = child["type"]
        if t == "text":
            raw = child.get("raw", "")
            if raw:
                parts.append(raw)
        elif t == "codespan":
            raw = child.get("raw", "")
            if raw:
                parts.append(raw)
        elif t == "softbreak":
            parts.append(" ")
        elif t in ("strong", "emphasis", "strikethrough", "link", "image"):
            inner = _extract_inline_text(child.get("children", []))
            if inner:
                parts.append(inner)
        elif t == "linebreak":
            parts.append("\n")
        elif t == "html_inline":
            continue
    return "".join(parts)


def _extract_text_from_children(children: Sequence[dict]) -> str:
    """Recursively extract all text from block-level children."""
    parts: List[str] = []
    for child in children:
        t = child["type"]
        if t == "text":
            raw = child.get("raw", "")
            if raw:
                parts.append(raw)
        elif t == "codespan":
            raw = child.get("raw", "")
            if raw:
                parts.append(raw)
        elif t == "paragraph":
            text = _extract_inline_text(child.get("children", []))
            if text:
                parts.append(text)
        elif t == "block_text":
            text = _extract_inline_text(child.get("children", []))
            if text:
                parts.append(text)
        elif t in ("strong", "emphasis", "strikethrough", "link", "image"):
            inner = _extract_inline_text(child.get("children", []))
            if inner:
                parts.append(inner)
        elif t == "softbreak":
            parts.append(" ")
        elif t == "list":
            items = _list_to_items(child)
            parts.extend(items)
        elif t == "list_item":
            text = _extract_text_from_children(child.get("children", []))
            if text:
                parts.append(text)
        elif t == "block_quote":
            text = _extract_text_from_children(child.get("children", []))
            if text:
                parts.append(text)
        elif t == "table":
            rows = _table_to_rows(child)
            parts.extend(rows)
        elif t == "blank_line":
            parts.append(" ")
    return " ".join(parts).strip()


# ── table extraction ────────────────────────────────────────────

def _table_to_rows(table_token: dict) -> List[str]:
    """Convert a table token tree to structured text rows.

    For each data row, produces: "col1_name: val1, col2_name: val2, ..."
    This format preserves the column relationship so the co-occurrence
    parser sees related concepts together.
    """
    children = table_token.get("children", [])
    if len(children) < 2:
        return []

    headers = _extract_table_header(children[0])
    body = children[1]  # table_body

    rows: List[str] = []
    for row_tok in body.get("children", []):  # table_row
        cells = _extract_table_cells(row_tok)
        if not cells:
            continue
        parts: List[str] = []
        for i, cell_text in enumerate(cells):
            if headers and i < len(headers) and headers[i]:
                parts.append(f"{headers[i]}: {cell_text}")
            else:
                parts.append(cell_text)
        if parts:
            rows.append(". ".join(parts))
    return rows


def _extract_table_header(head_tok: dict) -> List[str]:
    """Extract header cell texts from table_head token."""
    headers: List[str] = []
    for cell in head_tok.get("children", []):
        if cell["type"] == "table_cell":
            text = _extract_inline_text(cell.get("children", []))
            headers.append(text)
    return headers


def _extract_table_cells(row_tok: dict) -> List[str]:
    """Extract cell texts from a table_row token."""
    cells: List[str] = []
    for cell in row_tok.get("children", []):
        if cell["type"] == "table_cell":
            text = _extract_inline_text(cell.get("children", []))
            cells.append(text)
    return cells


# ── list extraction ─────────────────────────────────────────────

def _list_to_items(list_token: dict, indent: int = 0) -> List[str]:
    """Convert list token tree to text items, preserving nesting."""
    items: List[str] = []
    prefix = "  " * indent
    for child in list_token.get("children", []):
        if child["type"] == "list_item":
            text = _extract_list_item_text(child, indent=indent)
            if not text:
                continue
            # Check for nested lists
            nested: List[str] = []
            for sub in child.get("children", []):
                if sub["type"] == "list":
                    nested.extend(_list_to_items(sub, indent + 1))
            if nested:
                text = text + ": " + "; ".join(nested)
            items.append(text)
    return items


def _extract_list_item_text(item_tok: dict, indent: int = 0) -> str:
    """Extract text content from a list_item token."""
    parts: List[str] = []
    for child in item_tok.get("children", []):
        if child["type"] == "block_text":
            text = _extract_inline_text(child.get("children", []))
            if text:
                parts.append(text)
        elif child["type"] == "paragraph":
            text = _extract_inline_text(child.get("children", []))
            if text:
                parts.append(text)
        elif child["type"] == "text":
            raw = child.get("raw", "")
            if raw:
                parts.append(raw)
        # Skip nested list tokens here — _list_to_items handles those
    return " ".join(parts).strip()
