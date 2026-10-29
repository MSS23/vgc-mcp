"""Tests for high-level workflow coordinator tools."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.workflow_tools import register_workflow_tools


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    return AsyncMock()


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    return AsyncMock()


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager."""
    manager = MagicMock()
    manager.size = 0
    manager.team = MagicMock()
    return manager


@pytest.fixture
def mock_analyzer():
    """Create a mock analyzer."""
    return MagicMock()


@pytest.fixture
def tools(mock_pokeapi, mock_smogon, mock_team_manager, mock_analyzer):
    """Register workflow tools and return functions."""
    mcp = FastMCP("test")
    register_workflow_tools(mcp, mock_pokeapi, mock_smogon, mock_team_manager, mock_analyzer)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestFullTeamCheck:
    """Tests for full_team_check."""

    async def test_empty_team_no_paste(self, tools):
        """Test with no team and no paste."""
        fn = tools["full_team_check"].fn
        result = await fn()
        assert "error" in result or result.get("success") is False

    async def test_invalid_paste(self, tools):
        """Test with an empty paste."""
        fn = tools["full_team_check"].fn
        result = await fn(paste="")
        assert "error" in result or result.get("success") is False


FLUTTER_MANE = {
    "base_stats": {"hp": 55, "attack": 55, "defense": 55,
                   "special_attack": 135, "special_defense": 135, "speed": 135},
    "types": ["ghost", "fairy"],
}
INCINEROAR = {
    "base_stats": {"hp": 95, "attack": 115, "defense": 90,
                   "special_attack": 80, "special_defense": 90, "speed": 60},
    "types": ["fire", "dark"],
}


def _moonblast():
    from vgc_mcp_core.models.move import Move, MoveCategory
    return Move(name="moonblast", type="fairy", category=MoveCategory.SPECIAL,
                power=95, accuracy=100)


class TestQuickDamageCheck:
    """Tests for quick_damage_check — the one-call damage workflow."""

    async def test_happy_path_runs_real_damage_calc(self, tools, mock_pokeapi):
        mock_pokeapi.get_pokemon = AsyncMock(
            side_effect=lambda name: FLUTTER_MANE if "flutter" in name else INCINEROAR)
        mock_pokeapi.get_move = AsyncMock(return_value=_moonblast())
        mock_pokeapi.get_pokemon_abilities = AsyncMock(return_value=["Protosynthesis"])

        fn = tools["quick_damage_check"].fn
        result = await fn(attacker="flutter-mane", defender="incineroar", move="moonblast")
        assert result.get("success", True) is not False
        # 252 SpA Modest Moonblast into 0/0 Incineroar does real damage
        text = str(result)
        assert "%" in text or "percent" in text.lower()

    async def test_unknown_attacker_is_error(self, tools, mock_pokeapi):
        mock_pokeapi.get_pokemon = AsyncMock(return_value=None)
        mock_pokeapi.get_move = AsyncMock(return_value=_moonblast())
        fn = tools["quick_damage_check"].fn
        result = await fn(attacker="not-a-mon", defender="incineroar", move="moonblast")
        assert result["success"] is False

    async def test_unknown_move_is_error(self, tools, mock_pokeapi):
        mock_pokeapi.get_pokemon = AsyncMock(
            side_effect=lambda name: FLUTTER_MANE if "flutter" in name else INCINEROAR)
        mock_pokeapi.get_move = AsyncMock(return_value=None)
        fn = tools["quick_damage_check"].fn
        result = await fn(attacker="flutter-mane", defender="incineroar", move="fake-move")
        assert result["success"] is False


class TestCalcDamageVsSmogonSetsChampions:
    """Champions sets carry `sps`; the tool used to skip every one of them.
    Both directions must iterate the SP sets, label them, and honour
    attacker_stage (-1 = Intimidate)."""

    @pytest.fixture
    def champions_session(self):
        from vgc_mcp_core.rules.regulation_loader import get_regulation_config
        cfg = get_regulation_config()
        cfg.set_session_regulation("reg_mc_champs")
        try:
            yield cfg
        finally:
            cfg.clear_session_override()

    @staticmethod
    def _wave_crash():
        from vgc_mcp_core.models.move import Move, MoveCategory
        return Move(name="wave-crash", type="water", category=MoveCategory.PHYSICAL,
                    power=120, accuracy=100)

    @staticmethod
    def _setup(mock_pokeapi, mock_smogon, move):
        from vgc_mcp_core.models.pokemon import BaseStats
        delphox = {"base_stats": {"hp": 75, "attack": 69, "defense": 72,
                                  "special_attack": 114, "special_defense": 100, "speed": 104},
                   "types": ["fire", "psychic"]}
        basculegion = {"base_stats": {"hp": 120, "attack": 112, "defense": 65,
                                      "special_attack": 80, "special_defense": 75, "speed": 78},
                       "types": ["water", "ghost"]}
        data = {"delphox": delphox, "basculegion": basculegion}
        mock_pokeapi.get_pokemon = AsyncMock(side_effect=lambda n: data[n])
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=lambda n: BaseStats(**data[n]["base_stats"]))
        mock_pokeapi.get_pokemon_types = AsyncMock(side_effect=lambda n: data[n]["types"])
        mock_pokeapi.get_pokemon_abilities = AsyncMock(return_value=["Blaze"])
        mock_pokeapi.get_move = AsyncMock(return_value=move)
        mock_smogon.get_pokemon_usage = AsyncMock(return_value={
            "spreads": [
                {"nature": "Adamant", "sps": {"hp": 24, "attack": 16, "defense": 0,
                                               "special_attack": 0, "special_defense": 0, "speed": 26},
                 "format_system": "champions", "usage": 31.0},
                {"nature": "Jolly", "sps": {"hp": 2, "attack": 32, "defense": 0,
                                             "special_attack": 0, "special_defense": 0, "speed": 32},
                 "format_system": "champions", "usage": 20.0},
            ],
            "items": {"Choice Band": 50.0},
            "abilities": {"Swift Swim": 70.0},
            "tera_types": {},
            "_meta": {"month": "2026-09", "format": "gen9championsvgc2026regmc", "rating": 1630},
        })

    async def test_from_direction_iterates_sp_sets_and_applies_intimidate(
        self, champions_session, tools, mock_pokeapi, mock_smogon
    ):
        self._setup(mock_pokeapi, mock_smogon, self._wave_crash())
        fn = tools["calc_damage_vs_smogon_sets"].fn
        common = dict(my_pokemon="delphox", my_nature="timid", my_hp_evs=4, my_spa_evs=32,
                      my_spe_evs=30, opponent_pokemon="basculegion", move="wave-crash",
                      direction="from")
        neutral = await fn(**common)
        assert neutral.get("success") is not False, neutral
        sets = neutral["damage_vs_sets"]
        assert len(sets) == 2
        assert sets[0]["sps"] == "24 HP / 16 Atk / 26 Spe"
        assert sets[0]["spread_line"] == "Adamant 24/16/0/0/0/26 SP @ choice-band"
        assert sets[0]["allocation_unit"] == "SP"
        assert neutral["your_build"]["sps"]["SpA"] == 32
        assert neutral["your_build"]["final_stats"]["special_attack"] == 166  # 114 base + 32 SP + 20, Timid is neutral on SpA
        assert neutral["meta_info"]["month"] == "2026-09"

        intimidated = await fn(**common, attacker_stage=-1)
        assert intimidated["attacker_stage"] == -1
        def _max_dmg(entry):  # "71-84 (45.2%-53.1%)" -> 84
            return int(entry["damage_range"].split("-")[1].split()[0])

        for n, i in zip(sets, intimidated["damage_vs_sets"]):
            assert _max_dmg(i) < _max_dmg(n)

    async def test_to_direction_uses_sp_sets(self, champions_session, tools, mock_pokeapi, mock_smogon):
        from vgc_mcp_core.models.move import Move, MoveCategory
        psychic = Move(name="psychic", type="psychic", category=MoveCategory.SPECIAL,
                       power=90, accuracy=100)
        self._setup(mock_pokeapi, mock_smogon, psychic)
        fn = tools["calc_damage_vs_smogon_sets"].fn
        res = await fn(my_pokemon="delphox", my_nature="timid", my_spa_evs=32, my_spe_evs=32,
                       opponent_pokemon="basculegion", move="psychic", direction="to")
        sets = res["damage_vs_sets"]
        assert len(sets) == 2
        # 24 HP SP set is bulkier than the 2 HP SP set -> different damage ranges
        assert sets[0]["damage_range"] != sets[1]["damage_range"]

    async def test_intimidate_auto_applied_when_my_side_has_it(
        self, champions_session, tools, mock_pokeapi, mock_smogon
    ):
        self._setup(mock_pokeapi, mock_smogon, self._wave_crash())
        fn = tools["calc_damage_vs_smogon_sets"].fn
        res = await fn(my_pokemon="delphox", my_nature="timid", my_hp_evs=4, my_spa_evs=32,
                       my_spe_evs=30, my_ability="intimidate",
                       opponent_pokemon="basculegion", move="wave-crash", direction="from")
        assert res["intimidate"]["applied"] is True
        assert res["intimidate"]["stage"] == -1
        assert res["intimidate"]["intimidate_user"] == "delphox"
        assert "survives" in res["intimidate"]["summary"]

        def _max_dmg(d):
            return int(d["damage_range"].split("-")[1].split()[0])

        for row in res["damage_vs_sets"]:
            assert row["after_intimidate"]["attack_stage"] == -1
            assert _max_dmg(row["after_intimidate"]) < _max_dmg(row)
            assert row["after_intimidate"]["outcome"]

    async def test_intimidate_auto_from_pokemons_real_ability_not_pokeapi_first(
        self, champions_session, tools, mock_pokeapi, mock_smogon
    ):
        """No my_ability passed: Smogon says my Pokemon runs Intimidate, pokeapi
        lists Blaze first. The Intimidate row must appear automatically."""
        self._setup(mock_pokeapi, mock_smogon, self._wave_crash())
        opp_usage = mock_smogon.get_pokemon_usage.return_value
        my_usage = {**opp_usage, "abilities": {"Intimidate": 90.0}}
        mock_smogon.get_pokemon_usage = AsyncMock(
            side_effect=lambda n, *a, **k: my_usage if n == "delphox" else opp_usage)
        fn = tools["calc_damage_vs_smogon_sets"].fn
        res = await fn(my_pokemon="delphox", my_nature="timid",
                       opponent_pokemon="basculegion", move="wave-crash", direction="from")
        assert res["your_build"]["ability"] == "intimidate"
        assert res["intimidate"]["applied"] is True
        assert res["intimidate"]["source"].startswith("auto")
        assert all("after_intimidate" in r for r in res["damage_vs_sets"])

    async def test_intimidate_requested_without_defender_having_it(
        self, champions_session, tools, mock_pokeapi, mock_smogon
    ):
        """intimidate=True = partner Intimidate: applies even to a Blaze defender."""
        self._setup(mock_pokeapi, mock_smogon, self._wave_crash())
        fn = tools["calc_damage_vs_smogon_sets"].fn
        res = await fn(my_pokemon="delphox", my_nature="timid", my_ability="blaze",
                       opponent_pokemon="basculegion", move="wave-crash", direction="from",
                       intimidate=True)
        assert res["intimidate"]["applied"] is True
        assert res["intimidate"]["source"] == "requested"
        assert "partner" in res["intimidate"]["intimidate_user"]
        assert all(r["after_intimidate"]["attack_stage"] == -1 for r in res["damage_vs_sets"])

    async def test_intimidate_false_suppresses_even_when_defender_has_it(
        self, champions_session, tools, mock_pokeapi, mock_smogon
    ):
        self._setup(mock_pokeapi, mock_smogon, self._wave_crash())
        fn = tools["calc_damage_vs_smogon_sets"].fn
        res = await fn(my_pokemon="delphox", my_nature="timid", my_ability="intimidate",
                       opponent_pokemon="basculegion", move="wave-crash", direction="from",
                       intimidate=False)
        assert "intimidate" not in res
        assert all("after_intimidate" not in r for r in res["damage_vs_sets"])

    async def test_intimidate_blocked_by_clear_body(
        self, champions_session, tools, mock_pokeapi, mock_smogon
    ):
        self._setup(mock_pokeapi, mock_smogon, self._wave_crash())
        usage = mock_smogon.get_pokemon_usage.return_value
        usage["abilities"] = {"Clear Body": 80.0}
        fn = tools["calc_damage_vs_smogon_sets"].fn
        res = await fn(my_pokemon="delphox", my_nature="timid", my_ability="intimidate",
                       opponent_pokemon="basculegion", move="wave-crash", direction="from")
        assert res["intimidate"]["applied"] is False
        assert "blocked" in res["intimidate"]["note"].lower()
        assert all("after_intimidate" not in r for r in res["damage_vs_sets"])

    async def test_no_intimidate_on_special_move_or_without_ability(
        self, champions_session, tools, mock_pokeapi, mock_smogon
    ):
        from vgc_mcp_core.models.move import Move, MoveCategory
        self._setup(mock_pokeapi, mock_smogon, self._wave_crash())
        fn = tools["calc_damage_vs_smogon_sets"].fn
        # Blaze defender -> nothing to apply
        res = await fn(my_pokemon="delphox", my_nature="timid", my_ability="blaze",
                       opponent_pokemon="basculegion", move="wave-crash", direction="from")
        assert "intimidate" not in res
        # Intimidate defender but a special move -> no Atk drop
        mock_pokeapi.get_move = AsyncMock(return_value=Move(
            name="surf", type="water", category=MoveCategory.SPECIAL, power=90, accuracy=100))
        res = await fn(my_pokemon="delphox", my_nature="timid", my_ability="intimidate",
                       opponent_pokemon="basculegion", move="surf", direction="from")
        assert "intimidate" not in res
        assert all("after_intimidate" not in r for r in res["damage_vs_sets"])

    async def test_sp_budget_enforced(self, champions_session, tools, mock_pokeapi, mock_smogon):
        self._setup(mock_pokeapi, mock_smogon, self._wave_crash())
        fn = tools["calc_damage_vs_smogon_sets"].fn
        res = await fn(my_pokemon="delphox", my_nature="timid", my_spa_evs=252,
                       opponent_pokemon="basculegion", move="wave-crash")
        assert res["success"] is False


class TestAnalyzeSpeedMatchup:
    """Tests for analyze_speed_matchup."""

    async def test_faster_pokemon_is_identified(self, tools, mock_pokeapi):
        mock_pokeapi.get_pokemon = AsyncMock(
            side_effect=lambda name: FLUTTER_MANE if "flutter" in name else INCINEROAR)
        fn = tools["analyze_speed_matchup"].fn
        result = await fn(my_pokemon="flutter-mane", opponent_pokemon="incineroar")
        assert result.get("success", True) is not False
        # Base 135 vs 60, both jolly 252 — we must be flagged faster
        assert "faster" in str(result).lower()

    async def test_unknown_pokemon_is_error(self, tools, mock_pokeapi):
        mock_pokeapi.get_pokemon = AsyncMock(return_value=None)
        fn = tools["analyze_speed_matchup"].fn
        result = await fn(my_pokemon="ghost-mon", opponent_pokemon="incineroar")
        assert result["success"] is False


class TestCheckTeamVsThreat:
    async def test_empty_team_is_error(self, tools, mock_team_manager):
        mock_team_manager.size = 0
        fn = tools["check_team_vs_threat"].fn
        result = await fn(threat_pokemon="flutter-mane")
        assert result["success"] is False
        assert "team" in result["message"].lower()
