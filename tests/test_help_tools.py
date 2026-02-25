"""Tests for help and guidance tools."""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.help_tools import register_help_tools


@pytest.fixture
def get_help():
    """Create an MCP server with help tools and return get_help function."""
    mcp = FastMCP("test")
    register_help_tools(mcp)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    return tools["get_help"].fn


class TestGetHelp:
    """Tests for the get_help tool."""

    async def test_main_help_menu(self, get_help):
        """Test main help menu with no topic."""
        result = await get_help(topic=None)
        assert result["help_type"] == "main_menu"
        assert "markdown_summary" in result
        assert "available_topics" in result
        assert "damage" in result["available_topics"]

    async def test_damage_topic(self, get_help):
        """Test damage help topic."""
        result = await get_help(topic="damage")
        assert result["help_type"] == "topic"
        assert result["topic"] == "damage"
        assert "OHKO" in result["markdown_summary"]

    async def test_team_building_topic(self, get_help):
        """Test team building help topic."""
        result = await get_help(topic="team building")
        assert result["help_type"] == "topic"
        assert result["topic"] == "team building"
        assert "Team Building" in result["markdown_summary"]

    async def test_team_alias(self, get_help):
        """Test 'team' alias for team building."""
        result = await get_help(topic="team")
        assert result["help_type"] == "topic"
        assert result["topic"] == "team building"

    async def test_teambuilding_alias(self, get_help):
        """Test 'teambuilding' alias for team building."""
        result = await get_help(topic="teambuilding")
        assert result["help_type"] == "topic"
        assert result["topic"] == "team building"

    async def test_speed_topic(self, get_help):
        """Test speed help topic."""
        result = await get_help(topic="speed")
        assert result["help_type"] == "topic"
        assert result["topic"] == "speed"
        assert "Speed" in result["markdown_summary"]

    async def test_unknown_topic(self, get_help):
        """Test unknown topic returns appropriate response."""
        result = await get_help(topic="xyznonexistent")
        assert result["help_type"] == "unknown_topic"
        assert "available_topics" in result

    async def test_markdown_has_headers(self, get_help):
        """Test that markdown content includes section headers."""
        result = await get_help(topic=None)
        md = result["markdown_summary"]
        assert "##" in md  # Has markdown headers

    async def test_main_menu_has_examples(self, get_help):
        """Test main menu includes example questions."""
        result = await get_help(topic=None)
        md = result["markdown_summary"]
        # Should include example prompts
        assert "Flutter Mane" in md or "team" in md.lower()
