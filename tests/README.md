# tests/ — Test Suite

Over 1,600 offline tests. Almost everything is pure-function testing with no
network; the 12 tests that hit live PokeAPI/Smogon are marked
`@pytest.mark.integration` and **excluded by default** (`addopts` in
`pyproject.toml`). Run them explicitly with `python -m pytest -m integration`.

## Layout

Directories mirror the architecture — find the code, find its tests:

| Directory | Tests | What lives here |
|---|---|---|
| `calc/` | ~430 | The mathematical engine: damage formula, stats, speed, matchup, priority, EV/HP/item optimization. Includes the single-mechanic regression files (`test_life_orb_sheer_force.py`, `test_paradox_boosted_stat.py`, `test_surging_strikes_ogerpon.py`, …) — each pins one subtle interaction that was reported broken once. |
| `tools/` | ~400 | The MCP tool wrappers in `src/vgc_mcp/tools/`: response structure, Showdown-paste fields, error shapes. |
| `champions/` | ~350 | The parallel Pokemon Champions (Reg MA/MB) format: Stat Point math, `SPs:` paste round-tripping, allowlist legality, regulation routing, Mega Evolution. |
| `team/` | ~180 | Team building: TeamManager, legality/rules, learnsets, game plans, core synergy, Showdown paste parsing, name normalization. |
| `api/` | ~40 | External API clients with mocked transport: PokeAPI form resolution, Smogon rating routing, disk caching. |
| `server/` | ~30 | Server infrastructure and meta-tests (see below). |

## The files that police the codebase

`server/` holds tests that assert properties of the *repo*, not of Pokemon math:

- **`test_error_contract.py`** — greps `src/vgc_mcp/tools/` and fails if any
  tool returns a raw `{"error": ...}` instead of `error_response(...)`.
- **`test_tool_registry.py`** — duplicate tool names or missing registration
  dependencies must be fatal at startup, never silently swallowed.
- **`test_deploy_smoke.py`** — pins the total tool count (208). Dropping a
  registration module fails here instead of quietly shipping a smaller server.
- **`test_http_transport.py` / `test_verify_production.py`** — the HTTP
  transport and the deploy smoke-test script itself.

## Ground truth: golden tests

`calc/test_damage_golden.py` hard-codes expected damage values taken from
`@smogon/calc` (Showdown's calculator) — they are **not** computed from the
code under test. If a refactor changes any of these numbers, the refactor is
wrong, full stop. When you fix a damage bug, add the Showdown-verified value
here.

`calc/test_damage_audit.py` adds 21 exact-roll cases from `@smogon/calc 0.11.0`
and regressions for multi-hit optimization. The oracle inputs and expected rolls
are stored in `calc/damage_audit_cases.json`. To refresh expectations using an
independently installed calculator (never the implementation under test):

```bash
node scripts/generate_damage_audit.cjs /absolute/path/to/node_modules/@smogon/calc
```

`calc/test_stat_formula_audit.py` checks more than 400,000 stat equations against
integer formulas. `calc/test_ko_probability_accuracy.py` checks exact independent
roll counts, ten-hit performance, and certainty labels. The opt-in
`api/test_smogon_live.py` verifies both EV and SP common sets reach the shared
calculation helper from real chaos datasets using a fresh temporary cache.

## Running

```bash
python -m pytest tests/ -q                 # everything (~45s)
python -m pytest tests/calc/ -q            # just the engine
python -m pytest tests/calc/test_damage.py -v
python -m pytest tests/ -k "speed" -q      # by keyword
python -m pytest tests/ -m integration     # live-API tests (off by default)
python -m pytest tests/ --cov=vgc_mcp --cov=vgc_mcp_core   # with coverage
```

CI runs the suite on Python 3.11/3.12/3.13 (see `.github/workflows/ci.yml`,
explained in `docs/ci-cd.md`). A local hook (`scripts/hooks/test_hot_paths.py`)
also runs the mapped tests whenever a hot source file changes — if you move a
test file, update that map.

## Fixtures (`conftest.py`)

- `_isolate_regulation_config` (autouse) — resets regulation state around every
  test. Regulation selection is session-global; without this, a test switching
  to Reg MA would poison every test that runs after it.
- `team_manager` — fresh `TeamManager`.
- `flutter_mane_stats`, `dragapult_stats`, `urshifu_stats`, … — common base-stat
  blocks.
- `mock_cache` — in-memory stand-in for the disk cache.

Most tests build Pokemon inline instead of via fixtures:

```python
def make_pokemon(name, types, base_hp=80, **kw):
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(hp=base_hp, ...),
        nature=Nature.SERIOUS,
        evs=EVSpread(),
        types=types,
    )
```

## Conventions

- **Where does a new test go?** Mirror the source: `vgc_mcp_core/calc/` →
  `tests/calc/`, `vgc_mcp/tools/` → `tests/tools/`, champions-format anything →
  `tests/champions/`.
- **Expected values must come from outside the code.** Compute them with
  Showdown/@smogon/calc or by hand — never by running the implementation and
  pasting its output back in as the assertion.
- **No live network** outside `-m integration`. CI must never go red because
  Smogon had a bad afternoon.
- Fixed a user-reported calc bug? Add a regression test with the original
  wrong number in the docstring (see `calc/test_surging_strikes_ogerpon.py`
  for the pattern).
