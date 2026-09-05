"""Pure exact benchmark verification and bounded spread candidate search."""

from fractions import Fraction
from typing import Any

from ..formats.showdown import pokemon_build_to_showdown
from ..models.move import GEN9_SPECIAL_MOVES, MoveCategory
from ..models.pokemon import EVSpread, Nature, PokemonBuild, StatPointSpread
from ..models.preparation import ResolvedBenchmark
from ..utils.normalize import normalize_move
from .damage import format_percent
from .outcomes import calculate_move_outcomes
from .stats import calculate_all_stats

STATS = ("hp", "attack", "defense", "special_attack", "special_defense", "speed")


def verify_benchmarks(pokemon: PokemonBuild, benchmarks: list[ResolvedBenchmark]) -> dict[str, Any]:
    """Recalculate every constraint using the actual final build."""
    stats = calculate_all_stats(pokemon)
    rows: list[dict[str, Any]] = []
    for benchmark in benchmarks:
        spec = benchmark.request
        row: dict[str, Any] = {
            "kind": spec.kind, "opponent": benchmark.opponent.name,
            "opponent_showdown_paste": pokemon_build_to_showdown(benchmark.opponent),
            "source": benchmark.source,
        }
        if spec.kind == "outspeed":
            speed = int(stats["speed"] * Fraction(str(spec.speed_multiplier)))
            other = int(calculate_all_stats(benchmark.opponent)["speed"] * Fraction(str(spec.opponent_speed_multiplier)))
            row.update({"speed": speed, "opponent_speed": other, "passed": speed > other, "margin": speed - other})
        else:
            if benchmark.move is None:
                raise ValueError("Damage benchmark is missing its resolved move")
            attacker, defender = (benchmark.opponent, pokemon) if spec.kind == "survive" else (pokemon, benchmark.opponent)
            outcomes = calculate_move_outcomes(attacker, defender, benchmark.move, benchmark.modifiers,
                                               include_accuracy=False, random_hits=False, max_uses=1)
            actual_probability = 1 - outcomes.ko_chances[0] if spec.kind == "survive" else outcomes.ko_chances[0]
            actual = float(actual_probability * 100)
            low, high = min(outcomes.damage_weights), max(outcomes.damage_weights)
            damage_range = f"{low}-{high} ({format_percent(int(low / outcomes.hp * 1000) / 10)}%-{format_percent(int(high / outcomes.hp * 1000) / 10)}%)"
            row.update({
                "move": benchmark.move.name, "damage": damage_range,
                "damage_basis": "net HP loss after any berry recovery or survival protection",
                "required_probability": spec.required_probability, "actual_probability": actual,
                "passed": actual_probability * 100 >= Fraction(str(spec.required_probability)),
                "attacker_showdown_paste": pokemon_build_to_showdown(attacker),
                "defender_showdown_paste": pokemon_build_to_showdown(defender),
                "conditions": spec.conditions, "probability_basis": "conditional on move landing and specified hit count",
            })
        rows.append(row)
    return {"verified": all(row["passed"] for row in rows), "benchmarks": rows,
            "stats": stats, "showdown_paste": pokemon_build_to_showdown(pokemon)}


def _allocation(pokemon: PokemonBuild) -> dict[str, int]:
    spread = pokemon.sps if pokemon.format_system == "champions" else pokemon.evs
    return {stat: int(getattr(spread, stat, 0)) for stat in STATS}


def _build(pokemon: PokemonBuild, nature: Nature, allocation: dict[str, int]) -> PokemonBuild:
    key = "sps" if pokemon.format_system == "champions" else "evs"
    spread = StatPointSpread(**allocation) if key == "sps" else EVSpread(**allocation)
    return pokemon.model_copy(update={"nature": nature, key: spread})


def recommend_verified_candidates(
    pokemon: PokemonBuild, benchmarks: list[ResolvedBenchmark], natures: list[Nature] | None = None
) -> dict[str, Any]:
    """Find low-investment candidates then offer verified offense/bulk variants.

    Enumerates HP and the minimum independently satisfying offensive/speed and
    defensive investments per nature. Final exact verification rejects coupled
    effects that invalidate an independently found minimum. Reports the search
    scope instead of claiming global optimality across every possible build.
    """
    champions = pokemon.format_system == "champions"
    # All four-EV grains are needed for even IVs and non-level-50 builds.
    values = list(range(33)) if champions else list(range(0, 253, 4))
    cap, budget = (32, 66) if champions else (252, 508)
    offense = "attack" if pokemon.base_stats.attack >= pokemon.base_stats.special_attack else "special_attack"
    chosen_natures = natures or list(dict.fromkeys([
        pokemon.nature, Nature.ADAMANT if offense == "attack" else Nature.MODEST,
        Nature.JOLLY if offense == "attack" else Nature.TIMID,
        Nature.IMPISH if offense == "attack" else Nature.BOLD,
        Nature.CAREFUL if offense == "attack" else Nature.CALM,
    ]))
    candidates: list[PokemonBuild] = []
    evaluations = 0

    def passed(candidate: PokemonBuild, subset: list[ResolvedBenchmark]) -> bool:
        nonlocal evaluations
        evaluations += 1
        return bool(verify_benchmarks(candidate, subset)["verified"])

    groups: dict[str, list[ResolvedBenchmark]] = {stat: [] for stat in STATS}
    for benchmark in benchmarks:
        if benchmark.request.kind == "outspeed":
            groups["speed"].append(benchmark)
        elif benchmark.move is not None:
            special = GEN9_SPECIAL_MOVES.get(normalize_move(benchmark.move.name), {})
            if benchmark.request.kind == "ko":
                stat = "defense" if special.get("uses_user_defense") else (
                    "attack" if benchmark.move.category == MoveCategory.PHYSICAL else "special_attack"
                )
            else:
                stat = "defense" if benchmark.move.category == MoveCategory.PHYSICAL or special.get("targets_physical_defense") else "special_defense"
            groups[stat].append(benchmark)

    for nature in chosen_natures:
        mandatory = {stat: 0 for stat in STATS}
        possible = True
        for stat in ("attack", "special_attack", "speed"):
            if not groups[stat]:
                continue
            for investment in values:
                trial = mandatory | {stat: investment}
                if sum(trial.values()) <= budget and passed(_build(pokemon, nature, trial), groups[stat]):
                    mandatory = trial
                    break
            else:
                possible = False
                break
        if not possible:
            continue
        for hp in values:
            allocation = mandatory | {"hp": hp}
            if sum(allocation.values()) > budget:
                break
            for stat in ("defense", "special_defense"):
                for investment in values:
                    trial = allocation | {stat: investment}
                    if sum(trial.values()) > budget:
                        break
                    if passed(_build(pokemon, nature, trial), groups[stat]):
                        allocation = trial
                        break
                else:
                    possible = False
                    break
                if not passed(_build(pokemon, nature, allocation), groups[stat]):
                    possible = False
                    break
            if possible:
                candidate = _build(pokemon, nature, allocation)
                if passed(candidate, benchmarks):
                    candidates.append(candidate)
            possible = True

    if not candidates:
        return {"verified": False, "status": "no_verified_candidate", "candidates_evaluated": evaluations,
                "current": verify_benchmarks(pokemon, benchmarks),
                "reason": "No candidate passed within the evaluated natures and allocation search; this is not proof of impossibility."}
    minimum = min(candidates, key=lambda p: sum(_allocation(p).values()))

    def fill(candidate: PokemonBuild, order: tuple[str, ...]) -> PokemonBuild:
        allocation = _allocation(candidate)
        for stat in order:
            for investment in reversed(values):
                if investment < allocation[stat] or investment > cap:
                    continue
                trial = allocation | {stat: investment}
                if sum(trial.values()) <= budget:
                    build = _build(candidate, candidate.nature, trial)
                    if passed(build, benchmarks):
                        candidate, allocation = build, trial
                        break
        return candidate

    offensive = max(candidates, key=lambda p: calculate_all_stats(fill(p, (offense,)))[offense])
    variants = [("minimum_investment", minimum),
                ("more_offense", fill(offensive, (offense, "speed", "hp", "defense", "special_defense"))),
                ("more_bulk", fill(minimum, ("hp", "defense", "special_defense", offense, "speed")))]
    original_stats = calculate_all_stats(pokemon)
    results: list[dict[str, Any]] = []
    for label, candidate in variants:
        verified = verify_benchmarks(candidate, benchmarks)
        if not verified["verified"]:
            continue
        results.append({"purpose": label, **verified,
                        "investment": sum(_allocation(candidate).values()), "units": "SP" if champions else "EV",
                        "stat_changes": {stat: verified["stats"][stat] - original_stats[stat] for stat in STATS}})
    return {"verified": True, "candidates": results, "candidates_evaluated": evaluations,
            "current_showdown_paste": pokemon_build_to_showdown(pokemon),
            "search_scope": "Item, ability, moves, IVs and level retained; evaluated natures and independent minimum allocations, followed by exact final verification.",
            "tradeoff_note": "Only the supplied benchmarks are guaranteed; inspect stat_changes for lost offense, bulk or Speed."}
