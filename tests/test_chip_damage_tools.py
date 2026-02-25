"""Tests for chip damage calculation tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.chip_damage_tools import register_chip_damage_tools


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_pokemon_stats = AsyncMock(return_value={
        "hp": 95, "attack": 115, "defense": 90,
        "special-attack": 80, "special-defense": 90, "speed": 60
    })
    client.get_pokemon = AsyncMock(return_value={
        "name": "incineroar",
        "types": [
            {"type": {"name": "fire"}},
            {"type": {"name": "dark"}}
        ]
    })
    return client


@pytest.fixture
def tools(mock_pokeapi):
    """Register chip damage tools and return functions."""
    mcp = FastMCP("test")
    register_chip_damage_tools(mcp, mock_pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestCalculateWeatherDamage:
    """Tests for calculate_weather_damage."""

    async def test_sandstorm_damage(self, tools):
        """Test sandstorm damage on non-immune Pokemon."""
        fn = tools["calculate_weather_damage"].fn
        result = await fn(pokemon_name="incineroar", weather="sandstorm")
        assert result["immune"] is False
        assert result["damage_per_turn"] > 0

    async def test_immune_types(self, tools, mock_pokeapi):
        """Test sandstorm immunity for Steel type."""
        mock_pokeapi.get_pokemon.return_value = {
            "name": "metagross",
            "types": [{"type": {"name": "steel"}}, {"type": {"name": "psychic"}}]
        }
        fn = tools["calculate_weather_damage"].fn
        result = await fn(pokemon_name="metagross", weather="sandstorm")
        assert result["immune"] is True

    async def test_sun_no_damage(self, tools):
        """Test that sun doesn't do chip damage."""
        fn = tools["calculate_weather_damage"].fn
        result = await fn(pokemon_name="incineroar", weather="sun")
        assert result["damage_per_turn"] == 0


class TestCalculateStatusChip:
    """Tests for calculate_status_chip."""

    async def test_burn_damage(self, tools):
        """Test burn chip damage."""
        fn = tools["calculate_status_chip"].fn
        result = await fn(pokemon_name="incineroar", status="burn")
        assert result["damage_per_turn"] > 0
        assert result["status"] == "Burn"

    async def test_toxic_damage(self, tools):
        """Test toxic damage progression."""
        fn = tools["calculate_status_chip"].fn
        result = await fn(pokemon_name="incineroar", status="toxic")
        assert result["damage_per_turn"] > 0
        assert result["toxic_progression"] is not None
        assert len(result["toxic_progression"]) == 5


class TestCalculateGrassyTerrainHealing:
    """Tests for calculate_grassy_terrain_healing."""

    async def test_grounded_pokemon(self, tools):
        """Test grassy terrain healing for grounded Pokemon."""
        fn = tools["calculate_grassy_terrain_healing"].fn
        result = await fn(pokemon_name="incineroar")
        assert result["is_grounded"] is True
        assert result["receives_healing"] is True
        assert result["healing_per_turn"] > 0

    async def test_flying_pokemon(self, tools, mock_pokeapi):
        """Test flying Pokemon doesn't receive grassy healing."""
        mock_pokeapi.get_pokemon.return_value = {
            "name": "tornadus",
            "types": [{"type": {"name": "flying"}}]
        }
        fn = tools["calculate_grassy_terrain_healing"].fn
        result = await fn(pokemon_name="tornadus")
        assert result["is_grounded"] is False


class TestCalculateLeftoversHealing:
    """Tests for calculate_leftovers_healing."""

    async def test_leftovers(self, tools):
        """Test Leftovers recovery."""
        fn = tools["calculate_leftovers_healing"].fn
        result = await fn(pokemon_name="incineroar", item="leftovers")
        assert result["effect"] == "HEALING"
        assert result["healing_per_turn"] > 0

    async def test_black_sludge_non_poison(self, tools):
        """Test Black Sludge damages non-Poison types."""
        fn = tools["calculate_leftovers_healing"].fn
        result = await fn(pokemon_name="incineroar", item="black-sludge")
        assert result["effect"] == "DAMAGE"
        assert "warning" in result


class TestSimulateChipOverTurns:
    """Tests for simulate_chip_over_turns."""

    async def test_simulate_weather(self, tools):
        """Test simulating weather chip over turns."""
        fn = tools["simulate_chip_over_turns"].fn
        result = await fn(pokemon_name="incineroar", turns=5, weather="sandstorm")
        assert "final_hp" in result
        assert "turn_breakdown" in result

    async def test_simulate_clamps_turns(self, tools):
        """Test that turns are clamped to 1-20."""
        fn = tools["simulate_chip_over_turns"].fn
        result = await fn(pokemon_name="incineroar", turns=100)
        # Should be clamped to 20
        assert "final_hp" in result


class TestCalculateSurvivalWithChip:
    """Tests for calculate_survival_with_chip."""

    async def test_survives_with_chip(self, tools):
        """Test survival after attack plus chip."""
        fn = tools["calculate_survival_with_chip"].fn
        result = await fn(
            pokemon_name="incineroar",
            incoming_damage_percent=50.0,
            weather="sandstorm"
        )
        assert result["survives_attack"] is True
        assert "hp_after_chip" in result
        assert "verdict" in result

    async def test_ko_by_attack(self, tools):
        """Test KO'd by the attack itself."""
        fn = tools["calculate_survival_with_chip"].fn
        result = await fn(
            pokemon_name="incineroar",
            incoming_damage_percent=200.0
        )
        assert result["survives_attack"] is False
        assert result["hp_after_attack"] == 0
