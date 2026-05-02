"""End-to-end damage calc tests for the Champions SP system.

These exercise the full pipeline: stat calc dispatch -> damage formula ->
stat-stage / type / doubles modifiers, with builds carrying StatPointSpreads.
"""

from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.stats import calculate_all_stats
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import (
    BaseStats,
    Nature,
    PokemonBuild,
    StatPointSpread,
)


def _garchomp_champions_32plus_atk() -> PokemonBuild:
    return PokemonBuild(
        name="garchomp",
        base_stats=BaseStats(
            hp=108, attack=130, defense=95,
            special_attack=80, special_defense=85, speed=102
        ),
        types=["ground", "dragon"],
        nature=Nature.ADAMANT,
        sps=StatPointSpread(attack=32),
        format_system="champions",
        ability="Rough Skin",
    )


def _mega_manectric_12hp_2def() -> PokemonBuild:
    return PokemonBuild(
        name="manectric-mega",
        base_stats=BaseStats(
            hp=70, attack=75, defense=80,
            special_attack=135, special_defense=80, speed=135
        ),
        types=["electric"],
        nature=Nature.SERIOUS,
        sps=StatPointSpread(hp=12, defense=2),
        format_system="champions",
        ability="Intimidate",
    )


def _stomping_tantrum() -> Move:
    return Move(
        name="stomping-tantrum",
        type="ground",
        category=MoveCategory.PHYSICAL,
        power=75,
        accuracy=100,
        target="selected-pokemon",
        makes_contact=True,
    )


class TestGarchompVsMegaManectric:
    """Verifies the Champions calc reproduces a known Showdown-style result.

    Reference (from user-provided calc):
      -1 32+ Atk Garchomp Stomping Tantrum vs. 12 HP / 2 Def Mega Manectric:
      114-134 (72.6 - 85.3%) -- guaranteed 2HKO
    """

    def test_garchomp_attack_stat_at_32_plus(self):
        gar = _garchomp_champions_32plus_atk()
        stats = calculate_all_stats(gar)
        # 32 SP Adamant on base 130 -> 200 Attack
        assert stats["attack"] == 200

    def test_mega_manectric_defensive_stats(self):
        mm = _mega_manectric_12hp_2def()
        stats = calculate_all_stats(mm)
        # 12 HP / 2 Def neutral on Mega Manectric (70/80 base) at level 50
        assert stats["hp"] == 157
        assert stats["defense"] == 102

    def test_stomping_tantrum_damage_range(self):
        gar = _garchomp_champions_32plus_atk()
        mm = _mega_manectric_12hp_2def()
        move = _stomping_tantrum()
        mods = DamageModifiers(is_doubles=True, attack_stage=-1)

        result = calculate_damage(gar, mm, move, mods)

        assert result.min_damage == 114
        assert result.max_damage == 134
        assert round(result.min_percent, 1) == 72.6
        assert round(result.max_percent, 1) == 85.3
        assert result.ko_chance == "Guaranteed 2HKO"
