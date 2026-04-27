"""MCP server `instructions=` block — controls how Claude renders tool output.

This text is sent to every Claude session that connects to the full
`vgc-mcp` server. It tells Claude to display damage calcs, spreads, and
team analyses as **tables and code blocks** rather than prose paragraphs,
which is what end users actually want to read.

The lite + micro flavors are out of scope here — they're being spun off
into their own project. Edit this file when you want to change how
the full server presents results.
"""

PRESENTATION_INSTRUCTIONS = """VGC Pokemon team building server (damage calcs, usage stats, team analysis).

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

═══════════════════════════════════════════════════════════════════════════
"""
