"""Verification must enforce actual final-build survival, including protection."""

from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.verified_spreads import recommend_verified_candidates, verify_benchmarks
from vgc_mcp_core.models.move import Move
from vgc_mcp_core.models.pokemon import BaseStats, IVSpread, Nature, PokemonBuild
from vgc_mcp_core.models.preparation import BenchmarkSpec, ResolvedBenchmark


def build(**kwargs):
    return PokemonBuild(name="Mew", types=["Psychic"], base_stats=BaseStats(
        hp=100, attack=100, defense=100, special_attack=100, special_defense=100, speed=100), **kwargs)


def test_verification_does_not_promise_ohko_through_focus_sash():
    move = Move(name="tackle", type="Normal", category="physical", power=10000)
    benchmark = ResolvedBenchmark(BenchmarkSpec(kind="ko", opponent_name="Mew", move="tackle"),
                                  build(item="focus-sash"), move, DamageModifiers(), {})
    result = verify_benchmarks(build(), [benchmark])
    assert not result["verified"]
    assert result["benchmarks"][0]["actual_probability"] == 0


def test_minimum_speed_with_zero_iv_uses_the_right_ev_grain():
    # At level 50, IV=0: 8 EVs, not 4 EVs, buy the first Speed point.
    pokemon = build(ivs=IVSpread(speed=0))
    benchmark = ResolvedBenchmark(BenchmarkSpec(kind="outspeed", opponent_name="Mew"),
                                  pokemon, None, DamageModifiers(), {})
    result = recommend_verified_candidates(pokemon, [benchmark], [Nature.SERIOUS])
    minimum = next(c for c in result["candidates"] if c["purpose"] == "minimum_investment")
    assert minimum["investment"] == 8
    assert minimum["verified"]
    assert "IVs: 0 Spe" in minimum["showdown_paste"]
