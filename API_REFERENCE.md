# API Reference

Complete tool catalog for the VGC MCP Server with 157+ tools for competitive Pokemon team building.

## Table of Contents

- [Tool Categories](#tool-categories)
- [Damage Calculation Tools](#damage-calculation-tools)
- [Speed Analysis Tools](#speed-analysis-tools)
- [EV/IV Optimization Tools](#eviv-optimization-tools)
- [Team Building Tools](#team-building-tools)
- [Usage Statistics Tools](#usage-statistics-tools)
- [Learning & Reference Tools](#learning--reference-tools)
- [Import/Export Tools](#importexport-tools)
- [Common Parameters](#common-parameters)

---

## Tool Categories

| Category | Tool Count | Description |
|----------|------------|-------------|
| Damage Calculations | 15 | Calculate damage, find KO thresholds, survival EVs |
| Speed Analysis | 12 | Compare speeds, speed tiers, Tailwind/Trick Room |
| EV/IV Optimization | 10 | Optimize spreads, nature suggestions, bulk calcs |
| Team Building | 14 | Build teams, analyze synergy, core recommendations |
| Usage Statistics | 8 | Smogon usage data, common sets, meta analysis |
| Learning & Reference | 12 | VGC glossary, Pokemon guides, type charts |
| Import/Export | 5 | Showdown paste, JSON formats, team sharing |
| Legality Checking | 6 | VGC rules, species clause, move legality |
| Matchup Analysis | 8 | Type matchups, threat analysis, coverage gaps |
| Chip Damage | 7 | Hazards, weather, status conditions |
| Lead Recommendations | 6 | Lead pairs, team positioning |
| Special Calculations | 8 | Tera mechanics, multi-hit moves, special cases |
| **Total** | **157+** | All competitive VGC needs covered |

---

## Damage Calculation Tools

### calculate_damage_output

Calculate full damage output between two Pokemon with all modifiers.

**Parameters:**
- `attacker_name` (string, required): Attacking Pokemon
- `defender_name` (string, required): Defending Pokemon
- `move_name` (string, required): Move being used
- `attacker_nature` (string, default: "serious"): Attacker's nature
- `attacker_spa_evs` (integer, default: 252): Special Attack EVs
- `attacker_atk_evs` (integer, default: 0): Attack EVs
- `defender_nature` (string, default: "serious"): Defender's nature
- `defender_spd_evs` (integer, default: 0): Special Defense EVs
- `defender_hp_evs` (integer, default: 252): HP EVs
- `attacker_item` (string, optional): Attacker's held item
- `defender_item` (string, optional): Defender's held item
- `weather` (string, optional): Weather condition
- `terrain` (string, optional): Terrain type
- `attacker_tera_type` (string, optional): Attacker's Tera type (if active)
- `defender_tera_type` (string, optional): Defender's Tera type (if active)

**Returns:**
```json
{
  "attacker_name": "Flutter Mane",
  "defender_name": "Incineroar",
  "move_name": "Moonblast",
  "damage_min": 85,
  "damage_max": 100,
  "damage_percent_min": 96.5,
  "damage_percent_max": 113.6,
  "ohko_chance": 75.0,
  "ko_type": "75% OHKO",
  "attacker_showdown_paste": "...",
  "defender_showdown_paste": "...",
  "notes": ["STAB applied: 1.5x", "Assault Vest boosts SpD by 1.5x"]
}
```

**Example Usage:**
> "Does my Timid 252 SpA Flutter Mane OHKO Assault Vest Incineroar with Moonblast?"

---

### find_survival_evs

Find minimum HP/Def/SpD EVs needed to survive a specific attack.

**Parameters:**
- `defender_name` (string, required): Pokemon to optimize
- `attacker_name` (string, required): Attacking Pokemon
- `move_name` (string, required): Move to survive
- `defender_nature` (string, optional): Desired nature
- `target_survival_chance` (float, default: 93.75): % of damage rolls to survive (93.75 = survive max roll)
- `defender_tera_type` (string, optional): Tera type if active

**Returns:**
```json
{
  "defender_name": "Ogerpon-Hearthflame",
  "required_hp_evs": 252,
  "required_def_evs": 4,
  "final_stats": {"hp": 187, "def": 111, "spd": 100},
  "damage_range": "67.4-78.6%",
  "survival_rate": 100.0,
  "showdown_paste": "...",
  "attacker_spread_info": "Adamant 4 HP / 252 Atk / 252 Spe Urshifu-Rapid-Strike @ Choice Scarf"
}
```

**Example Usage:**
> "What EVs does Ogerpon need to survive Adamant Choice Scarf Urshifu's Surging Strikes?"

---

### find_ko_threshold

Find minimum Attack/Special Attack EVs needed to guarantee OHKO.

**Parameters:**
- `attacker_name` (string, required): Attacking Pokemon
- `defender_name` (string, required): Target Pokemon
- `move_name` (string, required): Move to use
- `attacker_nature` (string, optional): Nature
- `target_ko_chance` (float, default: 100.0): Required KO chance

**Returns:**
```json
{
  "attacker_name": "Flutter Mane",
  "required_spa_evs": 196,
  "final_stats": {"spa": 190, "spe": 205},
  "damage_range": "101.2-119.8%",
  "ko_guaranteed": true,
  "evs_left_over": 56,
  "showdown_paste": "..."
}
```

**Example Usage:**
> "How much SpA does Flutter Mane need to OHKO Assault Vest Rillaboom?"

---

### optimize_multi_survival_spread

Optimize a defensive spread to survive 3-6 different attacks simultaneously.

**Parameters:**
- `pokemon_name` (string, required): Pokemon to optimize
- `threats` (array, required): List of 3-6 threats to survive
  - Each threat: `{"attacker": "...", "move": "...", "tera_type": "..." (optional)}`
- `defender_tera_type` (string, optional): Defender's Tera type
- `outspeed_pokemon` (string, optional): Speed benchmark
- `target_survival` (float, default: 93.75): Survival rate per threat

**Returns:**
```json
{
  "pokemon": "Ogerpon-Hearthflame",
  "optimized_spread": "Impish 180 HP / 116 Def / 60 SpD / 152 Spe",
  "showdown_paste": "...",
  "survival_breakdown": [
    {"threat": "Urshifu Surging Strikes", "damage": "67-79%", "survival": "100%"},
    {"threat": "Flutter Mane Moonblast", "damage": "81-96%", "survival": "93.75%"},
    {"threat": "Chi-Yu Heat Wave", "damage": "72-85%", "survival": "100%"}
  ],
  "final_stats": {"hp": 186, "def": 142, "spd": 110, "spe": 143},
  "speed_benchmark": "Outspeeds max speed Tornadus"
}
```

**Example Usage:**
> "Design a spread for Ogerpon that survives Urshifu, Flutter Mane, and Chi-Yu"

---

## Speed Analysis Tools

### compare_speed

Compare speeds between two Pokemon at specific spreads.

**Parameters:**
- `pokemon1_name` (string, required)
- `pokemon1_nature` (string, default: "serious")
- `pokemon1_speed_evs` (integer, default: 252)
- `pokemon2_name` (string, required)
- `pokemon2_nature` (string, default: "serious")
- `pokemon2_speed_evs` (integer, default: 252)
- `tailwind_active` (boolean, default: false)
- `trick_room_active` (boolean, default: false)

**Returns:**
```json
{
  "pokemon1": "Dragapult",
  "pokemon1_speed": 213,
  "pokemon2": "Flutter Mane",
  "pokemon2_speed": 205,
  "result": "Dragapult outspeeds by 8 points",
  "speed_difference": 8,
  "outspeeds": true
}
```

---

### visualize_speed_tiers

Get visual speed tier chart showing Pokemon at various speed benchmarks.

**Parameters:**
- `format` (string, default: "gen9vgc2024regh"): VGC format
- `tailwind` (boolean, default: false): Show Tailwind speeds
- `trick_room` (boolean, default: false): Show Trick Room order

**Returns:**
```json
{
  "tiers": [
    {"speed": 220, "pokemon": ["Dragapult (Jolly 252)", "Regieleki (Adamant 252)"]},
    {"speed": 205, "pokemon": ["Flutter Mane (Timid 252)", "Iron Bundle (Timid 252)"]},
    {"speed": 189, "pokemon": ["Landorus (Jolly 252)", "Tornadus (Timid 252)"]}
  ]
}
```

---

### get_speed_probability

Calculate probability of outspeeding a Pokemon based on Smogon usage data.

**Parameters:**
- `pokemon_name` (string, required): Your Pokemon
- `nature` (string, required): Your Pokemon's nature
- `speed_evs` (integer, required): Your Speed EVs
- `opponent_name` (string, required): Opponent Pokemon
- `format` (string, default: "gen9vgc2024regh")

**Returns:**
```json
{
  "your_pokemon": "Landorus",
  "your_speed": 189,
  "opponent": "Tornadus",
  "outspeed_probability": 67.5,
  "analysis": "Outspeeds 67.5% of Tornadus sets (based on Smogon 0 ELO data - all competitive players)",
  "common_opponent_spreads": [
    {"spread": "Timid 252 Spe", "speed": 196, "usage": 45.2%, "result": "lose"},
    {"spread": "Timid 180 Spe", "speed": 182, "usage": 32.1%, "result": "win"}
  ]
}
```

---

## EV/IV Optimization Tools

### suggest_spread

Suggest an optimal EV spread for a Pokemon based on role.

**Parameters:**
- `pokemon_name` (string, required)
- `role` (string, required): "offense", "defense", "support", "mixed", "speed_control"
- `benchmark_pokemon` (string, optional): Speed benchmark to outspeed
- `survival_benchmark` (object, optional): Attack to survive

**Returns:**
```json
{
  "pokemon": "Flutter Mane",
  "role": "offense",
  "recommended_spread": "Timid 4 HP / 252 SpA / 252 Spe",
  "showdown_paste": "...",
  "final_stats": {"hp": 131, "spa": 198, "spe": 205},
  "explanation": "Maximizes Special Attack and Speed for sweeping role"
}
```

---

### check_spread_efficiency

Check if an EV spread is efficient or if EVs are wasted.

**Parameters:**
- `pokemon_name` (string, required)
- `nature` (string, required)
- `hp_evs`, `atk_evs`, `def_evs`, `spa_evs`, `spd_evs`, `spe_evs` (integers)

**Returns:**
```json
{
  "pokemon": "Flutter Mane",
  "spread_analysis": "Efficient",
  "wasted_evs": 0,
  "suggestions": [],
  "showdown_paste": "..."
}
```

---

### suggest_nature_optimization

Check if a different nature can achieve the same stats with fewer EVs.

**Parameters:**
- `pokemon_name` (string, required)
- `current_nature` (string, required)
- `current_evs` (object, required): Current EV spread

**Returns:**
```json
{
  "pokemon": "Landorus",
  "current_spread": "Serious 4 HP / 252 Atk / 252 Spe",
  "optimized_spread": "Jolly 4 HP / 244 Atk / 252 Spe",
  "evs_saved": 8,
  "current_showdown_paste": "...",
  "optimized_showdown_paste": "...",
  "explanation": "Jolly nature's +Spe lets you reach same Speed with 252 EVs, saving 8 Atk EVs"
}
```

---

## Team Building Tools

### add_to_team

Add a Pokemon to your current team.

**Parameters:**
- `pokemon_name` (string, required)
- `nature` (string, optional)
- `evs` (object, optional)
- `item` (string, optional)
- `ability` (string, optional)
- `moves` (array, optional)

**Returns:**
```json
{
  "success": true,
  "team_size": 3,
  "pokemon_added": "Flutter Mane",
  "current_team": ["Flutter Mane", "Incineroar", "Landorus"]
}
```

---

### analyze_team

Analyze team composition, synergy, and weaknesses.

**Parameters:**
- None (analyzes current team in memory)

**Returns:**
```json
{
  "team_size": 6,
  "type_coverage": {
    "offensive": ["fire", "fairy", "ground", "dark", "ghost"],
    "defensive": ["water", "grass", "fire", "electric"]
  },
  "weaknesses": {
    "4x": ["electric"],
    "2x": ["water", "ice", "rock"]
  },
  "threats": [
    {"pokemon": "Urshifu", "reason": "Hits 4/6 team members super effectively"}
  ],
  "synergies": [
    {"pair": "Incineroar + Flutter Mane", "reason": "Fake Out support + high damage output"}
  ]
}
```

---

### suggest_teammates

Get Pokemon recommendations that synergize well with your team.

**Parameters:**
- `core_pokemon` (array, required): 1-3 Pokemon already on team
- `role_needed` (string, optional): "offense", "defense", "support", "speed_control"

**Returns:**
```json
{
  "recommendations": [
    {
      "pokemon": "Incineroar",
      "synergy_score": 9.2,
      "reasons": ["Fake Out support", "Intimidate lowers physical attacks", "Fire/Dark coverage"]
    },
    {
      "pokemon": "Landorus",
      "synergy_score": 8.7,
      "reasons": ["Ground coverage", "Intimidate stacking", "Electric immunity"]
    }
  ]
}
```

---

### import_showdown_team

Import a team from Pokemon Showdown paste format.

**Parameters:**
- `paste` (string, required): Showdown team paste

**Returns:**
```json
{
  "success": true,
  "team_size": 6,
  "pokemon_imported": [
    "Flutter Mane @ Choice Specs",
    "Incineroar @ Assault Vest",
    "..."
  ],
  "validation_errors": []
}
```

---

## Usage Statistics Tools

### get_usage_stats

Get Pokemon usage percentages from Smogon Stats.

**Parameters:**
- `format` (string, default: "gen9vgc2026regfbo3")
- `rating` (integer, default: 0): ELO rating cutoff (0 = all competitive players)
- `top_n` (integer, default: 20): Number of Pokemon to return

**Returns:**
```json
{
  "format": "gen9vgc2026regfbo3",
  "rating": 0,
  "month": "2026-01",
  "top_pokemon": [
    {"rank": 1, "pokemon": "flutter-mane", "usage": 45.2},
    {"rank": 2, "pokemon": "incineroar", "usage": 42.1},
    {"rank": 3, "pokemon": "rillaboom", "usage": 38.5}
  ]
}
```

---

### get_common_sets

Get the most common EV spread, item, and moves for a Pokemon.

**Parameters:**
- `pokemon_name` (string, required)
- `format` (string, default: "gen9vgc2024regh")

**Returns:**
```json
{
  "pokemon": "flutter-mane",
  "most_common_set": {
    "nature": "timid",
    "evs": {"hp": 4, "spa": 252, "spe": 252},
    "item": "choice-specs",
    "ability": "protosynthesis",
    "moves": ["moonblast", "shadow-ball", "dazzling-gleam", "mystical-fire"],
    "usage": 67.8
  },
  "showdown_paste": "..."
}
```

---

## Learning & Reference Tools

### explain_vgc_term

Get definition and explanation of VGC terms.

**Parameters:**
- `term` (string, required): Term to explain

**Returns:**
```json
{
  "term": "STAB",
  "full_name": "Same Type Attack Bonus",
  "definition": "A 1.5x damage boost when a Pokemon uses a move that matches one of its types",
  "example": "Flutter Mane (Fairy/Ghost) using Moonblast (Fairy) gets STAB"
}
```

**Available terms:** STAB, OHKO, 2HKO, EVs, IVs, nature, spread, Tera, Protosynthesis, Intimidate, etc.

---

### get_type_matchup

Get type effectiveness chart for a Pokemon or type.

**Parameters:**
- `pokemon_or_type` (string, required)

**Returns:**
```json
{
  "name": "flutter-mane",
  "types": ["ghost", "fairy"],
  "weaknesses": ["ghost", "steel"],
  "resistances": ["bug", "fighting", "normal"],
  "immunities": ["dragon", "normal", "fighting"],
  "offensive_advantages": {
    "super_effective": ["ghost", "psychic", "dark", "dragon", "fighting"],
    "not_very_effective": ["steel", "fire", "poison"]
  }
}
```

---

## Common Parameters

### Nature Values

Valid natures:
- **Neutral**: `serious`, `bashful`, `docile`, `quirky`, `hardy`
- **+Atk**: `adamant` (-SpA), `lonely` (-Def), `brave` (-Spe), `naughty` (-SpD)
- **+Def**: `bold` (-Atk), `impish` (-SpA), `lax` (-SpD), `relaxed` (-Spe)
- **+SpA**: `modest` (-Atk), `mild` (-Def), `quiet` (-Spe), `rash` (-SpD)
- **+SpD**: `calm` (-Atk), `careful` (-SpA), `gentle` (-Def), `sassy` (-Spe)
- **+Spe**: `jolly` (-SpA), `hasty` (-Def), `naive` (-SpD), `timid` (-Atk)

### EV Ranges

- **Per stat**: 0-252
- **Total**: 508 maximum
- **Increments**: EVs work in increments of 4 (0, 4, 8, 12, ..., 252)

### IV Ranges

- **Per stat**: 0-31
- **Common IVs**:
  - 31 (max) for most stats
  - 0 Atk for special attackers (reduce Foul Play damage)
  - 0 Spe for Trick Room

### Weather Conditions

- `sun` - Boosts Fire moves 1.5x, weakens Water moves to 0.5x
- `rain` - Boosts Water moves 1.5x, weakens Fire moves to 0.5x
- `sandstorm` - Boosts Rock SpD by 1.5x, chip damage
- `snow` - Boosts Ice Def by 1.5x

### Terrain Types

- `electric` - Boosts Electric moves 1.3x, prevents sleep
- `grassy` - Boosts Grass moves 1.3x, heals 1/16 HP per turn
- `psychic` - Boosts Psychic moves 1.3x, blocks priority
- `misty` - Halves Dragon move damage, prevents status

---

## Tool Usage Tips

1. **Auto-fetch Smogon sets**: Most tools auto-fetch common spreads from Smogon when EVs aren't specified
2. **Showdown paste output**: All spread tools return `showdown_paste` fields for easy copy-paste
3. **Nature optimization**: Use `suggest_nature_optimization` before finalizing spreads to save EVs
4. **Multi-threat survival**: Use `optimize_multi_survival_spread` for 3-6 threats simultaneously
5. **Speed benchmarks**: Always specify speed benchmarks when optimizing spreads
6. **Survival rates**: 93.75% (survive max roll) is optimal - 100% often wastes EVs

---

## Complete Tool List

For a complete list of all 157+ tools, run in Claude Desktop:

> "List all your VGC tools"

Or see the [VGC_MCP_Guide.md](VGC_MCP_Guide.md) for categorized examples.

---

**Need Help?** See [FAQ.md](FAQ.md) or [USER_GUIDE.md](USER_GUIDE.md)!
