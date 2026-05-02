# Tool-Layer Format Dispatch Audit

Status snapshot of how each tool handles the dual format system
(`mainline` EVs vs `champions` SPs). Goal: every tool that builds or
emits a spread must produce SP-shaped output when the active regulation
is Champions, and EV-shaped output otherwise.

## Status legend

- **DISPATCHED** — tool reads `format_system` and emits the right shape
- **EV-ONLY** — tool hardcodes EV math; works fine for mainline, returns
  EV-shaped output for Champions users (confusing but not broken)
- **CONVERSION-ONLY** — tool builds in EVs internally but uses
  `build_dual_paste_payload` to emit both shapes
- **PURE READ** — tool only reads stats; format-agnostic by construction

## Hot-path tools (user-facing)

| Tool                            | File                          | Status            | Notes |
|---------------------------------|-------------------------------|-------------------|-------|
| `suggest_ev_spread`             | workflow_tools.py             | DISPATCHED        | Auto-detects format from Pokemon name; emits both pastes. Fixed 2026-05. |
| `design_spread_with_benchmarks` | spread_tools.py               | EV-ONLY           | Hot path for survival design. Highest ROI to migrate next. |
| `optimize_dual_survival_spread` | spread_tools.py               | EV-ONLY           | Dual-survival optimizer; same shape as multi-threat below. |
| `optimize_multi_survival_spread`| multi_threat_tools.py         | EV-ONLY           | Auto-fetches Smogon; consider attaching dual paste payload. |
| `suggest_spread`                | spread_tools.py               | EV-ONLY           | Role-based; safe to migrate via build_dual_paste_payload. |
| `optimize_bulk` / `_math`       | spread_tools.py               | EV-ONLY           | |
| `find_survival_evs`             | damage_tools.py               | EV-ONLY           | Returns `defender_showdown_paste`. |
| `find_ko_evs`                   | damage_tools.py               | EV-ONLY           | Returns `attacker_showdown_paste`. |
| `find_breakpoint`               | breakpoint_tools.py           | EV-ONLY           | Search granularity (4 EVs) becomes (1 SP) under Champions. |
| `calculate_damage_output`       | damage_tools.py               | DISPATCHED        | Reads `format_system` from PokemonBuild; calc.stats handles dispatch. |
| `quick_damage_check`            | workflow_tools.py             | DISPATCHED        | Same — uses calc.damage which auto-dispatches. |
| `analyze_speed_spread`          | speed_analysis_tools.py       | EV-ONLY           | Speed tier viz uses EV breakpoints. |
| `meta_outspeed_analysis`        | speed_analysis_tools.py       | EV-ONLY           | |
| `import_showdown_pokemon`       | (paste IO)                    | DISPATCHED        | Parser handles `SPs:` line. |
| `export_pokemon_to_paste`       | team_tools.py                 | DISPATCHED        | Exporter emits SPs for Champions builds. |

## Migration recipe

For an EV-only spread tool to become DISPATCHED:

1. After computing the EV spread, call:
   ```python
   from vgc_mcp_core.formats.showdown import build_dual_paste_payload
   from vgc_mcp_core.rules.regulation_loader import get_regulation_config

   fmt = get_regulation_config().get_format_system() or "mainline"
   payload = build_dual_paste_payload(
       species=pokemon_name, nature=nature.title(),
       evs={"hp": hp_evs, "atk": atk_evs, ...},
       format_system=fmt,
   )
   return success_response(..., **payload)
   ```
2. The response now carries `showdown_paste` (format-aware),
   `mainline_showdown_paste`, `champions_showdown_paste`, `spread_evs`,
   and `spread_sps`. Existing mainline clients keep working; Champions
   clients get the SP-shaped output they expect.

## Tools deliberately not dispatched

- Damage / matchup / coverage tools that don't generate spreads. They
  read stats from a `PokemonBuild`, and `calc.stats` already dispatches
  on `pokemon.format_system`.
- Smogon usage / meta tools that report on real-world spreads — these
  are sourced from EV-shaped or SP-shaped Smogon data and tagged with
  `format_system` already (see `_parse_spread` in api/smogon.py).

## Open questions

- `find_breakpoint` under Champions: is the user expecting "minimum SPs
  to hit benchmark" or "minimum EVs"? Current EV-only output may
  actually be more useful since it shows the underlying stat math.
  Decide before migrating.
- Should Champions detection be sticky? Today auto-detect respects
  `session_set_explicitly` — confirm we don't want a global "Champions
  mode" toggle that survives across calls without a Pokemon mention.
