"""Tests for VGC glossary tools."""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.glossary_tools import register_glossary_tools
from vgc_mcp_core.data.glossary_data import VGC_GLOSSARY


@pytest.fixture
def mcp_with_glossary():
    """Create an MCP server with glossary tools registered."""
    mcp = FastMCP("test")
    register_glossary_tools(mcp)
    return mcp


@pytest.fixture
def explain_term(mcp_with_glossary):
    """Get the explain_vgc_term tool function."""
    # Access the registered tool directly
    tools = {t.name: t for t in mcp_with_glossary._tool_manager._tools.values()}
    return tools["explain_vgc_term"].fn


class TestExplainVGCTerm:
    """Tests for the explain_vgc_term tool."""

    async def test_exact_match_evs(self, explain_term):
        """Test exact match for 'evs' term."""
        result = await explain_term(term="evs")
        assert "error" not in result
        assert result["term"] == "EVs (Effort Values)"
        assert "simple_explanation" in result
        assert "why_it_matters" in result
        assert "markdown_summary" in result

    async def test_exact_match_case_insensitive(self, explain_term):
        """Test that lookup is case-insensitive."""
        result = await explain_term(term="EVs")
        assert "error" not in result
        assert result["term"] == "EVs (Effort Values)"

    async def test_exact_match_with_whitespace(self, explain_term):
        """Test that whitespace is trimmed."""
        result = await explain_term(term="  evs  ")
        assert "error" not in result
        assert result["term"] == "EVs (Effort Values)"

    async def test_term_not_found(self, explain_term):
        """Test term that doesn't exist returns error with suggestions."""
        result = await explain_term(term="xyznonexistent")
        assert "error" in result
        assert "suggestions" in result or "available_terms" in result

    async def test_common_patterns_included(self, explain_term):
        """Test that terms with common_patterns include them."""
        result = await explain_term(term="evs")
        assert "common_patterns" in result
        assert len(result["common_patterns"]) > 0

    async def test_related_terms_included(self, explain_term):
        """Test that related terms are included."""
        result = await explain_term(term="evs")
        assert "related_terms" in result
        assert "IVs" in result["related_terms"]

    async def test_fuzzy_match_partial(self, explain_term):
        """Test fuzzy matching with partial term."""
        result = await explain_term(term="stab")
        # Should either find STAB or return suggestions
        if "error" not in result:
            assert "term" in result
        else:
            assert "suggestions" in result or "available_terms" in result

    async def test_markdown_summary_has_headers(self, explain_term):
        """Test markdown summary includes section headers."""
        result = await explain_term(term="nature")
        assert "error" not in result
        md = result["markdown_summary"]
        assert "## Term:" in md
        assert "### Simple Explanation" in md
        assert "### Why It Matters" in md

    async def test_nature_term(self, explain_term):
        """Test nature term lookup."""
        result = await explain_term(term="nature")
        assert "error" not in result
        assert result["term"] == "Nature"
        assert "common_patterns" in result
        # Nature should have patterns like Timid, Adamant
        pattern_names = [p["pattern"] for p in result["common_patterns"]]
        assert "Timid" in pattern_names

    async def test_ivs_term(self, explain_term):
        """Test IVs term lookup."""
        result = await explain_term(term="ivs")
        assert "error" not in result
        assert "Individual Values" in result["term"]

    async def test_all_glossary_terms_accessible(self, explain_term):
        """Test that all glossary terms can be looked up."""
        for term_key in list(VGC_GLOSSARY.keys())[:10]:  # Test first 10
            result = await explain_term(term=term_key)
            assert "error" not in result, f"Failed to look up term: {term_key}"
            assert "term" in result
