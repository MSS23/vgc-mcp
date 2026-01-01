# vgc_mcp - Main Package

The core VGC MCP server package. This folder contains the entry points and configuration.

## Files

| File | Purpose |
|------|---------|
| `server.py` | Full MCP server with 157 tools |
| `server_lite.py` | Lite MCP server with 49 essential tools |
| `config.py` | Settings (API URLs, timeouts, VGC defaults) |
| `__init__.py` | Package exports |
| `__main__.py` | `python -m vgc_mcp` entry point |

## Subpackages

| Folder | Purpose |
|--------|---------|
| `api/` | External API clients (PokeAPI, Smogon, PokePaste) |
| `calc/` | Pure calculation functions (damage, stats, speed) |
| `models/` | Pydantic data models (Pokemon, Move, Team) |
| `tools/` | MCP tool definitions (22 modules, 157 tools) |
| `rules/` | VGC format rules and legality checking |
| `team/` | Team management and analysis |
| `formats/` | Import/export (Showdown paste) |
| `ui/` | MCP-UI templates for interactive displays |
| `utils/` | Error handling, fuzzy matching |
| `validation/` | Input validation |

## Architecture

```
server.py
    │
    ├── Initializes shared state:
    │   ├── APICache (disk-based caching)
    │   ├── PokeAPIClient (Pokemon data)
    │   ├── SmogonStatsClient (usage stats)
    │   ├── TeamManager (current team)
    │   └── TeamAnalyzer (team analysis)
    │
    └── Registers tools from tools/*_tools.py
        └── Each tool module exports register_*_tools(mcp, ...)
```

## Key Design Patterns

### Tool Registration
Each tool module exports a `register_*_tools()` function:
```python
def register_damage_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: SmogonStatsClient):
    @mcp.tool()
    async def calculate_damage_output(...):
        ...
```

### Shared Dependencies
Tools receive dependencies via registration:
- `pokeapi` - For fetching Pokemon/move data
- `smogon` - For usage statistics
- `team_manager` - For current team state
- `analyzer` - For team analysis

### Error Handling
All tools use structured error responses from `utils/errors.py`:
```python
from ..utils.errors import pokemon_not_found_error, api_error
return pokemon_not_found_error(name, suggestions)
```
