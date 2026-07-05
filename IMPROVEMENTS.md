# IMPROVEMENTS.md — VGC MCP Improvement Plan

A prioritized, evidence-based plan for what to fix, change, add, and optimize across the
whole project. Compiled from a full-codebase audit (core library, MCP tool surface,
tests/CI/deployment) on 2026-07-05. Every finding cites the file it was verified in.

**Snapshot at audit time:** 209 tools across 53 modules, ~1,384 test functions in 117 files,
hosted at vgc-mcp.onrender.com (Streamable HTTP `/mcp` + legacy `/sse`), CI = pytest + ruff
on Python 3.11–3.13.

---

## Priority 0 — Critical (correctness & production safety)

These are bugs or unsafe behavior in the *deployed* server. Fix before adding features.

### 0.1 Per-session state isolation for hosted HTTP mode
- **Problem:** `server.py:174-181` creates `team_manager`, `build_manager`, `battle_manager`
  as module-level singletons shared by every request. `BattleStateManager` stores exactly one
  battle and `start()` replaces any in-flight one (`state/battle_manager.py:116-133`);
  `BuildStateManager._name_to_id` collides builds by species name (`state/build_manager.py:23`).
  On the hosted `/mcp` endpoint, **concurrent users read and mutate each other's teams,
  builds, battles, and "my Pokemon" context** — `reset_session` wipes everyone.
- **Fix:** key all mutable state by MCP session id (`Mcp-Session-Id`) — a
  `dict[session_id, ManagerSet]` with TTL eviction, populated via a `ContextVar` from the
  request context. Stdio mode keeps a single default session. Until done, document the
  hosted deployment as single-tenant.

### 0.2 Auth + CORS hardening on the public endpoint
- **Problem:** `main_http` has no auth layer at all, and
  `CORSMiddleware(allow_origins=["*"], allow_credentials=True)` (`server.py:302-311`) is a
  contradictory combination browsers reject. Combined with 0.1, any origin can mutate shared
  state and drive upstream API traffic.
- **Fix:** drop `allow_credentials=True` (not needed for token-less MCP), add an optional
  bearer-token check (env var `VGC_MCP_API_KEY`; skip when unset for local use), and add
  basic per-IP rate limiting middleware.

### 0.3 `makes_contact` is never populated — contact mechanics silently wrong
- **Problem:** `api/pokeapi.py:218-266` initializes `makes_contact = False` and never assigns
  it, so every API-fetched move is "non-contact". Tough Claws (`calc/damage.py:1038`),
  Fluffy (`damage.py:1261`), and all contact gating compute against an always-false flag.
- **Fix:** add a static contact-move flag table in `vgc_mcp_core/data/` (same pattern as the
  existing multi-hit/punch tables) and populate the flag in `get_move`. Add golden tests for
  Tough Claws and Fluffy.

### 0.4 Delete the duplicate damage formula in meta-threat analysis
- **Problem:** `calc/meta_threats.py:62-159` (`calculate_simple_damage`) reimplements the
  damage formula with wrong rounding and no items/abilities/weather/screens. Every
  meta-threat verdict can contradict the authoritative `calc/damage.calculate_damage` —
  a spread "survives" in one tool and is "OHKO'd" in another.
- **Fix:** build lightweight `PokemonBuild`s from usage spreads and route through
  `calculate_damage`; delete the parallel formula.

### 0.5 Model Parental Bond
- **Problem:** `calc/mega_evolution.py:27` maps Mega Kangaskhan → Parental Bond, but
  `calc/damage.py` never handles it. Since Megas are Champions-legal, its damage is
  materially wrong (missing the +0.25× second hit).
- **Fix:** model as a 2-hit sequence (second hit at 2048/4096) feeding the existing
  multi-hit KO-probability path.

---

## Priority 1 — High (CI trust, packaging, and known-wrong outputs)

### 1.1 Make CI enforce what the config promises
- **mypy `strict = true` is configured (`pyproject.toml:64-66`) but never run anywhere.**
  Add a `type` job to `ci.yml` running `mypy src/`. Start with `continue-on-error: true`,
  burn down violations, then flip to blocking.
- **The `integration` marker is decorative.** `pyproject.toml` documents it as "skipped by
  default in CI" but `ci.yml:38` runs plain `pytest tests/ -q`, so
  `tests/test_pokeapi_forms.py:118` hits live PokeAPI on every CI run (flaky gate). Add
  `addopts = "-m 'not integration'"` to `[tool.pytest.ini_options]` and a separate
  nightly/manual job for `-m integration`.
- **CI installs deps ad-hoc** (`pip install pytest pytest-asyncio ruff`) instead of
  `pip install -e ".[dev]"` — the declared toolchain (mypy, pytest-cov) is silently dropped.
- **Coverage is never measured.** Add `--cov=vgc_mcp --cov=vgc_mcp_core` with a floor
  (start at current level, ratchet up).
- **Catalog drift gate:** run `scripts/build_catalog.py` in CI with `git diff --exit-code`
  so `docs/tools-catalog.md` (currently says 196 vs ~209 actual) can never rot again.

### 1.2 Fix or delete `requirements.txt`
It contradicts `pyproject.toml`: lists phantom `mcp-ui-server` (explicitly not a dependency
per `server.py:45`), **omits runtime deps `openpyxl`/`fpdf2`** (breaking Excel/PDF export for
anyone installing from it), and promotes `uvicorn`/`starlette` to core. No deploy config uses
it. Delete it, or generate it from `pyproject.toml`.

### 1.3 Test the flagship features (currently zero coverage)
- **Battle copilot** (`battle_tools.py`: `start_battle`/`record_turn`/`suggest_next_move`/
  `get_battle_state`) — zero tests despite being a README headline feature.
- **Replay analyzer** (`replay_tools.py::analyze_replay`) — zero tests.
- **HTTP transport** — no test touches `main_http`, `/health`, `/mcp`, or `/sse`. Add
  Starlette `TestClient` smoke tests (initialize handshake, health JSON, tool count).
- Move root-level `test_deploy.py` under `tests/` (pytest's `testpaths = ["tests"]` means it
  currently runs nowhere) and unskip the 4 stubbed learnset tests
  (`tests/test_learnset.py:129-144`).

### 1.4 Consolidate the tool surface: 209 → ~70–90 tools
209 tools blows past what LLM clients select well — the project even ships
`what_tool_should_i_use` as a workaround (`router_tools.py:1-9`). Most consolidation is
mechanical parameter-collapsing:

| Cluster | Now | Target | Merge notes |
|---|---|---|---|
| Speed (`speed_*_tools.py` ×4 + strays) | ~22 | ~5 | 4 "speed tier" tools and 5 "outspeed" tools become `speed_tiers`, `outspeed` (mode flag), `speed_compare`, `speed_control_team`, `speed_ev_search` |
| Survival/bulk | ~10 | ~2 | `find_survival_evs(pokemon, threats: list)` where len 1..6 subsumes single/dual/multi/double-up variants |
| Per-item calculators (`item_tools.py`) | 8+3 | 1–2 | `calculate_choice_item` already takes generic `item: str` — generalize to `calculate_item_effect` |
| Bulk optimizers | 3 | 1 | `optimize_bulk` + `optimize_bulk_math` + `analyze_bulk_diminishing_returns` |
| Spread suggestion | 4 | 1 | `suggest_spread`, `suggest_ev_spread`, `optimize_spread`, `suggest_spread_for_role` |
| `analyze_team_*` | 8+ | 1–2 | `analyze_team(sections=[...])`; keep the bundlers (`full_team_check`, `import_and_analyze`) |

Confirmed exact-duplicate pairs to merge first: `analyze_outspeed_probability` ↔
`outspeed_probability`, `visualize_speed_tiers` ↔ `visualize_team_speed_tiers`,
`survive_multiple_hits` ↔ `find_bulk_to_survive_hits`, `find_multi_threat_bulk_evs` ↔
`optimize_multi_survival_spread`, `find_survival_evs` ↔ `find_survival_evs_meta`.

Keep old names as thin deprecated aliases for one release, then remove.

### 1.5 Standardize tool parameter conventions
- **One EV representation.** Today there are three: six int params (`context_tools.py:25-30`),
  a dict (`build_checker_tools.py:22`), and a parsed string (`bulk_calc_tools.py:201`). Worst:
  `attacker_evs` is an **int** in `damage_tools.py:1525` but a **string** in
  `bulk_calc_tools.py` — same name, different type, a real LLM foot-gun. Standardize on the
  `"HP/Atk/Def/SpA/SpD/Spe"` string everywhere (accept dict as fallback).
- **One naming scheme:** `attacker_name`/`defender_name`/`move_name` vs `attacker`/`defender`
  vs `your_pokemon`/`threat_pokemon` — pick one (suggest `attacker`/`defender`/`move`,
  `pokemon` for the subject) and apply across all tools during the 1.4 consolidation.

### 1.6 Finish the error/success contract
`errors.py` is adopted in ~46 files but ~6 modules still return raw `{"error": ...}` dicts:
`ability_tools.py:54`, `matchup_tools.py:45`, `coverage_tools.py:43,233,351`,
`core_tools.py` (6 returns), `sample_team_tools.py:53,112`, `preset_tools.py:45,149-205`.
Route them through `error_response`/helpers; route successes through `success_response` so
`success`/`message` fields are uniform. Add a CI grep-gate (or extend `codemod_errors.py`
into a lint) forbidding raw `{"error":` returns in `src/vgc_mcp/tools/`.

---

## Priority 2 — Medium (accuracy, performance, MCP polish)

### 2.1 Damage-calc mechanic gaps
- **Weight-based moves:** `calc/damage.py:451-467` reads `attacker_weight`/`defender_weight`
  that are never auto-populated from PokeAPI, so Heavy Slam/Heat Crash/Low Kick/Grass Knot
  silently use fallback BP. Fetch and cache species weight in `PokeAPIClient.get_pokemon`
  and auto-fill (mirroring the existing item/ability auto-fill at `damage.py:566-575`).
- **Knock Off boost:** treated as flat 65 BP (`calc/matchup.py:200`); model the 1.5× when the
  target holds a removable item. It's a staple VGC move.
- **Reported type effectiveness bug:** `damage.py:1445` recomputes `type_eff`, overwriting the
  Tera Shell clamp (1013-1015) and Mind's Eye/Scrappy override (1018-1022) in the *reported*
  breakdown (rolls are correct; display is wrong).
- **Champions format-dispatch completeness:** `presentation.py:253-256` literally instructs
  the LLM to flag tools that return `252/508` in Champions mode as bugs. Audit the remaining
  non-Champions-aware tools (there's a `docs/format-dispatch-audit.md` to drive from) and
  remove that instruction once clean.

### 2.2 Performance
- **Bulk EV/SP solvers are O(n²) full-calc sweeps:** `calc/damage.py:1936-1979` runs ~33×33
  complete damage calcs per call (same for the SP branch at 1895-1934). Exploit monotonicity:
  compute base damage once and scale by defensive-stat ratio, or bisect HP per Def breakpoint
  (as `find_speed_evs` in `stats.py:179` already does for speed). This directly cuts the
  5–30s multi-threat optimizer times.
- **API client hygiene** (`api/pokeapi.py:120-152`, `api/smogon.py:276-352`):
  in-flight request coalescing (concurrent identical requests share one fetch), short-TTL
  negative caching for 404s, and a normalized-name index built once per Smogon chaos payload
  instead of a full re-normalizing scan per lookup (6 scans per team today).
- **Smogon month arithmetic:** `_get_recent_months` uses `timedelta(days=30*i)`
  (`api/smogon.py:114-128`) which skips/duplicates months near boundaries; use proper
  year/month decrement. Also label results with the month actually resolved, not `months[0]`.

### 2.3 MCP protocol polish
- **Tool annotations:** zero tools declare `readOnlyHint`/`destructiveHint`/`idempotentHint`.
  ~190 of 209 are read-only calculators; the ~15 mutators (`add_to_team`, `start_battle`,
  `reset_session`, `clear_team`, ...) should be flagged so clients can gate destructive calls.
- **Resources:** static reference data currently exposed as tools (`list_banned_pokemon`,
  `list_available_regulations`, `get_format_rules`, `explain_vgc_term`, glossary, speed-tier
  tables) are natural `@mcp.resource()` / resource templates (`vgc://regulation/{id}`) —
  trims the tool count and lets clients cache them.
- **Output schemas:** return shapes are convention-only untyped dicts. Add typed output
  models (FastMCP emits `outputSchema`) at least for the high-traffic calc tools; this also
  makes the §1.6 contract machine-enforced.
- **Stop reaching into private FastMCP attrs:** `server.py:251,260` uses
  `mcp._tool_manager._tools` for the health/root endpoints — breaks on any internal rename.

### 2.4 Shared-code cleanups
- Deduplicate copy-pasted private helpers into `vgc_mcp_core`: `_session_is_champions`
  (`breakpoint_tools.py:54`, `delta_tools.py:33`), `_detect_champions` (`build_tools.py:23`),
  `_sps_from_smogon_spread` (`damage_tools.py:72`, `bulk_calc_tools.py:70`), inline
  `NATURE_MAP` (`speed_tools.py:157-167`).
- Single source of truth for meta speed tiers: `META_SPEED_TIERS` (`speed_tools.py:19-79`)
  duplicates `calc/speed.get_meta_speed_tier` — and both will rot; prefer deriving from
  Smogon usage data with the static table as offline fallback.
- Unify the parallel mainline/Champions optimizer code: `champions_optimization.py` mirrors
  `hp_optimization.py`/`bulk_optimization.py`, and the EV/SP branches inside
  `calculate_ko_threshold`/`calculate_bulk_threshold` (`damage.py:1811-1934`) duplicate each
  other. Introduce one format-parameterized "allocation grain" abstraction (breakpoint list +
  stat formula injected).
- A shared `DamageModifiers` factory: it's hand-constructed in 4+ modules (`bulk_calc.py`,
  `matchup.py` ×3, `team_matchup.py`) — a `from_battle_state()/from_usage_set()` factory
  removes drift and directly enables the battle-copilot feature below.
- `models/pokemon.py:156`: `MAX_TOTAL: int = 66` on `StatPointSpread` is an accidental
  Pydantic field (serializes, caller-overridable) — make it `ClassVar[int]`.
- Battle default regulation is stale: `state/battle_manager.py:92,131` hardcodes `"reg_h"`
  while `config.py:56` says Reg F — derive from settings/regulation router.
- Cache config duplication: `config.py:40` and `api/cache.py:22` compute *different* cache
  dirs and `Settings.CACHE_DIR`/`CACHE_EXPIRE_DAYS` are unused — have `APICache` read settings.

### 2.5 Deployment & docs consolidation
- **One blessed deploy target.** Render is live; `fly.toml` + `docker-compose.yml` are
  unexercised and rotting. Move to `deploy/examples/` or delete.
- **`smithery.yaml`:** points discovery clients at legacy `/sse` — update to `/mcp`
  (Streamable HTTP); also fix its internal 206-vs-208 tool-count contradiction.
- **Single source of truth for tool count.** Today: README says 208, smithery 206/208,
  tools-catalog 196, `docs/api-reference.md` "157+", actual ≈209. Have `build_catalog.py`
  emit the count and inject it everywhere; deprecate or regenerate `api-reference.md`.
- Fix stale `tests/README.md` ("289 tests" vs ~1,384) or delete it.
- Commit or remove untracked `WIKI.md` (currently duplicates README with Obsidian frontmatter).
- Delete spent one-shot `scripts/codemod_errors.py` (or repurpose per §1.6) and reconcile the
  two diverging `validate_regulations.py` copies (`scripts/` vs `scripts/hooks/`).

---

## Priority 3 — New features (roadmap)

Ordered by leverage-per-effort given what the architecture already supports.

1. **Live-battle damage coaching (highest leverage).** Wire `BattleStateManager` field/stage/
   HP state into a `DamageModifiers` factory so `record_turn` → auto-recomputed KO ranges and
   turn-order each turn. State and calc both exist; only the adapter is missing. This turns
   the battle copilot from a state notebook into a real coach.
2. **Offline/bundled meta snapshot.** Ship a periodically refreshed Smogon chaos snapshot +
   static PokeAPI subset so the server works with a cold cache or no network (also de-risks
   the PokeAPI dependency and CI flakiness).
3. **Turn-order probability trees.** Combine `FieldState` (Tailwind/Trick Room timers,
   paralysis) with `speed_probability.py` to output full turn-order probability per lead
   matchup.
4. **Team-wide defensive-backbone solver.** After the §2.2 solver speedup, batch bulk
   optimization across all 6 team members vs the live meta threat list — "reallocate 44 EVs
   from X to Y to survive 3 more top-10 threats."
5. **What-if diff tool.** `diff/team_diff.py` + damage calc → KO/speed deltas when swapping
   item, ability, Tera type, or nature ("what changes if I drop Choice Scarf for Life Orb?").
6. **Legal set generator.** `rules/regulation_router.py` + Smogon spreads + learnset
   validation → fully legal sample sets per regulation on demand.
7. **Meta drift alerts.** `compare_pokemon_usage` already computes month-over-month deltas —
   surface "your team vs the shifting meta" watch reports.
8. **Weight/multi-hit accuracy pack.** After §2.1: Heavy Slam/Low Kick BP breakpoints,
   Loaded Dice + Population Bomb roll distributions, Parental Bond breakpoints as first-class
   outputs.
9. **Persisted user sessions.** Once §0.1 lands, per-session state naturally extends to
   saved teams/battles per user and shareable build links.
10. **Tournament data integration.** Pull top-cut teams from Limitless/tournament APIs into
    the meta-threat and sample-team tooling (complements Smogon ladder data with actual
    tournament results).

---

## Suggested sequencing

| Phase | Contents | Outcome |
|---|---|---|
| **1. Trust** (small, do first) | 1.1 CI gates (integration marker, mypy, cov, catalog drift), 1.2 requirements.txt, 2.5 doc/tool-count SSOT, quick calc bugs (0.3, 0.4, 2.1 type-eff display) | CI you can believe; calcs stop contradicting each other |
| **2. Production safety** | 0.1 session isolation, 0.2 auth/CORS, 1.3 transport + battle/replay tests | Hosted endpoint safe for concurrent users |
| **3. Surface quality** | 1.4 tool consolidation, 1.5 param standardization, 1.6 error contract, 2.3 annotations/resources/schemas | ~70–90 well-typed tools LLMs select reliably |
| **4. Depth** | 2.1 remaining mechanics (weight, Knock Off, Parental Bond 0.5), 2.2 solver performance, 2.4 dedup | Faster, more accurate engine with one code path per concept |
| **5. Features** | P3 roadmap, starting with live-battle coaching + offline snapshot | New capability, not just polish |

## Quick wins (each < 1 hour)

- Add `-m "not integration"` to CI / `addopts` (kills live-network CI flakiness).
- Delete `requirements.txt`.
- `MAX_TOTAL` → `ClassVar` in `models/pokemon.py:156`.
- Fix `smithery.yaml` endpoint (`/sse` → `/mcp`) and tool count.
- Fix battle default regulation (`reg_h` → settings-derived).
- Regenerate `docs/tools-catalog.md` and fix `tests/README.md`.
- Move `test_deploy.py` into `tests/`.
- Remove `allow_credentials=True` from CORS config.

## Strengths to preserve (don't refactor away)

- Auto-discovery + dependency-injection tool registration (`vgc_mcp/tools/__init__.py`).
- Docstring discipline — tool descriptions are consistently strong for LLM consumption.
- The `errors.py` structured-error contract (finish adopting it, keep the design).
- `presentation.py` output-formatting instructions.
- Hermetic test design (`conftest.py` mock fixtures, autouse regulation-state isolation).
- The regulation validation CI gate (`scripts/validate_regulations.py`).
