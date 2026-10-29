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
from typing import Any, Mapping, Optional, Union

from ..models.pokemon import (
    BaseStats,
    EVSpread,
    IVSpread,
    Nature,
    PokemonBuild,
    StatPointSpread,
)


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


Allocation = Union[EVSpread, StatPointSpread, Mapping[str, int], str, None]
"""A stat allocation in any accepted shape: an EVSpread / StatPointSpread, a
stat dict, or a "HP/Atk/Def/SpA/SpD/Spe" slash string. None means no investment."""


def parse_ev_string(ev_string: str) -> dict:
    """Parse '252/0/0/252/0/4' format into EV dict."""
    parts = ev_string.split("/")
    if len(parts) != 6:
        raise ValueError(f"EV string must have 6 values separated by '/', got: {ev_string}")
    stat_names = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
    return {name: int(val) for name, val in zip(stat_names, parts)}


def parse_sp_string(sp_string: str) -> StatPointSpread:
    """Parse 'HP/Atk/Def/SpA/SpD/Spe' Stat Points into a StatPointSpread.

    Champions caps: 0-32 per stat (enforced by the model); the 66 total is
    enforced when the spread is placed on a PokemonBuild.
    """
    parts = [p.strip() for p in sp_string.replace(",", "/").split("/")]
    if len(parts) != 6:
        raise ValueError(
            "Stat Points must be 'HP/Atk/Def/SpA/SpD/Spe' (six values)"
        )
    vals = [int(p) for p in parts]
    return StatPointSpread(
        hp=vals[0], attack=vals[1], defense=vals[2],
        special_attack=vals[3], special_defense=vals[4], speed=vals[5],
    )


def to_allocation(
    spread: Allocation, *, champions: bool
) -> Union[EVSpread, StatPointSpread]:
    """Coerce any accepted allocation shape into the format's spread model.

    Champions -> StatPointSpread (dicts via `StatPointSpread.from_sps_dict`,
    strings via `parse_sp_string`); mainline -> EVSpread (dicts via
    `parse_ev_dict`, strings via `parse_ev_string`). Passing a spread model of
    the other format is a programming error: convert explicitly with
    `calc.conversion.evs_to_sps_spread` / `sps_to_evs_spread` instead.
    """
    if spread is None:
        return StatPointSpread() if champions else EVSpread()
    if isinstance(spread, StatPointSpread):
        if not champions:
            raise TypeError("StatPointSpread given for a mainline build")
        return spread
    if isinstance(spread, EVSpread):
        if champions:
            raise TypeError("EVSpread given for a Champions build")
        return spread
    if isinstance(spread, str):
        return parse_sp_string(spread) if champions else EVSpread(**parse_ev_string(spread))
    return StatPointSpread.from_sps_dict(dict(spread)) if champions else parse_ev_dict(dict(spread))


def build_pokemon(
    name: str,
    base_stats: BaseStats,
    types: Optional[list[str]] = None,
    *,
    nature: Nature = Nature.SERIOUS,
    evs: Allocation = None,
    ivs: Optional[IVSpread] = None,
    item: Optional[str] = None,
    ability: Optional[str] = None,
    tera_type: Optional[str] = None,
    moves: Optional[list[str]] = None,
    spread: Allocation = None,
    champions: Optional[bool] = None,
    level: int = 50,
) -> PokemonBuild:
    """Construct a format-correct PokemonBuild.

    `spread` is the stat allocation in any `Allocation` shape (`evs` is the
    legacy name for the same argument). `champions=True` yields a
    `format_system="champions"` build carrying a StatPointSpread; False yields
    a mainline build carrying an EVSpread. When `champions` is None it is
    inferred from the spread type (a StatPointSpread means Champions).
    """
    if spread is not None and evs is not None:
        raise TypeError("Pass the allocation as `spread` or `evs`, not both")
    alloc = spread if spread is not None else evs
    if champions is None:
        champions = isinstance(alloc, StatPointSpread)
    stats = to_allocation(alloc, champions=champions)
    common: dict[str, Any] = dict(
        name=name,
        base_stats=base_stats,
        types=types or [],
        nature=nature,
        ivs=ivs or IVSpread(),
        level=level,
        item=item,
        ability=ability,
        tera_type=tera_type,
        moves=moves or [],
    )
    if champions:
        return PokemonBuild(format_system="champions", sps=stats, **common)
    return PokemonBuild(evs=stats, **common)


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
