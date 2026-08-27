"""Regression tests for Gen 9 / Champions mechanics fixes (2026-08 audit).

Covers: move priorities, Hydro Steam in sun, sand/snow defensive boosts,
Sniper crits, Expanding Force / Rising Voltage terrain BP, wind-move list,
Supreme Overlord exact mods, Champions Smogon-spread handling, Champions
paste IV handling, and SP-aware team diff.
"""

from vgc_mcp_core.calc.damage import WIND_MOVES, calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.priority import get_move_priority
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import BaseStats, EVSpread, Nature, PokemonBuild


def _make(name, types, *, base=None, nature=Nature.SERIOUS, evs=None):
    return PokemonBuild(
        name=name,
        base_stats=base or BaseStats(hp=100, attack=100, defense=100,
                                     special_attack=100, special_defense=100, speed=100),
        nature=nature,
        evs=evs or EVSpread(),
        types=types,
    )


def _move(name, mtype, category, power=80, target="selected-pokemon"):
    return Move(name=name, type=mtype, category=category, power=power,
                accuracy=100, pp=10, target=target)


class TestPriorityCorrections:
    def test_redirection_moves_are_plus_2(self):
        assert get_move_priority("follow-me") == 2
        assert get_move_priority("rage-powder") == 2
        assert get_move_priority("ally-switch") == 2

    def test_counter_and_mirror_coat_are_minus_5(self):
        assert get_move_priority("counter") == -5
        assert get_move_priority("mirror-coat") == -5

    def test_teleport_is_minus_6(self):
        assert get_move_priority("teleport") == -6

    def test_zero_priority_moves(self):
        # These were previously listed with wrong non-zero priorities
        assert get_move_priority("mat-block") == 0
        assert get_move_priority("after-you") == 0
        assert get_move_priority("metal-burst") == 0


class TestHydroSteam:
    def test_hydro_steam_boosted_in_sun(self):
        attacker = _make("walking-wake", ["Water", "Dragon"])
        defender = _make("dummy", ["Normal"])
        hydro_steam = _move("hydro-steam", "Water", MoveCategory.SPECIAL, 80)

        clear = calculate_damage(attacker, defender, hydro_steam, DamageModifiers())
        sun = calculate_damage(attacker, defender, hydro_steam,
                               DamageModifiers(weather="sun"))
        # 1.5x boost, NOT the 0.5x Water-in-sun nerf
        assert sun.max_damage > clear.max_damage
        assert abs(sun.max_damage / clear.max_damage - 1.5) < 0.1

    def test_regular_water_still_nerfed_in_sun(self):
        attacker = _make("attacker", ["Water"])
        defender = _make("dummy", ["Normal"])
        surf = _move("surf", "Water", MoveCategory.SPECIAL, 90)
        clear = calculate_damage(attacker, defender, surf, DamageModifiers())
        sun = calculate_damage(attacker, defender, surf, DamageModifiers(weather="sun"))
        assert sun.max_damage < clear.max_damage


class TestWeatherDefensiveBoosts:
    def test_sand_boosts_rock_type_spd(self):
        attacker = _make("attacker", ["Ghost"])
        rock_def = _make("garganacl", ["Rock"])
        shadow_ball = _move("shadow-ball", "Ghost", MoveCategory.SPECIAL, 80)

        clear = calculate_damage(attacker, rock_def, shadow_ball, DamageModifiers())
        sand = calculate_damage(attacker, rock_def, shadow_ball,
                                DamageModifiers(weather="sand"))
        assert sand.max_damage < clear.max_damage

    def test_sand_does_not_boost_rock_type_def(self):
        attacker = _make("attacker", ["Fighting"])
        rock_def = _make("garganacl", ["Rock"])
        cc = _move("close-combat", "Fighting", MoveCategory.PHYSICAL, 120)
        clear = calculate_damage(attacker, rock_def, cc, DamageModifiers())
        sand = calculate_damage(attacker, rock_def, cc, DamageModifiers(weather="sand"))
        assert sand.max_damage == clear.max_damage

    def test_snow_boosts_ice_type_def(self):
        attacker = _make("attacker", ["Fighting"])
        ice_def = _make("cetitan", ["Ice"])
        cc = _move("close-combat", "Fighting", MoveCategory.PHYSICAL, 120)
        clear = calculate_damage(attacker, ice_def, cc, DamageModifiers())
        snow = calculate_damage(attacker, ice_def, cc, DamageModifiers(weather="snow"))
        assert snow.max_damage < clear.max_damage


class TestSniperCrit:
    def test_sniper_crit_is_stronger_than_normal_crit(self):
        attacker = _make("inteleon", ["Water"])
        defender = _make("dummy", ["Normal"])
        snipe = _move("snipe-shot", "Water", MoveCategory.SPECIAL, 80)

        crit = calculate_damage(attacker, defender, snipe,
                                DamageModifiers(is_critical=True))
        sniper_crit = calculate_damage(attacker, defender, snipe,
                                       DamageModifiers(is_critical=True,
                                                       attacker_ability="sniper"))
        # 2.25x vs 1.5x crit mod
        assert abs(sniper_crit.max_damage / crit.max_damage - 1.5) < 0.1


class TestTerrainBPMoves:
    def test_expanding_force_boosted_in_psychic_terrain(self):
        attacker = _make("indeedee", ["Psychic"])
        defender = _make("dummy", ["Normal"])
        ef = _move("expanding-force", "Psychic", MoveCategory.SPECIAL, 80)
        clear = calculate_damage(attacker, defender, ef, DamageModifiers())
        terrain = calculate_damage(attacker, defender, ef,
                                   DamageModifiers(terrain="psychic"))
        # 1.5x BP plus the generic ~1.3x terrain boost
        assert terrain.max_damage / clear.max_damage > 1.8

    def test_rising_voltage_doubled_in_electric_terrain(self):
        attacker = _make("raichu", ["Electric"])
        defender = _make("dummy", ["Normal"])
        rv = _move("rising-voltage", "Electric", MoveCategory.SPECIAL, 70)
        clear = calculate_damage(attacker, defender, rv, DamageModifiers())
        terrain = calculate_damage(attacker, defender, rv,
                                   DamageModifiers(terrain="electric"))
        # 2x BP plus the generic ~1.3x terrain boost
        assert terrain.max_damage / clear.max_damage > 2.3


class TestWindAndSoundMoveLists:
    def test_common_vgc_wind_moves_present(self):
        for move in ("heat-wave", "icy-wind", "blizzard", "springtide-storm"):
            assert move in WIND_MOVES

    def test_shadow_force_not_a_sound_move(self):
        from vgc_mcp_core.calc.damage import SOUND_MOVES
        assert "shadow-force" not in SOUND_MOVES
        assert "alluring-voice" in SOUND_MOVES
        assert "psychic-noise" in SOUND_MOVES


class TestSupremeOverlord:
    def test_five_fallen_allies_is_exactly_1_5x(self):
        attacker = _make("kingambit", ["Dark", "Steel"])
        defender = _make("dummy", ["Normal"])
        kowtow = _move("kowtow-cleave", "Dark", MoveCategory.PHYSICAL, 85)
        base = calculate_damage(attacker, defender, kowtow, DamageModifiers())
        boosted = calculate_damage(
            attacker, defender, kowtow,
            DamageModifiers(attacker_ability="supreme-overlord",
                            supreme_overlord_count=5))
        assert abs(boosted.max_damage / base.max_damage - 1.5) < 0.05


class TestChampionsFixes:
    FLUTTER_BASE = BaseStats(hp=55, attack=55, defense=55,
                             special_attack=135, special_defense=135, speed=135)

    def test_build_from_spread_reads_champions_sps(self):
        from vgc_mcp.tools.breakpoint_tools import _build_from_spread
        from vgc_mcp_core.calc.stats import calculate_all_stats

        spread = {
            "nature": "timid",
            "sps": {"speed": 32, "special_attack": 32},
            "format_system": "champions",
        }
        build = _build_from_spread(self.FLUTTER_BASE, ["Ghost", "Fairy"],
                                   "flutter-mane", spread)
        assert build.format_system == "champions"
        # 32 SP Timid Flutter Mane = 205 Speed (not the 0-investment 170)
        assert calculate_all_stats(build)["speed"] == 205

    def test_champions_paste_ignores_iv_line(self):
        from vgc_mcp_core.formats.showdown import (
            parse_showdown_pokemon,
            parsed_to_pokemon_build,
        )
        paste = (
            "Flutter Mane\n"
            "SPs: 32 SpA / 32 Spe\n"
            "Timid Nature\n"
            "IVs: 0 Atk\n"
        )
        parsed = parse_showdown_pokemon(paste)
        build = parsed_to_pokemon_build(parsed, self.FLUTTER_BASE,
                                        ["Ghost", "Fairy"],
                                        format_hint="champions")
        # Champions has no IVs — everything acts as 31 and cannot be lowered
        assert build.ivs.attack == 31

    def test_team_diff_detects_sp_change(self):
        from vgc_mcp_core.diff.team_diff import compare_pokemon
        from vgc_mcp_core.formats.showdown import ParsedPokemon

        v1 = ParsedPokemon(species="Flutter Mane", nature="Timid",
                           sps={"hp": 0, "atk": 0, "def": 0,
                                "spa": 32, "spd": 2, "spe": 32})
        v2 = ParsedPokemon(species="Flutter Mane", nature="Timid",
                           sps={"hp": 16, "atk": 0, "def": 0,
                                "spa": 32, "spd": 0, "spe": 32})
        changes = compare_pokemon(v1, v2)
        assert changes, "SP-only spread change must be detected"
