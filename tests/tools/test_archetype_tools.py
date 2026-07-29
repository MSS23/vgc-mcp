"""Tests for the rule-based team archetype classifier."""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.archetype_tools import register_archetype_tools

TRICK_ROOM_TEAM = ["indeedee-female", "hatterene", "ursaluna", "torkoal", "incineroar", "amoonguss"]
RAIN_TEAM = ["pelipper", "archaludon", "basculegion-male", "rillaboom", "incineroar", "amoonguss"]
SUN_TEAM = ["torkoal", "venusaur", "walking-wake", "flutter-mane"]


@pytest.fixture
def classify():
    mcp = FastMCP("test")
    register_archetype_tools(mcp)
    return {t.name: t for t in mcp._tool_manager._tools.values()}["classify_team_archetype"].fn


class TestClassification:
    async def test_trick_room_team(self, classify):
        result = await classify(pokemon_names=TRICK_ROOM_TEAM)
        assert result["success"] is True
        assert result["archetype"] == "Trick Room"
        # Setter + abuser present → boosted confidence
        assert result["confidence"] >= 0.8
        assert "indeedee-female" in result["triggers"]["TR setters"]

    async def test_rain_team(self, classify):
        result = await classify(pokemon_names=RAIN_TEAM)
        assert result["archetype"] == "Rain"
        assert "pelipper" in result["triggers"]["rain setters"]

    async def test_sun_team(self, classify):
        result = await classify(pokemon_names=SUN_TEAM)
        assert result["archetype"] == "Sun"

    async def test_no_signature_pieces_falls_back_to_balance(self, classify):
        result = await classify(pokemon_names=["pikachu", "charizard", "blastoise", "venusaur-mega"])
        assert result["success"] is True
        assert result["archetype"] == "Balance / Other"

    async def test_names_are_normalized(self, classify):
        # Spaces and capitals must match the hyphenated lowercase tables
        result = await classify(pokemon_names=["Indeedee Female", "Hatterene", "Ursaluna", "Torkoal"])
        assert result["archetype"] == "Trick Room"

    async def test_response_contract(self, classify):
        result = await classify(pokemon_names=TRICK_ROOM_TEAM)
        for key in ("team", "archetype", "confidence", "all_scores", "triggers",
                    "win_condition", "recommended_brings"):
            assert key in result
        assert 0.0 <= result["confidence"] <= 1.0


class TestPasteInput:
    async def test_paste_is_parsed(self, classify):
        paste = "\n\n".join(
            f"{name}\nLevel: 50\nSerious Nature\n- Protect"
            for name in ("Pelipper", "Archaludon", "Rillaboom", "Incineroar")
        )
        result = await classify(paste=paste)
        assert result["success"] is True
        assert result["archetype"] == "Rain"

    async def test_junk_paste_is_error(self, classify):
        # The parser is lenient — junk "parses" into one garbage species,
        # which must then fail the minimum-team-size check.
        result = await classify(paste="::::not a paste::::")
        assert result["success"] is False


class TestErrors:
    async def test_no_input_is_error(self, classify):
        result = await classify()
        assert result["success"] is False

    async def test_too_few_pokemon_is_error(self, classify):
        result = await classify(pokemon_names=["pelipper", "archaludon"])
        assert result["success"] is False
        assert "3" in result["message"]
