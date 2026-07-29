# CI/CD — How It Works

How code gets from your laptop to `https://vgc-mcp.onrender.com`, what checks
it passes on the way, and what to do when one fails.

---

## The short version

```
git push
   │
   ▼
┌─────────────────────────────────────────────────────────┐
│  CI  (.github/workflows/ci.yml)                         │
│  5 jobs, all in parallel:                               │
│    • test (Python 3.11 / 3.12 / 3.13) + ruff            │
│    • typecheck (mypy strict, ratcheting)                │
│    • catalog-drift                                      │
│    • validate-regulations                               │
│    • docker                                             │
└─────────────────────────────────────────────────────────┘
   │  all green, branch == main
   ▼
┌─────────────────────────────────────────────────────────┐
│  RENDER  (render.yaml)                                  │
│  autoDeployTrigger: checksPass                          │
│  Render watches GitHub checks and deploys itself.       │
│  ── Nothing in this repo pushes the deploy. ──          │
└─────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────┐
│  VERIFY  (.github/workflows/deploy-verify.yml)          │
│  Polls the live server until the deployed git SHA       │
│  matches the commit that just passed CI, then smoke-    │
│  tests the real MCP endpoint.                           │
└─────────────────────────────────────────────────────────┘

  Separately, on a schedule:
  keep-alive.yml — pings /health so the free dyno never sleeps.
```

The important structural point: **this is pull-based CD, not push-based.** No
workflow here holds a Render API key or runs `render deploy`. Render's GitHub
App watches the commit status on `main` and deploys when checks pass. That's
why `ci.yml` only needs `permissions: contents: read` — there is no deploy
credential in this repository to leak.

---

## CI — the five gates

All five run in parallel on every push to `main` and every PR targeting it.

### 1. `test` — the actual gate

Runs the full suite on **Python 3.11, 3.12 and 3.13** (`fail-fast: false`, so
one version failing still tells you about the others). 1494 tests, ~45s.

Integration tests that hit live PokeAPI/Smogon are **excluded by default** via
`addopts = "-m 'not integration'"` in `pyproject.toml`. This is deliberate: CI
must never go red because Smogon had a bad afternoon. Run them yourself with:

```bash
python -m pytest tests/ -m integration
```

The same job then runs **ruff** as a hard gate over `src/`, `tests/` and
`scripts/verify_production.py`.

### 2. `typecheck` — mypy strict, ratcheting

mypy is configured `strict = true`, which currently produces ~1301 findings —
mostly bare `dict`/`list` annotations, not bugs. Historically this ran with
`continue-on-error: true`, which meant it was *reported but unenforced*: the
count could grow forever and nobody would know.

It is now a **ratchet**:

```yaml
env:
  MYPY_BASELINE: "1301"
```

- Count goes **up** → CI fails. You added new type debt; fix it.
- Count goes **down** → CI passes and prints a notice telling you to lower the
  baseline. Do that in the same PR.
- Count hits **0** → delete the whole step body and replace it with a plain
  `python -m mypy src/vgc_mcp_core src/vgc_mcp`.

This buys enforcement today without blocking on a 1300-line annotation sweep.

> **Why not just fix all 1301?** Because ~494 are `type-arg` (a bare `dict`
> where `dict[str, Any]` was meant) with no behavioural bug behind them.
> Enforcement now beats a perfect number later.

### 3. `catalog-drift` — docs can't rot

`docs/tools-catalog.md` is **generated from the live server**, not hand-written.
This job regenerates it and fails if the result differs from what's committed.

If you add a tool and forget to regenerate, CI stops you:

```bash
python scripts/build_catalog.py   # then commit docs/tools-catalog.md
```

### 4. `validate-regulations` — data integrity

`regulations.json` drives format legality across the whole server. This job:

1. Runs `scripts/validate_regulations.py` — JSON schema check plus router-alias
   drift detection.
2. Runs the champions alias/regulation consistency tests.

Drift between `regulations.json` and the router's alias map produces *silent*
wrong answers rather than crashes, which is exactly the class of bug worth a
dedicated gate.

### 5. `docker` — the image builds *and* serves

`Dockerfile` is a documented deployment path (`docs/deploy.md` covers Docker and
Fly.io, and `fly.toml` builds from it) but nothing in CI exercised it, so a
broken Dockerfile only surfaced at deploy time.

This job does two things, and the second matters more than the first:

1. `docker build` — proves it compiles.
2. Boots the container and polls `http://localhost:8000/health` for 30s —
   **proves the image actually serves traffic**. On failure it dumps
   `docker logs` so you can see why.

A build that succeeds and then crashes on startup is the failure mode worth
catching, and only step 2 catches it.

---

## CD — how the deploy actually happens

### `render.yaml`

```yaml
branch: main
buildCommand: python -m pip install -e ".[remote]"
startCommand: vgc-mcp-http
healthCheckPath: /health
autoDeployTrigger: checksPass
```

`autoDeployTrigger: checksPass` is the entire CD trigger. Render will not deploy
a commit whose GitHub checks failed. (Note: `autoDeployTrigger` replaced
Render's deprecated `autoDeploy` field — don't reintroduce the old one.)

### Why `main` CI runs are never cancelled

`ci.yml` uses:

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

Superseded **PR** pushes get cancelled to save runner minutes. **`main` never
does** — a cancelled run is not a passed run, and cancelling it would strand
Render waiting for a `checksPass` signal that never arrives.

### `deploy-verify.yml` — trust but verify

Triggered by `workflow_run` when CI *completes*, gated on
`conclusion == 'success'` and `head_branch == 'main'`. It checks out the exact
validated SHA and runs:

```bash
python scripts/verify_production.py --expected-sha "$EXPECTED_SHA" --timeout 900
```

This polls the live service until the revision it reports matches the commit
that just passed CI, then smoke-tests the real MCP endpoint. **A green CI run
tells you nothing about what Render is currently serving** — this is the job
that closes that gap.

Run it manually any time (it's `workflow_dispatch`-enabled), or locally:

```bash
python scripts/verify_production.py
# Production verified: revision=039b64b… tools=208 url=https://vgc-mcp.onrender.com
```

### `keep-alive.yml` — the free-tier tax

Render's free tier sleeps after 15 minutes idle, and the ~50s cold start breaks
the Claude connector handshake.

The critical caveat is documented in the workflow itself: **GitHub cron cannot
keep a 15-minute-idle dyno warm.** Scheduled workflows on shared runners get
delayed — a `*/14` cron was observed firing ~2 hours apart. To compensate, each
run pings every 4 minutes for ~24 minutes rather than pinging once, so any run
that *does* fire covers a window.

This is a backup, not the primary mechanism. The reliable fixes are an external
uptime monitor (UptimeRobot etc., every 5 min against `/health`) or Render's
Starter plan, which never sleeps.

---

## Dependabot

`.github/dependabot.yml` was added because CI had **no CVE signal at all** —
nothing told you when `httpx` or `pydantic` shipped a security patch.

- **pip**, weekly — dev toolchain (`pytest*`, `ruff`, `mypy`) is grouped into a
  single PR, since reviewing five low-risk tooling bumps separately is noise.
  Runtime deps get individual PRs, because those deserve real review.
- **github-actions**, monthly — pinned action versions go stale silently and
  eventually break when GitHub retires a runner image.

Every Dependabot PR runs the full five-gate CI above, so a bad bump is caught
before it reaches `main`, and therefore before Render sees it.

---

## Running the pipeline locally

Everything CI does, minus the Docker job, in the order it'd fail:

```bash
python -m pytest tests/ -q                      # 1494 tests, ~45s
python -m ruff check src/ tests/ scripts/
python -m mypy src/vgc_mcp_core src/vgc_mcp     # count must not exceed baseline
python scripts/build_catalog.py && git diff --exit-code docs/tools-catalog.md
python scripts/validate_regulations.py
docker build -t vgc-mcp:ci .                    # requires Docker
```

---

## When something fails

| Symptom | Cause | Fix |
|---|---|---|
| `docs/tools-catalog.md is stale` | Added a tool, didn't regenerate | `python scripts/build_catalog.py`, commit |
| `mypy errors increased: N > 1301` | New type debt | Fix the new findings, or justify raising the baseline |
| mypy notice: count dropped | You cleaned some up | Lower `MYPY_BASELINE` in `ci.yml` |
| `container failed /health within 30s` | Image builds but won't serve | Read the dumped `docker logs`; check `[remote]` extra installs |
| `validate_regulations` fails | `regulations.json` ↔ router alias drift | Re-sync the alias map |
| CI green, `deploy-verify` fails | Render didn't deploy, or deployed a different SHA | Check the Render dashboard; confirm `autoDeployTrigger: checksPass` |
| Tests fail only on 3.11 | Version-specific syntax | Check f-string nesting — this has bitten before |
| Connector handshake times out | Free dyno slept | Expected on free tier; see keep-alive caveat above |

---

## Adding a new gate

Add a job to `ci.yml` — the five existing ones are independent and parallel, so
a sixth costs wall-clock time only if it's slower than the slowest current job.

Two rules worth keeping:

1. **Never let a gate depend on a third-party service.** That's what the
   `integration` marker is for. A gate that goes red when Smogon is down trains
   people to ignore red.
2. **Prefer a gate that proves behaviour over one that proves shape.** The
   docker job builds *and* boots for exactly this reason.
