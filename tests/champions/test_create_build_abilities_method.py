"""Regression: create_build must call the REAL PokeAPI abilities method.

create_build was wired to ``pokeapi.get_abilities(...)`` which does NOT exist on
PokeAPIClient (the real method is ``get_pokemon_abilities`` and returns
``list[str]``). With a live client every call raised AttributeError and was
swallowed into an internal_error, so the SP/EV logic was never reached in
either format.

The pre-existing champions suite missed this because its fixture used a lenient
``AsyncMock`` that auto-creates any attribute (``get_abilities`` included),
masking the typo. These tests pin the mock to the REAL surface of
``PokeAPIClient`` via ``spec=`` so that ``get_abilities`` is NOT available — a
build wired to the wrong method name fails here, while the fixed code passes.

Champions assertions: 32 Speed SP -> Speed 205 after round-trip; >32 / >66 are
rejected. Mainline assertions: EVs stored, 32 EV Speed -> 174, >508 rejected.
"""

from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.build_tools import register_build_tools
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.stats import calculate_all_stats
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.rules.regulation_loader import (
    get_regulation_config,
    reset_regulation_config,
)
from vgc_mcp_core.state.build_manager import BuildStateManager

FLUTTER_MANE_BASE = BaseStats(
    hp=55, attack=55, defense=55,
    special_attack=135, special_defense=135, speed=135,
)


@pytest.fixture
def champions_session():
    reset_regulation_config()
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_ma_champs", by_user=True)
    assert cfg.get_format_system() == "champions"
    yield cfg
    reset_regulation_config()


@pytest.fixture
def mainline_session():
    reset_regulation_config()
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_f", by_user=True)
    assert cfg.get_format_system() == "mainline"
    yield cfg
    reset_regulation_config()


@pytest.fixture
def strict_pokeapi():
    """Mock pinned to the REAL PokeAPIClient surface.

    ``spec=PokeAPIClient`` makes accessing ``get_abilities`` raise
    AttributeError (it is not a real method), so the regression bug surfaces
    instead of being silently auto-mocked.
    """
    client = AsyncMock(spec=PokeAPIClient)
    client.get_base_stats = AsyncMock(return_value=FLUTTER_MANE_BASE)
    client.get_pokemon_types = AsyncMock(return_value=["Ghost", "Fairy"])
    client.get_pokemon_abilities = AsyncMock(return_value=["Protosynthesis"])
    return client


@pytest.fixture
def build_tools(strict_pokeapi):
    mcp = FastMCP("test")
    build_manager = BuildStateManager()
    register_build_tools(mcp, build_manager, strict_pokeapi)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    return tools, build_manager, strict_pokeapi


def test_strict_mock_lacks_get_abilities(strict_pokeapi):
    """Guard: the spec'd mock must NOT expose the buggy method name."""
    assert hasattr(strict_pokeapi, "get_pokemon_abilities")
    with pytest.raises(AttributeError):
        _ = strict_pokeapi.get_abilities


class TestCreateBuildChampions:
    async def test_calls_real_abilities_method_and_stores_sps(
        self, champions_session, build_tools
    ):
        tools, build_manager, api = build_tools
        result = await tools["create_build"].fn(
            pokemon_name="flutter-mane", nature="Timid", spe_evs=32,
        )

        # Reached the SP logic (would be internal_error if the wrong method
        # name were used against the strict mock).
        assert result["success"] is True
        api.get_pokemon_abilities.assert_awaited_once_with("flutter-mane")

        assert result["build"]["format_system"] == "champions"
        assert result["build"]["ability"] == "Protosynthesis"
        assert result["build"]["sps"]["speed"] == 32
        assert "evs" not in result["build"]

        rebuilt = build_manager.to_pokemon_build(result["build_id"])
        assert rebuilt.format_system == "champions"
        assert calculate_all_stats(rebuilt)["speed"] == 205

    async def test_ev_scale_input_coerced_to_sps(self, champions_session, build_tools):
        # A stat > 32 is unambiguously EV-scale input: it now converts to SPs
        # (100 EV -> 13 SP) instead of failing the per-stat cap.
        tools, _, _ = build_tools
        result = await tools["create_build"].fn(
            pokemon_name="flutter-mane", spe_evs=100,
        )
        assert result["success"] is True
        assert result["build"]["sps"]["speed"] == 13
        assert result["sp_conversion"]["converted_sps"] == {"speed": 13}

    async def test_total_cap_enforced(self, champions_session, build_tools):
        tools, _, _ = build_tools
        result = await tools["create_build"].fn(
            pokemon_name="flutter-mane",
            hp_evs=32, spa_evs=32, spe_evs=32,  # 96 > 66
        )
        assert result["success"] is False
        assert result["error"] == "invalid_evs"


class TestCreateBuildMainline:
    async def test_calls_real_abilities_method_and_stores_evs(
        self, mainline_session, build_tools
    ):
        tools, build_manager, api = build_tools
        result = await tools["create_build"].fn(
            pokemon_name="flutter-mane", nature="Timid", spe_evs=32,
        )
        assert result["success"] is True
        api.get_pokemon_abilities.assert_awaited_once_with("flutter-mane")

        assert result["build"]["ability"] == "Protosynthesis"
        assert "evs" in result["build"]
        assert "sps" not in result["build"]

        rebuilt = build_manager.to_pokemon_build(result["build_id"])
        assert rebuilt.format_system == "mainline"
        assert calculate_all_stats(rebuilt)["speed"] == 174

    async def test_over_508_rejected(self, mainline_session, build_tools):
        tools, _, _ = build_tools
        result = await tools["create_build"].fn(
            pokemon_name="flutter-mane",
            hp_evs=252, atk_evs=252, spe_evs=252,  # 756 > 508
        )
        assert result["success"] is False
        assert result["error"] == "invalid_evs"
