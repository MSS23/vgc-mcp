"""The server instructions must model phone-width output."""

import re

from vgc_mcp_core.presentation import PRESENTATION_INSTRUCTIONS


def _table_header_rows(text: str) -> list[str]:
    lines = text.splitlines()
    return [
        line
        for line, nxt in zip(lines, lines[1:])
        if line.strip().startswith("|") and re.match(r"^\s*\|[\s:|-]+\|\s*$", nxt)
    ]


def test_every_example_table_fits_a_phone():
    headers = _table_header_rows(PRESENTATION_INSTRUCTIONS)
    assert headers, "expected example tables in the instructions"
    for header in headers:
        columns = [c for c in header.strip().strip("|").split("|")]
        assert len(columns) <= 4, f"table wider than 4 columns: {header.strip()}"


def test_phone_rules_are_stated():
    text = PRESENTATION_INSTRUCTIONS
    assert "at most 4 columns" in text
    assert "Lead with the answer" in text
    assert "export_damage_report" in text
