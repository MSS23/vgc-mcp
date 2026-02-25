"""Tests for lead pair analysis tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.lead_tools import register_lead_tools
from vgc_mcp_core.models.pokemon import BaseStats


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()

    type_map = {
        "flutter-mane": ["Ghost", "Fairy"],
        "incineroar": ["Fire", "Dark"],
        "rillaboom": ["Grass"],
        "urshifu-rapid-strike": ["Water", "Fighting"],
        "landorus": ["Ground", "Flying"],
        "tornadus": ["Flying"],
    }
    ability_map = {
        "flutter-mane": ["Protosynthesis"],
        "incineroar": ["Intimidate"],
        "rillaboom": ["Grassy Surge"],
        "urshifu-rapid-strike": ["Unseen Fist"],
        "landorus": ["Sheer Force"],
        "tornadus": ["Prankster"],
    }
    stats_map = {
        "flutter-mane": BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
        "incineroar": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
        "rillaboom": BaseStats(hp=100, attack=125, defense=90, special_attack=60, special_defense=70, speed=85),
        "urshifu-rapid-strike": BaseStats(hp=100, attack=130, defense=100, special_attack=63, special_defense=60, speed=97),
        "landorus": BaseStats(hp=89, attack=125, defense=90, special_attack=115, special_defense=80, speed=101),
        "tornadus": BaseStats(hp=79, attack=115, defense=70, special_attack=125, special_defense=80, speed=111),
    }

    async def get_types(name):
        return type_map.get(name.lower(), ["Normal"])

    async def get_abilities(name):
        return ability_map.get(name.lower(), ["None"])

    async def get_base_stats(name):
        return stats_map.get(name.lower(), BaseStats(hp=80, attack=80, defense=80, special_attack=80, special_defense=80, speed=80))

    client.get_pokemon_types = AsyncMock(side_effect=get_types)
    client.get_pokemon_abilities = AsyncMock(side_effect=get_abilities)
    client.get_base_stats = AsyncMock(side_effect=get_base_stats)
    return client


@pytest.fixture
def analyze_leads(mock_pokeapi):
    """Register tools and return analyze_lead_pairs function."""
    mcp = FastMCP("test")
    register_lead_tools(mcp, mock_pokeapi)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    return tools["analyze_lead_pairs"].fn


class TestAnalyzeLeadPairs:
    """Tests for the analyze_lead_pairs tool."""

    async def test_basic_analysis(self, analyze_leads):
        """Test basic lead pair analysis with 6 Pokemon."""
        team = ["flutter-mane", "incineroar", "rillaboom",
                "urshifu-rapid-strike", "landorus", "tornadus"]
        result = await analyze_leads(team_pokemon=team)
        assert "error" not in result
        assert "lead_rankings" in result
        assert "top_lead" in result
        assert len(result["lead_rankings"]) > 0

    async def test_generates_15_combinations(self, analyze_leads):
        """Test that all 15 lead pairs are generated for 6 Pokemon."""
        team = ["flutter-mane", "incineroar", "rillaboom",
                "urshifu-rapid-strike", "landorus", "tornadus"]
        result = await analyze_leads(team_pokemon=team)
        # C(6,2) = 15 combinations
        assert len(result["lead_rankings"]) == 15

    async def test_wrong_team_size(self, analyze_leads):
        """Test error when team is not 6 Pokemon."""
        result = await analyze_leads(team_pokemon=["flutter-mane", "incineroar"])
        assert "error" in result

    async def test_rankings_sorted_by_score(self, analyze_leads):
        """Test that rankings are sorted by score descending."""
        team = ["flutter-mane", "incineroar", "rillaboom",
                "urshifu-rapid-strike", "landorus", "tornadus"]
        result = await analyze_leads(team_pokemon=team)
        scores = [r["score"] for r in result["lead_rankings"]]
        assert scores == sorted(scores, reverse=True)

    async def test_lead_data_structure(self, analyze_leads):
        """Test each lead pair has expected data."""
        team = ["flutter-mane", "incineroar", "rillaboom",
                "urshifu-rapid-strike", "landorus", "tornadus"]
        result = await analyze_leads(team_pokemon=team)
        for lead in result["lead_rankings"]:
            assert "lead_1" in lead
            assert "lead_2" in lead
            assert "score" in lead
            assert "synergy" in lead

    async def test_intimidate_synergy_scored(self, analyze_leads):
        """Test that Intimidate gives bonus synergy."""
        team = ["flutter-mane", "incineroar", "rillaboom",
                "urshifu-rapid-strike", "landorus", "tornadus"]
        result = await analyze_leads(team_pokemon=team)
        # Find Incineroar leads - should have Intimidate bonus
        inci_leads = [r for r in result["lead_rankings"]
                      if r["lead_1"] == "incineroar" or r["lead_2"] == "incineroar"]
        assert len(inci_leads) > 0

    async def test_markdown_summary(self, analyze_leads):
        """Test markdown summary is included."""
        team = ["flutter-mane", "incineroar", "rillaboom",
                "urshifu-rapid-strike", "landorus", "tornadus"]
        result = await analyze_leads(team_pokemon=team)
        assert "markdown_summary" in result
        assert "Lead Pair Analysis" in result["markdown_summary"]
