# models/ - Pydantic Data Models

Type-safe data models using Pydantic for validation and serialization.

## Files

| File | Purpose |
|------|---------|
| `pokemon.py` | Pokemon builds, stats, natures, EVs/IVs |
| `move.py` | Move data with category, power, priority |
| `team.py` | Team with species clause validation |

---

## pokemon.py - Pokemon Models

### BaseStats
Raw base stats from PokeAPI:
```python
from vgc_mcp.models.pokemon import BaseStats

stats = BaseStats(
    hp=80,
    attack=120,
    defense=84,
    special_attack=60,
    special_defense=96,
    speed=110
)
```

### EVSpread / IVSpread
EV and IV distributions:
```python
from vgc_mcp.models.pokemon import EVSpread, IVSpread

evs = EVSpread(hp=252, attack=4, speed=252)  # Defaults to 0
ivs = IVSpread()  # Defaults to 31 for all
```

### Nature
All 25 natures as enum:
```python
from vgc_mcp.models.pokemon import Nature, get_nature_modifier

nature = Nature.ADAMANT
modifier = get_nature_modifier(nature, "attack")  # 1.1
modifier = get_nature_modifier(nature, "special_attack")  # 0.9
```

### PokemonBuild
Complete Pokemon build for calculations:
```python
from vgc_mcp.models.pokemon import PokemonBuild, Nature, EVSpread, BaseStats

pokemon = PokemonBuild(
    name="Flutter Mane",
    base_stats=BaseStats(hp=55, attack=55, defense=55,
                         special_attack=135, special_defense=135, speed=135),
    types=["Ghost", "Fairy"],
    nature=Nature.MODEST,
    evs=EVSpread(hp=4, special_attack=252, speed=252),
    item="choice-specs",
    ability="protosynthesis",
    tera_type="Fairy",
    moves=["Moonblast", "Shadow Ball", "Dazzling Gleam", "Psyshock"]
)

# Calculate final stats
pokemon.calculate_stats()  # Updates hp, attack, defense, etc.
```

---

## move.py - Move Models

### MoveCategory
Physical, Special, or Status:
```python
from vgc_mcp.models.move import MoveCategory

MoveCategory.PHYSICAL
MoveCategory.SPECIAL
MoveCategory.STATUS
```

### Move
Complete move data:
```python
from vgc_mcp.models.move import Move, MoveCategory

move = Move(
    name="moonblast",
    type="Fairy",
    category=MoveCategory.SPECIAL,
    power=95,
    accuracy=100,
    pp=15,
    priority=0,
    target="selected-pokemon",
    makes_contact=False
)

# Spread move check (for doubles damage reduction)
move.is_spread_move()  # True for Dazzling Gleam, Earthquake, etc.
```

### Spread Targets
Moves that hit multiple targets:
```python
from vgc_mcp.models.move import SPREAD_TARGETS

# ["all-opponents", "all-other-pokemon", "all-pokemon", ...]
```

---

## team.py - Team Model

### Team
Team with validation:
```python
from vgc_mcp.models.team import Team
from vgc_mcp.models.pokemon import PokemonBuild

team = Team()

# Add Pokemon (validates species clause)
team.add(pokemon1)
team.add(pokemon2)

# Get team info
team.size  # 2
team.pokemon  # List of PokemonBuild
team.get_types()  # All types on team

# Species clause validation
team.add(duplicate_pokemon)  # Raises TeamValidationError
```

---

## Usage in Tools

Models are used throughout the codebase:

```python
# In damage_tools.py
attacker = PokemonBuild(
    name=attacker_name,
    base_stats=await pokeapi.get_base_stats(attacker_name),
    nature=Nature(attacker_nature.lower()),
    evs=EVSpread(attack=atk_evs, special_attack=spa_evs),
    ...
)

result = calculate_damage(attacker, defender, move, modifiers)
```

## Validation

All models include Pydantic validation:
- EV totals cannot exceed 508
- Individual EVs cannot exceed 252
- IVs must be 0-31
- Natures must be valid enum values
