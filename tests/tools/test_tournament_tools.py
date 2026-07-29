"""Tests for tournament matchup analysis tools."""

from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.tournament_tools import register_tournament_tools
from vgc_mcp_core.data.sample_teams import ALL_SAMPLE_TEAMS


@pytest.fixture
def mock_pokepaste():
    """Create a mock PokePaste client."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    client = AsyncMock()
    return client


@pytest.fixture
def tools(mock_pokepaste, mock_pokeapi, mock_smogon):
    """Register tournament tools and return functions."""
    mcp = FastMCP("test")
    register_tournament_tools(mcp, mock_pokepaste, mock_pokeapi, mock_smogon)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestGetMetaTeams:
    """Tests for get_meta_teams."""

    async def test_returns_teams(self, tools):
        """Test that meta teams are returned."""
        fn = tools["get_meta_teams"].fn
        result = await fn()
        assert "total_teams" in result
        assert "teams" in result
        assert result["total_teams"] == len(ALL_SAMPLE_TEAMS)

    async def test_team_structure(self, tools):
        """Test team data structure."""
        fn = tools["get_meta_teams"].fn
        result = await fn()
        if result["teams"]:
            team = result["teams"][0]
            assert "name" in team
            assert "archetype" in team
            assert "pokemon" in team

    async def test_has_archetypes(self, tools):
        """Test that archetypes are listed."""
        fn = tools["get_meta_teams"].fn
        result = await fn()
        assert "archetypes" in result
        assert len(result["archetypes"]) > 0


class TestAnalyzeTeamVsMeta:
    """Tests for analyze_team_vs_meta."""

    async def test_paste_error(self, tools, mock_pokepaste):
        """Test handling paste fetch error."""
        from vgc_mcp_core.api.pokepaste import PokePasteError
        mock_pokepaste.get_paste.side_effect = PokePasteError("Not found")
        fn = tools["analyze_team_vs_meta"].fn
        result = await fn(pokepaste_url="https://pokepast.es/invalid")
        assert "error" in result


class TestCompareTwoTeams:
    """Tests for compare_two_teams."""

    async def test_paste_error(self, tools, mock_pokepaste):
        """Test handling paste fetch error."""
        mock_pokepaste.get_paste.side_effect = Exception("Network error")
        fn = tools["compare_two_teams"].fn
        result = await fn(
            team1_url="https://pokepast.es/team1",
            team2_url="https://pokepast.es/team2"
        )
        assert "error" in result


class TestAnalyzeVsSpecificTeam:
    """Tests for analyze_vs_specific_team."""

    async def test_invalid_archetype(self, tools):
        """Test with an invalid archetype."""
        fn = tools["analyze_vs_specific_team"].fn
        result = await fn(
            pokepaste_url="https://pokepast.es/abc",
            opponent_archetype="nonexistent_archetype"
        )
        assert "error" in result
        assert "available_archetypes" in result


def _paste(*names: str) -> str:
    return "\n\n".join(
        f"{n}\nLevel: 50\nSerious Nature\n- Protect" for n in names
    )


def _stock_pokeapi(mock_pokeapi):
    """Give every species the same real base stats/types so builds parse."""
    from vgc_mcp_core.models.pokemon import BaseStats
    mock_pokeapi.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=95, attack=115, defense=90, special_attack=80,
        special_defense=90, speed=60,
    ))
    mock_pokeapi.get_pokemon_types = AsyncMock(return_value=["fire", "dark"])


class TestAnalyzeTeamVsMetaFullFlow:
    async def test_too_few_pokemon_is_parse_error(self, tools, mock_pokepaste, mock_pokeapi):
        _stock_pokeapi(mock_pokeapi)
        mock_pokepaste.get_paste = AsyncMock(return_value=_paste("Incineroar", "Rillaboom"))
        fn = tools["analyze_team_vs_meta"].fn
        result = await fn(pokepaste_url="https://pokepast.es/abc")
        assert result["success"] is False
        assert result["parsed_pokemon"] == ["Incineroar", "Rillaboom"]

    async def test_full_matchup_run_against_one_meta_team(self, tools, mock_pokepaste, mock_pokeapi):
        _stock_pokeapi(mock_pokeapi)
        mock_pokepaste.get_paste = AsyncMock(return_value=_paste(
            "Incineroar", "Rillaboom", "Flutter Mane", "Urshifu"))
        fn = tools["analyze_team_vs_meta"].fn
        result = await fn(pokepaste_url="https://pokepast.es/abc", top_n=1)
        assert result["success"] is True
        assert result["teams_analyzed"] == 1
        report = result["matchup_reports"][0]
        assert 0 <= report["overall_advantage"] <= 100
        assert result["worst_matchup"] == result["best_matchup"] == report["opponent_name"]


class TestCompareTwoTeamsFullFlow:
    async def test_head_to_head_report(self, tools, mock_pokepaste, mock_pokeapi):
        _stock_pokeapi(mock_pokeapi)
        team1 = _paste("Incineroar", "Rillaboom", "Flutter Mane", "Urshifu")
        team2 = _paste("Tornadus", "Amoonguss", "Chi-Yu", "Landorus")
        mock_pokepaste.get_paste = AsyncMock(side_effect=[team1, team2])
        fn = tools["compare_two_teams"].fn
        result = await fn(
            team1_url="https://pokepast.es/t1", team2_url="https://pokepast.es/t2")
        assert result.get("success", True) is not False
        assert "advantage" in str(result).lower()
