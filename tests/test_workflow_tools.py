"""Tests for high-level workflow coordinator tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.workflow_tools import register_workflow_tools


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    return AsyncMock()


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    return AsyncMock()


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager."""
    manager = MagicMock()
    manager.size = 0
    manager.team = MagicMock()
    return manager


@pytest.fixture
def mock_analyzer():
    """Create a mock analyzer."""
    return MagicMock()


@pytest.fixture
def tools(mock_pokeapi, mock_smogon, mock_team_manager, mock_analyzer):
    """Register workflow tools and return functions."""
    mcp = FastMCP("test")
    register_workflow_tools(mcp, mock_pokeapi, mock_smogon, mock_team_manager, mock_analyzer)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestFullTeamCheck:
    """Tests for full_team_check."""

    async def test_empty_team_no_paste(self, tools):
        """Test with no team and no paste."""
        fn = tools["full_team_check"].fn
        result = await fn()
        assert "error" in result or result.get("success") is False

    async def test_invalid_paste(self, tools):
        """Test with an empty paste."""
        fn = tools["full_team_check"].fn
        result = await fn(paste="")
        assert "error" in result or result.get("success") is False
