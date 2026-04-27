"""Shared tool helpers used by `vgc_mcp` and re-usable by any sibling project.

This module holds *implementation* helpers (not tool registrations). The
plain-MCP server in `vgc_mcp/tools/` and any MCP-UI sibling project can both
import from here so the logic stays in one place.

Currently exports:

- `build_helpers`: shorthand constructors for PokemonBuild + EVSpread, plus
  parallel-fetch helpers that hit PokeAPI for several Pokemon at once.
- `parse_helpers`: nature/EV parsing with structured error returns.
"""

from .build_helpers import (
    fetch_pokemon_basics,
    fetch_pokemon_basics_many,
    build_pokemon,
    parse_ev_dict,
    evs_from_kwargs,
)
from .parse_helpers import (
    parse_nature,
    parse_ev_total,
)
from .smogon_helpers import (
    get_common_spread,
    get_common_spreads,
)

__all__ = [
    "fetch_pokemon_basics",
    "fetch_pokemon_basics_many",
    "build_pokemon",
    "parse_ev_dict",
    "evs_from_kwargs",
    "parse_nature",
    "parse_ev_total",
    "get_common_spread",
    "get_common_spreads",
]
