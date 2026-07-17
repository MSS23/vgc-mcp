# MCP-UI / MCP Apps Architecture Decision

**Status:** Accepted

**Date:** 2026-07-17

**Decision:** Keep `vgc-mcp` plain and client-agnostic. Build interactive views
as an optional sibling server that imports `vgc_mcp_core`; do not add
`mcp-ui-server` to this package or change the existing Render endpoint's tool
results to UI-only responses.

## Why this decision exists

VGC analysis is unusually visual. Damage scenarios, speed tiers, type coverage,
EV/SP trade-offs, and battle state are easier to understand and manipulate in a
compact interactive view than in a long chat response. MCP-UI is therefore a
good product fit.

It is not a good fit as a mandatory dependency of the universal server:

- MCP Apps is an extension to core MCP and host support varies. Plain tools and
  structured results remain the widest compatibility surface.
- The existing service already has 208 tested tools and supports stdio,
  Streamable HTTP, and legacy SSE. UI code should not increase the failure
  surface of damage calculations, format detection, or community clients that
  do not render apps.
- `vgc_mcp_core` is deliberately reusable. A UI server can consume the same
  calculations, models, handlers, and session-aware state without copying the
  competitive logic.
- The recommended MCP Apps pattern links a tool to a `ui://` resource through
  `_meta.ui.resourceUri`. The Python `mcp-ui-server` package can create legacy
  embedded UI resources, but it is not required to implement the standard wire
  format and should not be introduced into the calculation package by default.

Primary references:

- [MCP-UI repository](https://github.com/MCP-UI-Org/mcp-ui)
- [MCP Apps specification and SDK](https://github.com/modelcontextprotocol/ext-apps)
- [MCP-UI Python walkthrough](https://mcpui.dev/guide/server/python/walkthrough)
- [`mcp-ui-server` on PyPI](https://pypi.org/project/mcp-ui-server/)

## Recommended shape

```text
vgc_mcp_core                 shared source of truth
├── calculations
├── models and validation
├── API clients and cache
└── pure/shared handlers
        │
        ├── vgc_mcp          current universal server
        │   └── text + structured tool results
        │
        └── vgc_mcp_apps     optional sibling server
            ├── 5-7 composite UI tools
            ├── ui:// HTML resources
            └── text/structured fallback in every result
```

The UI server may be deployed separately (for example,
`vgc-mcp-apps.onrender.com/mcp`) or mounted later under a separate endpoint.
Separate deployment is preferred for the first release because it isolates UI
dependencies, CSP changes, asset builds, and cold-start regressions from the
community's stable endpoint.

## First UI tools

Do not create UI wrappers for all 208 tools. Start with a handful of composite
experiences where interaction provides clear value:

| UI tool | Interaction | Reused core output |
|---|---|---|
| Damage lab | Toggle Tera, weather, item, stages, and spreads | Damage ranges, rolls, verdicts, Showdown pastes |
| Speed explorer | Compare normal, Tailwind, Trick Room, Scarf, Booster | Final speeds and ordering |
| Team matrix | Inspect weaknesses, coverage, roles, and item clause | Team analysis and legality |
| Spread studio | Move EV/SP sliders while preserving benchmarks | Breakpoints, final stats, survival/KO checks |
| Battle board | Record HP, status, reveals, field timers, and turns | Session-scoped battle state and suggestions |

Each UI tool must also return a concise text result and structured data. A host
that ignores `_meta.ui.resourceUri` must still receive a useful answer.

## Compatibility gate

Before advertising the UI endpoint broadly, test this matrix:

| Host class | Expected behavior |
|---|---|
| MCP Apps host | Fetches `ui://` resource and renders the sandboxed view |
| Legacy MCP-UI host | Supported only if an explicit compatibility response is added |
| Plain MCP host | Ignores UI metadata and shows the text/structured fallback |
| ChatGPT Apps environment | Validate through the documented MCP-UI/Apps adapter path |

The existing `https://vgc-mcp.onrender.com/mcp` endpoint remains the fallback
and must continue passing its current protocol and 208-tool evaluations.

## Security and operations requirements

- Render self-contained HTML in a sandboxed iframe; do not embed arbitrary
  third-party URLs supplied by tool input.
- Apply a restrictive Content Security Policy. Allow only the assets and
  network destinations the view actually needs.
- Escape serialized Pokemon/team data before embedding it in HTML. Prefer host
  messages or JSON script blocks over string interpolation into executable JS.
- Never put API keys, bearer tokens, cookies, or private session identifiers in
  a UI resource.
- UI actions must call narrow, declared MCP tools and be validated by the same
  Pydantic/core layer as chat-originated calls.
- Pin UI SDK versions and add a dependency-update test; MCP Apps is evolving.
- Keep the UI bundle small enough that Render cold starts and first render do
  not regress the connector handshake.

## Rollout and success criteria

1. Prototype the Damage lab in a sibling package with static fixture data.
2. Wire it to the existing damage handler and preserve the exact fallback
   result used by plain MCP.
3. Run the MCP-UI inspector plus at least one MCP Apps host and one plain host.
4. Deploy it separately and measure tool-call success, first-render time,
   interaction errors, and fallback behavior.
5. Add the other views only after the Damage lab is demonstrably easier than
   the table-based flow.

Adopt the UI endpoint publicly when all of these hold:

- no regression in calculation golden tests;
- plain-host fallback is complete;
- UI initialization succeeds at least 99% in monitored tests;
- warm first render is under two seconds, excluding external API fetch time;
- the view reduces follow-up tool calls or time-to-answer in a small user test.

## Rejected alternatives

### Add `mcp-ui-server` to the existing core dependencies

Rejected because every user would pay the compatibility and maintenance cost,
including clients that cannot display the result.

### Convert all 208 tools to UI tools

Rejected because most lookup and validation tools are clearer as text or
structured data. It would create a large, duplicated presentation surface and
make tool discovery harder.

### Fork calculation logic into a TypeScript UI server

Rejected because damage and format logic would drift. The Python core remains
the single source of truth.
