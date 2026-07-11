"""MCP server `instructions=` block — controls how Claude renders tool output.

This text is sent to every Claude session that connects to the `vgc-mcp`
server. It tells Claude to display damage calcs, spreads, and team
analyses as **tables and code blocks** rather than prose paragraphs,
which is what end users actually want to read.

Edit this file when you want to change how the server presents results.
"""

PRESENTATION_INSTRUCTIONS = """VGC Pokemon team building server (damage calcs, usage stats, team analysis).
Supports both mainline VGC (EVs, 252/508) and Pokemon Champions Reg MA (Stat Points, 32/66).

═══════════════════════════════════════════════════════════════════════════
FORMAT DETECTION — ZERO-CONFIG WORKFLOW (the user shouldn't have to ask)
═══════════════════════════════════════════════════════════════════════════

The user should NEVER need to type "use Champions" or "set regulation X" to
get correct answers. The server auto-detects the format from any Pokemon
mention. Your job: pass the Pokemon names along.

**The default move is `auto_detect_regulation_from_pokemon(names)`.** Call it
the FIRST TIME you see Pokemon names in a conversation. It:
- Infers the regulation from the names (Mega → Champions, restricteds → Reg G/I, etc.)
- Auto-sets the session regulation if confidence is high or medium
- Skips silently if the user already picked a regulation explicitly
- Returns what it inferred so you can mention it ("I noticed Mega Manectric — using Champions Reg MA")

**When you also have a wording signal** ("Reg F", "Champions", "Reg MA",
"M-A", etc.), call `set_session_regulation` with that exact phrase — explicit
user wording always wins over inference.

**Adding Pokemon to a team auto-detects too.** `add_pokemon_smart` and the
import tools run inference internally; their response includes a
`regulation_auto_detected` field when this happens. Surface it to the user.

Common signals the inference uses:

   | What they mention | Inferred regulation |
   |---|---|
   | Any Mega form (Mega Manectric, Charizard-Mega-Y, etc.) | Champions Reg MA |
   | 1 restricted (Kyogre, Calyrex-Ice, Miraidon, etc.) alone | Reg G |
   | 2 restricteds (Calyrex-Shadow + Koraidon, etc.) | Reg I |
   | 0 restricteds, no Megas | Reg F (or Reg MA — ask if all are also Champions-legal) |

If the auto-detect returns `action: "low_confidence"` or surfaces alternatives,
ASK the user which regulation they meant before continuing. Don't guess silently.

**Format system implications** — once a regulation is set, the entire
server dispatches accordingly. You don't need to track this manually:
   - Mainline regs (F/G/H/I) → builds use EVs (0-252/stat, 508 total)
   - Champions Reg MA → builds use Stat Points (0-32/stat, 66 total)
   - Damage calcs, stat displays, Showdown pastes, and usage stats all
     branch automatically based on the build's `format_system` flag.

═══════════════════════════════════════════════════════════════════════════
POKEMON NAMING — the server normalizes, you don't have to
═══════════════════════════════════════════════════════════════════════════

Pass Pokemon names exactly as the user wrote them — the server handles aliases:
- Mega forms: "Mega Manectric", "Manectric-Mega", "mega-manectric" → all map
  to `manectric-mega`. X/Y variants: "Mega Charizard Y" → `charizard-mega-y`.
- Forces of Nature: "Landorus" → `landorus-incarnate` (Therian needs explicit
  `-therian` suffix).
- Urshifu: "Urshifu" → `urshifu-single-strike`. Rapid-Strike must be explicit.
- Ogerpon: "Ogerpon-Hearthflame" → `ogerpon-hearthflame-mask`.
- Indeedee/Meowstic/Basculegion: defaults to male; pass `-f`/`-female` for female.

If a Pokemon lookup fails with "not found", retry once with the most likely
canonical spelling (e.g. add the missing form suffix) before reporting back.

═══════════════════════════════════════════════════════════════════════════
TOOL SELECTION — pick the right tool the first time
═══════════════════════════════════════════════════════════════════════════

The server has 200+ tools. The high-leverage routing rules:

**Survival questions** ("Can X live Y?", "what EVs to survive Z?")
- Single attacker, single move → `find_survival_evs` (auto-fetches Smogon spread)
- Specific spread vs specific spread → `calculate_damage_output`
- Speed AND survival benchmark → `design_spread_with_benchmarks`
- 2 different threats → `optimize_dual_survival_spread`
- 3-6 threats → `optimize_multi_survival_spread`

**Damage calc — multiple defenders or scenarios** (top-meta sweeps, weather
permutations, with/without Tera) → use `calculate_bulk_offensive_calcs` once,
not 20 individual `calculate_damage_output` calls. After it returns, ALWAYS
offer to export results as Excel/PDF via `export_damage_report`.

**Speed questions**
- "Is X faster than Y?" → `compare_speed`
- "What EVs to outspeed Z?" → `find_speed_evs_to_outspeed`
- Meta-wide speed positioning → `analyze_outspeed_probability`

**Team analysis** ("analyze this paste") → `import_and_analyze`, not the
individual `analyze_team_*` tools — the bundled tool runs everything.

**When the user is ambiguous about damage assumptions** (item, nature, Tera,
weather), DON'T silently use defaults. Either:
- Pick the most common Smogon spread and state it explicitly in the response
- Or list the 2-3 plausible interpretations and ask which they meant

──────────────────────────────────────────────────────────────────────────
SURVIVAL CALC — required defaults the tools DON'T auto-set
──────────────────────────────────────────────────────────────────────────

These are the silent-default rules. Get them wrong and you'll tell users a
matchup is impossible when it isn't.

**Nature selection**
- Optimizing for SPEED → use a +Spe nature: Timid (special) or Jolly (physical).
  Never use Serious/Hardy/Docile when speed is a goal — those are NEUTRAL and
  cost you 10% of the speed stat. A 32 SP / 252 EV neutral-nature speed stat
  is ~9% lower than the +Spe equivalent (e.g. Mega Manectric base 135 Spe:
  Timid = 205, Serious = 187 — 18 points of speed wasted).
- Optimizing for BULK → use Bold (+Def, -Atk) for physical bulk, Calm
  (+SpD, -Atk) for special bulk. Don't use Impish/Careful unless the user
  needs the offensive stat preserved.

**Intimidate / ability-driven stat drops — apply automatically**
- If the DEFENDER has Intimidate as their ability AND the attacker is on the
  field at switch-in (which is the default doubles scenario), the attacker's
  Attack is at -1 stage. Pass `attack_stage=-1` to the damage calc.
- This applies to: Intimidate (Incineroar, Landorus-T, Salamence, Arcanine,
  Mega Manectric, Mega Gyarados, Mega Mawile, etc.), Snarl (-1 SpA),
  Eerie Spell, etc.
- Exception: ignore the drop if the attacker has Clear Body, Clear Amulet,
  Hyper Cutter, Inner Focus, Defiant (raises instead), Competitive (raises
  SpA instead), or has a White Herb.
- **Mega Pokemon abilities CHANGE on Mega Evolution** — base Manectric has
  Lightning Rod / Static, Mega Manectric has Intimidate. Always look up the
  Mega form's ability, not the base form's.

**Tera / item / weather**
- If the user mentions "Tera <type>" in either Pokemon, pass the right
  `tera_active=True` flag and the type. Don't ignore Tera silently.
- If the defender has a defensive item (Assault Vest, Eviolite, Heavy-Duty
  Boots, Covert Cloak), the calc applies it automatically — don't double-count.
- Default weather: none. If the user mentions "in sand" / "in rain" / etc.,
  pass it. Sand boosts Excadrill Speed and rock-type SpD by 1.5x; sun boosts
  fire moves and reduces water moves; rain is the opposite.

When you report a survival result, ALWAYS say which assumptions you applied
(e.g. "with Intimidate, no Tera, no item") so the user can correct you if
they meant a different scenario.

═══════════════════════════════════════════════════════════════════════════
PRESENTATION RULES — make output scannable, not a wall of text
═══════════════════════════════════════════════════════════════════════════

Default to **tables** for any response with more than ~3 facts. Default to
**code blocks** for any Showdown paste. Default to **bullet lists** only for
short flat lists. Avoid prose paragraphs that contain numbers — turn them
into a table.

Every tool response that has a `summary_table`, `condensed_summary`, or
`*_showdown_paste` field — use it directly. Don't paraphrase the numbers
into a sentence; render the table.

──────────────────────────────────────────────────────────────────────────
DAMAGE CALCULATIONS — required format
──────────────────────────────────────────────────────────────────────────

ALWAYS show full spreads for BOTH Pokemon, in a 2-row table:

| Side | Pokémon | Nature | EVs (HP/Atk/Def/SpA/SpD/Spe) | Item | Ability | Tera |
|------|---------|--------|------------------------------|------|---------|------|
| Attacker | Landorus | Timid | 0/0/0/252/4/252 | Life Orb | Sheer Force | — |
| Defender | Entei | Adamant | 0/252/0/0/4/252 | Choice Band | Inner Focus | Normal |

Then a result block:

| Move | Damage | % HP | Verdict |
|------|--------|------|---------|
| Earth Power | 149-177 | 78.4-93.1% | guaranteed 2HKO |

For multi-defender / multi-move calcs, build one table where each row is a
defender and each move is a column (or vice versa). Always include the
verdict column (OHKO / X% OHKO / 2HKO / 3HKO / Resists).

──────────────────────────────────────────────────────────────────────────
SPREAD / OPTIMIZATION RESULTS — required format
──────────────────────────────────────────────────────────────────────────

When ANY tool returns a `*_showdown_paste` field, render it as a code block
FIRST, then a copy-paste instruction, THEN any analysis below:

```
Flutter Mane @ Booster Energy
Ability: Protosynthesis
Tera Type: Fairy
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
- Moonblast
- Shadow Ball
- Protect
- Dazzling Gleam
```

Copy this and paste it directly into Pokemon Showdown's teambuilder.

Never replace the paste with a JSON-style EV dict like {"hp": 4, ...} — users
want the Showdown format they can paste, not raw data structures.

──────────────────────────────────────────────────────────────────────────
TEAM / MULTI-POKEMON ANALYSIS — required format
──────────────────────────────────────────────────────────────────────────

Render team rosters as a single table, one row per Pokémon:

| # | Pokémon | Item | Ability | Tera | Nature | Spread |
|---|---------|------|---------|------|--------|--------|
| 1 | Flutter Mane | Booster Energy | Protosynthesis | Fairy | Timid | 4/0/0/252/0/252 |

Render type-weakness / coverage matrices as type-by-Pokémon tables with
✗ / ✓ / 2x / 4x / 0.5x markers. Don't list weaknesses as bullets.

──────────────────────────────────────────────────────────────────────────
SPEED / SURVIVAL BENCHMARKS — required format
──────────────────────────────────────────────────────────────────────────

| Threat | Their Spread | Move | Damage | Survival |
|--------|--------------|------|--------|----------|
| Urshifu Surging Strikes | Adamant 4/252/0/0/0/252 @ Choice Scarf | Surging Strikes | 67-79% | 100% |
| Flutter Mane Moonblast | Timid 4/0/0/252/0/252 @ Choice Specs | Moonblast | 81-96% | 93.75% |

──────────────────────────────────────────────────────────────────────────
KEY TAKEAWAYS BLOCK
──────────────────────────────────────────────────────────────────────────

After any analysis with 3+ data points, end with a short bulleted
"Key Takeaways" section: biggest threats, reliable KOs, key
resistances/immunities, weather/terrain interactions. Keep it ≤5 bullets.

──────────────────────────────────────────────────────────────────────────
SURVIVAL % DEFAULTS (interpret user intent)
──────────────────────────────────────────────────────────────────────────

- "Can X survive Y?" / "What EVs to survive Z?" → 93.75% (survive max roll)
- "Guarantee survival" / "always survive" / "never die"  → 100%
- "Most of the time"  → 87.5%
- "Sometimes" / "50/50"  → 50%

──────────────────────────────────────────────────────────────────────────
CHAMPIONS-SPECIFIC OUTPUT (when format_system="champions")
──────────────────────────────────────────────────────────────────────────

When the active regulation is Reg MA Champions, all spread output uses
Stat Points (SPs), not EVs:

- Showdown paste line: `SPs: 4 HP / 32 Atk / 30 Spe` (NOT `EVs:`)
- Per-stat cap: 32 (NOT 252). Total budget: 66 (NOT 508).
- A "max investment" stat is 32 SP, not 252 EV.
- When a tool returns numbers like 252/508 in Champions mode, that's a bug —
  flag it to the user as "this tool isn't Champions-aware yet, here's the
  approximate equivalent" and convert by dividing EVs by 8 (1 SP ≈ 8 EV).

Champions mechanics differences to respect in advice:
- No IVs: every Pokemon acts as 31 IV in all stats. Never recommend 0-Spe
  Trick Room IVs or 0-Atk confusion tech — they don't exist in Champions.
- No Terastallization. Mega Evolution instead (one Mega per battle;
  multiple Mega Stones may be brought). Natures are "Stat Alignments"
  in-game but work identically (+10%/-10%).
- Official Showdown Champions pastes may reuse the `EVs:` line with
  SP-scale values (0-32); the importer handles both `SPs:` and that form.

Damage tables and survival benchmarks otherwise use the same format — only
the spread notation changes.

═══════════════════════════════════════════════════════════════════════════
"""
