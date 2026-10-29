---
tags: [project]
type: mcp-server
status: active
---

# mcp vgc

**Type:** MCP server (Python)
**Stack:** Python 3.11+, FastMCP, httpx, pydantic, diskcache; Starlette/uvicorn for Streamable HTTP and legacy SSE
**Repo:** https://github.com/MSS23/vgc-mcp.git (branch: main)
**Status:** active

## What it does
A Model Context Protocol server that turns any LLM into a competitive Pokémon
VGC coach: 213 tools covering the full Gen 9 damage formula, Smogon usage data,
EV/spread optimization, team analysis, legality checking, replay analysis and a
live battle copilot. Clients see a 34-tool core profile by default; `/mcp/full`
serves everything. Supports both mainline VGC (EVs, Reg F/G/H/I) and Pokémon
Champions (Stat Points, Reg MA/MB/MC, MC default) with zero-config regulation
auto-detection.

## How it works
- `src/vgc_mcp/server.py` — FastMCP server entry; registers 52 tool modules
  (213 tools) and builds the core server from `profiles.py`. `main()` = stdio,
  `main_http()` = Streamable HTTP at `/mcp` (core) and `/mcp/full`, legacy SSE
  at `/sse`, plus `/health` (deployed at vgc-mcp.onrender.com, Render free plan
  kept awake by `.github/workflows/keep-alive.yml`).
- `src/vgc_mcp_core/` — engine: damage calc (`calc/`), models, Smogon/PokeAPI
  clients (`api/`), regulation rules (`rules/`), team analysis (`team/`).
- `data/cache/` — diskcache SQLite cache for PokeAPI/Smogon responses.

## Dev
- Venvs: `.venv` (Python 3.13), `.venv311` (Python 3.11 compat check)
- Tests: `python -m pytest tests/ -q` — offline suite, under a minute
- Lint: `ruff check src/ tests/ scripts/` — hard gate in CI; mypy strict with a
  ratcheting baseline in `.github/workflows/ci.yml`
- Production smoke test: `python scripts/verify_production.py --expected-sha <sha>`
