# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VGC MCP Server - A Model Context Protocol server for Pokemon VGC (Video Game Championships) team building. Provides 120+ tools for damage calculations, stat analysis, team management, and competitive play optimization.

## Commands

```bash
# Install (editable mode)
pip install -e .

# Run server
python -m vgc_mcp
# or after install:
vgc-mcp

# Run all tests
python -m pytest tests/ -v

# Run single test file
python -m pytest tests/test_damage.py -v

# Run specific test
python -m pytest tests/test_matchup.py::TestSingleMatchup::test_type_advantage_improves_matchup -v

# Run with coverage
python -m pytest tests/ --cov=vgc_mcp

# Linting
ruff check src/
ruff format src/

# Type checking
mypy src/vgc_mcp
```

## Architecture

### Core Structure

```
src/vgc_mcp/
├── server.py          # MCP server entry point, registers all tools
├── config.py          # Settings (API URLs, VGC defaults, EV limits)
├── api/               # External API clients
│   ├── pokeapi.py     # PokeAPI client for Pokemon data
│   ├── smogon.py      # Smogon Stats client for usage data
│   └── cache.py       # Disk-based API response caching
├── calc/              # Pure calculation functions
│   ├── damage.py      # Full Gen 9 damage formula
│   ├── modifiers.py   # Type chart, weather, terrain, items
│   ├── stats.py       # Stat calculation formulas
│   └── ...            # Speed, matchup, chip damage calcs
├── models/            # Pydantic data models
│   ├── pokemon.py     # PokemonBuild, Nature, EVSpread, IVSpread
│   ├── move.py        # Move model with multi-hit support
│   └── team.py        # Team with species clause validation
├── tools/             # MCP tool definitions (22 files)
│   └── *_tools.py     # Each registers tools via register_*_tools(mcp, ...)
├── rules/             # VGC format rules and legality
├── formats/           # Showdown paste import/export
└── utils/             # Error handling, fuzzy matching
```

### Key Patterns

**Tool Registration**: Each `tools/*_tools.py` exports a `register_*_tools(mcp, ...)` function that decorates async functions with `@mcp.tool()`. Dependencies (pokeapi, team_manager, etc.) are passed in.

**Error Handling**: Use `utils/errors.py` helpers:
```python
from ..utils.errors import pokemon_not_found_error, api_error
from ..utils.fuzzy import suggest_pokemon_name

# Good - structured error with suggestions
suggestions = suggest_pokemon_name(pokemon_name)
return pokemon_not_found_error(pokemon_name, suggestions)

# Avoid - raw error strings
return {"error": f"Pokemon not found: {name}"}  # Don't do this
```

**Pydantic Models**: All data structures use Pydantic for validation. `PokemonBuild` is the central model containing base stats, nature, EVs, IVs, item, ability, and tera type.

**Calculations**: `calc/` modules are pure functions. `calc/damage.py` implements the Gen 9 damage formula with all modifiers (STAB, type effectiveness, weather, terrain, screens, items).

### Type Chart

Located in `calc/modifiers.py`. Key mechanics:
- Fire is super effective against Steel (2x), not resisted
- Fire resists Fire (0.5x)
- Type effectiveness stacks for dual types (0.25x to 4x)

### VGC Defaults

- Level 50 (standard VGC)
- 508 max total EVs, 252 per stat
- Doubles format (spread moves get 0.75x multiplier)

## Testing

Tests use pytest with `asyncio_mode = "auto"`. Common fixtures in `tests/conftest.py`:
- `team_manager` - Fresh TeamManager instance
- Sample stats fixtures: `flutter_mane_stats`, `dragapult_stats`, etc.

Test files mirror the module structure. Many tests create Pokemon inline:
```python
def make_pokemon(name, types, base_hp=80, ...):
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(hp=base_hp, ...),
        nature=Nature.SERIOUS,
        evs=EVSpread(),
        types=types
    )
```

## Dependencies

- `mcp` - Model Context Protocol framework
- `httpx` - Async HTTP client for APIs
- `pydantic` - Data validation
- `diskcache` - Persistent API caching

## Smogon Data Source

Usage stats are pulled from Smogon's chaos JSON files:
- **URL**: `https://www.smogon.com/stats/{YYYY-MM}/chaos/{format}-{rating}.json`
- **Rating**: 1760 (highest available ELO cutoff)
- **Available ratings**: 0, 1500, 1630, 1760
- **Auto-detection**: Finds latest available month automatically

## Damage Calculation Output Format

When presenting damage calculation results to users, format them as markdown tables for readability:

**Header format:**
```
Your [Pokemon Name]
[Nature] | [HP] HP / [Atk] Atk / [Def] Def / [SpD] SpD / [Spe] Spe | [Item]
```

**Damage dealt table:**
| Target | Their Spread | Item | Damage | Result |
|--------|--------------|------|--------|--------|
| Rillaboom | Adamant 252/116/4/0/60/76 | Assault Vest | 130-154% | OHKO |

**Damage taken table:**
| Attacker | Their Spread | Item | Move | Damage |
|----------|--------------|------|------|--------|
| Tornadus | Timid 36/0/12/204/4/252 | Covert Cloak | Bleakwind Storm | 85-100% |

**Result column values:**
- OHKO (guaranteed one-hit KO)
- X% OHKO (probability)
- 2HKO, 3HKO for multi-hit KOs
- "Resists" for low damage (<30%)

**Include a "Key Takeaways" section** summarizing:
- Biggest threats (moves that can OHKO or come close)
- Pokemon you OHKO reliably
- Notable type resistances/immunities
- Weather/terrain interactions
