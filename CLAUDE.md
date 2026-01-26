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

## Tool Selection Guide

### For Survival Questions ("Can X survive Y?", "What EVs to survive?")

Use the RIGHT tool for survival calculations:

1. **find_survival_evs** - Find minimum HP/Def EVs to survive an attack
   - Auto-fetches attacker's Smogon spread (nature, EVs, item)
   - Returns required defensive EVs + damage calculation
   - Use when: "What EVs does Ogerpon need to survive Urshifu?"
   - **ALWAYS show the attacker_spread_info in your response**

2. **calculate_damage_output** - Check exact damage with specific spreads
   - Use when verifying a specific spread survives
   - Shows damage percentage against multiple common defender spreads
   - **ALWAYS show the attacker_spread field so user knows what was assumed**

3. **design_spread_with_benchmarks** - Complex spread with speed + survival
   - Use when: "Design a spread that outspeeds X AND survives Y"
   - Handles Tera, Tailwind, Booster Energy, speed stages

### Common Mistakes to Avoid

- **DON'T give offensive spreads when asked about survival** - If user asks "what spread survives X?", return defensive EVs (HP/Def), not offensive (Atk/Spe)
- **ALWAYS show the FULL attacker spread with EVs** - Don't just say "Adamant Choice Scarf Urshifu", say "Adamant 4 HP / 252 Atk / 252 Spe Choice Scarf Urshifu"
- **Understand damage calc notation**: "252 Atk" = neutral nature, "252+ Atk" = boosting nature (Adamant)
- **Don't hallucinate numbers** - If the tool returns 81.8-96.2%, don't say 81.2-98.7%

### CRITICAL: Always Show Full Spreads

When reporting damage calculations, ALWAYS include the full EV spread for the attacker. The tool response includes `attacker_ev_spread` at the top level - USE IT.

**Good:** "survives Surging Strikes from **Adamant 4 HP / 252 Atk / 252 Spe Choice Scarf Urshifu** (67.4-78.6%)"

**Bad:** "survives Surging Strikes from Adamant Choice Scarf Urshifu (67.4-78.6%)"

The user needs to know the EXACT spread used to verify the calculation themselves.

### Example: Correct Survival Response

User: "What EVs does Ogerpon need to survive Urshifu Surging Strikes?"

Good response:
```
Urshifu's Smogon spread: Adamant 4 HP / 252 Atk / 252 Spe @ Choice Scarf

With 252 HP / 4 Def / 252 Spe Jolly, you survive taking 67.4-78.6% (126-147 damage).
```

Bad response (DON'T DO THIS):
```
You survive Adamant Choice Scarf Urshifu with 252 HP / 4 Def.
[Missing the attacker's EV spread! User can't verify.]
```

## User Onboarding

### When Users Say "Hi" or Greet
**IMPORTANT:** When a user greets you (Hi, Hello, Hey, etc.) or asks what you can do,
you MUST call the `welcome_new_user()` tool to show them the welcome message and
starter prompts. Do NOT manually type the welcome message - always use the tool.

This ensures consistent onboarding and shows users the available capabilities.

### Example Prompts to Share

**Damage Calculations:**
- "Does my Flutter Mane OHKO Incineroar with Moonblast?"
- "Can Amoonguss survive Flutter Mane's Moonblast?"
- "What's the damage range for Landorus EQ vs Rillaboom?"
- "Check damage with Tera active"

**Team Building:**
- "Help me build a Rain team"
- "What Pokemon pair well with Flutter Mane?"
- "Analyze my team: [Showdown paste]"
- "What are my team's weaknesses?"

**EV Optimization:**
- "What EVs does Incineroar need to survive Flutter Mane?"
- "Is my spread efficient? Suggest a better nature"
- "Find bulk EVs to survive multiple threats"
- "Optimize my Dragonite's EVs"

**Speed Analysis:**
- "Is my Landorus faster than Tornadus?"
- "What speed tier is 252 Spe Timid Flutter Mane?"
- "Show speed tiers under Tailwind"
- "Compare speeds with different natures"

**Learning VGC:**
- "Explain what EVs are"
- "What makes Flutter Mane good?"
- "Explain Fire type matchups"
- "What does STAB mean?"
- "Explain Trick Room"

**Nature Optimization:**
- "Can I save EVs with a different nature?"
- "Suggest nature optimization for my spread"
- "Is Serious nature optimal?"

### Common User Flows

1. **New User**: "I'm new to VGC" → Show capabilities → Suggest beginner team
2. **Team Building**: "Build a team around [Pokemon]" → Suggest core → Add support → Check weaknesses
3. **Damage Check**: "Does X OHKO Y?" → Calculate → Show transparent breakdown
4. **EV Optimization**: "What EVs to survive X?" → Calculate bulk → Suggest spread
5. **Learning**: "Explain [term]" → Show glossary entry → Provide examples
