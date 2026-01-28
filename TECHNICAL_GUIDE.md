# VGC MCP Server - Technical Architecture Guide

A beginner-friendly deep-dive into the Model Context Protocol and how this VGC team builder works under the hood.

## Table of Contents

1. [What is MCP?](#what-is-mcp-model-context-protocol)
2. [Architecture Overview](#architecture-overview)
3. [How Tool Calls Work](#how-tool-calls-work-step-by-step)
4. [Project Architecture Deep-Dive](#project-architecture-deep-dive)
5. [Tool Registration Pattern](#tool-registration-pattern)
6. [Caching Strategy](#caching-strategy)
7. [Local vs Remote Deployment](#local-vs-remote-deployment)
8. [Extension Points](#extension-points-how-to-extend-this-project)
9. [Protocol Details (Advanced)](#protocol-details-advanced)

---

## What is MCP (Model Context Protocol)?

### The Simple Explanation

Think of MCP as a **phone book of tools** that AI assistants like Claude can call.

Just like you might call a plumber when your sink breaks or a electrician when the lights go out, Claude can "call" specialized tools when it needs to:
- Calculate Pokemon damage
- Find optimal EV spreads
- Analyze team matchups
- Look up speed tiers

### The Problem MCP Solves

Large Language Models (LLMs) like Claude are great at understanding language and reasoning, but they have limitations:

- **No real-time data**: They can't fetch current Pokemon usage stats
- **No calculations**: They can't reliably calculate damage formulas with 20+ modifiers
- **No external state**: They can't remember your team across conversations
- **Knowledge cutoff**: They don't know about new Pokemon or moves added after training

**MCP solves this** by letting AI assistants call external tools that CAN do these things.

### How MCP Bridges the Gap

```
User Question:
"Does my Flutter Mane OHKO Incineroar?"

Without MCP:
Claude: "I don't have access to specific damage calculations or current VGC spreads."

With MCP:
Claude calls tools:
  1. get_pokemon_stats("flutter-mane") → Stats, types, abilities
  2. get_common_sets("incineroar") → Smogon spread (EVs, nature, item)
  3. calculate_damage_output(...) → 85-100 damage (96.5%-113.6%)

Claude: "Your Flutter Mane with Moonblast deals 96.5-113.6% to a standard
Adamant 252 HP Incineroar, giving you a 75% chance to OHKO."
```

MCP is the **protocol** (set of rules) that makes this communication possible.

---

## Architecture Overview

### The Big Picture

```
┌─────────────────────────────────────────────────────────────┐
│                         User                                │
│                 "Does Flutter Mane OHKO                     │
│                      Incineroar?"                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Claude Desktop                             │
│            (MCP Client - User Interface)                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Claude AI reads question and decides:              │   │
│  │  "I need to call calculate_damage_output tool"      │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │ JSON-RPC message
                       │ over stdio or HTTP
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              VGC MCP Server (This Project!)                 │
│                 Python Process                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. Receives tool call: calculate_damage_output(      │  │
│  │      attacker_name="flutter-mane",                   │  │
│  │      defender_name="incineroar",                     │  │
│  │      move_name="moonblast"                           │  │
│  │    )                                                  │  │
│  │                                                       │  │
│  │ 2. Validates parameters                              │  │
│  │                                                       │  │
│  │ 3. Fetches data (cached or from APIs)                │  │
│  │                                                       │  │
│  │ 4. Runs calculations                                 │  │
│  │                                                       │  │
│  │ 5. Returns JSON response                             │  │
│  └──────────────────────────────────────────────────────┘  │
│                       ▲                                     │
│                       │                                     │
│       ┌───────────────┼───────────────┐                    │
│       │               │               │                    │
│       ▼               ▼               ▼                    │
│  ┌────────┐    ┌──────────┐    ┌──────────┐              │
│  │PokeAPI │    │  Smogon  │    │  Local   │              │
│  │(stats) │    │ (usage)  │    │  Calcs   │              │
│  └────────┘    └──────────┘    └──────────┘              │
│       ▲               ▲               ▲                    │
│       └───────────────┴───────────────┘                    │
│              DiskCache (7 days)                            │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼ JSON response
┌─────────────────────────────────────────────────────────────┐
│                  Claude Desktop                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Receives: {                                        │   │
│  │    "damage_min": 85,                                │   │
│  │    "damage_max": 100,                               │   │
│  │    "ohko_chance": 75.0,                             │   │
│  │    ...                                              │   │
│  │  }                                                  │   │
│  │                                                      │   │
│  │  Formats natural language response for user        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                         User                                │
│  "Your Flutter Mane with Moonblast deals 96.5-113.6%       │
│   to standard Incineroar, giving you a 75% OHKO chance."   │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

1. **MCP Client** (Claude Desktop)
   - User interface
   - Runs Claude AI model
   - Sends tool requests
   - Formats responses for users

2. **MCP Server** (This project - Python)
   - Receives tool calls
   - Validates inputs
   - Executes tools
   - Returns structured data

3. **Data Sources**
   - **PokeAPI**: Pokemon base stats, types, moves, abilities
   - **Smogon Stats**: Usage percentages, common EV spreads, item/move frequencies
   - **Local Calculations**: Gen 9 damage formula, speed calculations, team analysis

4. **Cache Layer**
   - **DiskCache**: Persistent storage for API responses (7-day TTL)
   - **In-memory**: Fast access for frequently used data

---

## How Tool Calls Work (Step-by-Step)

Let's follow a real example from start to finish.

### User's Question:
> "Does my Flutter Mane OHKO Incineroar with Moonblast?"

### Step 1: Claude Analyzes the Question

Claude (the AI model) reads the question and thinks:
- User wants to know if Flutter Mane can one-hit KO Incineroar
- This requires a damage calculation
- I need to call the `calculate_damage_output` tool
- Required parameters: attacker_name, defender_name, move_name

### Step 2: MCP Client Sends Tool Call

Claude Desktop (MCP client) sends a JSON-RPC message:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "calculate_damage_output",
    "arguments": {
      "attacker_name": "flutter-mane",
      "defender_name": "incineroar",
      "move_name": "moonblast",
      "attacker_nature": "timid",
      "attacker_spa_evs": 252
    }
  }
}
```

This message travels over **stdio** (standard input/output) if running locally, or **HTTP** if running remotely.

### Step 3: VGC MCP Server Receives Request

The server (Python process) receives the message and:

1. **Validates the tool exists**: "Is `calculate_damage_output` a registered tool?" ✓
2. **Validates parameters**:
   - "flutter-mane" is a valid Pokemon name ✓
   - "incineroar" is a valid Pokemon name ✓
   - "moonblast" is a valid move name ✓
   - "timid" is a valid nature ✓
   - 252 is a valid EV value ✓

### Step 4: Server Fetches Data

The server needs several pieces of data to calculate damage. It checks the cache first, then fetches from APIs if needed:

```python
# Fetch Flutter Mane stats (cached for 7 days if previously fetched)
flutter_mane_data = pokeapi.get_pokemon("flutter-mane")
# Returns: {
#   base_stats: {hp: 55, spa: 135, spd: 135, spe: 135, ...},
#   types: ["ghost", "fairy"],
#   abilities: ["protosynthesis"]
# }

# Fetch Moonblast move data
moonblast_data = pokeapi.get_move("moonblast")
# Returns: {
#   power: 95,
#   type: "fairy",
#   category: "special",
#   ...
# }

# Fetch Incineroar common set from Smogon (cached)
incineroar_set = smogon.get_common_set("incineroar", format="gen9vgc2024regh")
# Returns: {
#   nature: "adamant",
#   evs: {hp: 252, atk: 116, def: 4, spd: 60, spe: 76},
#   item: "assault-vest",
#   ability: "intimidate"
# }
```

### Step 5: Server Runs Calculations

Now the server has everything it needs. It calls the damage calculation engine:

```python
from vgc_mcp_core.calc.damage import calculate_damage

# Build Pokemon models
attacker = PokemonBuild(
    name="flutter-mane",
    base_stats=BaseStats(hp=55, spa=135, ...),
    nature=Nature.TIMID,
    evs=EVSpread(spa=252, spe=252, hp=4),
    types=["ghost", "fairy"],
    ability="protosynthesis"
)

defender = PokemonBuild(
    name="incineroar",
    base_stats=BaseStats(hp=95, spd=90, ...),
    nature=Nature.ADAMANT,
    evs=EVSpread(hp=252, atk=116, def=4, spd=60, spe=76),
    types=["fire", "dark"],
    item="assault-vest"
)

# Calculate damage
result = calculate_damage(
    attacker=attacker,
    defender=defender,
    move=moonblast_data,
    context={
        "format": "doubles",  # VGC is doubles format
        "weather": None,
        "terrain": None,
        "screens": {}
    }
)

# Result: {
#   damage_min: 85,
#   damage_max: 100,
#   damage_percent_min: 96.5,
#   damage_percent_max: 113.6,
#   ohko_chance: 75.0,  # 12 out of 16 damage rolls OHKO
#   ko_type: "75% OHKO"
# }
```

### Step 6: Server Returns Response

The server sends back a JSON-RPC response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "attacker_name": "Flutter Mane",
    "defender_name": "Incineroar",
    "move_name": "Moonblast",
    "damage_min": 85,
    "damage_max": 100,
    "damage_percent_min": 96.5,
    "damage_percent_max": 113.6,
    "ohko_chance": 75.0,
    "ko_type": "75% OHKO",
    "attacker_spread": "Timid 4 HP / 0 Atk / 0 Def / 252 SpA / 0 SpD / 252 Spe",
    "defender_spread": "Adamant 252 HP / 116 Atk / 4 Def / 0 SpA / 60 SpD / 76 Spe",
    "defender_item": "Assault Vest",
    "notes": [
      "STAB (Same Type Attack Bonus) applied: 1.5x",
      "Super effective: 1.0x (neutral damage)",
      "Assault Vest boosts Special Defense by 1.5x"
    ]
  }
}
```

### Step 7: Claude Formats the Response

Claude Desktop receives the JSON data and Claude AI formats it naturally:

> "Your **Timid 252 SpA Flutter Mane** with **Moonblast** deals **96.5-113.6%** to a standard **Adamant 252 HP / 60 SpD Incineroar @ Assault Vest**.
>
> **Result**: **75% chance to OHKO** (12 out of 16 damage rolls will KO)
>
> Notes:
> - STAB boost applied (Moonblast is Fairy-type, Flutter Mane is Fairy-type)
> - Assault Vest boosts Incineroar's Special Defense by 1.5x
> - Neutral type matchup (Fairy vs Fire/Dark)"

### Step 8: User Sees the Answer

The user gets a clear, natural language response with all the details they need!

---

## Project Architecture Deep-Dive

### Directory Structure

```
vgc-mcp/
├── src/
│   ├── vgc_mcp/                    # Main MCP server package
│   │   ├── server.py               # Entry point, registers all 157 tools
│   │   ├── tools/                  # Tool definitions (47 modules)
│   │   │   ├── damage_tools.py     # Damage calculations (15 tools)
│   │   │   ├── speed_tools.py      # Speed analysis (12 tools)
│   │   │   ├── spread_tools.py     # EV optimization (10 tools)
│   │   │   ├── team_tools.py       # Team building (14 tools)
│   │   │   ├── usage_tools.py      # Smogon stats (8 tools)
│   │   │   └── ...                 # 42 more tool modules
│   │   └── __main__.py             # CLI entry point
│   │
│   ├── vgc_mcp_core/               # Shared calculation engine
│   │   ├── api/                    # External API clients
│   │   │   ├── pokeapi.py          # Pokemon stats, moves, abilities
│   │   │   ├── smogon.py           # Usage data, common sets
│   │   │   └── cache.py            # DiskCache wrapper
│   │   │
│   │   ├── calc/                   # Pure calculation functions
│   │   │   ├── damage.py           # Gen 9 damage formula
│   │   │   ├── stats.py            # Stat calculations (EVs, IVs, nature)
│   │   │   ├── speed.py            # Speed comparisons, tiers
│   │   │   ├── modifiers.py        # Type chart, weather, terrain, items
│   │   │   ├── abilities.py        # Ability effects on damage/speed
│   │   │   └── ...                 # 13 calculation modules
│   │   │
│   │   ├── models/                 # Pydantic data models
│   │   │   ├── pokemon.py          # PokemonBuild, Nature, EVSpread
│   │   │   ├── move.py             # Move with multi-hit support
│   │   │   ├── team.py             # Team with legality validation
│   │   │   └── battle_context.py   # Weather, terrain, screens
│   │   │
│   │   ├── rules/                  # VGC format rules
│   │   │   ├── legality.py         # Species clause, item clause
│   │   │   ├── regulations.py      # Reg F/G/H restricted lists
│   │   │   └── learnsets.py        # Move legality checking
│   │   │
│   │   ├── team/                   # Team management
│   │   │   ├── manager.py          # In-memory team storage
│   │   │   ├── builder.py          # Team building suggestions
│   │   │   └── analysis.py         # Team synergy, coverage
│   │   │
│   │   ├── formats/                # Import/export
│   │   │   ├── showdown.py         # Showdown paste parsing/generation
│   │   │   └── json.py             # JSON team format
│   │   │
│   │   ├── utils/                  # Utilities
│   │   │   ├── errors.py           # Structured error messages
│   │   │   ├── fuzzy.py            # Fuzzy name matching
│   │   │   └── validation.py       # Input validation
│   │   │
│   │   └── data/                   # Static data
│   │       ├── glossary.json       # VGC term definitions
│   │       └── presets.json        # Common team archetypes
│   │
│   ├── vgc_mcp_lite/               # Lite version (49 tools)
│   │   ├── tools/                  # Essential tools only
│   │   ├── ui/                     # MCP-UI components
│   │   └── server.py               # Lite server entry
│   │
│   └── vgc_mcp_micro/              # Micro version (minimal)
│
├── tests/                          # Test suite (337+ tests)
│   ├── conftest.py                 # Shared fixtures
│   ├── test_damage.py              # Damage calculation tests
│   ├── test_speed.py               # Speed analysis tests
│   └── ...                         # 30+ test modules
│
├── data/
│   └── cache/                      # DiskCache storage (gitignored)
│
└── pyproject.toml                  # Package configuration
```

### Data Flow

Let's trace how data flows through the system for a damage calculation:

```
1. User Question → Claude Desktop

2. Claude Desktop → MCP Client
   - Identifies tool needed: calculate_damage_output
   - Prepares parameters from user's question

3. MCP Client → VGC MCP Server (via stdio or HTTP)
   - JSON-RPC message with tool call

4. Server Entry Point (server.py)
   - Receives message
   - Routes to registered tool

5. Tool Module (tools/damage_tools.py)
   - Validates parameters using Pydantic
   - Calls calculation functions

6. API Clients (api/pokeapi.py, api/smogon.py)
   - Fetches Pokemon stats (cached if available)
   - Fetches common sets from Smogon

7. Data Models (models/pokemon.py)
   - Constructs PokemonBuild objects
   - Validates EVs, IVs, nature

8. Calculation Engine (calc/damage.py)
   - Applies Gen 9 damage formula
   - Considers all modifiers (STAB, type, weather, items, abilities)

9. Back to Tool Module
   - Formats result
   - Adds context (attacker/defender spreads, notes)

10. Server Response → MCP Client
    - JSON-RPC response with calculation results

11. Claude Desktop → User
    - Natural language formatting
    - Display to user
```

---

## Tool Registration Pattern

### How Tools Are Defined

Tools are Python functions decorated with `@mcp.tool()`:

```python
# tools/damage_tools.py
from mcp import McpServer

def register_damage_tools(mcp: McpServer, pokeapi, team_manager):
    """Register all damage calculation tools."""

    @mcp.tool()
    async def calculate_damage_output(
        attacker_name: str,
        defender_name: str,
        move_name: str,
        attacker_nature: str = "serious",
        attacker_spa_evs: int = 252,
        defender_nature: str = "serious",
        defender_spd_evs: int = 0
    ) -> dict:
        """Calculate damage output between two Pokemon.

        Args:
            attacker_name: Name of the attacking Pokemon
            defender_name: Name of the defending Pokemon
            move_name: Name of the move being used
            attacker_nature: Attacker's nature (default: serious)
            attacker_spa_evs: Attacker's Special Attack EVs (default: 252)
            defender_nature: Defender's nature (default: serious)
            defender_spd_evs: Defender's Special Defense EVs (default: 0)

        Returns:
            Dictionary with damage range, KO chance, and spread info
        """
        # Implementation...
        return {
            "damage_min": 85,
            "damage_max": 100,
            "ohko_chance": 75.0,
            ...
        }
```

### Parameter Validation with Pydantic

MCP automatically validates parameters using type hints and Pydantic:

```python
# If user provides invalid data:
calculate_damage_output(
    attacker_name="flutter-mane",
    attacker_spa_evs="lots"  # ← Invalid! Should be int
)

# MCP responds with validation error:
{
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "attacker_spa_evs": ["Input should be a valid integer"]
    }
  }
}
```

### Tool Schema

MCP automatically generates a schema for each tool:

```json
{
  "name": "calculate_damage_output",
  "description": "Calculate damage output between two Pokemon.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "attacker_name": {"type": "string"},
      "defender_name": {"type": "string"},
      "move_name": {"type": "string"},
      "attacker_nature": {"type": "string", "default": "serious"},
      "attacker_spa_evs": {"type": "integer", "default": 252}
    },
    "required": ["attacker_name", "defender_name", "move_name"]
  }
}
```

Claude uses this schema to:
1. Know what tools are available
2. Understand what each tool does
3. Know what parameters are required
4. Know the types of parameters

---

## Caching Strategy

### Why Caching Matters

Without caching, every damage calculation would require:
- 1-2 PokeAPI requests (attacker + defender stats)
- 1-2 Smogon Stats requests (common sets)
- **Total**: 2-4 network requests per calculation

With caching:
- First request: Fetches from API and caches (slow)
- Subsequent requests: Reads from disk cache (fast)
- **Speedup**: 10-100x faster for cached data

### DiskCache for API Responses

We use DiskCache for persistent caching:

```python
# api/cache.py
from diskcache import Cache

cache = Cache("data/cache", size_limit=100_000_000)  # 100 MB limit

def cached_get(key: str, fetch_func, ttl: int = 604800):
    """Get from cache or fetch and cache.

    Args:
        key: Cache key
        fetch_func: Function to call if not cached
        ttl: Time to live in seconds (default: 7 days)
    """
    if key in cache:
        return cache[key]

    value = fetch_func()
    cache.set(key, value, expire=ttl)
    return value
```

**Usage:**

```python
# api/pokeapi.py
def get_pokemon(name: str):
    key = f"pokemon:{name}"
    return cached_get(
        key,
        lambda: requests.get(f"https://pokeapi.co/api/v2/pokemon/{name}").json(),
        ttl=604800  # 7 days
    )
```

### Cache Performance

| Operation | Without Cache | With Cache | Speedup |
|-----------|---------------|------------|---------|
| Get Pokemon stats | 200-500ms | 1-5ms | 40-500x |
| Get Smogon set | 300-800ms | 1-5ms | 60-800x |
| Damage calculation | 500-1300ms | 2-10ms | 50-650x |

### In-Memory Caching for Calculations

Frequently used calculations are cached in memory:

```python
# calc/damage.py
from functools import lru_cache

@lru_cache(maxsize=1000)
def calculate_stat(base: int, iv: int, ev: int, nature: float, level: int = 50):
    """Calculate final stat value (cached)."""
    return int(((2 * base + iv + ev // 4) * level // 100 + 5) * nature)
```

This prevents recalculating the same stat values repeatedly.

---

## Local vs Remote Deployment

### Local Deployment (stdio)

**How it works:**
1. Claude Desktop spawns a Python process: `python -m vgc_mcp`
2. Server listens on **stdin** (standard input) and writes to **stdout**
3. Communication uses **JSON-RPC over stdio**

**Advantages:**
- ✅ Fast (no network latency)
- ✅ Private (data doesn't leave your machine)
- ✅ Offline (works without internet, except API calls)
- ✅ FREE (works on free Claude Desktop)

**Disadvantages:**
- ❌ Requires Python installation
- ❌ Each user must set up locally
- ❌ Manual updates (git pull)

**Configuration:**

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

### Remote Deployment (HTTP/SSE)

**How it works:**
1. VGC MCP server runs on a cloud platform (Fly.io, Render, etc.)
2. Server exposes HTTP endpoint: `https://vgc-mcp.example.com/sse`
3. Claude Desktop connects via **Server-Sent Events (SSE)**
4. Communication uses **JSON-RPC over HTTP**

**Advantages:**
- ✅ No local installation needed
- ✅ Automatic updates
- ✅ Centralized management
- ✅ Shared cache across users

**Disadvantages:**
- ❌ Network latency (100-500ms per request)
- ❌ Requires internet connection
- ❌ Server costs (hosting, bandwidth)
- ❌ Requires Claude Desktop Premium

**Configuration:**

```json
{
  "mcpServers": {
    "vgc": {
      "url": "https://vgc-mcp.example.com/sse"
    }
  }
}
```

### Performance Comparison

| Metric | Local (stdio) | Remote (HTTP) |
|--------|---------------|---------------|
| Tool call latency | 1-10ms | 100-500ms |
| Cached request | <5ms | 150-300ms |
| Uncached request | 500-1000ms | 600-1500ms |
| Offline support | ✅ (except APIs) | ❌ |
| Setup complexity | Medium | Low |

---

## Extension Points (How to Extend This Project)

### 1. Adding a New Tool

**Example: Add a "find_best_item" tool**

**Step 1: Create tool function**

```python
# tools/item_tools.py
def register_item_tools(mcp, pokeapi, team_manager):
    @mcp.tool()
    async def find_best_item(
        pokemon_name: str,
        role: str = "offense"
    ) -> dict:
        """Find the best item for a Pokemon based on its role.

        Args:
            pokemon_name: Pokemon to find item for
            role: Role (offense, defense, support, etc.)

        Returns:
            Recommended item with explanation
        """
        # Fetch Pokemon data
        pokemon_data = await pokeapi.get_pokemon(pokemon_name)

        # Logic to determine best item
        if role == "offense":
            if pokemon_data["stats"]["speed"] > 100:
                return {"item": "choice-scarf", "reason": "Maximize speed"}
            else:
                return {"item": "life-orb", "reason": "Boost damage"}

        # ... more logic
```

**Step 2: Register in server**

```python
# server.py
from vgc_mcp.tools.item_tools import register_item_tools

def main():
    mcp = McpServer("vgc-mcp")

    # ... existing registrations
    register_item_tools(mcp, pokeapi, team_manager)

    mcp.run()
```

**Step 3: Test**

```python
# tests/test_item_tools.py
async def test_find_best_item_offense():
    result = await find_best_item("flutter-mane", role="offense")
    assert result["item"] in ["choice-scarf", "choice-specs", "life-orb"]
```

### 2. Adding a New Calculation

**Example: Add "burn damage reduction" to damage formula**

```python
# calc/damage.py
def calculate_damage(..., is_burned: bool = False):
    # ... existing damage calculation

    # Apply burn reduction to physical moves
    if is_burned and move.category == "physical":
        damage = int(damage * 0.5)

    return damage
```

### 3. Adding a New Data Source

**Example: Add support for Pikalytics data**

**Step 1: Create API client**

```python
# api/pikalytics.py
import httpx
from .cache import cached_get

class PikalyticsClient:
    BASE_URL = "https://pikalytics.com/api"

    async def get_usage(self, format: str = "vgc2024"):
        """Fetch usage data from Pikalytics."""
        key = f"pikalytics:usage:{format}"
        return cached_get(
            key,
            lambda: httpx.get(f"{self.BASE_URL}/{format}/usage").json(),
            ttl=86400  # 1 day
        )
```

**Step 2: Use in tools**

```python
# tools/usage_tools.py
pikalytics = PikalyticsClient()

@mcp.tool()
async def get_pikalytics_usage(format: str = "vgc2024"):
    """Get Pokemon usage data from Pikalytics."""
    return await pikalytics.get_usage(format)
```

### 4. Testing New Tools

```python
# tests/test_new_tool.py
import pytest
from vgc_mcp.tools.new_tools import new_tool_function

@pytest.mark.asyncio
async def test_new_tool_basic():
    result = await new_tool_function(param1="value1")
    assert result["key"] == "expected_value"

@pytest.mark.asyncio
async def test_new_tool_error_handling():
    with pytest.raises(ValueError):
        await new_tool_function(param1="invalid")
```

---

## Protocol Details (Advanced)

### MCP Message Format

MCP uses **JSON-RPC 2.0** for all messages.

**Tool Call Request:**

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "method": "tools/call",
  "params": {
    "name": "calculate_damage_output",
    "arguments": {
      "attacker_name": "flutter-mane",
      "defender_name": "incineroar",
      "move_name": "moonblast"
    }
  }
}
```

**Success Response:**

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "result": {
    "damage_min": 85,
    "damage_max": 100,
    "ohko_chance": 75.0
  }
}
```

**Error Response:**

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "attacker_name": "Pokemon 'fluttermane' not found. Did you mean: flutter-mane?"
    }
  }
}
```

### Tool Discovery

Clients can discover available tools:

```json
Request:
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}

Response:
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "calculate_damage_output",
        "description": "Calculate damage output between two Pokemon",
        "inputSchema": { ... }
      },
      {
        "name": "find_survival_evs",
        "description": "Find minimum EVs to survive an attack",
        "inputSchema": { ... }
      },
      // ... 155 more tools
    ]
  }
}
```

### Debugging Tool Calls

**Enable logging:**

```python
# server.py
import logging

logging.basicConfig(level=logging.DEBUG)

# Now all MCP messages are logged
```

**Example log output:**

```
DEBUG:mcp: → Received: {"jsonrpc": "2.0", "id": 1, "method": "tools/call", ...}
DEBUG:mcp: Calling tool: calculate_damage_output
DEBUG:mcp: ← Sending: {"jsonrpc": "2.0", "id": 1, "result": {...}}
```

---

## Summary

**MCP (Model Context Protocol)** enables AI assistants to call external tools. The VGC MCP Server provides 157+ tools for competitive Pokemon team building.

**Key Concepts:**
- **Client** (Claude Desktop) sends tool requests
- **Server** (this project) executes tools and returns data
- **Protocol** (JSON-RPC over stdio/HTTP) handles communication
- **Caching** (DiskCache) speeds up repeated requests
- **Tools** (Python functions) perform calculations and fetch data

**Data Flow:**
1. User asks question
2. Claude identifies needed tool
3. MCP client sends tool call
4. Server validates and executes
5. Server returns structured data
6. Claude formats natural response
7. User sees answer

**Extension:**
- Add tools by decorating functions with `@mcp.tool()`
- Add calculations in `calc/` modules
- Add data sources in `api/` modules
- Test everything with pytest

**Next Steps:**
- Read [DEVELOPMENT.md](DEVELOPMENT.md) to start contributing
- Read [API_REFERENCE.md](API_REFERENCE.md) for complete tool catalog
- Read [DEPLOYMENT.md](DEPLOYMENT.md) to self-host

---

## Additional Resources

- **MCP Specification**: https://spec.modelcontextprotocol.io/
- **Python MCP SDK**: https://github.com/modelcontextprotocol/python-sdk
- **Pokemon Damage Calculator**: https://calc.pokemonshowdown.com/
- **Smogon VGC Forum**: https://www.smogon.com/forums/forums/vgc/

---

**Questions?** Open an issue on GitHub or see [FAQ.md](FAQ.md)!
