# Changelog

All notable changes to the VGC MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Tool discovery is now fail-fast: import failures, misnamed registration
  functions, unresolved required dependencies, empty tool modules, and
  duplicate tool names abort startup instead of exposing a silently partial
  service. `/health` and `/` now report both the 51 discovered modules and 208
  registered tools.
- Added an MCP-UI/MCP Apps architecture decision. Interactive views are a good
  fit for damage, speed, team, spread, and battle workflows, but will live in
  an optional sibling server so the public plain-MCP endpoint remains compatible
  with every client.
- Render and self-host deployment documentation now uses the real
  `vgc-mcp-http` entrypoint and matches the live health response.
- CI now uses the current Node 24 GitHub Action generations
  (`actions/checkout@v7` and `actions/setup-python@v6`).
- Package version bumped to **1.0.0** (the root endpoint previously hardcoded
  "1.0.0" while the package said 0.1.0; both now agree, and the endpoint
  reads the real installed version).
- **All 208 MCP tools modernized to professional MCP Python SDK style.** Every
  tool now declares `Annotated[type, Field(...)]` parameters (descriptions plus
  `ge`/`le`/`min_length` constraints surfaced in the JSON schema), a
  human-readable `title`, and `ToolAnnotations` hints (`readOnlyHint`,
  `destructiveHint`, `idempotentHint`, `openWorldHint`) so MCP clients can
  reason about side effects. Docstring `Args:` blocks were folded into the
  Field descriptions. No tool names, parameter names, defaults, or behavior
  changed.
- Champions documentation corrected against primary sources (Bulbapedia,
  Serebii, Game8): the official closed-form SP formula
  (`HP = Base + SP + 75`, `Stat = floor((Base + SP + 20) x Nature)`) is
  documented and verified bit-for-bit identical to the implementation;
  32 SP == 252 EVs exactly; HOME conversion `SP = (EVs + 4) / 8`.

### Fixed
- Champions multi-threat bulk optimization now solves physical and special
  defenses independently for each shared HP breakpoint instead of sweeping
  every HP/Defense/SpD combination. The representative regression case drops
  from roughly 85 seconds to under a tenth of a second without changing the
  minimum-allocation objective; a damage-call budget guards the fast path.
- **Connection reliability (claude.ai connectors):** `POST /sse` no longer
  returns a bare 405 — it forwards to the Streamable HTTP handler, so a
  streamable client configured with the legacy `/sse` URL completes its
  handshake anyway (`DELETE /sse` forwards too). Docs and `smithery.yaml`
  now present `/mcp` as the primary connector URL with `/sse` marked
  legacy-only. The keep-alive workflow pings in a 24-minute loop per run to
  survive GitHub cron drift (an external 5-min uptime monitor is still the
  recommended primary pinger — see docs/connection-fix-plan.md). The root
  endpoint reports the real package version instead of a hardcoded "1.0.0".
- Champions has no IVs (every Pokemon acts as 31 IV): `get_pokemon_speed` in a
  Champions session no longer reports an impossible "Brave 0 IV" minimum speed
  and now pins the SP formula to IV 31; presentation instructions now warn
  against recommending 0-Spe/0-Atk IV tech in Champions.
- Showdown import: official Showdown Champions pastes reuse the `EVs:` line
  with SP-scale values (0-32, total <= 66). `parsed_to_pokemon_build` now
  reinterprets such a line as Stat Points when the format resolves to
  Champions (explicit `format_hint`, session regulation, or Mega-name
  inference), instead of misreading it as a mainline EV spread.
- `optimize_dual_survival_spread`: the HP-item-optimization branch crashed with
  `NameError` (undefined `mods1`/`mods2`) whenever a defender item triggered an
  HP EV adjustment. Damage modifiers are now rebuilt for the re-verification
  pass, and regression tests cover the path.
- `compare_speed` / team-template speed benchmarks in workflow tools crashed with
  `NameError: EV_BREAKPOINTS_LV50` when the slower Pokemon needed EV suggestions
  (missing module-level import).
- Restored Python 3.11 compatibility: `check_build_for_mistakes` used 3.12-only
  nested f-string quoting; the full test suite now passes on 3.11, 3.12 and 3.13,
  matching `requires-python >= 3.11`.
- `calculate_damage`: removed a local `dataclasses.replace` import that shadowed
  the module-level import.
- Pydantic v2 deprecation: `BaseStats` now uses `ConfigDict` instead of
  class-based `Config`.

### Added
- Streamable HTTP transport at `/mcp` (what Claude.ai custom connectors and
  current MCP clients expect), served alongside the legacy HTTP+SSE
  transport at `/sse`. Root and `/health` endpoints advertise both.
- Champions EV->SP auto-conversion at tool entry points: `add_to_team`,
  `swap_team_pokemon`, `create_build` and `modify_build` now detect EV-scale
  input (any stat > 32) in a Champions (Reg MA/MB) session and convert it to
  Stat Points (1 SP = 8 EVs, rounded up, trimmed to the 66 budget) instead of
  rejecting it with "exceeds per-stat max (32)". Responses include an
  `sp_conversion` note showing the translation. Native SP input (all stats
  0-32) passes through unchanged; mainline sessions are unaffected.
  (`coerce_champions_allocation` in `vgc_mcp_core.calc.conversion`.)

### Changed
- Lint: cleaned up the entire historical ruff backlog (~1,900 findings — unused
  imports, unsorted imports, dead assignments, misplaced module-level imports,
  one-line `if` statements, ambiguous names). `ruff check src/ tests/` is now
  clean and CI enforces it as a hard gate.
- CI matrix now tests Python 3.11, 3.12 and 3.13.
- README/smithery badges updated to the real counts (208 tools, 1,417 tests).
- Deduplicated setup documentation (SETUP_GUIDE.md, LOCAL_SETUP.md)
- Simplified README.md with focus on quick start
- Updated USER_GUIDE.md to focus on usage rather than setup
- Improved documentation cross-linking
- Prioritized free Claude Desktop local setup in all docs

### Added
- Comprehensive production documentation:
  - `docs/technical-guide.md` - MCP architecture explained for beginners
  - `docs/development.md` - Developer workflow and contribution guide
  - `docs/deploy.md` - Deployment options (Docker, Fly.io, Render, self-hosted)
  - `docs/api-reference.md` - Complete tool catalog with examples
  - `docs/faq.md` - Frequently asked questions and troubleshooting
  - `CONTRIBUTING.md` - Contribution guidelines and code of conduct
  - `LICENSE` - MIT License
- Beginner-friendly MCP protocol explanations with analogies
- Complete API reference documenting all 157+ tools
- Deployment guides for multiple platforms

### Removed
- Build artifacts (`dist/` directory) from repository
- Redundant setup instructions across multiple docs

## [0.1.0] - 2026-01-28

### Fixed
- **Critical**: Fixed 3 damage calculation bugs - all calculations now match Pokemon Showdown exactly ([6019acb](https://github.com/MSS23/vgc-mcp/commit/6019acb))
  - Corrected damage formula rounding behavior
  - Fixed type effectiveness multiplier stacking
  - Fixed critical hit damage calculation
- **Critical**: Fixed Life Orb + Sheer Force interaction in damage calculations ([4f29388](https://github.com/MSS23/vgc-mcp/commit/4f29388))
  - Life Orb recoil is correctly negated when Sheer Force activates
  - Life Orb boost is properly applied to moves with secondary effects
- Fixed speed stage and HP EV calculation bugs ([014645f](https://github.com/MSS23/vgc-mcp/commit/014645f))
  - Speed stages now correctly apply in speed comparisons
  - HP EV calculations now account for rounding properly
- Fixed Surging Strikes calculation for Ogerpon ([78bbd2d](https://github.com/MSS23/vgc-mcp/commit/78bbd2d))
  - Removed incorrect Tera type assumption in damage calculations
- Fixed Ogerpon Tera type display in spread optimization tools ([e2e9816](https://github.com/MSS23/vgc-mcp/commit/e2e9816))

### Added
- Multi-survival spread optimization (`optimize_multi_survival_spread`) for 3-6 threats
- Dual survival spread optimization (`optimize_dual_survival_spread`)
- Prominent Showdown paste output in all spread tools ([f4f2697](https://github.com/MSS23/vgc-mcp/commit/f4f2697))
- `pokemon_build_to_showdown` utility function ([6e510e9](https://github.com/MSS23/vgc-mcp/commit/6e510e9))
- Comprehensive spread optimization with damage caching (7x speedup)

### Changed
- **Documentation**: Prioritized free Claude Desktop local setup ([3c1093a](https://github.com/MSS23/vgc-mcp/commit/3c1093a))
  - Updated all setup guides to emphasize local = free
  - Clarified remote setup requires premium subscription
  - Improved verification steps
- Improved Smogon auto-fetch behavior ([1dd5d78](https://github.com/MSS23/vgc-mcp/commit/1dd5d78))
  - Auto-fetch is prevented when user manually specifies EVs
  - Respects explicit EV configurations
- Enhanced survival EV calculations with better error messages
- Optimized bulk optimization performance with caching

### Technical
- All damage calculations verified against Pokemon Showdown
- Extensive test coverage for Gen 9 mechanics
- Support for Gen 9 abilities: Protosynthesis, Quark Drive, Embody Aspect, Mind's Eye, Scrappy
- Support for Gen 9 moves: Ivy Cudgel, Psyblade, Collision Course, Electro Drift, Salt Cure
- Full Tera type mechanics including Stellar type
- Multi-hit move support (Surging Strikes, Population Bomb, etc.)
- Complete VGC Regulation H legality checking

## [0.0.1] - 2025-12-15

### Added
- Initial release of VGC MCP Server
- 157+ tools for competitive Pokemon team building
- Full Gen 9 damage formula implementation
- Smogon usage statistics integration
- Speed tier analysis
- EV/IV optimization
- Team import/export (Showdown paste format)
- VGC format legality checking
- Coverage analysis and threat identification
- MCP-UI support for interactive displays
- Three server variants: full, lite, micro
- Local (stdio) and remote (HTTP/SSE) deployment options
- Docker, Fly.io, and Render deployment configs
- Comprehensive test suite (337+ tests)
- API response caching (7-day TTL)

---

## Version History

- **0.1.0** (2026-01-28): Critical bug fixes, multi-survival optimization, documentation improvements
- **0.0.1** (2025-12-15): Initial release

[Unreleased]: https://github.com/MSS23/vgc-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/MSS23/vgc-mcp/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/MSS23/vgc-mcp/releases/tag/v0.0.1
