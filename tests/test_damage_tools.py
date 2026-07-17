"""Tests for damage calculation tools."""

from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.damage_tools import _normalize_smogon_name, register_damage_tools
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import BaseStats


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()

    async def _get_base_stats(name):
        stats = {
            "incineroar": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
            "flutter-mane": BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
        }
        return stats.get(name.lower(), BaseStats(hp=80, attack=80, defense=80, special_attack=80, special_defense=80, speed=80))

    async def _get_types(name):
        types_map = {
            "incineroar": ["Fire", "Dark"],
            "flutter-mane": ["Ghost", "Fairy"],
        }
        return types_map.get(name.lower(), ["Normal"])

    async def _get_abilities(name):
        return ["Intimidate"]

    async def _get_move(name, user_name=None):
        moves = {
            "moonblast": Move(name="moonblast", power=95, type="fairy", category=MoveCategory.SPECIAL, accuracy=100, pp=15, priority=0),
            "flare-blitz": Move(name="flare-blitz", power=120, type="fire", category=MoveCategory.PHYSICAL, accuracy=100, pp=15, priority=0),
        }
        return moves.get(name.lower())

    client.get_base_stats = AsyncMock(side_effect=_get_base_stats)
    client.get_pokemon_types = AsyncMock(side_effect=_get_types)
    client.get_pokemon_abilities = AsyncMock(side_effect=_get_abilities)
    client.get_move = AsyncMock(side_effect=_get_move)
    return client


@pytest.fixture
def tools(mock_pokeapi):
    """Register damage tools and return functions."""
    mcp = FastMCP("test")
    register_damage_tools(mcp, mock_pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestNormalizeSmogonName:
    """Tests for _normalize_smogon_name helper."""

    def test_known_items(self):
        assert _normalize_smogon_name("lifeorb") == "life-orb"
        assert _normalize_smogon_name("choiceband") == "choice-band"
        assert _normalize_smogon_name("assaultvest") == "assault-vest"

    def test_already_hyphenated(self):
        assert _normalize_smogon_name("life-orb") == "life-orb"

    def test_unknown_name(self):
        result = _normalize_smogon_name("some-unknown-item")
        assert isinstance(result, str)


class TestCalculateDamageOutput:
    """Tests for calculate_damage_output."""

    def test_schema_exposes_complete_attacker_and_defender_spreads(self, tools):
        properties = tools["calculate_damage_output"].parameters["properties"]
        assert {
            "attacker_hp_evs",
            "attacker_def_evs",
            "attacker_spd_evs",
            "attacker_spe_evs",
            "defender_atk_evs",
            "defender_spa_evs",
            "defender_spe_evs",
        } <= properties.keys()

        booster_schema = properties["attacker_booster_energy"]
        assert booster_schema["default"] is None
        assert {branch.get("type") for branch in booster_schema["anyOf"]} == {
            "boolean",
            "null",
        }

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test with invalid attacker."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["calculate_damage_output"].fn
        result = await fn(
            attacker_name="fakemon",
            defender_name="incineroar",
            move_name="moonblast"
        )
        assert "error" in result

    async def test_invalid_nature(self, tools):
        """Test with invalid attacker nature."""
        fn = tools["calculate_damage_output"].fn
        result = await fn(
            attacker_name="flutter-mane",
            defender_name="incineroar",
            move_name="moonblast",
            attacker_nature="notanature"
        )
        assert "error" in result

    async def test_basic_damage_calc(self, tools):
        """Test basic damage calculation."""
        fn = tools["calculate_damage_output"].fn
        result = await fn(
            attacker_name="flutter-mane",
            defender_name="incineroar",
            move_name="moonblast"
        )
        # Should return damage result or structured response
        assert isinstance(result, dict)
        assert "error" not in result or "damage" in str(result).lower()

    async def test_speed_investment_makes_protosynthesis_boost_speed(self, tools):
        """Timid 252 SpA / 4 SpD / 252 Spe Flutter Mane is Speed-boosted.

        The Speed boost must not inflate Moonblast damage.
        """
        fn = tools["calculate_damage_output"].fn
        common = {
            "attacker_name": "flutter-mane",
            "defender_name": "incineroar",
            "move_name": "moonblast",
            "attacker_nature": "timid",
            "attacker_spa_evs": 252,
            "attacker_spd_evs": 4,
            "attacker_spe_evs": 252,
            "attacker_item": "booster-energy",
            "attacker_ability": "Protosynthesis",
            "defender_nature": "careful",
            "defender_hp_evs": 252,
            "defender_spd_evs": 252,
            "use_smogon_spreads": False,
            "num_defender_spreads": 1,
        }

        boosted = await fn(**common, attacker_booster_energy=True)
        inactive = await fn(**common, attacker_booster_energy=False)

        assert boosted["damage"] == inactive["damage"]
        assert boosted["ability_effects"] == [
            "Protosynthesis: Attacker's Speed boosted (1.3x, 1.5x for Speed)"
        ]
        assert "252 SpA / 4 SpD / 252 Spe" in boosted["attacker_showdown_paste"]
        assert "252 SpA / 4 SpD / 252 Spe" in boosted["attacker_ev_spread"]

    async def test_explicit_false_disables_booster_item_inference(self, tools):
        """False is authoritative; omission retains convenient item inference."""
        fn = tools["calculate_damage_output"].fn
        common = {
            "attacker_name": "flutter-mane",
            "defender_name": "incineroar",
            "move_name": "moonblast",
            "attacker_nature": "timid",
            "attacker_spa_evs": 252,
            "attacker_item": "booster-energy",
            "attacker_ability": "Protosynthesis",
            "defender_nature": "careful",
            "defender_hp_evs": 252,
            "defender_spd_evs": 252,
            "use_smogon_spreads": False,
            "num_defender_spreads": 1,
        }

        inactive = await fn(**common, attacker_booster_energy=False)
        active = await fn(**common, attacker_booster_energy=True)
        inferred = await fn(**common)

        assert "ability_effects" not in inactive
        assert active["ability_effects"] == [
            "Protosynthesis: Attacker's Special Attack boosted (1.3x, 1.5x for Speed)"
        ]
        assert active["damage"] == inferred["damage"]
        assert active["damage"]["min"] > inactive["damage"]["min"]
        assert active["damage"]["max"] > inactive["damage"]["max"]


class TestFindKoEvs:
    """Tests for find_ko_evs."""

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["find_ko_evs"].fn
        result = await fn(
            attacker_name="flutter-mane",
            defender_name="incineroar",
            move_name="moonblast",
            attacker_nature="notanature"
        )
        assert "error" in result

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when attacker is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["find_ko_evs"].fn
        result = await fn(
            attacker_name="fakemon",
            defender_name="incineroar",
            move_name="moonblast"
        )
        assert "error" in result


class TestFindSurvivalEvs:
    """Tests for find_survival_evs."""

    async def test_invalid_nature(self, tools):
        """Test with invalid defender nature."""
        fn = tools["find_survival_evs"].fn
        result = await fn(
            attacker_name="flutter-mane",
            defender_name="incineroar",
            move_name="moonblast",
            defender_nature="notanature"
        )
        assert "error" in result

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when defender is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["find_survival_evs"].fn
        result = await fn(
            attacker_name="flutter-mane",
            defender_name="fakemon",
            move_name="moonblast"
        )
        assert "error" in result
