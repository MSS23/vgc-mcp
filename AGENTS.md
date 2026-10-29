# AGENTS.md

Instructions for coding agents (Codex, Claude Code and others) working in this
repository live in [CLAUDE.md](CLAUDE.md). Read it first; it is the single
source of truth for commands, architecture, the mainline vs Champions format
split, the response contract and output-format rules.

Quick facts:

- Install: `pip install -e ".[dev,remote]"`; run tests with `python -m pytest tests/ -q`.
- The server registers 213 tools; `/mcp` serves the 34-tool core profile and
  `/mcp/full` serves everything (`src/vgc_mcp/profiles.py`).
- Logic goes in `src/vgc_mcp_core/`; tool modules in `src/vgc_mcp/tools/` are
  thin wrappers. Build Pokemon with `build_pokemon`, detect the format with
  `detect_champions_format`, and return errors through
  `vgc_mcp_core/utils/errors.py`.
- Agent tooling (caveman, ponytail, graphify) is described in
  [docs/agents/tooling.md](docs/agents/tooling.md).
