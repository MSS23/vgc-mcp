"""Tests for matchup analysis tools."""

import pytest
from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.matchup_tools import register_matchup_tools
from vgc_mcp_core.team.manager import TeamManager


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager."""
    manager = MagicMock(spec=TeamManager)
    manager.size = 0
    manager.team = MagicMock()
    manager.team.get_pokemon_names.return_value = []
    return manager


@pytest.fixture
def tools(mock_team_manager):
    """Register matchup tools and return functions."""
    mcp = FastMCP("test")
    register_matchup_tools(mcp, mock_team_manager)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestAnalyzeMatchup:
    """Tests for analyze_matchup."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["analyze_matchup"].fn
        result = await fn(threat_name="flutter-mane")
        assert "error" in result

    async def test_unknown_threat(self, tools, mock_team_manager):
        """Test with an unknown threat."""
        mock_team_manager.size = 1
        fn = tools["analyze_matchup"].fn
        result = await fn(threat_name="not-a-real-pokemon")
        assert "error" in result
        assert "available_threats" in result


class TestFindThreatsToTeam:
    """Tests for find_threats_to_team."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["find_threats_to_team"].fn
        result = await fn()
        assert "error" in result


class TestCheckOffensiveCoverage:
    """Tests for check_offensive_coverage."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["check_offensive_coverage"].fn
        result = await fn(target_type="Steel")
        assert "error" in result


class TestCheckDefensiveMatchup:
    """Tests for check_defensive_matchup."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["check_defensive_matchup"].fn
        result = await fn(attacking_type="Ground")
        assert "error" in result


class TestGetAvailableThreats:
    """Tests for get_available_threats."""

    async def test_returns_threats(self, tools):
        """Test that it returns available threats."""
        fn = tools["get_available_threats"].fn
        result = await fn()
        assert "threat_count" in result
        assert result["threat_count"] > 0
        assert "threats" in result

    async def test_threat_structure(self, tools):
        """Test threat data structure."""
        fn = tools["get_available_threats"].fn
        result = await fn()
        if result["threats"]:
            threat = result["threats"][0]
            assert "name" in threat
            assert "types" in threat


class TestFullMatchupReport:
    """Tests for full_matchup_report."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["full_matchup_report"].fn
        result = await fn()
        assert "error" in result
