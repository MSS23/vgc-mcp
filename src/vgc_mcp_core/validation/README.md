# validation/ - Input Validation

Validation utilities for Pokemon data.

## Files

| File | Purpose |
|------|---------|
| `learnset.py` | Move learnset validation |

---

## learnset.py - Move Learnset Validation

Validate that a Pokemon can learn specific moves:

```python
from vgc_mcp.validation.learnset import (
    can_learn_move,
    validate_moveset,
    get_learnable_moves
)

# Check if Pokemon can learn a move
can_learn = can_learn_move("Flutter Mane", "Moonblast")  # True
can_learn = can_learn_move("Flutter Mane", "Earthquake")  # False

# Validate entire moveset
result = validate_moveset(
    pokemon="Incineroar",
    moves=["Fake Out", "Flare Blitz", "Parting Shot", "Protect"]
)
# Returns: {
#   "valid": True,
#   "illegal_moves": [],
#   "warnings": []
# }

# Get all learnable moves
moves = get_learnable_moves("Flutter Mane")
# Returns list of move names
```

### Data Sources
- PokeAPI learnset data
- Gen 9 TM/TR compatibility
- Egg moves
- Move tutors

---

## Usage in Tools

```python
# In legality_tools.py
from ..validation.learnset import validate_moveset

@mcp.tool()
async def check_moveset_legality(pokemon: str, moves: list[str]):
    result = validate_moveset(pokemon, moves)
    return result
```

---

## Common Issues Caught

| Issue | Example |
|-------|---------|
| Invalid move | Flutter Mane with Earthquake |
| Gen mismatch | Move not available in Gen 9 |
| Form-specific | Wrong Rotom form for move |
| Event-only | Limited distribution moves |
