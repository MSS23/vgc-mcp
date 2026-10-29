# tools/ - MCP Tool Definitions

MCP tools exposed to AI assistants. Each module registers tools via `register_*_tools()`.

## Tool Modules

The server registers **206 tools** across these modules (`FULL_TOOL_COUNT` in
[`../profiles.py`](../profiles.py) pins the total). The per-module list with
every tool's one-line description is generated from the running server in
[`docs/tools-catalog.md`](../../../docs/tools-catalog.md); CI fails if it
drifts, so use it rather than keeping counts here.

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

### Registration

There is no list to edit in `server.py`. `tools/__init__.py` imports every
`*_tools.py` module here, calls its `register_<module>()` function, and passes
the dependencies it names (`pokeapi`, `smogon`, `team_manager`, ...). A new
module is picked up automatically; then bump `FULL_TOOL_COUNT` and regenerate
the catalog with `python scripts/build_catalog.py`.

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

## Profiles

Every tool is registered on one server. What a client sees depends on the
profile:

- **core** (default, `/mcp`): the 34 tools in `CORE_TOOLS` in
  [`../profiles.py`](../profiles.py). They cover damage, survival and spreads,
  speed, team prep, usage, legality, the battle copilot, onboarding and export.
- **full** (`/mcp/full`, or `VGC_MCP_PROFILE=full`): all 206 tools.

The catalog marks core tools with ★. Add a new tool to `CORE_TOOLS` only if
most users need it.
