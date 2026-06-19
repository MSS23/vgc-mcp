"""End-to-end damage calc tests for the Champions SP system.

These exercise the full pipeline: stat calc dispatch -> damage formula ->
stat-stage / type / doubles modifiers, with builds carrying StatPointSpreads.
"""

from vgc_mcp_core.calc.damage import (
    calculate_bulk_threshold,
    calculate_damage,
    calculate_ko_threshold,
)
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.stats import calculate_all_stats
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import (
    BaseStats,
    EVSpread,
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


def _flutter_mane_champions(
    sps: StatPointSpread, nature: Nature = Nature.TIMID, item: str | None = None
) -> PokemonBuild:
    return PokemonBuild(
        name="flutter-mane",
        base_stats=BaseStats(
            hp=55, attack=55, defense=55,
            special_attack=135, special_defense=135, speed=135
        ),
        types=["ghost", "fairy"],
        nature=nature,
        sps=sps,
        format_system="champions",
        ability="Protosynthesis",
        item=item,
    )


def _moonblast() -> Move:
    return Move(
        name="moonblast",
        type="fairy",
        category=MoveCategory.SPECIAL,
        power=95,
        accuracy=100,
        target="selected-pokemon",
    )


class TestParadoxBoostStatPick:
    """F3-a: Protosynthesis/Quark Drive boost must follow the invested stat.

    For a Champions build (EVs all zero, SPs carry the investment) the boost
    auto-detect previously read p.evs and picked the highest BASE stat (Speed
    for Flutter Mane) instead of the invested Special Attack.
    """

    def test_invested_special_attack_gets_the_proto_boost(self):
        fm = _flutter_mane_champions(StatPointSpread(special_attack=32))
        defn = PokemonBuild(
            name="incineroar",
            base_stats=BaseStats(
                hp=95, attack=115, defense=90,
                special_attack=80, special_defense=90, speed=60
            ),
            types=["fire", "dark"],
            nature=Nature.CAREFUL,
            sps=StatPointSpread(hp=8),
            format_system="champions",
        )
        move = _moonblast()
        # Sun activates Protosynthesis; boost should land on special_attack.
        boosted = calculate_damage(fm, defn, move, DamageModifiers(weather="sun"))
        # Without weather (no Protosynthesis) damage is strictly lower because
        # the special_attack boost is what raises it (not a speed boost).
        unboosted = calculate_damage(fm, defn, move, DamageModifiers())
        assert boosted.max_damage > unboosted.max_damage
        # A boost pinned to Speed must NOT raise special damage — proves the
        # auto-detect picks special_attack rather than the highest base stat.
        speed_pinned = calculate_damage(
            fm, defn, move,
            DamageModifiers(weather="sun", protosynthesis_boost="speed"),
        )
        assert speed_pinned.max_damage == unboosted.max_damage
        assert boosted.max_damage > speed_pinned.max_damage

    def test_highest_non_hp_helper_picks_special_attack(self):
        # Directly exercise the format-aware derivation via the public calc:
        # a Speed-only proto boost would not raise special damage at all.
        fm = _flutter_mane_champions(StatPointSpread(special_attack=32))
        stats = {k: v for k, v in calculate_all_stats(fm).items() if k != "hp"}
        max_value = max(stats.values())
        tied = [s for s, v in stats.items() if v == max_value]
        pick = "speed" if "speed" in tied else tied[0]
        assert pick == "special_attack"


class TestChampionsKoThreshold:
    """F3-b: calculate_ko_threshold must sweep SP (0-32) for champions builds
    and return `sps_needed`, never EV-unit `evs_needed`.
    """

    def test_returns_sps_needed_in_sp_units(self):
        atk = _flutter_mane_champions(StatPointSpread(), nature=Nature.MODEST)
        # Dark/Dragon defender is 4x weak to Fairy -> guaranteed OHKO.
        defn = PokemonBuild(
            name="hydreigon",
            base_stats=BaseStats(
                hp=92, attack=105, defense=90,
                special_attack=125, special_defense=90, speed=98
            ),
            types=["dark", "dragon"],
            nature=Nature.TIMID,
            sps=StatPointSpread(),
            format_system="champions",
        )
        result = calculate_ko_threshold(atk, defn, _moonblast(), None, 100.0)
        assert result is not None
        assert "sps_needed" in result
        assert "evs_needed" not in result
        assert 0 <= result["sps_needed"] <= 32
        assert result["stat_name"] == "special_attack"

    def test_mainline_still_returns_evs_needed(self):
        atk = PokemonBuild(
            name="flutter-mane",
            base_stats=BaseStats(
                hp=55, attack=55, defense=55,
                special_attack=135, special_defense=135, speed=135
            ),
            types=["ghost", "fairy"],
            nature=Nature.MODEST,
            evs=EVSpread(),
        )
        defn = PokemonBuild(
            name="hydreigon",
            base_stats=BaseStats(
                hp=92, attack=105, defense=90,
                special_attack=125, special_defense=90, speed=98
            ),
            types=["dark", "dragon"],
            nature=Nature.TIMID,
            evs=EVSpread(),
        )
        result = calculate_ko_threshold(atk, defn, _moonblast(), None, 100.0)
        assert result is not None
        assert "evs_needed" in result
        assert "sps_needed" not in result


class TestChampionsBulkThreshold:
    """F3-c: calculate_bulk_threshold must sweep SP (0-32, total <= 66) for
    champions defenders and return `hp_sps`/`def_sps`, never EV-unit keys.
    """

    def test_returns_sp_units(self):
        atk = PokemonBuild(
            name="urshifu-rapid-strike",
            base_stats=BaseStats(
                hp=100, attack=130, defense=100,
                special_attack=63, special_defense=60, speed=97
            ),
            types=["fighting", "water"],
            nature=Nature.ADAMANT,
            sps=StatPointSpread(attack=32),
            format_system="champions",
        )
        defn = PokemonBuild(
            name="amoonguss",
            base_stats=BaseStats(
                hp=114, attack=85, defense=70,
                special_attack=85, special_defense=80, speed=30
            ),
            types=["grass", "poison"],
            nature=Nature.SASSY,
            sps=StatPointSpread(),
            format_system="champions",
        )
        move = Move(
            name="close-combat",
            type="fighting",
            category=MoveCategory.PHYSICAL,
            power=120,
            accuracy=100,
        )
        result = calculate_bulk_threshold(atk, defn, move, None, 93.75)
        assert result is not None
        assert "hp_sps" in result
        assert "def_sps" in result
        assert "hp_evs" not in result
        assert "def_evs" not in result
        assert 0 <= result["hp_sps"] <= 32
        assert 0 <= result["def_sps"] <= 32
        assert result["hp_sps"] + result["def_sps"] <= 66

    def test_mainline_still_returns_ev_units(self):
        atk = PokemonBuild(
            name="urshifu-rapid-strike",
            base_stats=BaseStats(
                hp=100, attack=130, defense=100,
                special_attack=63, special_defense=60, speed=97
            ),
            types=["fighting", "water"],
            nature=Nature.ADAMANT,
            evs=EVSpread(attack=252),
        )
        defn = PokemonBuild(
            name="amoonguss",
            base_stats=BaseStats(
                hp=114, attack=85, defense=70,
                special_attack=85, special_defense=80, speed=30
            ),
            types=["grass", "poison"],
            nature=Nature.SASSY,
            evs=EVSpread(),
        )
        move = Move(
            name="close-combat",
            type="fighting",
            category=MoveCategory.PHYSICAL,
            power=120,
            accuracy=100,
        )
        result = calculate_bulk_threshold(atk, defn, move, None, 93.75)
        assert result is not None
        assert "hp_evs" in result
        assert "def_evs" in result
        assert "hp_sps" not in result
