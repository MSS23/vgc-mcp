# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VGC MCP Server - A Model Context Protocol server for Pokemon VGC (Video Game Championships) team building. Provides 120+ tools for damage calculations, stat analysis, team management, and competitive play optimization.

## Commands

```bash
# Install (editable mode)
pip install -e .

# Run server
python -m vgc_mcp
# or after install:
vgc-mcp

# Run all tests
python -m pytest tests/ -v

# Run single test file
python -m pytest tests/test_damage.py -v

# Run specific test
python -m pytest tests/test_matchup.py::TestSingleMatchup::test_type_advantage_improves_matchup -v

# Run with coverage
python -m pytest tests/ --cov=vgc_mcp

# Linting
ruff check src/
ruff format src/

# Type checking
mypy src/vgc_mcp
```

## Architecture

### Core Structure

```
src/vgc_mcp/
├── server.py          # MCP server entry point, registers all tools
├── config.py          # Settings (API URLs, VGC defaults, EV limits)
├── api/               # External API clients
│   ├── pokeapi.py     # PokeAPI client for Pokemon data
│   ├── smogon.py      # Smogon Stats client for usage data
│   └── cache.py       # Disk-based API response caching
├── calc/              # Pure calculation functions
│   ├── damage.py      # Full Gen 9 damage formula
│   ├── modifiers.py   # Type chart, weather, terrain, items
│   ├── stats.py       # Stat calculation formulas
│   └── ...            # Speed, matchup, chip damage calcs
├── models/            # Pydantic data models
│   ├── pokemon.py     # PokemonBuild, Nature, EVSpread, IVSpread
│   ├── move.py        # Move model with multi-hit support
│   └── team.py        # Team with species clause validation
├── tools/             # MCP tool definitions (22 files)
│   └── *_tools.py     # Each registers tools via register_*_tools(mcp, ...)
├── rules/             # VGC format rules and legality
├── formats/           # Showdown paste import/export
└── utils/             # Error handling, fuzzy matching
```

### Key Patterns

**Tool Registration**: Each `tools/*_tools.py` exports a `register_*_tools(mcp, ...)` function that decorates async functions with `@mcp.tool()`. Dependencies (pokeapi, team_manager, etc.) are passed in.

**Error Handling**: Use `utils/errors.py` helpers:
```python
from ..utils.errors import pokemon_not_found_error, api_error
from ..utils.fuzzy import suggest_pokemon_name

# Good - structured error with suggestions
suggestions = suggest_pokemon_name(pokemon_name)
return pokemon_not_found_error(pokemon_name, suggestions)

# Avoid - raw error strings
return {"error": f"Pokemon not found: {name}"}  # Don't do this
```

**Pydantic Models**: All data structures use Pydantic for validation. `PokemonBuild` is the central model containing base stats, nature, EVs, IVs, item, ability, and tera type.

**Calculations**: `calc/` modules are pure functions. `calc/damage.py` implements the Gen 9 damage formula with all modifiers (STAB, type effectiveness, weather, terrain, screens, items).

### Type Chart

Located in `calc/modifiers.py`. Key mechanics:
- Fire is super effective against Steel (2x), not resisted
- Fire resists Fire (0.5x)
- Type effectiveness stacks for dual types (0.25x to 4x)

### VGC Defaults

- Level 50 (standard VGC)
- 508 max total EVs, 252 per stat
- Doubles format (spread moves get 0.75x multiplier)

## Testing

Tests use pytest with `asyncio_mode = "auto"`. Common fixtures in `tests/conftest.py`:
- `team_manager` - Fresh TeamManager instance
- Sample stats fixtures: `flutter_mane_stats`, `dragapult_stats`, etc.

Test files mirror the module structure. Many tests create Pokemon inline:
```python
def make_pokemon(name, types, base_hp=80, ...):
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(hp=base_hp, ...),
        nature=Nature.SERIOUS,
        evs=EVSpread(),
        types=types
    )
```

## Dependencies

- `mcp` - Model Context Protocol framework
- `httpx` - Async HTTP client for APIs
- `pydantic` - Data validation
- `diskcache` - Persistent API caching

## Smogon Data Source

Usage stats are pulled from Smogon's chaos JSON files:
- **URL**: `https://www.smogon.com/stats/{YYYY-MM}/chaos/{format}-{rating}.json`
- **Rating**: 0 (all competitive players - broadest dataset)
- **Available ratings**: 0, 1500, 1630, 1760
- **Auto-detection**: Finds latest available month automatically

## Damage Calculation Output Format

When presenting damage calculation results to users, format them as markdown tables for readability:

**Header format:**
```
Your [Pokemon Name]
[Nature] | [HP] HP / [Atk] Atk / [Def] Def / [SpD] SpD / [Spe] Spe | [Item]
```

**Damage dealt table:**
| Target | Their Spread | Item | Damage | Result |
|--------|--------------|------|--------|--------|
| Rillaboom | Adamant 252/116/4/0/60/76 | Assault Vest | 130-154% | OHKO |

**Damage taken table:**
| Attacker | Their Spread | Item | Move | Damage |
|----------|--------------|------|------|--------|
| Tornadus | Timid 36/0/12/204/4/252 | Covert Cloak | Bleakwind Storm | 85-100% |

**Result column values:**
- OHKO (guaranteed one-hit KO)
- X% OHKO (probability)
- 2HKO, 3HKO for multi-hit KOs
- "Resists" for low damage (<30%)

**Include a "Key Takeaways" section** summarizing:
- Biggest threats (moves that can OHKO or come close)
- Pokemon you OHKO reliably
- Notable type resistances/immunities
- Weather/terrain interactions

## Showdown Paste Export

All tools that return Pokemon spreads now include Showdown paste format for easy copy-paste into Pokemon Showdown.

### Field Names

Tools use consistent field naming for Showdown paste output:

- **`showdown_paste`** - Single recommended spread
- **`attacker_showdown_paste`** - Attacker's spread in damage calculations
- **`defender_showdown_paste`** - Defender's spread in damage calculations
- **`current_showdown_paste`** - Before optimization
- **`optimized_showdown_paste`** - After optimization

### Tools with Showdown Output

**Spread Optimization Tools** (spread_tools.py):
- `suggest_nature_optimization` - Returns `current_showdown_paste` and `optimized_showdown_paste`
- `suggest_spread` - Returns `showdown_paste`
- `optimize_bulk` - Returns `showdown_paste`
- `optimize_bulk_math` - Returns `showdown_paste`
- `check_spread_efficiency` - Returns `showdown_paste` for analyzed spread
- `design_spread_with_benchmarks` - Returns `showdown_paste`
- `optimize_dual_survival_spread` - Returns `showdown_paste`

**Damage Calculation Tools** (damage_tools.py):
- `calculate_damage_output` - Returns `attacker_showdown_paste` and `defender_showdown_paste`
- `find_survival_evs` - Returns `defender_showdown_paste`
- `find_ko_threshold` - Returns `attacker_showdown_paste`

### Usage for LLM - CRITICAL INSTRUCTIONS

**PRIMARY OUTPUT FORMAT**: When any tool returns a `*_showdown_paste` field, you MUST display it prominently in a code block as the main output. Showdown paste is not a secondary detail - it's what users came for.

**Response Structure Template:**
1. Brief context (1-2 sentences about what the spread does)
2. **Showdown Paste in code block** ← THE MAIN EVENT
3. Copy-paste instruction
4. Optional: Technical details (stats, analysis) if relevant

**Formatting Rules:**
- ✅ ALWAYS put Showdown paste in triple-backtick code blocks
- ✅ ALWAYS include the copy-paste instruction
- ✅ Make Showdown paste the focal point - it should be immediately visible
- ❌ DON'T bury Showdown paste after paragraphs of text
- ❌ DON'T show raw EV dicts (like `{"hp": 252, "attack": 4, ...}`) when Showdown paste exists
- ❌ DON'T make users dig through JSON to find the paste

**Copy-Paste Instruction (use this exact phrasing):**
> "Copy this and paste it directly into Pokemon Showdown's teambuilder."

### Showdown Format Details

The Showdown paste format includes:
- **Species name** (with form if applicable, e.g., "Urshifu-Rapid-Strike")
- **Item** after @ symbol (omitted if none)
- **Ability** line (omitted if none)
- **Level** (defaults to 50 for VGC, only shown if different)
- **EVs** line showing non-zero values only (e.g., "EVs: 252 HP / 4 Def / 252 Spe")
- **Nature** line (e.g., "Adamant Nature")
- **IVs** line only if non-31 values exist (e.g., "IVs: 0 Atk" for special attackers)
- **Moves** with - prefix (omitted if none)
- **Tera Type** line (omitted if none)

Missing data is handled gracefully - tools will include whatever information is available. If a spread doesn't have an ability, item, or moves specified, those lines are simply omitted from the paste.

### Response Templates by Tool Type

#### Template 1: Single Spread Recommendation (suggest_spread, optimize_bulk, etc.)

User: "What's a good offensive spread for Landorus?"

**Response Format:**
```
Here's a max Attack & Speed offensive Landorus spread:

```
Landorus
EVs: 4 HP / 252 Atk / 252 Spe
Jolly Nature
```

Copy this and paste it directly into Pokemon Showdown's teambuilder.

**Why this spread:**
- Maximizes Attack and Speed for sweeping
- Jolly nature outspeeds most threats
- 4 HP EVs for slight bulk
- Final stats: 166 HP / 197 Atk / 110 Def / 115 SpD / 169 Spe
```

#### Template 2: Nature Optimization (suggest_nature_optimization)

User: "Can I use a different nature to save EVs?"

**Response Format:**
```
Yes! You can save 8 EVs by switching to Jolly nature.

**Current Spread:**
```
Landorus
EVs: 4 HP / 252 Atk / 252 Spe
Serious Nature
```

**Optimized Spread (saves 8 EVs):**
```
Landorus
EVs: 4 HP / 244 Atk / 252 Spe
Jolly Nature
```

Copy the optimized spread above and paste it into Pokemon Showdown's teambuilder.

**What changed:**
- Jolly's +Spe boost lets you reach the same Speed with fewer EVs
- Same final stats, but you save 8 EVs to invest elsewhere
- Could add those 8 EVs to Def or SpD for extra bulk
```

#### Template 3: Damage Calculations (calculate_damage_output, find_survival_evs)

User: "Does Urshifu OHKO Ogerpon?"

**Response Format:**
```
No, Urshifu does NOT OHKO Ogerpon.

**Attacker:**
```
Urshifu-Rapid-Strike @ Choice Scarf
Ability: Unseen Fist
EVs: 4 HP / 252 Atk / 252 Spe
Adamant Nature
```

**Defender:**
```
Ogerpon-Hearthflame @ Hearthflame Mask
EVs: 252 HP / 4 Def / 252 Spe
Jolly Nature
```

**Damage:** Surging Strikes deals 67.4-78.6% (126-147 damage to 187 HP)
**Result:** Ogerpon survives with 21-33% HP remaining

Copy either spread above to paste into Pokemon Showdown's teambuilder.
```

#### Template 4: Survival Spread (find_survival_evs)

User: "What EVs does Ogerpon need to survive Urshifu?"

**Response Format:**
```
Ogerpon needs **252 HP / 4 Def** to survive Adamant Choice Scarf Urshifu's Surging Strikes.

**Recommended Spread:**
```
Ogerpon-Hearthflame @ Hearthflame Mask
EVs: 252 HP / 4 Def / 252 Spe
Jolly Nature
```

Copy this and paste it directly into Pokemon Showdown's teambuilder.

**Matchup Details:**
- **Attacker:** Adamant 4/252/0/0/0/252 Urshifu-Rapid-Strike @ Choice Scarf
- **Damage:** 67.4-78.6% (126-147 to 187 HP)
- **Survival:** You live with 21-33% HP remaining
```

#### Template 5: Offensive Threshold (find_ko_threshold)

User: "How much Attack do I need to OHKO Rillaboom?"

**Response Format:**
```
You need **196 SpA EVs** to guarantee OHKO Rillaboom with Moonblast.

**Recommended Spread:**
```
Flutter Mane
Ability: Protosynthesis
EVs: 196 SpA / 60 Def / 252 Spe
Timid Nature
```

Copy this and paste it directly into Pokemon Showdown's teambuilder.

**Matchup:**
- Target: Adamant 252/116/4/0/60/76 Rillaboom @ Assault Vest
- Damage: 101.2-119.8% (guaranteed OHKO)
- You have 56 EVs left over to invest in bulk or other stats
```

## Tool Selection Guide

### For Survival Questions ("Can X survive Y?", "What EVs to survive?")

Use the RIGHT tool for survival calculations:

1. **find_survival_evs** - Find minimum HP/Def EVs to survive an attack
   - Auto-fetches attacker's Smogon spread (nature, EVs, item)
   - Returns required defensive EVs + damage calculation
   - Use when: "What EVs does Ogerpon need to survive Urshifu?"
   - **ALWAYS show the attacker_spread_info in your response**

2. **calculate_damage_output** - Check exact damage with specific spreads
   - Use when verifying a specific spread survives
   - Shows damage percentage against multiple common defender spreads
   - **ALWAYS show the attacker_spread field so user knows what was assumed**

3. **design_spread_with_benchmarks** - Complex spread with speed + survival
   - Use when: "Design a spread that outspeeds X AND survives Y"
   - Handles Tera, Tailwind, Booster Energy, speed stages

4. **optimize_multi_survival_spread** - Optimize spread to survive 3-6 different threats
   - Use when: "Design a spread that survives Urshifu, Flutter Mane, AND Chi-Yu"
   - Handles multiple attackers simultaneously (3-6 Pokemon)
   - Auto-fetches Smogon spreads for all attackers
   - Reports impossibility with suggestions if no spread can survive all threats
   - **Performance:** 3 threats ~5s, 6 threats ~20s
   - **For 2 threats only**, use `optimize_dual_survival_spread` instead (faster)

### Multi-Threat Survival Optimization

The `optimize_multi_survival_spread` tool extends dual survival optimization to handle 3-6 threats.

**When to Use:**
- User wants to survive THREE OR MORE different attacks
- Examples: "survive Urshifu, Flutter Mane, AND Chi-Yu", "live through the top 4 meta threats"
- For only 2 threats, use `optimize_dual_survival_spread` instead

**Threat List Format:**
```python
threats = [
    {
        "attacker": "urshifu-rapid-strike",
        "move": "surging-strikes",
        # Optional overrides (auto-fetched if not specified):
        "nature": "adamant",
        "evs": 252,
        "item": "choice-scarf",
        "ability": "unseen-fist",
        "tera_type": "dark"  # If Tera active
    },
    {
        "attacker": "flutter-mane",
        "move": "moonblast"
        # Auto-fetches Smogon spread, item, ability
    },
    {
        "attacker": "chi-yu",
        "move": "heat-wave",
        "tera_type": "fire"
    }
]
```

**Example Usage:**
```
User: "Design a spread for Ogerpon-Hearthflame that survives Urshifu, Flutter Mane, and Chi-Yu"

LLM Response:
```python
result = await optimize_multi_survival_spread(
    pokemon_name="ogerpon-hearthflame",
    defender_tera_type="fire",
    threats=[
        {"attacker": "urshifu-rapid-strike", "move": "surging-strikes"},
        {"attacker": "flutter-mane", "move": "moonblast"},
        {"attacker": "chi-yu", "move": "heat-wave", "tera_type": "fire"}
    ],
    outspeed_pokemon="tornadus",  # Optional speed benchmark
    target_survival=93.75  # Default: survive max roll only
)
```

**Output Format (Success):**
```
Here's an optimized spread that survives all 3 threats:

```
Ogerpon-Hearthflame @ Hearthflame Mask
EVs: 180 HP / 116 Def / 60 SpD / 152 Spe
Impish Nature
```

Copy this and paste it directly into Pokemon Showdown's teambuilder.

**Threat Survival Breakdown:**
| Threat | Spread | Damage | Survival |
|--------|--------|--------|----------|
| Urshifu Surging Strikes | Adamant 252 Atk Choice Scarf | 67-79% | 100% |
| Flutter Mane Moonblast | Timid 252 SpA Choice Specs | 81-96% | 93.75% |
| Chi-Yu Heat Wave (Tera Fire) | Timid 252 SpA Choice Specs | 72-85% | 100% |

**Final Stats:** 186 HP / 142 Def / 110 SpD / 143 Spe
```

**Output Format (Impossible):**
```
Unfortunately, no EV spread can survive all 4 threats simultaneously.

**Individual Requirements:**
- Urshifu Surging Strikes: 280 EVs (HP+Def) minimum
- Flutter Mane Moonblast: 224 EVs (HP+SpD) minimum
- Chi-Yu Heat Wave: 312 EVs (HP+SpD) minimum
- Tornadus Bleakwind Storm: 196 EVs (HP+SpD) minimum

**Suggestions:**
1. Drop Chi-Yu (hardest single threat - requires 312 EVs alone)
2. Use Tera Fairy to resist Dark/Fighting and survive all 4
3. Best 3-threat combo: Urshifu + Flutter Mane + Tornadus (140 EVs spare)
```

**Performance Notes:**
- 3 threats: 3-8 seconds typical
- 4 threats: 8-15 seconds typical
- 5-6 threats: 15-30 seconds typical
- Uses damage caching for efficiency (7x speedup)

## Intelligent Nature Selection

### Automatic Nature Optimization

When calling spread tools with benchmark requirements, you can omit the `nature`
parameter to enable intelligent auto-selection:

```python
# Auto-selects optimal nature (Adamant for this case)
result = await design_spread_with_benchmarks(
    pokemon_name="entei",
    outspeed_pokemon="chien-pao",
    prioritize="offense",
    offensive_evs=252
)
# Result: Adamant nature, 132 Speed EVs, 132 Attack EVs → 167 Attack
```

The optimizer tests all relevant natures and chooses the one that:

1. **Meets all benchmarks** (speed targets, survival requirements)
2. **Maximizes total stats** in key areas (Attack/SpA + Speed + HP)
3. **Minimizes wasted EVs** from nature penalties

**Example - Entei Optimization:**

**Goal:** 137 Speed (outspeed -1 Chien-Pao), maximize Attack

**Bad (Timid nature):**
- Timid (+Spe/-Atk): 36 Speed EVs, 228 Attack EVs → 147 Attack
- Suffers -10% Attack penalty, wastes 20 stat points

**Optimal (Adamant nature):**
- Adamant (+Atk/-SpA): 132 Speed EVs, 132 Attack EVs → 167 Attack
- Gains +10% Attack boost, maximizes Attack while hitting speed benchmark

**Result:** 20 stat points saved by choosing the right nature!

### When to Specify Nature Explicitly

Specify `nature` parameter when:

- **User has strong preference** for a specific nature
- **Building for specific format rules** (e.g., Nature Clause in some formats)
- **Testing "what-if" scenarios** with different natures
- **Trick Room teams** (user wants minimum speed, not maximum)

### Tools with Auto-Selection

These tools support intelligent nature selection when `nature=None`:

1. **design_spread_with_benchmarks** - Speed + survival benchmarks
2. **suggest_spread** - Role-based spread suggestions (offensive role)
3. **optimize_dual_survival_spread** - Dual survival optimization
4. **optimize_multi_survival_spread** - Multi-threat survival (3-6 threats)

All tools return `nature_selection_reasoning` field when nature is auto-selected,
explaining why the chosen nature is optimal.

### Survival Rate Interpretation

When users ask about survival, interpret their intent correctly:

**Default (no qualifier specified):**
- "Can X survive Y?" → 93.75% survival (survive max roll only)
- "What EVs to survive Z?" → 93.75% survival (minimal EV investment)
- This is OPTIMAL - leaves more EVs for offense, speed, or other stats

**User Specifies Guaranteed Survival:**
- "Guarantee survival" → 100% (all 16 rolls)
- "Always survive" → 100%
- "Never die to X" → 100%
- "100% survival" → 100%

**User Specifies Partial Survival:**
- "Survive sometimes" → 75% (12/16 rolls)
- "Survive most of the time" → 87.5% (14/16 rolls)
- "Live through it usually" → 87.5%
- "50/50 chance" → 50% (8/16 rolls)

**User Specifies Exact Percentage:**
- "37.5% of the time" → 37.5%
- "At least 80%" → 81.25% (next valid tier: 13/16 rolls)

**Understanding Survival Percentages:**

Pokemon damage has **16 possible rolls** based on RNG (85% to 100% of base damage):

| Survival % | Rolls Survived | Meaning |
|------------|----------------|---------|
| **93.75%** | 15/16 | Survive max roll only - **DEFAULT & RECOMMENDED** |
| 87.5% | 14/16 | Can die to 2 highest rolls |
| 81.25% | 13/16 | Can die to 3 highest rolls |
| 75% | 12/16 | Can die to 4 highest rolls |
| 100% | 16/16 | Guaranteed survival (wastes EVs) |

**When calling `find_survival_evs`:**
- Use the `target_survival_chance` parameter with the appropriate value
- Default 93.75% is optimal for competitive play
- Only use 100% when user explicitly requests guaranteed survival

### Common Mistakes to Avoid

- **DON'T give offensive spreads when asked about survival** - If user asks "what spread survives X?", return defensive EVs (HP/Def), not offensive (Atk/Spe)
- **ALWAYS show the FULL attacker spread with EVs** - Don't just say "Adamant Choice Scarf Urshifu", say "Adamant 4 HP / 252 Atk / 252 Spe Choice Scarf Urshifu"
- **Understand damage calc notation**: "252 Atk" = neutral nature, "252+ Atk" = boosting nature (Adamant)
- **Don't hallucinate numbers** - If the tool returns 81.8-96.2%, don't say 81.2-98.7%
- **DON'T hide Showdown paste** - If a tool returns `showdown_paste` or `*_showdown_paste` fields, display them prominently. Don't just mention "the spread is X EVs" - SHOW the paste.
- **DON'T show raw EV dictionaries** - Users don't want `{"hp": 252, "attack": 4, ...}`. They want the Showdown format they can copy.
- **DON'T make users ask twice** - If they ask for a spread, give them the Showdown paste immediately, not just stats.

### CRITICAL: Always Show Full Spreads for BOTH Pokemon

When reporting damage calculations, ALWAYS include the full EV spread for BOTH the attacker AND the defender. The tool response includes `attacker_ev_spread` and defender spread info - USE THEM.

**Every damage calculation response MUST include:**

```
**Attacker:** [Nature] [HP]/[Atk]/[Def]/[SpA]/[SpD]/[Spe] [Pokemon] @ [Item]
**Defender:** [Nature] [HP]/[Atk]/[Def]/[SpA]/[SpD]/[Spe] [Pokemon] @ [Item]
**Result:** [damage range]% ([verdict])
```

**Example - Correct Format:**
```
**Attacker:** Adamant 4/252/0/0/0/252 Urshifu-Rapid-Strike @ Choice Scarf
**Defender:** Jolly 252/0/4/0/0/252 Ogerpon-Hearthflame @ Hearthflame Mask
**Result:** 67.4-78.6% (survives with 21-33% HP remaining)
```

**Bad - Missing Information (DON'T DO THIS):**
```
You survive Adamant Choice Scarf Urshifu with 252 HP.
[Missing: Urshifu's EVs, Ogerpon's full spread, item info]
```

The user needs the EXACT spreads for both Pokemon to verify calculations themselves.

### Example: Correct Survival Response

User: "What EVs does Ogerpon need to survive Urshifu Surging Strikes?"

Good response:
```
**Attacker:** Adamant 4/252/0/0/0/252 Urshifu-Rapid-Strike @ Choice Scarf
**Defender:** Jolly 252/0/4/0/0/252 Ogerpon-Hearthflame @ Hearthflame Mask

Surging Strikes deals 67.4-78.6% (126-147 damage to 187 HP).
You survive with 21-33% HP remaining.
```

Bad response (DON'T DO THIS):
```
You survive Adamant Choice Scarf Urshifu with 252 HP / 4 Def.
[Missing the attacker's EVs! User can't verify the calculation.]
```

## User Onboarding

### When Users Say "Hi" or Greet
**IMPORTANT:** When a user greets you (Hi, Hello, Hey, etc.) or asks what you can do,
you MUST call the `welcome_new_user()` tool to show them the welcome message and
starter prompts. Do NOT manually type the welcome message - always use the tool.

This ensures consistent onboarding and shows users the available capabilities.

### Example Prompts to Share

**Damage Calculations:**
- "Does my Flutter Mane OHKO Incineroar with Moonblast?"
- "Can Amoonguss survive Flutter Mane's Moonblast?"
- "What's the damage range for Landorus EQ vs Rillaboom?"
- "Check damage with Tera active"

**Team Building:**
- "Help me build a Rain team"
- "What Pokemon pair well with Flutter Mane?"
- "Analyze my team: [Showdown paste]"
- "What are my team's weaknesses?"

**EV Optimization:**
- "What EVs does Incineroar need to survive Flutter Mane?"
- "Is my spread efficient? Suggest a better nature"
- "Find bulk EVs to survive multiple threats"
- "Optimize my Dragonite's EVs"

**Speed Analysis:**
- "Is my Landorus faster than Tornadus?"
- "What speed tier is 252 Spe Timid Flutter Mane?"
- "Show speed tiers under Tailwind"
- "Compare speeds with different natures"

**Learning VGC:**
- "Explain what EVs are"
- "What makes Flutter Mane good?"
- "Explain Fire type matchups"
- "What does STAB mean?"
- "Explain Trick Room"

**Nature Optimization:**
- "Can I save EVs with a different nature?"
- "Suggest nature optimization for my spread"
- "Is Serious nature optimal?"

### Common User Flows

1. **New User**: "I'm new to VGC" → Show capabilities → Suggest beginner team
2. **Team Building**: "Build a team around [Pokemon]" → Suggest core → Add support → Check weaknesses
3. **Damage Check**: "Does X OHKO Y?" → Calculate → Show transparent breakdown
4. **EV Optimization**: "What EVs to survive X?" → Calculate bulk → Suggest spread
5. **Learning**: "Explain [term]" → Show glossary entry → Provide examples
