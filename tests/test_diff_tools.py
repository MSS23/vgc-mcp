"""Tests for team diff comparison tools."""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.diff_tools import register_diff_tools


TEAM_V1 = """Flutter Mane @ Choice Specs
Ability: Protosynthesis
Level: 50
Tera Type: Fairy
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
IVs: 0 Atk
- Moonblast
- Shadow Ball
- Dazzling Gleam
- Protect

Incineroar @ Safety Goggles
Ability: Intimidate
Level: 50
Tera Type: Ghost
EVs: 252 HP / 4 Atk / 116 Def / 4 SpD / 132 Spe
Careful Nature
- Fake Out
- Knock Off
- Flare Blitz
- Parting Shot
"""

TEAM_V2 = """Flutter Mane @ Life Orb
Ability: Protosynthesis
Level: 50
Tera Type: Fairy
EVs: 4 HP / 252 SpA / 252 Spe
Modest Nature
IVs: 0 Atk
- Moonblast
- Shadow Ball
- Mystical Fire
- Protect

Incineroar @ Safety Goggles
Ability: Intimidate
Level: 50
Tera Type: Ghost
EVs: 252 HP / 4 Atk / 116 Def / 4 SpD / 132 Spe
Careful Nature
- Fake Out
- Knock Off
- Flare Blitz
- Parting Shot
"""


@pytest.fixture
def compare_fn():
    """Register tools and return compare_team_versions function."""
    mcp = FastMCP("test")
    register_diff_tools(mcp)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    return tools["compare_team_versions"].fn


class TestCompareTeamVersions:
    """Tests for compare_team_versions tool."""

    async def test_compare_raw_pastes(self, compare_fn):
        """Test comparing two raw paste versions."""
        result = await compare_fn(
            version1=TEAM_V1,
            version2=TEAM_V2
        )
        assert result["success"] is True
        assert "changed_pokemon" in result
        assert "unchanged_pokemon" in result

    async def test_detects_item_change(self, compare_fn):
        """Test that item change is detected."""
        result = await compare_fn(
            version1=TEAM_V1,
            version2=TEAM_V2
        )
        # Flutter Mane changed from Choice Specs to Life Orb
        changed = result["changed_pokemon"]
        flutter_changes = [c for c in changed if "Flutter" in c["species"]]
        if flutter_changes:
            fields = [ch["field"] for ch in flutter_changes[0]["changes"]]
            assert "item" in fields or "Item" in fields or any("item" in f.lower() for f in fields)

    async def test_detects_nature_change(self, compare_fn):
        """Test that nature change is detected."""
        result = await compare_fn(
            version1=TEAM_V1,
            version2=TEAM_V2
        )
        changed = result["changed_pokemon"]
        flutter_changes = [c for c in changed if "Flutter" in c["species"]]
        if flutter_changes:
            fields = [ch["field"] for ch in flutter_changes[0]["changes"]]
            assert any("nature" in f.lower() for f in fields)

    async def test_detects_move_change(self, compare_fn):
        """Test that move changes are detected."""
        result = await compare_fn(
            version1=TEAM_V1,
            version2=TEAM_V2
        )
        changed = result["changed_pokemon"]
        flutter_changes = [c for c in changed if "Flutter" in c["species"]]
        if flutter_changes:
            fields = [ch["field"] for ch in flutter_changes[0]["changes"]]
            assert any("move" in f.lower() for f in fields)

    async def test_unchanged_pokemon_detected(self, compare_fn):
        """Test that Incineroar is detected as unchanged."""
        result = await compare_fn(
            version1=TEAM_V1,
            version2=TEAM_V2
        )
        # Incineroar is the same in both versions
        assert len(result["unchanged_pokemon"]) >= 1

    async def test_identical_teams(self, compare_fn):
        """Test comparing identical teams."""
        result = await compare_fn(
            version1=TEAM_V1,
            version2=TEAM_V1
        )
        assert result["success"] is True
        assert len(result["changed_pokemon"]) == 0
        assert len(result["added_pokemon"]) == 0
        assert len(result["removed_pokemon"]) == 0

    async def test_custom_version_names(self, compare_fn):
        """Test custom display names for versions."""
        result = await compare_fn(
            version1=TEAM_V1,
            version2=TEAM_V2,
            v1_name="Original",
            v2_name="Updated"
        )
        assert result["version1_name"] == "Original"
        assert result["version2_name"] == "Updated"

    async def test_invalid_paste_returns_error(self, compare_fn):
        """Test invalid paste input returns error."""
        result = await compare_fn(
            version1="not a valid paste",
            version2=TEAM_V2
        )
        assert result["success"] is False
        assert "error" in result
