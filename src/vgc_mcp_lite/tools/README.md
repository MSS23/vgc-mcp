# vgc_mcp_lite/tools/

Lite-server tool registrations. Each `*_tools.py` file here mirrors a file in
`src/vgc_mcp/tools/` and exposes a curated subset of the full server's tools,
optionally with MCP-UI extensions wired in.

## Why does this directory exist separately?

Historically the lite server forked the full server's tool implementations to:

1. Trim the tool surface (49 tools instead of ~195) so smaller models can pick
   tools reliably without running out of selection budget.
2. Layer MCP-UI resource attachments on tool responses (HTML cards, summary
   tables) — see `vgc_mcp_lite/ui/`.

The forks have inevitably drifted. We're consolidating step by step:

- ✅ **Smogon spread fetch** — `_get_common_spread` / `_get_common_spreads` now
  delegate to `vgc_mcp_core.tools.smogon_helpers`. Both flavors share one
  implementation.
- ✅ **Name normalization** — all `_normalize_smogon_name` copies replaced with
  `vgc_mcp_core.utils.normalize.normalize_smogon_name`.
- ✅ **Error contract** — every tool returns `error_response(...)` from the
  shared `vgc_mcp_core.utils.errors` module.
- 🚧 **Tool body logic** — most tool functions still have forked bodies.
  Future work: extract handler logic to `vgc_mcp_core/tools/<area>_handlers.py`
  and let both flavors register thin wrappers.

## Adding a new tool

If the tool is going into both flavors:

1. Put the *handler* (a pure async function returning a dict) in
   `vgc_mcp_core/tools/<area>_handlers.py`.
2. In `vgc_mcp/tools/<area>_tools.py`, register the handler with `@mcp.tool()`.
3. In `vgc_mcp_lite/tools/<area>_tools.py`, register the same handler and
   optionally attach UI metadata via `add_ui_metadata(response, ...)`.

If the tool is full-server-only, just add it in `vgc_mcp/tools/`.
