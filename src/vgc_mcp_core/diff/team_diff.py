"""Core team diff logic for comparing Pokemon team versions."""

from typing import Optional
from dataclasses import asdict

from ..formats.showdown import ParsedPokemon
from .models import (
    TeamDiff,
    PokemonDiff,
    FieldChange,
    ChangeType,
    FieldType,
    StatChange,
    MoveChange,
)
from .change_reasons import (
    explain_nature_change,
    explain_ev_change,
    explain_item_change,
    explain_move_change,
    explain_ability_change,
    explain_tera_change,
)


def normalize_species_name(name: str) -> str:
    """Normalize species name for matching.

    Examples:
        "Flutter Mane" -> "flutter-mane"
        "Ogerpon-Wellspring" -> "ogerpon-wellspring"
        "flutter mane" -> "flutter-mane"
    """
    return name.lower().replace(" ", "-").strip()


def pokemon_to_dict(pokemon: ParsedPokemon) -> dict:
    """Convert ParsedPokemon to a dict for storage/display."""
    return {
        "species": pokemon.species,
        "nickname": pokemon.nickname,
        "item": pokemon.item,
        "ability": pokemon.ability,
        "level": pokemon.level,
        "tera_type": pokemon.tera_type,
        "evs": pokemon.evs.copy(),
        "ivs": pokemon.ivs.copy(),
        "nature": pokemon.nature,
        "moves": pokemon.moves.copy(),
    }


def match_pokemon_by_species(
    team1: list[ParsedPokemon],
    team2: list[ParsedPokemon],
) -> tuple[list[tuple[ParsedPokemon, ParsedPokemon]], list[ParsedPokemon], list[ParsedPokemon]]:
    """Match Pokemon between two teams by species name.

    Pokemon forms (e.g., Ogerpon-Wellspring vs Ogerpon-Hearthflame) are treated
    as different species.

    Args:
        team1: First team (version 1)
        team2: Second team (version 2)

    Returns:
        Tuple of:
        - matched: List of (v1_pokemon, v2_pokemon) tuples
        - removed: Pokemon in v1 but not in v2
        - added: Pokemon in v2 but not in v1
    """
    # Build dicts mapping normalized name to Pokemon
    # Use lists to handle potential duplicates
    team1_by_name: dict[str, list[ParsedPokemon]] = {}
    for p in team1:
        name = normalize_species_name(p.species)
        if name not in team1_by_name:
            team1_by_name[name] = []
        team1_by_name[name].append(p)

    team2_by_name: dict[str, list[ParsedPokemon]] = {}
    for p in team2:
        name = normalize_species_name(p.species)
        if name not in team2_by_name:
            team2_by_name[name] = []
        team2_by_name[name].append(p)

    matched: list[tuple[ParsedPokemon, ParsedPokemon]] = []
    removed: list[ParsedPokemon] = []
    added: list[ParsedPokemon] = []

    # Find matches
    matched_names: set[str] = set()
    for name, v1_list in team1_by_name.items():
        if name in team2_by_name:
            v2_list = team2_by_name[name]
            # Match first-to-first for duplicates
            for i, v1_pokemon in enumerate(v1_list):
                if i < len(v2_list):
                    matched.append((v1_pokemon, v2_list[i]))
                else:
                    removed.append(v1_pokemon)
            # Any extra in v2 are "added"
            for i in range(len(v1_list), len(v2_list)):
                added.append(v2_list[i])
            matched_names.add(name)
        else:
            # All v1 Pokemon with this name are removed
            removed.extend(v1_list)

    # Find added (in v2 but not matched)
    for name, v2_list in team2_by_name.items():
        if name not in matched_names:
            added.extend(v2_list)

    return matched, removed, added


def compare_evs(v1_evs: dict, v2_evs: dict) -> Optional[FieldChange]:
    """Compare EV spreads and generate change if different."""
    stats = ["hp", "atk", "def", "spa", "spd", "spe"]

    stat_changes = []
    for stat in stats:
        before = v1_evs.get(stat, 0)
        after = v2_evs.get(stat, 0)
        if before != after:
            stat_changes.append(StatChange(stat=stat, before=before, after=after))

    if not stat_changes:
        return None

    # Format before/after strings
    def format_evs(evs: dict) -> str:
        parts = []
        stat_display = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}
        for stat in stats:
            val = evs.get(stat, 0)
            if val > 0:
                parts.append(f"{val} {stat_display[stat]}")
        return " / ".join(parts) if parts else "0 EVs"

    reason = explain_ev_change([
        {"stat": sc.stat, "before": sc.before, "after": sc.after, "delta": sc.delta}
        for sc in stat_changes
    ])

    return FieldChange(
        field=FieldType.EVS,
        before=format_evs(v1_evs),
        after=format_evs(v2_evs),
        reason=reason,
        stat_changes=stat_changes,
    )


def compare_ivs(v1_ivs: dict, v2_ivs: dict) -> Optional[FieldChange]:
    """Compare IV spreads and generate change if different.

    Only reports changes from non-default IVs (31 is default).
    """
    stats = ["hp", "atk", "def", "spa", "spd", "spe"]

    stat_changes = []
    for stat in stats:
        before = v1_ivs.get(stat, 31)
        after = v2_ivs.get(stat, 31)
        if before != after:
            stat_changes.append(StatChange(stat=stat, before=before, after=after))

    if not stat_changes:
        return None

    # Format before/after strings
    def format_ivs(ivs: dict) -> str:
        parts = []
        stat_display = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}
        for stat in stats:
            val = ivs.get(stat, 31)
            if val != 31:
                parts.append(f"{val} {stat_display[stat]}")
        return " / ".join(parts) if parts else "31 all"

    return FieldChange(
        field=FieldType.IVS,
        before=format_ivs(v1_ivs),
        after=format_ivs(v2_ivs),
        reason="IV spread changed",
        stat_changes=stat_changes,
    )


def compare_moves(v1_moves: list[str], v2_moves: list[str]) -> Optional[FieldChange]:
    """Compare movesets and generate change if different."""
    # Normalize move names for comparison
    v1_set = {m.lower().strip() for m in v1_moves}
    v2_set = {m.lower().strip() for m in v2_moves}

    if v1_set == v2_set:
        return None

    # Find added and removed (use original names for display)
    v1_lookup = {m.lower().strip(): m for m in v1_moves}
    v2_lookup = {m.lower().strip(): m for m in v2_moves}

    removed_keys = v1_set - v2_set
    added_keys = v2_set - v1_set

    removed = [v1_lookup[k] for k in removed_keys]
    added = [v2_lookup[k] for k in added_keys]

    move_changes = MoveChange(added=added, removed=removed)
    reason = explain_move_change(added, removed)

    return FieldChange(
        field=FieldType.MOVES,
        before=", ".join(v1_moves) if v1_moves else "No moves",
        after=", ".join(v2_moves) if v2_moves else "No moves",
        reason=reason,
        move_changes=move_changes,
    )


def compare_pokemon(v1: ParsedPokemon, v2: ParsedPokemon) -> list[FieldChange]:
    """Compare two versions of the same Pokemon species.

    Checks: EVs, IVs, Nature, Item, Ability, Tera Type, Moves

    Args:
        v1: Version 1 of the Pokemon
        v2: Version 2 of the Pokemon

    Returns:
        List of FieldChange objects for all detected differences
    """
    changes: list[FieldChange] = []

    # Nature
    if v1.nature != v2.nature:
        changes.append(FieldChange(
            field=FieldType.NATURE,
            before=v1.nature,
            after=v2.nature,
            reason=explain_nature_change(v1.nature, v2.nature),
        ))

    # EVs
    ev_change = compare_evs(v1.evs, v2.evs)
    if ev_change:
        changes.append(ev_change)

    # IVs (only if changed from non-default)
    iv_change = compare_ivs(v1.ivs, v2.ivs)
    if iv_change:
        changes.append(iv_change)

    # Item
    if v1.item != v2.item:
        changes.append(FieldChange(
            field=FieldType.ITEM,
            before=v1.item or "None",
            after=v2.item or "None",
            reason=explain_item_change(v1.item, v2.item),
        ))

    # Ability
    if v1.ability != v2.ability:
        changes.append(FieldChange(
            field=FieldType.ABILITY,
            before=v1.ability or "None",
            after=v2.ability or "None",
            reason=explain_ability_change(v1.ability, v2.ability),
        ))

    # Tera Type
    if v1.tera_type != v2.tera_type:
        changes.append(FieldChange(
            field=FieldType.TERA_TYPE,
            before=v1.tera_type or "None",
            after=v2.tera_type or "None",
            reason=explain_tera_change(v1.tera_type, v2.tera_type),
        ))

    # Moves
    move_change = compare_moves(v1.moves, v2.moves)
    if move_change:
        changes.append(move_change)

    return changes


def generate_team_diff(
    team1: list[ParsedPokemon],
    team2: list[ParsedPokemon],
    v1_name: str = "Version 1",
    v2_name: str = "Version 2",
) -> TeamDiff:
    """Generate complete diff between two team versions.

    This is the main entry point for team comparison.

    Args:
        team1: First team (older version)
        team2: Second team (newer version)
        v1_name: Display name for version 1
        v2_name: Display name for version 2

    Returns:
        TeamDiff object with all changes and summary
    """
    matched, removed, added = match_pokemon_by_species(team1, team2)

    pokemon_diffs: list[PokemonDiff] = []
    unchanged: list[str] = []

    # Process removed Pokemon
    for pokemon in removed:
        pokemon_diffs.append(PokemonDiff(
            species=pokemon.species,
            change_type=ChangeType.REMOVED,
            changes=[],
            pokemon_data=pokemon_to_dict(pokemon),
        ))

    # Process added Pokemon
    for pokemon in added:
        pokemon_diffs.append(PokemonDiff(
            species=pokemon.species,
            change_type=ChangeType.ADDED,
            changes=[],
            pokemon_data=pokemon_to_dict(pokemon),
        ))

    # Process matched Pokemon (check for modifications)
    for v1_pokemon, v2_pokemon in matched:
        changes = compare_pokemon(v1_pokemon, v2_pokemon)
        if changes:
            pokemon_diffs.append(PokemonDiff(
                species=v1_pokemon.species,
                change_type=ChangeType.MODIFIED,
                changes=changes,
                pokemon_data=pokemon_to_dict(v2_pokemon),  # Store new version data
            ))
        else:
            unchanged.append(v1_pokemon.species)

    return TeamDiff(
        version1_name=v1_name,
        version2_name=v2_name,
        pokemon_diffs=pokemon_diffs,
        unchanged=unchanged,
    )
