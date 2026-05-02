"""Tests for the StatPointSpread model — Champions Reg MA."""

import pytest
from pydantic import ValidationError

from vgc_mcp_core.models.pokemon import (
    StatPointSpread,
    PokemonBuild,
    BaseStats,
    EVSpread,
    Nature,
)


class TestStatPointSpread:
    def test_default_is_all_zero(self):
        sps = StatPointSpread()
        assert sps.total == 0
        assert sps.is_valid()
        assert sps.remaining() == 66

    def test_max_per_stat_is_32(self):
        sps = StatPointSpread(hp=32)
        assert sps.hp == 32
        assert sps.total == 32

    def test_per_stat_over_32_raises(self):
        with pytest.raises(ValidationError):
            StatPointSpread(hp=33)

    def test_full_max_budget_66(self):
        sps = StatPointSpread(hp=32, attack=32, speed=2)
        assert sps.total == 66
        assert sps.is_valid()
        assert sps.remaining() == 0

    def test_over_budget_is_invalid(self):
        # Three 32s = 96 SP — model allows the field values (each ≤ 32) but
        # `is_valid()` reports the total budget violation.
        sps = StatPointSpread(hp=32, attack=32, speed=32)
        assert sps.total == 96
        assert not sps.is_valid()

    def test_negative_sp_raises(self):
        with pytest.raises(ValidationError):
            StatPointSpread(hp=-1)

    def test_from_sps_dict_short_keys(self):
        sps = StatPointSpread.from_sps_dict({
            "hp": 4, "at": 0, "df": 12, "sa": 0, "sd": 18, "sp": 32
        })
        assert sps.hp == 4
        assert sps.defense == 12
        assert sps.special_defense == 18
        assert sps.speed == 32
        assert sps.attack == 0

    def test_from_sps_dict_full_keys(self):
        sps = StatPointSpread.from_sps_dict({
            "hp": 4, "attack": 0, "defense": 12, "special_defense": 18, "speed": 32
        })
        assert sps.total == 66
        assert sps.special_defense == 18

    def test_to_sps_dict_round_trips(self):
        original = {"hp": 4, "at": 0, "df": 12, "sa": 0, "sd": 18, "sp": 32}
        sps = StatPointSpread.from_sps_dict(original)
        assert sps.to_sps_dict() == original


class TestPokemonBuildFormatSystem:
    @pytest.fixture
    def base_stats(self):
        return BaseStats(hp=88, attack=120, defense=75, special_attack=100, special_defense=75, speed=142)

    def test_default_format_is_mainline(self, base_stats):
        pb = PokemonBuild(name="dragapult", base_stats=base_stats)
        assert pb.format_system == "mainline"
        assert pb.is_champions() is False
        assert pb.sps is None

    def test_champions_build_carries_sps(self, base_stats):
        sps = StatPointSpread(speed=32, attack=32, hp=2)
        pb = PokemonBuild(
            name="dragapult",
            base_stats=base_stats,
            format_system="champions",
            sps=sps,
            nature=Nature.JOLLY,
        )
        assert pb.is_champions()
        assert pb.sps.speed == 32

    def test_sps_validator_rejects_over_budget(self, base_stats):
        with pytest.raises(ValidationError):
            PokemonBuild(
                name="dragapult",
                base_stats=base_stats,
                format_system="champions",
                sps=StatPointSpread(hp=32, attack=32, defense=32),  # 96 SP
            )

    def test_get_stat_allocation_dispatches(self, base_stats):
        # Mainline build returns EV value
        ml = PokemonBuild(
            name="dragapult",
            base_stats=base_stats,
            evs=EVSpread(speed=252, attack=252, hp=4),
            nature=Nature.JOLLY,
        )
        assert ml.get_stat_allocation("speed") == 252

        # Champions build returns SP value
        ch = PokemonBuild(
            name="dragapult",
            base_stats=base_stats,
            format_system="champions",
            sps=StatPointSpread(speed=32, attack=32, hp=2),
            nature=Nature.JOLLY,
        )
        assert ch.get_stat_allocation("speed") == 32

    def test_champions_build_with_no_sps_treats_as_zero(self, base_stats):
        # Some workflows construct a Champions build before SPs are known.
        pb = PokemonBuild(
            name="dragapult",
            base_stats=base_stats,
            format_system="champions",
        )
        assert pb.sps is None
        assert pb.get_stat_allocation("speed") == 0
