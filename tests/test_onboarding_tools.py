"""Tests for onboarding and discoverability tools."""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.onboarding_tools import register_onboarding_tools


@pytest.fixture
def mcp_with_onboarding():
    """Create an MCP server with onboarding tools registered."""
    mcp = FastMCP("test")
    register_onboarding_tools(mcp)
    return mcp


@pytest.fixture
def tools(mcp_with_onboarding):
    """Get all registered tool functions."""
    all_tools = {t.name: t for t in mcp_with_onboarding._tool_manager._tools.values()}
    return all_tools


class TestShowCapabilities:
    """Tests for the show_capabilities tool."""

    async def test_overview_no_category(self, tools):
        """Test capabilities overview with no category filter."""
        fn = tools["show_capabilities"].fn
        result = await fn(category=None)
        assert result["capabilities_type"] == "overview"
        assert "markdown_summary" in result
        assert "categories" in result
        assert "damage" in result["categories"]
        assert "team" in result["categories"]

    async def test_damage_category(self, tools):
        """Test damage category capabilities."""
        fn = tools["show_capabilities"].fn
        result = await fn(category="damage")
        assert result["capabilities_type"] == "category"
        assert result["category"] == "damage"
        assert "markdown_summary" in result
        assert "Damage" in result["markdown_summary"]

    async def test_team_category(self, tools):
        """Test team building category capabilities."""
        fn = tools["show_capabilities"].fn
        result = await fn(category="team")
        assert result["capabilities_type"] == "category"
        assert result["category"] == "team"

    async def test_team_building_alias(self, tools):
        """Test 'teambuilding' alias for team category."""
        fn = tools["show_capabilities"].fn
        result = await fn(category="teambuilding")
        assert result["capabilities_type"] == "category"
        assert result["category"] == "team"

    async def test_evs_category(self, tools):
        """Test EVs category capabilities."""
        fn = tools["show_capabilities"].fn
        result = await fn(category="evs")
        assert result["capabilities_type"] == "category"
        assert result["category"] == "evs"

    async def test_ev_alias(self, tools):
        """Test 'ev' alias for EVs category."""
        fn = tools["show_capabilities"].fn
        result = await fn(category="ev")
        assert result["capabilities_type"] == "category"
        assert result["category"] == "evs"

    async def test_speed_category(self, tools):
        """Test speed category capabilities."""
        fn = tools["show_capabilities"].fn
        result = await fn(category="speed")
        assert result["capabilities_type"] == "category"
        assert result["category"] == "speed"

    async def test_learn_category(self, tools):
        """Test learning category capabilities."""
        fn = tools["show_capabilities"].fn
        result = await fn(category="learn")
        assert result["capabilities_type"] == "category"
        assert result["category"] == "learn"

    async def test_learning_alias(self, tools):
        """Test 'learning' alias for learn category."""
        fn = tools["show_capabilities"].fn
        result = await fn(category="learning")
        assert result["capabilities_type"] == "category"
        assert result["category"] == "learn"

    async def test_unknown_category(self, tools):
        """Test unknown category returns error."""
        fn = tools["show_capabilities"].fn
        result = await fn(category="unknown_xyz")
        assert result["capabilities_type"] == "unknown"
        assert "available_categories" in result


class TestWelcomeNewUser:
    """Tests for the welcome_new_user tool."""

    async def test_welcome_message(self, tools):
        """Test welcome message is returned."""
        fn = tools["welcome_new_user"].fn
        result = await fn()
        assert result["welcome"] is True
        assert "markdown_summary" in result
        assert "Welcome" in result["markdown_summary"]

    async def test_suggested_prompts(self, tools):
        """Test suggested prompts are included."""
        fn = tools["welcome_new_user"].fn
        result = await fn()
        assert "suggested_prompts" in result
        assert len(result["suggested_prompts"]) > 0

    async def test_suggested_prompts_are_strings(self, tools):
        """Test all suggested prompts are strings."""
        fn = tools["welcome_new_user"].fn
        result = await fn()
        for prompt in result["suggested_prompts"]:
            assert isinstance(prompt, str)


class TestGetStarterPrompts:
    """Tests for the get_starter_prompts tool."""

    async def test_returns_prompts(self, tools):
        """Test that starter prompts are returned."""
        fn = tools["get_starter_prompts"].fn
        result = await fn()
        assert "prompts" in result
        assert "count" in result
        assert result["count"] == len(result["prompts"])

    async def test_prompt_structure(self, tools):
        """Test each prompt has required fields."""
        fn = tools["get_starter_prompts"].fn
        result = await fn()
        for prompt in result["prompts"]:
            assert "title" in prompt
            assert "prompt" in prompt
            assert "icon" in prompt
            assert "description" in prompt

    async def test_prompt_count(self, tools):
        """Test reasonable number of prompts."""
        fn = tools["get_starter_prompts"].fn
        result = await fn()
        assert result["count"] >= 3  # At least 3 starter prompts
        assert result["count"] <= 20  # Not too many
