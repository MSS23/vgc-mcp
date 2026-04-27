"""Shared helpers for constructing PokemonBuild objects in tools.

Tool implementations across `vgc_mcp/tools/` (and any sibling project that
reuses this core) repeatedly do:

    base = await pokeapi.get_base_stats(name)
    types = await pokeapi.get_pokemon_types(name)
    pkm = PokemonBuild(name=name, base_stats=base, types=types, ...)

These helpers consolidate that pattern, with parallel-fetch support for the
N-defender case (which previously did N sequential awaits).
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from ..models.pokemon import BaseStats, EVSpread, IVSpread, Nature, PokemonBuild


async def fetch_pokemon_basics(
    pokeapi: Any, name: str
) -> tuple[BaseStats, list[str]]:
    """Fetch base stats and types for a single Pokemon.

    These two PokeAPI calls land on the same underlying `/pokemon/<name>`
    endpoint and are both cached, so the second call is effectively free.

    Args:
        pokeapi: PokeAPIClient instance
        name: Pokemon name (any case / form notation)

    Returns:
        (base_stats, types) tuple
    """
    base = await pokeapi.get_base_stats(name)
    types = await pokeapi.get_pokemon_types(name)
    return base, types


async def fetch_pokemon_basics_many(
    pokeapi: Any, names: list[str]
) -> list[tuple[str, BaseStats, list[str]] | tuple[str, Exception]]:
    """Fetch (base_stats, types) for many Pokemon in parallel.

    Returns a list aligned with `names`. For each entry, a successful fetch
    returns `(name, base_stats, types)`; a failure returns `(name, exception)`.
    Callers can filter by length/type.

    This is the pattern bulk-calc / multi-defender tools should use instead of
    a sequential `for` loop of awaits — one round-trip wave per group, not N.
    """

    async def _one(n: str):
        try:
            return (n, *(await fetch_pokemon_basics(pokeapi, n)))
        except Exception as e:  # noqa: BLE001
            return (n, e)

    return await asyncio.gather(*[_one(n) for n in names])


def build_pokemon(
    name: str,
    base_stats: BaseStats,
    types: list[str],
    *,
    nature: Nature = Nature.SERIOUS,
    evs: Optional[EVSpread] = None,
    ivs: Optional[IVSpread] = None,
    item: Optional[str] = None,
    ability: Optional[str] = None,
    tera_type: Optional[str] = None,
    moves: Optional[list[str]] = None,
) -> PokemonBuild:
    """Construct a PokemonBuild with sensible defaults.

    Removes the 12-line PokemonBuild constructor invocation that's repeated
    78+ times across tool files. Pass only the fields that matter for your
    calculation; everything else gets a safe default.
    """
    return PokemonBuild(
        name=name,
        base_stats=base_stats,
        types=types,
        nature=nature,
        evs=evs or EVSpread(),
        ivs=ivs or IVSpread(),
        item=item,
        ability=ability,
        tera_type=tera_type,
        moves=moves or [],
    )


def parse_ev_dict(ev_dict: Optional[dict]) -> EVSpread:
    """Convert a flat EV dict like {'hp': 252, 'attack': 4} into EVSpread.

    Accepts both 'attack' / 'special_attack' / 'special_defense' (canonical)
    and short forms 'atk' / 'spa' / 'spd' / 'def' / 'spe' / 'hp'.

    Returns an empty EVSpread if `ev_dict` is None or empty.
    """
    if not ev_dict:
        return EVSpread()

    aliases = {
        "atk": "attack",
        "def": "defense",
        "spa": "special_attack",
        "spd": "special_defense",
        "spe": "speed",
    }
    canonical = {aliases.get(k.lower(), k.lower()): v for k, v in ev_dict.items()}
    return EVSpread(
        hp=canonical.get("hp", 0),
        attack=canonical.get("attack", 0),
        defense=canonical.get("defense", 0),
        special_attack=canonical.get("special_attack", 0),
        special_defense=canonical.get("special_defense", 0),
        speed=canonical.get("speed", 0),
    )


def evs_from_kwargs(
    *,
    hp_evs: int = 0,
    atk_evs: int = 0,
    def_evs: int = 0,
    spa_evs: int = 0,
    spd_evs: int = 0,
    spe_evs: int = 0,
) -> EVSpread:
    """Convert the flat-arg `*_evs` kwargs many tools accept into an EVSpread.

    Many tool signatures take `hp_evs`, `atk_evs`, etc. as separate ints
    (so MCP clients can supply them via JSON Schema int fields). This is the
    one-liner converter.
    """
    return EVSpread(
        hp=hp_evs,
        attack=atk_evs,
        defense=def_evs,
        special_attack=spa_evs,
        special_defense=spd_evs,
        speed=spe_evs,
    )
