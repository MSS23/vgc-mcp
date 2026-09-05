"""Preparation workflows shared by MCP transports; no client-specific UI."""

import asyncio
from datetime import datetime, timezone
from typing import Any, cast

from ..api.pokeapi import PokeAPIClient
from ..api.smogon import SmogonStatsClient, SmogonStatsError
from ..calc.damage import calculate_damage
from ..calc.modifiers import DamageModifiers
from ..calc.outcomes import calculate_move_outcomes, result_from_outcomes
from ..calc.stats import calculate_all_stats
from ..calc.verified_spreads import recommend_verified_candidates, verify_benchmarks
from ..formats.showdown import (
    parse_showdown_team,
    parsed_to_pokemon_build,
    pokemon_build_to_showdown,
)
from ..models.pokemon import EVSpread, FormatSystem, Nature, PokemonBuild, StatPointSpread
from ..models.preparation import BenchmarkSpec, ResolvedBenchmark, SourcedSet, validated_conditions
from ..models.team import Team, TeamSlot
from ..rules.regulation_loader import get_regulation_config
from ..rules.vgc_rules import validate_team_rules
from ..team.analysis import TeamAnalyzer
from ..team.manager import TeamManager
from ..utils.normalize import (
    normalize_ability,
    normalize_item,
    normalize_move,
    normalize_pokemon_name,
)


def resolve_regulation(regulation: str | None) -> tuple[str, FormatSystem]:
    config = get_regulation_config()
    code = regulation or config.current_regulation
    if code not in config.list_regulation_codes():
        raise ValueError(f"Unknown regulation: {code}")
    return code, cast(FormatSystem, config.get_format_system(code))


async def hydrate_paste(paste: str, pokeapi: PokeAPIClient, regulation: str | None) -> list[PokemonBuild]:
    _, system = resolve_regulation(regulation)
    parsed = parse_showdown_team(paste)
    if not 1 <= len(parsed) <= 6:
        raise ValueError("Provide a Showdown paste with 1-6 Pokemon")
    builds = []
    for mon in parsed:
        Nature(mon.nature.lower())  # Reject misspelled natures rather than silently using Serious.
        if system == "champions" and (mon.tera_type or any(iv != 31 for iv in mon.ivs.values())):
            raise ValueError("Champions has no Terastallization or adjustable IVs; remove Tera Type and non-31 IV lines")
        stats, types = await asyncio.gather(
            pokeapi.get_base_stats(mon.species), pokeapi.get_pokemon_types(mon.species)
        )
        build = parsed_to_pokemon_build(mon, stats, types, format_hint=system)
        if build.format_system != system:
            raise ValueError("Paste allocation system does not match the selected regulation")
        builds.append(build)
    return builds


async def preparation_dataset(smogon: SmogonStatsClient, formats: list[str]) -> dict[str, Any]:
    """Allow configured BO3/BO1 fallbacks without ever crossing regulations."""
    for fmt in formats:
        try:
            return await smogon.get_usage_stats(fmt)
        except SmogonStatsError:
            continue
    raise SmogonStatsError(f"No chaos dataset found for the selected regulation's formats: {formats}")


async def single_build(paste: str, pokeapi: PokeAPIClient, regulation: str | None) -> PokemonBuild:
    builds = await hydrate_paste(paste, pokeapi, regulation)
    if len(builds) != 1:
        raise ValueError("This parameter requires exactly one Pokemon")
    return builds[0]


async def common_build(
    name: str, pokeapi: PokeAPIClient, smogon: SmogonStatsClient,
    regulation: str | None, dataset: dict[str, Any] | None = None,
) -> tuple[PokemonBuild, dict[str, Any]]:
    code, system = resolve_regulation(regulation)
    config = get_regulation_config()
    formats = config.get_smogon_formats(code)
    if dataset is None:
        dataset = (await preparation_dataset(smogon, formats))["_meta"]
    if dataset["format"] not in formats:
        raise ValueError("Usage dataset does not match the selected regulation")
    usage = await smogon.get_pokemon_usage(name, dataset["format"], dataset["rating"], dataset["month"])
    if not usage or not usage["spreads"]:
        raise ValueError(f"No usable chaos spread found for {name}")
    if any(usage["_meta"][key] != dataset[key] for key in ("format", "rating", "month")):
        raise ValueError("Usage source changed during preparation; retry with one dataset")
    spread = next((s for s in usage["spreads"] if ("sps" if system == "champions" else "evs") in s), None)
    if spread is None:
        raise ValueError(f"No valid {system} spread for {name}")
    stats, types = await asyncio.gather(pokeapi.get_base_stats(name), pokeapi.get_pokemon_types(name))
    def top(field: str) -> str:
        return str(next(iter(usage.get(field, {})), ""))
    build = PokemonBuild(
        name=normalize_pokemon_name(name), base_stats=stats, types=types,
        nature=Nature(spread["nature"].lower()), format_system=system,
        evs=EVSpread(**spread.get("evs", {})),
        sps=StatPointSpread(**spread["sps"]) if system == "champions" else None,
        ability=normalize_ability(top("abilities")) or None,
        item=normalize_item(top("items")) or None,
        moves=[normalize_move(m) for m in list(usage.get("moves", {}))[:4]],
        tera_type=top("tera_types").capitalize() or None if system == "mainline" else None,
    )
    source = {**dataset, "kind": "usage_components", "usage_percent": usage["usage_percent"],
              "spread_usage_percent": spread.get("usage"),
              "methodology": "Most frequent nature/allocation plus independently ranked item, ability and moves. Not an observed complete set."}
    return build, source


async def resolve_benchmarks(
    specs: list[BenchmarkSpec], pokemon: PokemonBuild, pokeapi: PokeAPIClient,
    smogon: SmogonStatsClient, regulation: str | None,
) -> list[ResolvedBenchmark]:
    if not 1 <= len(specs) <= 6:
        raise ValueError("Provide 1-6 benchmarks")
    resolved = []
    dataset: dict[str, Any] | None = None
    for spec in specs:
        if spec.opponent_paste:
            opponent = await single_build(spec.opponent_paste, pokeapi, regulation)
            source: dict[str, Any] = {"kind": "explicit_paste", "source_verified": False}
        else:
            opponent, source = await common_build(spec.opponent_name or "", pokeapi, smogon, regulation, dataset)
            dataset = source
        attacker = opponent if spec.kind == "survive" else pokemon
        move = await pokeapi.get_move(spec.move, user_name=attacker.name) if spec.move else None
        if move is not None and not move.is_damaging:
            raise ValueError(f"{move.name} is not a damaging move")
        modifiers = validated_conditions(spec.conditions)
        if pokemon.format_system == "champions" and (modifiers.tera_active or modifiers.defender_tera_active):
            raise ValueError("Champions does not support Terastallization")
        resolved.append(ResolvedBenchmark(spec, opponent, move, modifiers, source))
    return resolved


async def benchmark_handler(
    paste: str, benchmarks: list[BenchmarkSpec], pokeapi: PokeAPIClient,
    smogon: SmogonStatsClient, regulation: str | None, *, recommend: bool = False,
    natures: list[Nature] | None = None,
) -> dict[str, Any]:
    pokemon = await single_build(paste, pokeapi, regulation)
    resolved = await resolve_benchmarks(benchmarks, pokemon, pokeapi, smogon, regulation)
    if recommend:
        return await asyncio.to_thread(recommend_verified_candidates, pokemon, resolved, natures)
    return verify_benchmarks(pokemon, resolved)


async def outcomes_handler(
    attacker_paste: str, defender_paste: str, move_name: str, pokeapi: PokeAPIClient,
    regulation: str | None, conditions: dict[str, Any] | None,
    include_accuracy: bool, random_hits: bool,
) -> dict[str, Any]:
    attacker, defender = await asyncio.gather(
        single_build(attacker_paste, pokeapi, regulation), single_build(defender_paste, pokeapi, regulation)
    )
    move = await pokeapi.get_move(move_name, user_name=attacker.name)
    if not move.is_damaging:
        raise ValueError("Select a damaging move")
    modifiers = validated_conditions(conditions or {})
    if attacker.format_system == "champions" and (modifiers.tera_active or modifiers.defender_tera_active):
        raise ValueError("Champions does not support Terastallization")
    outcomes = await asyncio.to_thread(calculate_move_outcomes, attacker, defender, move,
                                     modifiers,
                                     include_accuracy=include_accuracy, random_hits=random_hits)
    result = result_from_outcomes(outcomes)
    return {"attacker_showdown_paste": pokemon_build_to_showdown(attacker),
            "defender_showdown_paste": pokemon_build_to_showdown(defender),
            "move": move.name, "damage": result.damage_range,
            "ohko_percent": result.ohko_percent, "survival_percent": result.survival_percent,
            "ko_percent_by_uses": [float(p * 100) for p in outcomes.ko_chances],
            "details": result.details}


def reference_sets(manager: TeamManager, name: str, formats: list[str]) -> list[dict[str, Any]]:
    config = get_regulation_config()
    return [{"showdown_paste": pokemon_build_to_showdown(item.pokemon),
             **item.model_dump(exclude={"pokemon"})}
            for item in manager.sourced_sets
            if normalize_pokemon_name(item.pokemon.name) == normalize_pokemon_name(name)
            and any(fmt in config.get_smogon_formats(item.regulation) for fmt in formats)]


async def import_reference_handler(
    paste: str, source_name: str, source_url: str | None, regulation: str | None,
    pokeapi: PokeAPIClient, manager: TeamManager,
) -> dict[str, Any]:
    code, _ = resolve_regulation(regulation)
    builds = await hydrate_paste(paste, pokeapi, code)
    if any(not p.ability or len(p.moves) != 4 for p in builds):
        raise ValueError("A complete reference set requires an ability and four moves; no held item is allowed")
    sourced = [SourcedSet(pokemon=p, regulation=code, source_name=source_name, source_url=source_url) for p in builds]
    count = manager.add_sourced_sets(sourced)
    return {"imported": len(sourced), "session_reference_count": count,
            "source_verified": False, "source_kind": "user_imported_complete",
            "showdown_paste": "\n\n".join(pokemon_build_to_showdown(p) for p in builds),
            "notice": "Source attribution is supplied by the user, not independently authenticated. Stored for this MCP session."}


async def prepare_team_handler(
    team_paste: str | None, regulation: str | None, opponent_names: list[str] | None,
    meta_limit: int, benchmarks_by_slot: dict[int, list[BenchmarkSpec]] | None,
    pokeapi: PokeAPIClient, smogon: SmogonStatsClient, manager: TeamManager,
) -> dict[str, Any]:
    code, system = resolve_regulation(regulation)
    if team_paste:
        builds = await hydrate_paste(team_paste, pokeapi, code)
    else:
        current = manager.get_current_team()
        if current is None:
            raise ValueError("Provide a team_paste or load a team first")
        builds = list(current.pokemon)
    if any(p.format_system != system for p in builds):
        raise ValueError("Team format differs from selected regulation")
    if any(slot < 1 or slot > len(builds) for slot in (benchmarks_by_slot or {})):
        raise ValueError("Benchmark slots are one-based and must exist in the team")
    team = Team(slots=[TeamSlot(pokemon=p, slot_index=i) for i, p in enumerate(builds)])
    formats = get_regulation_config().get_smogon_formats(code)
    stats = await preparation_dataset(smogon, formats)
    dataset = stats["_meta"]
    names = opponent_names or sorted(stats["data"], key=lambda name: -stats["data"][name].get("usage", 0))[:meta_limit]
    if not 1 <= len(names) <= 12:
        raise ValueError("Choose 1-12 opponent names")
    opponents = [await common_build(name, pokeapi, smogon, code, dataset) for name in names]
    move_cache: dict[tuple[str, str], Any] = {}
    async def moves_for(pokemon: PokemonBuild) -> list[Any]:
        moves = []
        for name in pokemon.moves:
            key = pokemon.name, name
            if key not in move_cache:
                move_cache[key] = await pokeapi.get_move(name, user_name=pokemon.name)
            if move_cache[key].is_damaging:
                moves.append(move_cache[key])
        return moves
    rows: list[dict[str, Any]] = []
    for pokemon in builds:
        moves = await moves_for(pokemon)
        for opponent, source in opponents:
            opposing_moves = await moves_for(opponent)
            field = DamageModifiers(multiple_targets=True)
            outgoing = [(move, calculate_damage(pokemon, opponent, move, field)) for move in moves]
            incoming = [(move, calculate_damage(opponent, pokemon, move, field)) for move in opposing_moves]
            def best(calcs: list[Any]) -> dict[str, Any] | None:
                if not calcs:
                    return None
                move, damage = max(calcs, key=lambda pair: (pair[1].ohko_percent, pair[1].max_damage))
                return {"move": move.name, "damage": damage.damage_range, "ohko_percent": damage.ohko_percent}
            rows.append({"pokemon": pokemon.name, "opponent": opponent.name, "outgoing": best(outgoing),
                         "incoming": best(incoming), "faster": calculate_all_stats(pokemon)["speed"] > calculate_all_stats(opponent)["speed"],
                         "pokemon_showdown_paste": pokemon_build_to_showdown(pokemon),
                         "opponent_showdown_paste": pokemon_build_to_showdown(opponent), "source": source})
    adjustments = []
    for slot, specs in (benchmarks_by_slot or {}).items():
        pokemon = builds[slot - 1]
        resolved = await resolve_benchmarks(specs, pokemon, pokeapi, smogon, code)
        recommendation = await asyncio.to_thread(recommend_verified_candidates, pokemon, resolved)
        adjustments.append({"slot": slot, "pokemon": pokemon.name, **recommendation})
    legality = validate_team_rules(team, code)
    for pokemon in builds:
        if pokemon.level != 50:
            legality["violations"].append(f"{pokemon.name}: calculations use level {pokemon.level}, regulation uses 50")
        if len(pokemon.moves) != 4:
            legality["warnings"].append(f"{pokemon.name}: fewer than four moves supplied")
    legality["valid"] = not legality["violations"]
    legality["message"] = "Configured species, team and allocation checks passed" if legality["valid"] else "Team has rule violations"
    legality["scope"] = "Configured species, restricted limit, item/species clauses and validated allocation caps. Move learnsets and event-specific availability require separate validation."
    now = datetime.now(timezone.utc)
    month = datetime.strptime(dataset["month"], "%Y-%m")
    age_months = (now.year - month.year) * 12 + now.month - month.month
    paste = "\n\n".join(pokemon_build_to_showdown(p) for p in builds)
    report: dict[str, Any] = {
        "regulation": code, "format_system": system, "showdown_paste": paste,
        "source": {**dataset, "age_months": age_months, "stale": age_months > 2},
        "legality": legality, "team_summary": TeamAnalyzer().get_summary(team),
        "speed_tiers": [{"pokemon": p.name, "speed": calculate_all_stats(p)["speed"]} for p in builds],
        "matchups": rows, "verified_adjustments": adjustments,
        "complete_reference_sets": [r for p, _ in opponents for r in reference_sets(manager, p.name, formats)],
        "assumptions": ["Doubles with two targets present for spread moves, full HP, neutral field, conditional on landing the default number of hits.",
                        "Speed tiers and faster flags compare raw Speed stats; items, abilities, speed control and move priority are not included.",
                        "Chaos opponents combine independent usage components, not observed complete sets.",
                        "Matchups compare individual attacks; they are not battle-win probabilities.",
                        "Supply benchmarks_by_slot to obtain verified minimum-investment, offense and bulk alternatives."],
    }
    lines = [f"# Team preparation: {code}", "", "```", paste, "```", "",
             "Copy this and paste it directly into Pokemon Showdown's teambuilder.", "",
             f"Source: {dataset['month']} / {dataset['format']} / rating {dataset['rating']}",
             f"Chaos data: {dataset['source_url']}", "", legality["message"], "",
             "| Pokemon | Opponent | Best damage dealt | Strongest incoming attack | Faster |",
             "|---|---|---|---|---|"]
    for row in rows:
        def label(value: dict[str, Any] | None) -> str:
            return f"{value['move']}: {value['damage']} ({value['ohko_percent']:.2f}% OHKO)" if value else "No damaging moves"
        lines.append(f"| {row['pokemon']} | {row['opponent']} | {label(row['outgoing'])} | {label(row['incoming'])} | {row['faster']} |")
    lines.extend(["", "## Exact opponent spreads", ""])
    for opponent, _ in opponents:
        lines.extend(["```", pokemon_build_to_showdown(opponent), "```", ""])
    for adjustment in adjustments:
        lines.extend([f"## Verified alternatives: {adjustment['pokemon']}", ""])
        for candidate in adjustment.get("candidates", []):
            lines.extend([candidate["purpose"], "```", candidate["showdown_paste"], "```", ""])
    lines.extend(["## Assumptions and validation scope", "", legality["scope"], *report["assumptions"],
                  *legality["violations"], *legality["warnings"]])
    report["report_markdown"] = "\n".join(lines)
    return report
