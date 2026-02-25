"""Tests for PokePaste integration tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.pokepaste_tools import register_pokepaste_tools
from vgc_mcp_core.api.pokepaste import PokePasteError


SAMPLE_PASTE = """Flutter Mane @ Choice Specs
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


@pytest.fixture
def mock_pokepaste():
    """Create a mock PokePaste client."""
    client = AsyncMock()
    client.get_paste = AsyncMock(return_value=SAMPLE_PASTE)
    client.extract_paste_id = MagicMock(return_value="abc123")
    return client


@pytest.fixture
def tools(mock_pokepaste):
    """Register pokepaste tools and return tool functions."""
    mcp = FastMCP("test")
    register_pokepaste_tools(mcp, mock_pokepaste)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestFetchPokepaste:
    """Tests for the fetch_pokepaste tool."""

    async def test_fetch_valid_paste(self, tools, mock_pokepaste):
        """Test fetching and parsing a valid paste."""
        fn = tools["fetch_pokepaste"].fn
        result = await fn(url_or_id="https://pokepast.es/abc123")
        assert result.get("success") is True
        assert result["pokemon_count"] == 2
        assert result["paste_id"] == "abc123"

    async def test_team_data_structure(self, tools):
        """Test parsed team data has expected fields."""
        fn = tools["fetch_pokepaste"].fn
        result = await fn(url_or_id="abc123")
        team = result["team"]
        for mon in team:
            assert "species" in mon
            assert "moves" in mon
            assert "evs" in mon
            assert "nature" in mon

    async def test_flutter_mane_parsed(self, tools):
        """Test Flutter Mane is correctly parsed from the paste."""
        fn = tools["fetch_pokepaste"].fn
        result = await fn(url_or_id="abc123")
        flutter = result["team"][0]
        assert "Flutter Mane" in flutter["species"]
        assert flutter["item"] == "Choice Specs"
        assert "Moonblast" in flutter["moves"]

    async def test_ev_total_calculated(self, tools):
        """Test EV total is calculated for each Pokemon."""
        fn = tools["fetch_pokepaste"].fn
        result = await fn(url_or_id="abc123")
        for mon in result["team"]:
            assert "ev_total" in mon

    async def test_paste_error_handled(self, tools, mock_pokepaste):
        """Test PokePaste error is handled gracefully."""
        mock_pokepaste.get_paste.side_effect = PokePasteError("Paste not found")
        fn = tools["fetch_pokepaste"].fn
        result = await fn(url_or_id="invalid")
        assert "error" in result


class TestAnalyzePokepaste:
    """Tests for the analyze_pokepaste tool."""

    async def test_analyze_valid_paste(self, tools):
        """Test analyzing a valid paste."""
        fn = tools["analyze_pokepaste"].fn
        result = await fn(url_or_id="abc123")
        assert "error" not in result
        assert "pokemon_analysis" in result
        assert "team_analysis" in result

    async def test_team_analysis_structure(self, tools):
        """Test team analysis has expected fields."""
        fn = tools["analyze_pokepaste"].fn
        result = await fn(url_or_id="abc123")
        team = result["team_analysis"]
        assert "has_speed_control" in team
        assert "has_fake_out" in team
        assert "has_redirection" in team
        assert "restricted_count" in team

    async def test_detects_fake_out(self, tools):
        """Test detection of Fake Out user (Incineroar)."""
        fn = tools["analyze_pokepaste"].fn
        result = await fn(url_or_id="abc123")
        assert result["team_analysis"]["has_fake_out"] is True

    async def test_paste_error_handled(self, tools, mock_pokepaste):
        """Test analysis handles paste errors."""
        mock_pokepaste.get_paste.side_effect = PokePasteError("Not found")
        fn = tools["analyze_pokepaste"].fn
        result = await fn(url_or_id="invalid")
        assert "error" in result


class TestOptimizePokepastePokemon:
    """Tests for the optimize_pokepaste_pokemon tool."""

    async def test_optimize_first_pokemon(self, tools):
        """Test optimizing the first Pokemon."""
        fn = tools["optimize_pokepaste_pokemon"].fn
        result = await fn(url_or_id="abc123", pokemon_index=0)
        assert "error" not in result
        assert "species" in result
        assert "current_build" in result

    async def test_invalid_index(self, tools):
        """Test invalid Pokemon index."""
        fn = tools["optimize_pokepaste_pokemon"].fn
        result = await fn(url_or_id="abc123", pokemon_index=99)
        assert "error" in result

    async def test_ev_efficiency_check(self, tools):
        """Test EV efficiency is checked."""
        fn = tools["optimize_pokepaste_pokemon"].fn
        result = await fn(url_or_id="abc123", pokemon_index=0)
        # Flutter Mane has 508 EVs, so no efficiency warning
        optimizations = result.get("optimizations", [])
        ev_issues = [o for o in optimizations if o["type"] == "ev_efficiency"]
        # 4+252+252 = 508, so no issue expected
        assert len(ev_issues) == 0
