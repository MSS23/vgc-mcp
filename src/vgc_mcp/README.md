# vgc_mcp - Plain MCP Server

The client-agnostic MCP server package. Calculation, data, model, and state
logic lives in `vgc_mcp_core`; this package contains the transport entrypoints
and thin MCP tool registration wrappers.

## Files

| File | Purpose |
|------|---------|
| `server.py` | Stdio and HTTP entrypoints for the 208-tool server |
| `__init__.py` | Package exports |
| `__main__.py` | `python -m vgc_mcp` entry point |

## Subpackages

| Folder | Purpose |
|--------|---------|
| `tools/` | 51 auto-discovered MCP registration modules (208 tools) |

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

Discovery is fail-fast: a missing registration function, unresolved required
dependency, empty module, import failure, or duplicate tool name prevents
startup rather than exposing a partially healthy service.

MCP Apps/MCP-UI views belong in an optional sibling that imports
`vgc_mcp_core`; see `docs/mcp-ui-decision.md` at the repository root.

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
