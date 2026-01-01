# tools/ - MCP Tool Definitions

MCP tools exposed to AI assistants. Each module registers tools via `register_*_tools()`.

## Tool Modules (157 tools total)

### Core Tools

| Module | Tools | Description |
|--------|-------|-------------|
| `team_tools.py` | 9 | Team management (add, remove, view, analyze) |
| `damage_tools.py` | 3 | Damage calculations with Smogon auto-fetch |
| `stats_tools.py` | 2 | Pokemon stat calculations |
| `speed_tools.py` | 4 | Speed comparisons |
| `usage_tools.py` | 6 | Smogon usage data |

### Analysis Tools

| Module | Tools | Description |
|--------|-------|-------------|
| `coverage_tools.py` | 6 | Type coverage analysis |
| `matchup_tools.py` | 6 | Pokemon matchup scoring |
| `spread_tools.py` | 6 | EV optimization |
| `speed_tier_tools.py` | 3 | Speed tier visualization |
| `speed_probability_tools.py` | 4 | Outspeed probabilities |

### Import/Export

| Module | Tools | Description |
|--------|-------|-------------|
| `import_export_tools.py` | 4 | Showdown paste import/export |
| `pokepaste_tools.py` | 3 | PokePaste URL fetching |

### Legality & Rules

| Module | Tools | Description |
|--------|-------|-------------|
| `legality_tools.py` | 12 | VGC format legality checks |
| `move_tools.py` | 7 | Move validation and suggestions |

### Battle Mechanics

| Module | Tools | Description |
|--------|-------|-------------|
| `priority_tools.py` | 5 | Priority move analysis |
| `ability_tools.py` | 6 | Ability synergy |
| `speed_control_tools.py` | 6 | Trick Room/Tailwind |
| `item_tools.py` | 4 | Item effects |
| `chip_damage_tools.py` | 3 | Residual damage |

### Meta Analysis

| Module | Tools | Description |
|--------|-------|-------------|
| `meta_threat_tools.py` | 5 | Threat identification |
| `core_tools.py` | 6 | Core building suggestions |
| `lead_tools.py` | 3 | Lead matchup analysis |

### User Experience

| Module | Tools | Description |
|--------|-------|-------------|
| `workflow_tools.py` | 12 | High-level coordinators |
| `context_tools.py` | 4 | Pokemon context persistence |
| `preset_tools.py` | 3 | Preset spread suggestions |
| `sample_team_tools.py` | 2 | Sample team archetypes |

---

## Tool Registration Pattern

Each module exports a `register_*_tools()` function:

```python
# damage_tools.py
def register_damage_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: SmogonStatsClient):

    @mcp.tool()
    async def calculate_damage_output(
        attacker_name: str,
        defender_name: str,
        move_name: str,
        ...
    ) -> dict:
        """
        Calculate damage from one Pokemon to another.

        By default, uses the most common Smogon VGC spread...
        """
        # Implementation
        return {...}
```

### Registration in server.py

```python
from .tools.damage_tools import register_damage_tools
from .tools.team_tools import register_team_tools

# In server.py
register_damage_tools(mcp, pokeapi, smogon)
register_team_tools(mcp, pokeapi, team_manager, analyzer)
```

---

## Key Tools

### calculate_damage_output
```python
# Auto-fetches Smogon spreads when EVs not specified
result = await calculate_damage_output(
    attacker_name="flutter-mane",
    defender_name="incineroar",
    move_name="moonblast"
)
# Returns damage range, KO chance, spread info
```

### calc_damage_vs_smogon_sets
```python
# Calculate YOUR spread vs top Smogon sets
result = await calc_damage_vs_smogon_sets(
    my_pokemon="ogerpon-wellspring",
    my_nature="Impish",
    my_hp_evs=220,
    my_def_evs=204,
    opponent_pokemon="urshifu",
    move="close-combat",
    direction="from"  # opponent attacks me
)
# Returns survival info for top 3 Smogon sets
```

### import_showdown_team
```python
result = await import_showdown_team(paste="""
Flutter Mane @ Choice Specs
Ability: Protosynthesis
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Moonblast
- Shadow Ball
...
""")
```

---

## Error Handling

All tools use structured errors from `utils/errors.py`:

```python
from ..utils.errors import pokemon_not_found_error, api_error

# Pokemon not found
suggestions = suggest_pokemon_name(name)
return pokemon_not_found_error(name, suggestions)

# API error
return api_error("Smogon", str(e), is_retryable=True)
```

---

## Lite Server Tools

`server_lite.py` includes only these modules (49 tools):
- team_tools (9)
- damage_tools (3)
- stats_tools (2)
- speed_tools (4)
- speed_tier_tools (3)
- import_export_tools (4)
- spread_tools (6)
- coverage_tools (6)
- matchup_tools (6)
- usage_tools (6)
