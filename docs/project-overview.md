# VGC MCP Server - Project Overview

## What Is This?

This is a **Model Context Protocol (MCP) server** that helps AI assistants (like Claude) become expert Pokemon VGC team builders. It provides 120+ specialized tools that an AI can call to perform competitive Pokemon calculations, team analysis, and optimization.

## The Problem It Solves

Building competitive VGC (Video Game Championships) Pokemon teams requires:
- Complex damage calculations with dozens of modifiers
- Understanding speed tiers and who outspeeds whom
- Optimizing EV spreads for specific benchmarks
- Checking legality against tournament rules
- Analyzing team matchups against meta threats

This information is scattered across calculators, Smogon forums, and spreadsheets. This MCP server consolidates everything into a single interface that AI can use.

## How It Works

```
┌─────────────────┐     MCP Protocol      ┌─────────────────┐
│  AI Assistant   │ ◄──────────────────► │   VGC MCP       │
│  (Claude, etc)  │     Tool Calls        │   Server        │
└─────────────────┘                       └────────┬────────┘
                                                   │
                                    ┌──────────────┼──────────────┐
                                    ▼              ▼              ▼
                              ┌──────────┐  ┌──────────┐  ┌──────────┐
                              │ PokeAPI  │  │  Smogon  │  │  Local   │
                              │ (stats)  │  │ (usage)  │  │  Calcs   │
                              └──────────┘  └──────────┘  └──────────┘
```

1. User asks Claude: *"Will my Flutter Mane OHKO Dragapult with Moonblast?"*
2. Claude calls the `calculate_damage_output` tool
3. Server fetches Pokemon stats, calculates damage with Gen 9 formula
4. Returns: damage range, KO probability, and relevant modifiers
5. Claude explains the result in natural language

## Key Features

### Damage Calculations
Full Gen 9 damage formula including:
- STAB, type effectiveness, weather, terrain
- Spread move reduction in doubles (0.75x)
- Items (Life Orb, Choice Band/Specs, type-boosting)
- Terastallization (2x STAB for same-type Tera)
- Multi-hit moves (Surging Strikes hits 3x and always crits)
- Screens, burn, abilities

### Speed Analysis
- Compare speeds between Pokemon at any EV spread
- Find EVs needed to outspeed specific threats
- Analyze under Tailwind (2x) or Trick Room (reverse order)
- Speed tier rankings from Smogon usage data

### Team Building
- Import/export Pokemon Showdown paste format
- Species clause validation (no duplicate Pokemon)
- Restricted Pokemon limits (Reg F/G/H rules)
- Item clause checking
- Move legality validation

### Meta Analysis
- Pull usage statistics from Smogon
- Identify threats to your team
- Find checks and counters
- Type coverage gap analysis
- Lead pair recommendations

### EV Optimization
- Find minimum EVs to survive specific attacks
- Find minimum EVs to guarantee OHKOs
- Bulk optimization with diminishing returns math
- Speed probability analysis (% chance to outspeed based on meta spreads)

## Example Tool Calls

**Calculate damage:**
```python
calculate_damage_output(
    attacker_name="flutter-mane",
    defender_name="dragapult",
    move_name="moonblast",
    attacker_nature="timid",
    attacker_spa_evs=252
)
# Returns: 85-100 damage (96.5%-113.6%), 75% OHKO chance
```

**Compare speeds:**
```python
compare_pokemon_speed(
    pokemon1_name="flutter-mane",
    pokemon1_nature="timid",
    pokemon1_evs=252,
    pokemon2_name="dragapult",
    pokemon2_nature="jolly",
    pokemon2_evs=252
)
# Returns: Dragapult outspeeds (213 vs 205)
```

**Check team legality:**
```python
check_team_legality(regulation="H")
# Returns: Pass/fail with specific rule violations
```

**Import a team:**
```python
import_showdown_team(paste="""
Flutter Mane @ Choice Specs
Ability: Protosynthesis
Tera Type: Fairy
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Moonblast
- Shadow Ball
- Dazzling Gleam
- Protect
""")
```

## VGC-Specific Design

Everything is built for VGC doubles format:
- **Level 50** - All calculations at VGC standard level
- **Doubles mechanics** - Spread moves, Helping Hand, partner abilities
- **Bring 6, Pick 4** - Lead selection and back pair analysis
- **Current regulations** - Reg F/G/H restricted lists and rules
- **Meta awareness** - Smogon VGC usage data integration

## Data Sources

- **PokeAPI** - Pokemon stats, types, moves, abilities
- **Smogon Stats** - Usage rates, common spreads, item/move frequencies
- **Local data** - Type chart, damage formula, regulation rules

All API responses are cached to disk for 7 days to minimize external requests.

## Who Is This For?

- **VGC competitors** who want AI-assisted team building
- **Content creators** analyzing teams and matchups
- **Developers** building Pokemon tools on MCP
- **Anyone** who wants to understand VGC mechanics deeply

## Technical Stack

- **Python 3.11+**
- **FastMCP** - MCP server framework
- **Pydantic** - Data validation and models
- **httpx** - Async HTTP client
- **diskcache** - Persistent caching
