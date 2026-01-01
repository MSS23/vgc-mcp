# calc/ - Pure Calculation Functions

Pure functions for Pokemon battle calculations. No external dependencies or side effects.

## Core Calculations

| File | Purpose |
|------|---------|
| `damage.py` | Gen 9 damage formula with all modifiers |
| `stats.py` | Stat calculation formulas (HP, Atk, Def, etc.) |
| `modifiers.py` | Type chart, weather, terrain, item modifiers |
| `speed.py` | Speed comparisons and tier analysis |

## Advanced Calculations

| File | Purpose |
|------|---------|
| `bulk_optimization.py` | Optimal EV distribution for bulk |
| `speed_probability.py` | Outspeed probability using Smogon data |
| `coverage.py` | Type coverage analysis |
| `matchup.py` | Pokemon matchup scoring |
| `meta_threats.py` | Threat identification |

## Battle Mechanics

| File | Purpose |
|------|---------|
| `priority.py` | Priority move and turn order |
| `speed_control.py` | Trick Room, Tailwind analysis |
| `abilities.py` | Ability synergy and interactions |
| `items.py` | Item effect calculations |
| `chip_damage.py` | Residual damage (weather, recoil, etc.) |

---

## damage.py - Damage Calculator

Full Gen 9 damage formula implementation:

```python
from vgc_mcp.calc.damage import calculate_damage

result = calculate_damage(attacker, defender, move, modifiers)

# DamageResult contains:
result.min_damage      # 85
result.max_damage      # 101
result.damage_range    # "85-101"
result.min_percent     # 45.5
result.max_percent     # 54.0
result.ko_chance       # "Guaranteed 2HKO"
result.is_guaranteed_ohko  # False
result.rolls           # [85, 86, 87, ..., 101]
```

### Modifiers Supported
- Type effectiveness (0.25x to 4x)
- STAB (1.5x, 2x with Tera)
- Weather (Sun, Rain, Sand, Snow)
- Terrain (Electric, Grassy, Psychic, Misty)
- Items (Choice Band/Specs, Life Orb, etc.)
- Abilities (Huge Power, Protosynthesis, etc.)
- Screens (Reflect, Light Screen)
- Critical hits
- Spread move penalty (0.75x in doubles)
- Helping Hand (1.5x)

---

## stats.py - Stat Formulas

Level 50 stat calculations (VGC standard):

```python
from vgc_mcp.calc.stats import calculate_stat, calculate_hp, calculate_speed

# HP formula
hp = calculate_hp(base_hp=100, iv=31, ev=252, level=50)  # 207

# Other stats with nature
atk = calculate_stat(base_atk=130, iv=31, ev=252, level=50, nature=1.1)  # 200

# Speed calculation
speed = calculate_speed(base_speed=110, iv=31, ev=252, nature="jolly")  # 178
```

---

## modifiers.py - Type Chart & Modifiers

Type effectiveness and battle modifiers:

```python
from vgc_mcp.calc.modifiers import get_type_effectiveness, DamageModifiers

# Type effectiveness
eff = get_type_effectiveness("Fire", ["Grass", "Steel"])  # 4.0
eff = get_type_effectiveness("Fire", ["Water"])  # 0.5
eff = get_type_effectiveness("Normal", ["Ghost"])  # 0.0

# Damage modifiers object
mods = DamageModifiers(
    weather="sun",
    terrain="grassy",
    is_doubles=True,
    attacker_item="life-orb",
    helping_hand=True
)
```

---

## bulk_optimization.py - EV Optimization

Optimal bulk distribution:

```python
from vgc_mcp.calc.bulk_optimization import optimize_bulk_evs

result = optimize_bulk_evs(
    base_hp=80,
    base_def=84,
    base_spd=96,
    total_evs=508,
    defense_weight=0.6  # 60% physical, 40% special
)

# Returns optimal HP/Def/SpD split
```

---

## speed_probability.py - Speed Tier Analysis

Probability calculations using Smogon spread data:

```python
from vgc_mcp.calc.speed_probability import calculate_outspeed_probability

# Given opponent's common speed spreads from Smogon,
# calculate probability of outspeeding
prob = calculate_outspeed_probability(
    my_speed=152,
    opponent_spreads=[
        {"speed": 148, "usage": 30.0},
        {"speed": 156, "usage": 45.0},
        {"speed": 178, "usage": 25.0}
    ]
)
# Returns: 0.30 (30% chance to outspeed)
```

---

## Design Principles

1. **Pure Functions**: All calculations are pure - same inputs always produce same outputs
2. **No I/O**: No API calls, file access, or network requests
3. **Testable**: Easy to unit test with known inputs/outputs
4. **Reusable**: Used by multiple tools without duplication
