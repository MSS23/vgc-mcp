# VGC MCP Server

A Model Context Protocol (MCP) server for Pokemon VGC (Video Game Championships) team building and competitive analysis.

## Features

- **157+ tools** for competitive Pokemon team building
- Full Gen 9 damage formula with all modifiers (weather, terrain, items, abilities)
- Complete Tera mechanics including Stellar type and Tera Blast
- New Gen 9 abilities (Embody Aspect, Mind's Eye) and moves (Psyblade, Ivy Cudgel)
- Smogon usage statistics integration with auto-fetching spreads
- Speed tier analysis and optimization
- EV/IV optimization with bulk calculations
- Team import/export (Showdown paste format)
- Legality checking for VGC formats (Reg F/G/H)
- Coverage analysis and threat identification
- Salt Cure and other chip damage calculations
- MCP-UI support for interactive displays

## Quick Start

### For End Users (FREE Claude Desktop!)

**⚡ 5-Minute Setup - No Premium Required**

This MCP server works on **FREE Claude Desktop** using local setup!

#### Quick Links:
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Choose between local (free) or remote (premium) setup
- **[LOCAL_SETUP.md](LOCAL_SETUP.md)** - Detailed local installation guide

#### TL;DR for Local Setup:

1. Install Python 3.11+ from https://python.org
2. Run: `pip install -e .`
3. Add to Claude Desktop config (`%APPDATA%\Claude\claude_desktop_config.json` on Windows):
   ```json
   {
     "mcpServers": {
       "vgc": {
         "command": "python",
         "args": ["-m", "vgc_mcp"]
       }
     }
   }
   ```
4. Restart Claude Desktop
5. Say "What can you help me with?" - All 157 tools available!

**Windows users:** Just double-click `setup.bat` for automatic setup!

#### Verify It's Working:

After setup, in Claude Desktop:
1. Look for "vgc" MCP server indicator (should be green/connected)
2. Say: "What can you help me with?" - Should list VGC tools
3. Test: "Does Flutter Mane OHKO Incineroar?" - Should get damage calculations
4. Check speed: Local = instant, Remote = network delay

**How to tell if you're using local vs remote:**
- Local config has `"command": "python"`
- Remote config has `"url": "https://..."`
- See [SETUP_GUIDE.md](SETUP_GUIDE.md) for full verification steps

---

### For Developers

#### Installation

```bash
# Install in development mode
pip install -e .

# With remote server support
pip install -e ".[remote]"

# With development tools
pip install -e ".[dev]"
```

#### Running the Server

```bash
# Full server (157 tools) - for powerful models like Claude, GPT-4
vgc-mcp

# Lite server (49 tools) - for smaller models like Llama 3.3 70B
vgc-mcp-lite

# HTTP/SSE for remote access
vgc-mcp-http
vgc-mcp-lite-http
```

#### Claude Desktop Configuration

**Local Setup (FREE):**
```json
{
  "mcpServers": {
    "vgc": {
      "command": "python",
      "args": ["-m", "vgc_mcp"]
    }
  }
}
```

**Remote Setup (Premium):**
```json
{
  "mcpServers": {
    "vgc": {
      "url": "https://vgc-mcp.onrender.com/sse"
    }
  }
}
```

Config file locations:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`

#### Remote Server Deployment

For hosting your own remote server:
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
├── tests/                # Test suite (337 tests)
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

## Gen 9 Mechanics Support

### Tera Types
- Full type chart including Stellar type
- Tera Blast type/category changes when Terastallized
- Stellar type's 2x boost vs Terastallized Pokemon

### Abilities
- **Embody Aspect**: Ogerpon mask-specific stat boosts
- **Mind's Eye/Scrappy**: Normal/Fighting hit Ghost types
- **Protosynthesis/Quark Drive**: Paradox stat boosts

### Moves
- **Ivy Cudgel**: Form-dependent type (Hearthflame=Fire, Wellspring=Water, Cornerstone=Rock)
- **Psyblade**: 1.5x boost in Psychic Terrain
- **Collision Course/Electro Drift**: 1.33x boost when super effective
- **Salt Cure**: Chip damage (12.5%, doubled for Water/Steel)

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
