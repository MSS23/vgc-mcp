---
tags: [project]
type: mcp-server
status: active
---

# mcp vgc

**Type:** MCP server (Python)
**Stack:** Python 3.11+, FastMCP, httpx, pydantic, diskcache; Starlette/uvicorn for HTTP/SSE
**Repo:** https://github.com/MSS23/vgc-mcp.git (branch: main)
**Status:** active

## What it does
A Model Context Protocol server that turns any LLM into a competitive Pokémon
VGC coach: 208 tools covering the full Gen 9 damage formula, Smogon usage data,
EV/spread optimization, team analysis, legality checking, replay analysis and a
live battle copilot. Supports both mainline VGC (EVs, Reg F/G/H/I) and Pokémon
Champions (Stat Points, Reg MA/MB) with zero-config regulation auto-detection.

## How it works
- `src/vgc_mcp/server.py` — FastMCP server entry; registers 51 tool modules
  (208 tools). `main()` = stdio transport, `main_http()` = SSE over Starlette
  (`/sse`, `/health`) for remote use (deployed at vgc-mcp.onrender.com).
- `src/vgc_mcp_core/` — engine: damage calc (`calc/`), models, Smogon/PokeAPI
  clients (`api/`), regulation rules (`rules/`), team analysis (`team/`).
- `data/cache/` — diskcache SQLite cache for PokeAPI/Smogon responses.

## Dev
- Venvs: `.venv` (Python 3.13), `.venv311` (Python 3.11 compat check)
- Tests: `python -m pytest tests/ -q` — 1,417 tests, ~2 min
- Lint: `ruff check src/ tests/` — clean; enforced as hard gate in CI
- Smoke test: `python test_deploy.py`
