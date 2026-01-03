# -*- coding: utf-8 -*-
"""Shared CSS styles for UI components."""

from pathlib import Path

# Load shared styles from template
STYLES_PATH = Path(__file__).parent.parent / "templates" / "shared" / "styles.css"


def get_shared_styles() -> str:
    """Load shared CSS styles."""
    try:
        return STYLES_PATH.read_text()
    except FileNotFoundError:
        return ""
