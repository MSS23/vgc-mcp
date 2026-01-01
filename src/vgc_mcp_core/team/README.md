# team/ - Team Management

Team state management, analysis, and validation.

## Files

| File | Purpose |
|------|---------|
| `manager.py` | TeamManager - current team state |
| `analysis.py` | TeamAnalyzer - team analysis and scoring |
| `validation.py` | Team validation (species clause, etc.) |
| `core_builder.py` | Core synergy and suggestions |

---

## manager.py - TeamManager

Manages the current team state (singleton-like in server):

```python
from vgc_mcp.team.manager import TeamManager

team_manager = TeamManager()

# Add Pokemon (validates species clause)
team_manager.add_pokemon(pokemon_build)

# Remove Pokemon
team_manager.remove_by_slot(0)
team_manager.remove_by_name("Flutter Mane")

# Get team info
team_manager.size        # Number of Pokemon
team_manager.team        # List[PokemonBuild]
team_manager.is_full     # True if 6 Pokemon

# Reorder
team_manager.swap(0, 5)  # Swap positions
team_manager.reorder([3, 1, 0, 2, 5, 4])

# Clear
team_manager.clear()

# Get summary
summary = team_manager.get_team_summary()
```

### Species Clause
Automatically enforced - can't add duplicate species:
```python
team_manager.add_pokemon(pikachu)
team_manager.add_pokemon(pikachu_cosplay)  # Raises TeamValidationError
```

---

## analysis.py - TeamAnalyzer

Analyze team composition and identify issues:

```python
from vgc_mcp.team.analysis import TeamAnalyzer

analyzer = TeamAnalyzer()

# Quick summary
summary = analyzer.get_quick_summary(team)
# Returns: {
#   "types": ["Fire", "Water", ...],
#   "weaknesses": {"Ground": 3, "Electric": 2},
#   "resistances": {...},
#   "speed_range": {"min": 85, "max": 178}
# }

# Full analysis
analysis = analyzer.analyze_team(team)
# Returns detailed breakdown with:
# - Type coverage
# - Defensive weaknesses
# - Speed tier distribution
# - Role coverage (Fake Out, Tailwind, etc.)
```

---

## validation.py - Team Validation

Validate team against VGC rules:

```python
from vgc_mcp.team.validation import validate_team

result = validate_team(team)
# Returns: {
#   "valid": True/False,
#   "errors": [...],
#   "warnings": [...]
# }
```

### Validations Include:
- Species clause (no duplicates)
- Item clause (no duplicate items)
- Restricted count (max 2 in most formats)
- Banned Pokemon check
- Move legality

---

## core_builder.py - Core Building

Suggest Pokemon based on team composition:

```python
from vgc_mcp.team.core_builder import (
    analyze_core_synergy,
    suggest_teammates,
    get_pokemon_roles
)

# Analyze a two-Pokemon core
synergy = analyze_core_synergy("Flutter Mane", "Incineroar")
# Returns synergy score, shared weaknesses, coverage

# Suggest teammates
suggestions = suggest_teammates(team, smogon_data)
# Returns: [{"name": "Urshifu", "reasons": [...]}]

# Get Pokemon roles
roles = get_pokemon_roles("Incineroar")
# Returns: ["Fake Out", "Intimidate", "Pivot"]
```

### Role Data
Pre-defined roles for common Pokemon:
- Fake Out users
- Intimidate Pokemon
- Speed control (Tailwind, Trick Room)
- Redirection (Follow Me, Rage Powder)
- Weather setters

---

## Usage in Server

```python
# server.py
team_manager = TeamManager()
analyzer = TeamAnalyzer()

register_team_tools(mcp, pokeapi, team_manager, analyzer)
```

The `team_manager` is shared across all tool calls, maintaining team state throughout the session.
