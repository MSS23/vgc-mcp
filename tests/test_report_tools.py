"""Tests for build report generation tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.report_tools import register_report_tools


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    return client


@pytest.fixture
def tools(mock_pokeapi):
    """Register report tools and return functions."""
    mcp = FastMCP("test")
    register_report_tools(mcp, mock_pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestGenerateBuildReport:
    """Tests for generate_build_report."""

    async def test_minimal_report(self, tools):
        """Test generating a report with minimal data."""
        fn = tools["generate_build_report"].fn
        result = await fn(
            initial_team=[{"species": "Incineroar", "item": "Safety Goggles", "ability": "Intimidate", "tera_type": "Ghost"}],
            title="Test Report"
        )
        assert result["success"] is True
        assert result["title"] == "Test Report"
        assert result["initial_pokemon_count"] == 1
        assert "report" in result

    async def test_report_with_changes(self, tools):
        """Test report with changes documented."""
        fn = tools["generate_build_report"].fn
        result = await fn(
            initial_team=[{"species": "Incineroar", "item": "Safety Goggles"}],
            changes=[{
                "pokemon": "Incineroar",
                "field": "Speed EVs",
                "before": "0",
                "after": "132",
                "reason": "Outspeed Amoonguss"
            }]
        )
        assert result["success"] is True
        assert result["changes_count"] == 1
        assert "Changes Made" in result["report"]

    async def test_report_with_conversation(self, tools):
        """Test report with conversation exchanges."""
        fn = tools["generate_build_report"].fn
        result = await fn(
            conversation=[
                {"question": "Does Incineroar survive Moonblast?", "answer": "Yes, with 252 HP EVs"}
            ]
        )
        assert result["success"] is True
        assert result["conversation_count"] == 1
        assert "Discussion" in result["report"]

    async def test_report_with_takeaways(self, tools):
        """Test report with key takeaways."""
        fn = tools["generate_build_report"].fn
        result = await fn(
            takeaways=["Speed control is critical", "Intimidate helps with physical threats"]
        )
        assert result["success"] is True
        assert result["takeaways_count"] == 2
        assert "Key Takeaways" in result["report"]

    async def test_default_title(self, tools):
        """Test default report title."""
        fn = tools["generate_build_report"].fn
        result = await fn()
        assert result["title"] == "VGC Team Build Report"

    async def test_empty_report(self, tools):
        """Test generating an empty report."""
        fn = tools["generate_build_report"].fn
        result = await fn()
        assert result["success"] is True
        assert result["initial_pokemon_count"] == 0
