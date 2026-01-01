# utils/ - Utility Functions

Shared utilities for error handling, fuzzy matching, and formatting.

## Files

| File | Purpose |
|------|---------|
| `errors.py` | Structured error responses |
| `fuzzy.py` | Fuzzy name matching and suggestions |
| `damage_verdicts.py` | Damage result formatting |

---

## errors.py - Structured Errors

Consistent error responses across all tools:

```python
from vgc_mcp.utils.errors import (
    error_response,
    success_response,
    pokemon_not_found_error,
    api_error,
    ErrorCodes
)

# Generic error
return error_response(
    ErrorCodes.VALIDATION_ERROR,
    "Invalid EV value: must be 0-252"
)

# Pokemon not found with suggestions
suggestions = suggest_pokemon_name("fluter mane")
return pokemon_not_found_error("fluter mane", suggestions)
# Returns: {
#   "success": False,
#   "error": "pokemon_not_found",
#   "message": "Pokemon 'fluter mane' not found",
#   "suggestions": ["Did you mean: Flutter Mane?"]
# }

# API error (retryable)
return api_error("Smogon", str(exception), is_retryable=True)

# Success response
return success_response({"damage": 100})
```

### Error Codes

```python
class ErrorCodes:
    VALIDATION_ERROR = "validation_error"
    POKEMON_NOT_FOUND = "pokemon_not_found"
    MOVE_NOT_FOUND = "move_not_found"
    ITEM_NOT_FOUND = "item_not_found"
    INVALID_NATURE = "invalid_nature"
    TEAM_EMPTY = "team_empty"
    TEAM_FULL = "team_full"
    SPECIES_CLAUSE = "species_clause_violation"
    API_ERROR = "api_error"
    INTERNAL_ERROR = "internal_error"
```

---

## fuzzy.py - Fuzzy Matching

Suggest corrections for typos and common mistakes:

```python
from vgc_mcp.utils.fuzzy import (
    suggest_pokemon_name,
    suggest_move_name,
    suggest_nature,
    normalize_pokemon_name
)

# Pokemon suggestions
suggest_pokemon_name("fluter mane")  # ["Flutter Mane"]
suggest_pokemon_name("incin")         # ["Incineroar"]

# Move suggestions
suggest_move_name("moon blast")  # ["Moonblast"]
suggest_move_name("prtect")      # ["Protect"]

# Nature suggestions
suggest_nature("admant")  # ["Adamant"]

# Normalize names
normalize_pokemon_name("Flutter Mane")  # "flutter-mane"
normalize_pokemon_name("URSHIFU")       # "urshifu"
```

### Common VGC Pokemon
Pre-loaded list of common Pokemon for fast matching:
- All restricted Pokemon
- Top 100 usage Pokemon
- Common cores

---

## damage_verdicts.py - Damage Formatting

Format damage results for display:

```python
from vgc_mcp.utils.damage_verdicts import (
    get_ko_verdict,
    format_damage_range,
    format_ko_chance
)

# Get KO verdict
verdict = get_ko_verdict(min_pct=95, max_pct=105)
# Returns: "Guaranteed OHKO" or "Possible OHKO (roll)"

# Format damage range
formatted = format_damage_range(85, 101, defender_hp=187)
# Returns: "85-101 (45.5% - 54.0%)"

# Format KO chance
chance = format_ko_chance(rolls=[85, 87, 89, 91, 93, 95, 97, 99, 101], hp=100)
# Returns: "56.3% chance to OHKO"
```

---

## Usage Example

```python
# In damage_tools.py
from ..utils.errors import pokemon_not_found_error, api_error
from ..utils.fuzzy import suggest_pokemon_name

async def calculate_damage_output(attacker_name: str, ...):
    try:
        stats = await pokeapi.get_base_stats(attacker_name)
    except PokeAPIError:
        suggestions = suggest_pokemon_name(attacker_name)
        return pokemon_not_found_error(attacker_name, suggestions)

    # ... calculation ...

    return success_response(result)
```
