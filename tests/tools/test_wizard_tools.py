"""Tests for team building wizard tools."""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.wizard_tools import register_wizard_tools


@pytest.fixture
def wizard():
    """Register tools and return team_building_wizard function."""
    mcp = FastMCP("test")
    register_wizard_tools(mcp)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    return tools["team_building_wizard"].fn


class TestTeamBuildingWizard:
    """Tests for the team_building_wizard tool."""

    async def test_step_1_choose_playstyle(self, wizard):
        """Test step 1 presents playstyle options."""
        result = await wizard(step=1)
        assert result["step"] == 1
        assert result["total_steps"] == 5
        assert "options" in result
        assert "A" in result["options"]
        assert "markdown_summary" in result

    async def test_step_2_choose_core(self, wizard):
        """Test step 2 presents core Pokemon options."""
        result = await wizard(
            step=2,
            previous_choices={"playstyle": "Hyper Offense"}
        )
        assert result["step"] == 2
        assert "suggestions" in result
        assert len(result["suggestions"]) > 0

    async def test_step_2_trick_room(self, wizard):
        """Test step 2 with Trick Room playstyle."""
        result = await wizard(
            step=2,
            previous_choices={"playstyle": "Trick Room"}
        )
        assert result["step"] == 2
        suggestions_text = " ".join(result["suggestions"])
        assert "Amoonguss" in suggestions_text or "slow" in suggestions_text.lower()

    async def test_step_3_support(self, wizard):
        """Test step 3 about support Pokemon."""
        result = await wizard(step=3)
        assert result["step"] == 3
        assert "markdown_summary" in result
        assert "Support" in result["markdown_summary"]

    async def test_step_4_counters(self, wizard):
        """Test step 4 about counters."""
        result = await wizard(step=4)
        assert result["step"] == 4
        assert "Counters" in result["markdown_summary"]

    async def test_step_5_finalize(self, wizard):
        """Test step 5 finalization."""
        result = await wizard(step=5)
        assert result["step"] == 5
        assert result.get("complete") is True

    async def test_invalid_step(self, wizard):
        """Test invalid step number."""
        result = await wizard(step=99)
        assert "error" in result

    async def test_step_0_invalid(self, wizard):
        """Test step 0 is invalid."""
        result = await wizard(step=0)
        assert "error" in result

    async def test_no_previous_choices(self, wizard):
        """Test step 2 with no previous choices defaults gracefully."""
        result = await wizard(step=2, previous_choices=None)
        assert result["step"] == 2
        assert "suggestions" in result

    async def test_all_steps_have_markdown(self, wizard):
        """Test all valid steps include markdown summary."""
        for step in range(1, 6):
            result = await wizard(step=step)
            assert "markdown_summary" in result, f"Step {step} missing markdown_summary"
