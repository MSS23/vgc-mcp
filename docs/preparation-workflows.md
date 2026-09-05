# Verified preparation over MCP

The upgrade adds five MCP tools, bringing the server to 213 tools in 52 modules.
They work through the existing Claude/MCP connection and both stdio and HTTP
transports. No frontend or replay-analysis upgrade is part of this change.

## Ask Claude

- “Prepare this team against the six most common threats in Reg I: [Showdown paste].”
- “Verify that this spread survives this attack 100% of the time.”
- “Give me minimum-investment, offensive and bulky alternatives that meet these benchmarks.”
- “What is Population Bomb's KO chance including misses, with and without Loaded Dice?”
- “Save this complete reference team with its source, then compare it with chaos usage.”
- “Export the preparation report as an Excel spreadsheet.”

Select the regulation explicitly or use the existing session regulation tools.
The preparation tools keep the user's active team unchanged.

## Tools

| Tool | Purpose |
|---|---|
| `prepare_team` | Paste/current team → configured rules checks, raw speed tiers, common-threat damage, dated source, Markdown report and optional file export |
| `verify_spread_benchmarks` | Check the final build against explicit survival, KO and speed constraints |
| `recommend_verified_spreads` | Return three alternatives with exact final verification, full pastes and stat tradeoffs |
| `calculate_move_outcomes` | Include independent rolls, accuracy, variable hit counts and supported sequential effects |
| `import_reference_team` | Store complete attributed sets separately from chaos components for the current MCP session |

### Benchmark inputs

Each benchmark requires `kind` (`survive`, `ko`, or `outspeed`) and exactly one
of `opponent_paste` or `opponent_name`. Damage benchmarks also require `move`.
An opponent name loads a common spread from a dated chaos dataset; a paste fixes
the exact opponent. `probability` is a percentage: the survival default is 93.75,
while KO defaults to 100. Explicit `100` means guaranteed under the stated model.

`conditions` accepts validated `DamageModifiers` fields, for example
`{"weather": "rain", "multiple_targets": true}`. Unknown fields, out-of-range
stages, unsupported weather/terrain and Champions Terastallization are rejected.
Speed benchmarks use explicit `speed_multiplier` and
`opponent_speed_multiplier`, including any intended item/ability/speed-control
effects. They compare Speed, not move priority or turn order under Trick Room.

For `prepare_team`, pass `benchmarks_by_slot` to obtain improvements in the same
report. Slots are **one-based**:

```json
{
  "regulation": "reg_i",
  "meta_limit": 6,
  "benchmarks_by_slot": {
    "1": [
      {"kind": "survive", "opponent_name": "rillaboom", "move": "wood-hammer", "probability": 100}
    ]
  },
  "export_format": "excel"
}
```

Supply `team_paste` alongside these arguments or load a team first. The report
includes separate candidate pastes; it never silently replaces the original.
Exports support `markdown`, `json`, `excel`, and `pdf`. Responses carry both a
server file path and base64 bytes so a remote client can make a downloadable file.

### Source integrity

Chaos remains the live source:
`https://www.smogon.com/stats/{month}/chaos/{format}-{rating}.json`.
Reports lock month, format and cutoff across their opponent fetches, keep
configured BO3/BO1 fallbacks within the selected regulation, and flag sources
older than two months. The data can be historical when a regulation is inactive.

Chaos gives **marginal frequencies**, not the joint usage of a complete set.
Generated opponents therefore report `kind: usage_components`. The nature and
allocation are drawn from an observed spread entry; item, ability and moves are
independently ranked. No combined-set frequency is invented.

`import_reference_team` requires an ability and four moves per Pokemon. Held
items may be absent. These complete sets retain the user-supplied source name
and optional URL, with `source_verified: false`. Imports are deduplicated, kept
within the MCP session, capped at 120 sets, and exposed separately by
`get_common_sets.complete_sets`. They are not automatically authenticated as
tournament results or mixed into usage frequencies.

### Mathematical scope

- Damage comparisons include 2,037 pinned exact-roll cases against
  `@smogon/calc 0.11.0`: 21 mechanic scenarios plus 2,016 deterministic
  stat/level variations. CI regenerates the fixtures to catch drift.
- Sequential outcomes preserve independent rolls, resistance/healing berry
  consumption, loss of Multiscale, Parental Bond's quarter-strength child,
  Focus Sash, Sturdy, Disguise, Stamina, Weak Armor and Power-Up Punch.
- Accuracy includes base move accuracy, Wide Lens, No Guard and the weather
  rules for Thunder, Hurricane and Blizzard. Loaded Dice/Skill Link and the
  35/35/15/15 distribution for ordinary 2–5-hit moves are handled separately.
- Traditional damage is conditional on the chosen hit count (maximum by
  default). The outcomes tool defaults to accuracy and random hit counts on.
  Damage ranges retain overkill and explicitly label net HP loss when berries
  heal. Repeated-use probabilities assume no switches or between-turn recovery.
- Benchmark alternatives preserve item, ability, moves, IVs and level, search
  a bounded set of natures/allocations, then verify the complete final build.
  The minimum is within the evaluated candidates; no result is not proof of
  global impossibility. Unrequested stats can fall, and those changes are shown.
- The Champions survival grid uses exact damage instead of defensive-ratio
  scaling. The exported build retains its ability, includes its Speed investment,
  and its final survival percentage is rechecked.
- This is not a complete battle simulator. Recoil/contact retaliation, random
  secondary effects, all accuracy effects, and every battle-event interaction
  are not simulated. Team matchup percentages are not battle-win probabilities.
- Preparation legality is explicitly scoped to configured species/restricted
  rules, clauses and allocation validation. It does not certify all move
  learnsets or event-specific availability. Speed flags compare raw stats.

## Verification and maintenance

The regression suite exercises MCP argument validation and serialization,
report generation, source locking, reference isolation, exports, exact final
paste round-trips and mathematical edge cases. Live tests additionally exercise
real PokeAPI and chaos data for Reg I and Champions MB. The post-deployment
verifier now fetches real common spreads and checks a deterministic damage
calculation, beyond registering tools and returning a welcome message.

Upgrade validation on 5 September 2026: **3,681 offline tests and 14 live tests**;
213 tools registered; local Streamable HTTP functional verification passed;
Ruff and regulation validation passed. The six new core/tool workflow files
pass strict typing. Existing project-wide typing debt fell from 1,284 to 1,150
findings, with the CI ratchet lowered to 1,150.

```bash
python -m pytest tests/ -q
python -m pytest tests/api/test_smogon_live.py -m integration -q
python scripts/build_catalog.py
python scripts/validate_regulations.py
python scripts/verify_production.py --base-url http://127.0.0.1:8000
```

The offline name snapshot fixes real chaos identifiers such as `partingshot`,
`parentalbond`, `grassysurge` and `chilanberry`. It contains 937 moves, 374
abilities and 2,223 items. Refresh it with `python scripts/generate_name_index.py`;
the snapshot records its source URLs and retrieval date. Runtime normalization
does not add a network dependency.

Regenerate oracle expectations with a separately installed, pinned calculator:

```bash
node scripts/generate_damage_audit.cjs /path/to/node_modules/@smogon/calc
node scripts/generate_damage_audit.cjs /path/to/node_modules/@smogon/calc --matrix
```

Primary mechanics references:
[Showdown hit loop](https://github.com/smogon/pokemon-showdown/blob/master/sim/battle-actions.ts),
[Showdown items](https://github.com/smogon/pokemon-showdown/blob/master/data/items.ts),
[Smogon calculator](https://github.com/smogon/damage-calc).
