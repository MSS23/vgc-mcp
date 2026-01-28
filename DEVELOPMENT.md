# Development Guide

Guide for contributors and maintainers working on the VGC MCP Server codebase.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Running Tests](#running-tests)
- [Code Quality](#code-quality)
- [Debugging](#debugging)
- [Adding New Tools](#adding-new-tools)
- [Common Development Tasks](#common-development-tasks)
- [Release Process](#release-process)

---

## Development Setup

### Prerequisites

- **Python 3.11+** - Download from https://python.org
- **Git** - For version control
- **Claude Desktop** - For testing (optional but recommended)

### Initial Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/MSS23/vgc-mcp.git
   cd vgc-mcp
   ```

2. **Create virtual environment (recommended):**

   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Mac/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install in development mode:**

   ```bash
   pip install -e ".[dev]"
   ```

   This installs:
   - Core dependencies (mcp, httpx, pydantic, diskcache)
   - Development tools (pytest, ruff, mypy, coverage)

4. **Verify installation:**

   ```bash
   # Run tests
   python -m pytest tests/ -v

   # Run server
   python -m vgc_mcp
   # Should start without errors, press Ctrl+C to stop
   ```

### IDE Setup

**Recommended**: Visual Studio Code with Python extension

**.vscode/settings.json:**

```json
{
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll": true,
      "source.organizeImports": true
    }
  },
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false
}
```

---

## Project Structure

```
vgc-mcp/
├── src/                              # Source code
│   ├── vgc_mcp/                      # Main server package
│   │   ├── server.py                 # Server entry point
│   │   │   - Registers all tools
│   │   │   - Initializes API clients
│   │   │   - Runs MCP server
│   │   │
│   │   ├── tools/                    # MCP tool definitions (47 files)
│   │   │   ├── damage_tools.py       # Damage calculations
│   │   │   ├── speed_tools.py        # Speed analysis
│   │   │   ├── spread_tools.py       # EV optimization
│   │   │   ├── team_tools.py         # Team building
│   │   │   ├── usage_tools.py        # Smogon stats
│   │   │   └── ...                   # 42 more tool modules
│   │   │
│   │   │   Pattern: Each file exports register_*_tools(mcp, ...)
│   │   │   Tools are async functions decorated with @mcp.tool()
│   │   │
│   │   ├── config.py                 # Configuration (API URLs, VGC defaults)
│   │   └── __main__.py               # CLI entry point
│   │
│   └── vgc_mcp_core/                 # Shared calculation engine
│       ├── api/                      # External API clients
│       │   ├── pokeapi.py            # PokeAPI client
│       │   ├── smogon.py             # Smogon Stats client
│       │   └── cache.py              # DiskCache wrapper
│       │
│       ├── calc/                     # Pure calculation functions
│       │   ├── damage.py             # Gen 9 damage formula
│       │   ├── stats.py              # Stat calculations
│       │   ├── speed.py              # Speed comparisons
│       │   ├── modifiers.py          # Type chart, weather, items
│       │   ├── abilities.py          # Ability effects
│       │   └── ...                   # 13 calculation modules
│       │
│       ├── models/                   # Pydantic data models
│       │   ├── pokemon.py            # PokemonBuild, Nature, EVSpread
│       │   ├── move.py               # Move model
│       │   ├── team.py               # Team model
│       │   └── battle_context.py     # Weather, terrain, screens
│       │
│       ├── rules/                    # VGC format rules
│       │   ├── legality.py           # Legality checking
│       │   ├── regulations.py        # Reg F/G/H definitions
│       │   └── learnsets.py          # Move legality
│       │
│       ├── team/                     # Team management
│       │   ├── manager.py            # In-memory team storage
│       │   ├── builder.py            # Team suggestions
│       │   └── analysis.py           # Team analysis
│       │
│       ├── formats/                  # Import/export
│       │   ├── showdown.py           # Showdown paste parsing
│       │   └── json.py               # JSON format
│       │
│       ├── utils/                    # Utilities
│       │   ├── errors.py             # Error messages
│       │   ├── fuzzy.py              # Fuzzy matching
│       │   └── validation.py         # Input validation
│       │
│       └── data/                     # Static data
│           ├── glossary.json         # VGC terms
│           └── presets.json          # Team archetypes
│
├── tests/                            # Test suite (337+ tests)
│   ├── conftest.py                   # Pytest fixtures
│   ├── test_damage.py                # Damage tests
│   ├── test_speed.py                 # Speed tests
│   ├── test_spread_tools.py          # Spread optimization tests
│   └── ...                           # 30+ test modules
│
├── data/                             # Runtime data
│   └── cache/                        # DiskCache storage (gitignored)
│
├── docs/                             # Documentation
│   ├── README.md                     # Main documentation
│   ├── TECHNICAL_GUIDE.md            # MCP architecture
│   ├── DEVELOPMENT.md                # This file
│   └── ...
│
└── pyproject.toml                    # Package configuration
```

### Naming Conventions

- **Modules**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: `_leading_underscore`

### Where to Put New Code

| Type of Code | Location |
|--------------|----------|
| New MCP tool | `src/vgc_mcp/tools/category_tools.py` |
| Calculation logic | `src/vgc_mcp_core/calc/` |
| Data model | `src/vgc_mcp_core/models/` |
| API client | `src/vgc_mcp_core/api/` |
| Utility function | `src/vgc_mcp_core/utils/` |
| Test | `tests/test_feature.py` |

---

## Running Tests

### Run All Tests

```bash
python -m pytest tests/ -v
```

### Run Specific Test File

```bash
python -m pytest tests/test_damage.py -v
```

### Run Specific Test Function

```bash
python -m pytest tests/test_damage.py::TestDamageCalculation::test_stab_boost -v
```

### Run Tests Matching Pattern

```bash
# Run all tests with "speed" in name
python -m pytest tests/ -k "speed" -v

# Run all tests in speed_tools
python -m pytest tests/test_speed_tools.py -v
```

### Run with Coverage

```bash
# Terminal output
python -m pytest tests/ --cov=vgc_mcp --cov=vgc_mcp_core

# HTML report
python -m pytest tests/ --cov=vgc_mcp --cov-report=html
open htmlcov/index.html  # View in browser
```

### Run Tests in Parallel (faster)

```bash
pip install pytest-xdist
python -m pytest tests/ -n auto  # Auto-detect CPU count
```

### Writing New Tests

**Test Structure:**

```python
# tests/test_new_feature.py
import pytest
from vgc_mcp_core.calc.new_feature import new_calculation

class TestNewFeature:
    """Test suite for new feature."""

    def test_basic_case(self):
        """Test basic functionality."""
        result = new_calculation(param1=10, param2=20)
        assert result == 30

    def test_edge_case_zero(self):
        """Test edge case with zero values."""
        result = new_calculation(param1=0, param2=0)
        assert result == 0

    def test_invalid_input(self):
        """Test error handling for invalid input."""
        with pytest.raises(ValueError, match="param1 must be positive"):
            new_calculation(param1=-5, param2=10)

    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test async function."""
        result = await async_function()
        assert result is not None
```

**Using Fixtures (from conftest.py):**

```python
def test_with_team_manager(team_manager):
    """Test using team_manager fixture."""
    team_manager.add_pokemon("flutter-mane", {...})
    assert team_manager.get_team_size() == 1
```

**Parametrized Tests:**

```python
@pytest.mark.parametrize("pokemon,expected_type", [
    ("flutter-mane", ["ghost", "fairy"]),
    ("incineroar", ["fire", "dark"]),
    ("landorus", ["ground", "flying"])
])
def test_pokemon_types(pokemon, expected_type):
    result = get_pokemon_types(pokemon)
    assert result == expected_type
```

---

## Code Quality

### Formatting with Ruff

```bash
# Format all code
ruff format src/

# Check what would be formatted (dry run)
ruff format --check src/
```

### Linting with Ruff

```bash
# Check for issues
ruff check src/

# Fix auto-fixable issues
ruff check --fix src/

# Show errors with context
ruff check --show-source src/
```

### Type Checking with MyPy

```bash
# Check types
mypy src/vgc_mcp

# Strict mode
mypy --strict src/vgc_mcp
```

### Pre-Commit Checks

Run before committing:

```bash
# Format
ruff format src/

# Lint
ruff check --fix src/

# Type check
mypy src/vgc_mcp

# Test
python -m pytest tests/
```

**Automate with pre-commit hook (optional):**

```bash
pip install pre-commit
pre-commit install

# Now runs automatically on git commit
```

**.pre-commit-config.yaml:**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

---

## Debugging

### Debugging Tool Calls Locally

1. **Enable debug logging:**

   ```python
   # server.py (temporary for debugging)
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Run server:**

   ```bash
   python -m vgc_mcp
   ```

3. **Test tool call:**

   Create test script:

   ```python
   # test_tool.py
   import asyncio
   from vgc_mcp.tools.damage_tools import register_damage_tools
   from vgc_mcp_core.api.pokeapi import PokeAPIClient
   from vgc_mcp_core.team.manager import TeamManager

   async def main():
       pokeapi = PokeAPIClient()
       team_manager = TeamManager()

       # Simulate tool call
       result = await calculate_damage_output(
           attacker_name="flutter-mane",
           defender_name="incineroar",
           move_name="moonblast"
       )
       print(result)

   asyncio.run(main())
   ```

### Inspecting MCP Messages

**With Claude Desktop:**

1. Open Claude Desktop logs:
   - **Windows**: `%APPDATA%\Claude\logs\`
   - **Mac**: `~/Library/Logs/Claude/`
   - **Linux**: `~/.config/Claude/logs/`

2. Look for MCP-related messages in `mcp.log`

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'vgc_mcp'`

**Fix**: Install in development mode:
```bash
pip install -e .
```

**Issue**: Tests fail with import errors

**Fix**: Ensure PYTHONPATH includes project root:
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
python -m pytest tests/
```

**Issue**: Cache issues (stale data)

**Fix**: Clear cache:
```bash
rm -rf data/cache/
```

---

## Adding New Tools

### Step-by-Step Example

Let's add a `find_best_nature` tool.

**Step 1: Create tool function**

```python
# tools/nature_tools.py
from typing import Optional

def register_nature_tools(mcp, pokeapi, team_manager):
    """Register nature optimization tools."""

    @mcp.tool()
    async def find_best_nature(
        pokemon_name: str,
        attack_evs: int = 0,
        special_attack_evs: int = 0,
        speed_evs: int = 252,
        role: str = "offense"
    ) -> dict:
        """Find the best nature for a Pokemon based on its role.

        Args:
            pokemon_name: Pokemon to optimize nature for
            attack_evs: Physical Attack EVs (default: 0)
            special_attack_evs: Special Attack EVs (default: 0)
            speed_evs: Speed EVs (default: 252)
            role: Role (offense, defense, mixed, etc.)

        Returns:
            Recommended nature with explanation
        """
        # Fetch Pokemon data
        pokemon_data = await pokeapi.get_pokemon(pokemon_name)

        # Determine if physical or special attacker
        if attack_evs > special_attack_evs:
            offensive_stat = "attack"
            recommended_nature = "adamant" if speed_evs < 200 else "jolly"
        else:
            offensive_stat = "special-attack"
            recommended_nature = "modest" if speed_evs < 200 else "timid"

        return {
            "pokemon": pokemon_name,
            "recommended_nature": recommended_nature,
            "reason": f"Boosts {offensive_stat}, neutral or boosted speed",
            "alternative": "serious" if role == "mixed" else None
        }
```

**Step 2: Register in server.py**

```python
# server.py
from vgc_mcp.tools.nature_tools import register_nature_tools

def main():
    mcp = McpServer("vgc-mcp")
    pokeapi = PokeAPIClient()
    team_manager = TeamManager()

    # ... existing registrations
    register_nature_tools(mcp, pokeapi, team_manager)

    mcp.run()
```

**Step 3: Write tests**

```python
# tests/test_nature_tools.py
import pytest
from vgc_mcp.tools.nature_tools import register_nature_tools

@pytest.mark.asyncio
async def test_find_best_nature_physical():
    result = await find_best_nature(
        pokemon_name="landorus",
        attack_evs=252,
        speed_evs=252
    )
    assert result["recommended_nature"] == "jolly"
    assert "attack" in result["reason"].lower()

@pytest.mark.asyncio
async def test_find_best_nature_special():
    result = await find_best_nature(
        pokemon_name="flutter-mane",
        special_attack_evs=252,
        speed_evs=252
    )
    assert result["recommended_nature"] == "timid"
```

**Step 4: Document**

Add to [API_REFERENCE.md](API_REFERENCE.md):

```markdown
### find_best_nature

Find the best nature for a Pokemon based on its role.

**Parameters:**
- `pokemon_name` (string, required): Pokemon to optimize
- `attack_evs` (integer, default: 0): Physical Attack EVs
- `special_attack_evs` (integer, default: 0): Special Attack EVs
- `speed_evs` (integer, default: 252): Speed EVs
- `role` (string, default: "offense"): Role (offense, defense, mixed)

**Returns:**
```json
{
  "pokemon": "flutter-mane",
  "recommended_nature": "timid",
  "reason": "Boosts special-attack, boosted speed",
  "alternative": null
}
```

**Example:**
```
"What's the best nature for my 252 SpA / 252 Spe Flutter Mane?"
```
```

**Step 5: Update CHANGELOG.md**

```markdown
### Added
- New tool: `find_best_nature` - Recommends optimal nature for Pokemon role
```

---

## Common Development Tasks

### Update Pokemon Data

When PokeAPI adds new Pokemon or changes data:

```bash
# Clear cache to force re-fetch
rm -rf data/cache/

# Run tests to verify everything still works
python -m pytest tests/
```

### Update Smogon Stats URL

When Smogon changes stats URL format:

```python
# api/smogon.py
SMOGON_URL = "https://www.smogon.com/stats/{YYYY-MM}/chaos/{format}-{rating}.json"

# Update in code, then test
python -m pytest tests/test_smogon.py -v
```

### Add Support for New Generation

When a new generation is released:

1. **Update type chart** (if new types):
   ```python
   # calc/modifiers.py
   TYPE_CHART = {
       # ... existing types
       "new-type": {"super_effective": [...], "not_very_effective": [...]}
   }
   ```

2. **Add new abilities**:
   ```python
   # calc/abilities.py
   def apply_ability_modifier(ability: str, context: dict) -> float:
       if ability == "new-ability":
           return 1.5  # Or whatever the modifier is
       # ... existing abilities
   ```

3. **Add new moves**:
   ```python
   # models/move.py
   SPECIAL_MOVES = {
       # ... existing moves
       "new-move": {"power": 100, "type": "normal", "special_effect": ...}
   }
   ```

4. **Update tests**:
   ```python
   # tests/test_new_gen.py
   def test_new_ability():
       # Test new generation features
   ```

### Optimize Performance

**Profile code:**

```bash
# Install profiler
pip install py-spy

# Profile server
py-spy record -o profile.svg -- python -m vgc_mcp

# Profile specific function
python -m cProfile -s cumtime script.py
```

**Add caching:**

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def expensive_calculation(param1, param2):
    # Expensive operation
    return result
```

**Use bulk operations:**

```python
# Bad: Multiple API calls
for pokemon in pokemon_list:
    data = await pokeapi.get_pokemon(pokemon)

# Good: Batch request (if API supports it)
data_list = await pokeapi.get_pokemon_bulk(pokemon_list)
```

---

## Release Process

### 1. Update Version

```python
# pyproject.toml
[project]
version = "0.2.0"  # Update version number
```

### 2. Update CHANGELOG.md

```markdown
## [0.2.0] - 2026-02-15

### Added
- New feature X
- New tool Y

### Fixed
- Bug Z

### Changed
- Improved performance of W
```

### 3. Run Full Test Suite

```bash
# All tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=vgc_mcp --cov-report=html

# Check coverage is >= 80%
```

### 4. Code Quality Checks

```bash
ruff format src/
ruff check --fix src/
mypy src/vgc_mcp
```

### 5. Build Distribution

```bash
# Clean old builds
rm -rf dist/

# Build
python -m build

# Verify
ls dist/
# Should see: vgc_mcp-0.2.0.tar.gz and vgc_mcp-0.2.0-py3-none-any.whl
```

### 6. Create Git Tag

```bash
git add .
git commit -m "Release v0.2.0"
git tag -a v0.2.0 -m "Version 0.2.0"
git push origin main --tags
```

### 7. Publish to PyPI (if applicable)

```bash
pip install twine
twine upload dist/*
```

---

## Additional Resources

- **Contributing Guide**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Technical Architecture**: [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md)
- **API Reference**: [API_REFERENCE.md](API_REFERENCE.md)
- **Deployment**: [DEPLOYMENT.md](DEPLOYMENT.md)

---

**Questions?** Open an issue or discussion on GitHub!
