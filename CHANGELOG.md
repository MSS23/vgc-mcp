# Changelog

All notable changes to the VGC MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive production documentation:
  - `TECHNICAL_GUIDE.md` - MCP architecture explained for beginners
  - `DEVELOPMENT.md` - Developer workflow and contribution guide
  - `DEPLOYMENT.md` - Deployment options (Docker, Fly.io, Render, self-hosted)
  - `API_REFERENCE.md` - Complete tool catalog with examples
  - `FAQ.md` - Frequently asked questions and troubleshooting
  - `CONTRIBUTING.md` - Contribution guidelines and code of conduct
  - `LICENSE` - MIT License
- Beginner-friendly MCP protocol explanations with analogies
- Complete API reference documenting all 157+ tools
- Deployment guides for multiple platforms

### Changed
- Deduplicated setup documentation (SETUP_GUIDE.md, LOCAL_SETUP.md)
- Simplified README.md with focus on quick start
- Updated USER_GUIDE.md to focus on usage rather than setup
- Improved documentation cross-linking
- Prioritized free Claude Desktop local setup in all docs

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
