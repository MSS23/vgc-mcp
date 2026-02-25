"""Tests for build checker tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.build_checker_tools import register_build_checker_tools
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.models.move import Move, MoveCategory


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=55, attack=55, defense=55,
        special_attack=135, special_defense=135, speed=135
    ))
    # Mock a special move (Moonblast)
    client.get_move = AsyncMock(return_value=Move(
        name="moonblast",
        type="Fairy",
        category=MoveCategory.SPECIAL,
        power=95,
        accuracy=100,
        pp=15
    ))
    return client


@pytest.fixture
def check_build(mock_pokeapi):
    """Register tools and return check_build_for_mistakes function."""
    mcp = FastMCP("test")
    register_build_checker_tools(mcp, mock_pokeapi)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    return tools["check_build_for_mistakes"].fn


class TestCheckBuildForMistakes:
    """Tests for the check_build_for_mistakes tool."""

    async def test_good_build_no_issues(self, check_build):
        """Test a good build with no issues."""
        result = await check_build(
            pokemon_name="flutter-mane",
            nature="timid",
            evs={"hp": 4, "attack": 0, "defense": 0,
                 "special_attack": 252, "special_defense": 0, "speed": 252},
            moves=["moonblast", "shadow-ball", "dazzling-gleam", "protect"],
            item="choice-specs"
        )
        assert "error" not in result
        assert result["rating_score"] >= 80

    async def test_nature_move_mismatch_physical_attacker_with_spa_nature(self, check_build, mock_pokeapi):
        """Test detecting nature/move mismatch for physical attacker."""
        # Mock a physical move
        mock_pokeapi.get_move = AsyncMock(return_value=Move(
            name="close-combat",
            type="Fighting",
            category=MoveCategory.PHYSICAL,
            power=120,
            accuracy=100,
            pp=5
        ))
        result = await check_build(
            pokemon_name="urshifu",
            nature="modest",  # -Atk! Bad for physical attacker
            evs={"hp": 4, "attack": 252, "defense": 0,
                 "special_attack": 0, "special_defense": 0, "speed": 252},
            moves=["close-combat", "surging-strikes", "aqua-jet", "u-turn"]
        )
        # Should detect nature/move mismatch
        issues = result.get("issues", [])
        has_mismatch = any(i["type"] == "nature_move_mismatch" for i in issues)
        assert has_mismatch, "Should detect nature/move mismatch"

    async def test_wasted_evs_not_multiple_of_4(self, check_build):
        """Test detecting wasted EVs not in multiples of 4."""
        result = await check_build(
            pokemon_name="flutter-mane",
            nature="timid",
            evs={"hp": 5, "attack": 0, "defense": 0,  # 5 is not multiple of 4
                 "special_attack": 252, "special_defense": 0, "speed": 251},  # 251 too
            moves=["moonblast"],
        )
        issues = result.get("issues", [])
        has_wasted = any(i["type"] == "wasted_evs" for i in issues)
        assert has_wasted, "Should detect non-multiple-of-4 EVs"

    async def test_too_many_evs(self, check_build):
        """Test detecting total EVs exceeding 508."""
        result = await check_build(
            pokemon_name="flutter-mane",
            nature="timid",
            evs={"hp": 252, "attack": 252, "defense": 252,
                 "special_attack": 0, "special_defense": 0, "speed": 0},
            moves=["moonblast"],
        )
        issues = result.get("issues", [])
        has_too_many = any(i["type"] == "too_many_evs" for i in issues)
        assert has_too_many, "Should detect EVs exceeding 508"

    async def test_unused_evs_recommendation(self, check_build):
        """Test recommendation for unused EVs."""
        result = await check_build(
            pokemon_name="flutter-mane",
            nature="timid",
            evs={"hp": 0, "attack": 0, "defense": 0,
                 "special_attack": 252, "special_defense": 0, "speed": 252},
            moves=["moonblast"],
        )
        recs = result.get("recommendations", [])
        has_unused = any(r["type"] == "unused_evs" for r in recs)
        assert has_unused, "Should recommend using remaining 4 EVs"

    async def test_missing_protect_recommendation(self, check_build):
        """Test recommendation for missing Protect."""
        result = await check_build(
            pokemon_name="flutter-mane",
            nature="timid",
            evs={"hp": 4, "attack": 0, "defense": 0,
                 "special_attack": 252, "special_defense": 0, "speed": 252},
            moves=["moonblast", "shadow-ball", "dazzling-gleam", "thunderbolt"],
            item="life-orb"  # Non-Choice item, no Protect
        )
        recs = result.get("recommendations", [])
        has_protect = any(r["type"] == "missing_protect" for r in recs)
        assert has_protect, "Should recommend adding Protect"

    async def test_choice_item_no_protect_warning(self, check_build):
        """Test that Choice item users don't get Protect recommendation."""
        result = await check_build(
            pokemon_name="flutter-mane",
            nature="timid",
            evs={"hp": 4, "attack": 0, "defense": 0,
                 "special_attack": 252, "special_defense": 0, "speed": 252},
            moves=["moonblast", "shadow-ball", "dazzling-gleam", "thunderbolt"],
            item="choice-specs"
        )
        recs = result.get("recommendations", [])
        has_protect = any(r["type"] == "missing_protect" for r in recs)
        assert not has_protect, "Choice item users shouldn't get Protect warning"

    async def test_invalid_nature(self, check_build):
        """Test invalid nature returns error."""
        result = await check_build(
            pokemon_name="flutter-mane",
            nature="xyzinvalidnature",
            evs={"hp": 0, "attack": 0, "defense": 0,
                 "special_attack": 252, "special_defense": 0, "speed": 252},
            moves=["moonblast"],
        )
        assert "error" in result

    async def test_rating_scores(self, check_build):
        """Test that rating is calculated."""
        result = await check_build(
            pokemon_name="flutter-mane",
            nature="timid",
            evs={"hp": 4, "attack": 0, "defense": 0,
                 "special_attack": 252, "special_defense": 0, "speed": 252},
            moves=["moonblast", "shadow-ball", "dazzling-gleam", "protect"],
        )
        assert "rating" in result
        assert result["rating"] in ["A", "B+", "B", "C+", "C"]

    async def test_markdown_summary(self, check_build):
        """Test markdown summary is included."""
        result = await check_build(
            pokemon_name="flutter-mane",
            nature="timid",
            evs={"hp": 4, "attack": 0, "defense": 0,
                 "special_attack": 252, "special_defense": 0, "speed": 252},
            moves=["moonblast"],
        )
        assert "markdown_summary" in result
        assert "Build Check" in result["markdown_summary"]
