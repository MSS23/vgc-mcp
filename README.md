# VGC MCP Server

A Model Context Protocol (MCP) server for Pokemon VGC (Video Game Championships) team building and competitive analysis.

## Features

- **157+ tools** for competitive Pokemon team building
- Full Gen 9 damage formula with all modifiers (weather, terrain, items, abilities)
- Smogon usage statistics integration with auto-fetching spreads
- Speed tier analysis and optimization
- EV/IV optimization with bulk calculations
- Team import/export (Showdown paste format)
- Legality checking for VGC formats
- Coverage analysis and threat identification
- MCP-UI support for interactive displays

## Quick Start

### Installation

```bash
# Install in development mode
pip install -e .

# With remote server support
pip install -e ".[remote]"

# With development tools
pip install -e ".[dev]"
```

### Running the Server

```bash
# Full server (157 tools) - for powerful models like Claude, GPT-4
vgc-mcp

# Lite server (49 tools) - for smaller models like Llama 3.3 70B
vgc-mcp-lite

# HTTP/SSE for remote access
vgc-mcp-http
vgc-mcp-lite-http
```

### Claude Desktop Configuration

Add to your Claude Desktop config file:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "vgc": {
      "command": "C:\\Python313\\python.exe",
      "args": ["-m", "vgc_mcp"]
    }
  }
}
```

Or if vgc-mcp.exe is on your PATH:
```json
{
  "mcpServers": {
    "vgc": {
      "command": "vgc-mcp"
    }
  }
}
```

### Goose Configuration

Add to your Goose config file:
- **Windows**: `%APPDATA%\goose\config.yaml` or `~/.config/goose/config.yaml`
- **macOS/Linux**: `~/.config/goose/config.yaml`

```yaml
extensions:
  vgc-lite:
    name: VGC Team Builder Lite
    type: stdio
    cmd: C:\Python313\python.exe
    args:
      - "-m"
      - "vgc_mcp.server_lite"
```

Or using the entry point:
```yaml
extensions:
  vgc-lite:
    name: VGC Team Builder Lite
    type: stdio
    cmd: vgc-mcp-lite
```

### Remote (SSE)

For Claude.ai or remote access:
- Endpoint: `https://your-server.com/sse`
- Health check: `https://your-server.com/health`

```bash
# Start remote server
vgc-mcp-http  # Full version, port 8000
vgc-mcp-lite-http  # Lite version, port 8000
```

## Project Structure

```
vgc-mcp/
├── src/vgc_mcp/          # Main package
│   ├── api/              # External API clients (PokeAPI, Smogon)
│   ├── calc/             # Pure calculation functions
│   ├── models/           # Pydantic data models
│   ├── tools/            # MCP tool definitions (22 modules)
│   ├── rules/            # VGC format rules and legality
│   ├── team/             # Team management
│   ├── formats/          # Import/export formats
│   ├── ui/               # MCP-UI templates
│   ├── utils/            # Error handling, fuzzy matching
│   └── validation/       # Input validation
├── tests/                # Test suite (289 tests)
├── data/                 # Cache and static data
└── pyproject.toml        # Package configuration
```

## Server Variants

| Server | Tools | Best For |
|--------|-------|----------|
| `vgc-mcp` | 157 | Claude, GPT-4, powerful models |
| `vgc-mcp-lite` | 49 | Llama 3.3 70B, smaller models |

The lite version includes essential tools for:
- Team management
- Damage calculations (with auto Smogon spreads)
- Speed analysis
- Coverage analysis
- Import/export

## Key Tools

### Damage Calculations
- `calculate_damage_output` - Full damage calc with Smogon spread auto-fetch
- `find_ko_evs` - Find EVs needed to KO a target
- `find_bulk_evs` - Find EVs needed to survive an attack

### Team Building
- `add_to_team` / `remove_from_team` - Manage team roster
- `import_showdown_team` - Import from Showdown paste
- `analyze_team` - Full team analysis

### Speed Analysis
- `compare_speed` - Compare two Pokemon's speed
- `visualize_speed_tiers` - Visual speed tier chart
- `get_speed_probability` - Probability of outspeeding based on usage data

### Usage Data
- `get_usage_stats` - Smogon usage percentages
- `get_common_sets` - Popular builds for a Pokemon
- `suggest_teammates` - Teammate recommendations

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_damage.py -v

# Linting
ruff check src/
ruff format src/

# Type checking
mypy src/vgc_mcp
```

## License

MIT
