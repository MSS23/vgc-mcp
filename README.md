# VGC MCP — Pokémon damage calc, spreads, and team coaching for any AI assistant

> **Showdown-accurate damage calcs, EV optimization, and a live battle copilot — over MCP. Plug into Claude Desktop, ChatGPT, or any MCP-compatible client and ask in plain English.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![Live](https://img.shields.io/badge/live-vgc--mcp.onrender.com-brightgreen)](https://vgc-mcp.onrender.com/health)
[![CI](https://github.com/MSS23/vgc-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/MSS23/vgc-mcp/actions/workflows/ci.yml)
[![Tools](https://img.shields.io/badge/MCP%20tools-206-blueviolet)](docs/tools-catalog.md)

A **Model Context Protocol** server that turns any LLM into a competitive Pokémon VGC coach. **206 tools** spanning the full Gen 9 damage formula, Smogon usage data, multi-threat EV optimization, replay analysis, and a turn-by-turn live battle copilot. Clients get a focused **34-tool core** by default, so the model picks the right tool first time, even on a phone.

```
You:    Does Tera-Normal Entei live a Sheer-Force Life-Orb Earth Power
        from Timid 252 SpA Landorus, after one chip of Life Orb damage?

Claude: [calls calculate_damage_output once]

        | Side     | Pokémon  | Nature  | EVs            | Item        | Tera   |
        |----------|----------|---------|----------------|-------------|--------|
        | Attacker | Landorus | Timid   | 0/0/0/252/4/252| Life Orb    | —      |
        | Defender | Entei    | Adamant | 4/252/0/0/0/252| Choice Band | Normal |

        | Move        | Damage  | % HP        | Verdict @ 90% HP             |
        |-------------|---------|-------------|------------------------------|
        | Earth Power | 149-177 | 78.4-93.1%  | 75% survival (12/16 rolls)   |
```

---

## Why this exists

**Objective:** Give competitive Pokémon players exact answers (damage, spreads, speed, team prep) inside the AI assistant they already use, for both mainline VGC and Pokémon Champions, readable on a phone.

**Success looks like:** Calcs match Pokémon Showdown's calculator roll for roll; the format is detected without the user asking; the model picks the right tool first time; the hosted server stays free.

Every VGC team-builder is a wall of UI: type into a calculator, copy-paste a paste, click through tabs, run again. **VGC MCP collapses that loop into a conversation.** Claude does the calc, picks the right tool from the 34 core tools (damage, speed, survival, spreads, team prep, live battle), and leads with a one-line answer laid out for a phone screen.

**Built for:**
- 🏆 **Competitive players** — pre-tournament prep, live in-game coaching, post-game replay analysis
- 🛠 **Team builders** — multi-threat survival optimization, breakpoint finding, build deltas
- 📚 **Newcomers** — explain VGC terms, show legal sets, suggest archetypes

---

## What you get

**🧮 Damage calculations** — Full Gen 9 formula, [verified against Pokémon Showdown's calc](#correctness). Tera, Life Orb, Sheer Force stacking, Ruin abilities, screens, weather, terrain, multi-hit moves, always-crit moves, item-ability synergies, prior chip damage. *One tool call answers questions other calculators need three for.*

**📊 EV optimization** — Find minimum EVs to outspeed / OHKO / survive. Optimize against **3–6 threats simultaneously**. Auto-pick the optimal nature. Showdown paste in every output, ready to copy.

**Team preparation in one MCP call** — `prepare_team` combines a Showdown paste, dated chaos opponents, rules checks, speed tiers, damage comparisons and requested verified spread alternatives. Export the report as Markdown, JSON, Excel or PDF. [Workflow guide](docs/preparation-workflows.md).

**Verified alternatives and move outcomes** — Recheck final spreads, compare minimum-investment/offensive/bulky choices, and calculate misses, variable hit counts, consumed berries and Parental Bond. Complete imported reference sets remain separate from chaos usage components.

**⚡ Live battle copilot** — `start_battle` → `record_turn` → `suggest_next_move`. Persistent state (HP%, status, stat stages, revealed items/abilities, Tera usage, weather/screen timers) across turns so the agent coaches you between turns.

**📼 Replay analyzer** — Paste a `replay.pokemonshowdown.com` URL. Get turn-by-turn breakdown, key moments (KOs, Tera timing, weather wars), and concrete coaching takeaways.

**🎯 Focused by default** — `/mcp` serves 34 core tools; `/mcp/full` serves all 206, including spread iteration deltas, archetype classification and breakpoint Pareto-optimal options.

**🌐 Live and free** — Hosted at `https://vgc-mcp.onrender.com/mcp` (Streamable HTTP; legacy SSE at `/sse`) and kept awake around the clock on the free tier.

[**→ Browse the full 206-tool catalog**](docs/tools-catalog.md)

---

## Install in 30 seconds

### Option A — Hosted (zero install)

In **Claude.ai → Settings → Connectors → Add custom connector**, paste:

```
https://vgc-mcp.onrender.com/mcp
```

Start a new chat. Done. It also works in the Claude phone app once added.

Want every tool, not just the core 34? Use `https://vgc-mcp.onrender.com/mcp/full`.
Older clients that only speak the legacy HTTP+SSE transport can use
`https://vgc-mcp.onrender.com/sse`.

> **Note:** the server runs on Render's free tier, which sleeps after 15
> idle minutes. A scheduled keep-alive keeps it awake, so replies should be
> instant; if one ever takes 30-60 s, it was asleep and the next will be quick.

### Option B — Local (Claude Desktop, free)

```bash
git clone https://github.com/MSS23/vgc-mcp.git
cd vgc-mcp
pip install -e .
```

Add to your Claude Desktop config (`%APPDATA%\Claude\claude_desktop_config.json` on Windows, `~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):

```json
{
  "mcpServers": {
    "vgc": { "command": "vgc-mcp" }
  }
}
```

Restart Claude Desktop. Done. **[Full setup guide →](docs/user-guide.md#connect-2-minutes)**

### Option C — Self-host

```bash
docker run -p 8000:8000 ghcr.io/mss23/vgc-mcp:latest
# or: render / fly.io / heroku — see docs/deploy.md
```

---

## Try these prompts

```
"Does my Flutter Mane OHKO Incineroar with Moonblast?"

"What EVs does Ogerpon-Hearthflame need to survive
 Choice Scarf Adamant Urshifu's Surging Strikes 93.75% of the time?"

"What's the cheapest spread for Entei to outspeed Choice Scarf Incineroar?
 Show me the +Speed and neutral options."

"Compare Tera Fairy vs Tera Fire on Ogerpon-Hearthflame against
 Urshifu-Rapid-Strike, Flutter Mane, and Rillaboom."

"I'm starting a VGC match. My team is [paste]. Their preview shows
 [4 Pokémon]. I'm leading [X, Y]. They're leading [A, B]. What now?"

"Analyze this replay and tell me what the loser could have done
 differently: https://replay.pokemonshowdown.com/<id>"
```

---

## Correctness

Damage calc is verified against **Pokémon Showdown** — the source of truth used by every major calculator (`@pkmn/calc`). Live test on the very first prompt above:

| Source            | Damage    | Percent       | Verdict           |
|-------------------|-----------|---------------|-------------------|
| Pokémon Showdown  | 149-177   | 78.4 - 93.1%  | guaranteed 2HKO   |
| **VGC MCP**       | **149-177** | **78.4-93.1%** | **guaranteed 2HKO** |

The test suite covers Gen 9 damage, stats, items, abilities, Tera, weather, multi-hit probabilities, and MCP tool registration. An independent oracle suite pins 2,037 exact-roll cases from `@smogon/calc 0.11.0`; an integer-formula grid checks mainline EVs and Champions Stat Points. See the [preparation workflow guide](docs/preparation-workflows.md#mathematical-scope) for supported mechanics and limits.

Meta sets come directly from Smogon's monthly `chaos/*.json` datasets. The
active MCP regulation selects the matching Reg I / Champions MA / MB / MC
format, with 1630 as the default competitive weighting. Every usage response
reports its resolved format, month, rating, and source URL; callers may request
0 (unweighted), 1500 (average ladder), 1630 (competitive), or 1760 (elite).

Common-set components are independent usage rankings: chaos data does not
identify which complete item/ability/moves/spread combination was used together.
Move and teammate percentages measure inclusion among that Pokemon's weighted
occurrences. Trend comparisons use the actual resolved month and the same ladder
and rating for the preceding month.

---

## Tool catalog (highlights)

Full list, with the core tools starred: [`docs/tools-catalog.md`](docs/tools-catalog.md).

| Core area | Tools at `/mcp` |
|---|---|
| **Damage** | `calculate_damage_output`, `calc_damage_vs_smogon_sets`, `calculate_bulk_offensive_calcs`, `calculate_move_outcomes` |
| **Spreads** | `find_survival_evs`, `optimize_multi_survival_spread`, `design_spread_with_benchmarks`, `verify_spread_benchmarks` |
| **Speed** | `compare_speed`, `find_speed_evs_to_outspeed`, `analyze_outspeed_probability` |
| **Teams** | `prepare_team`, `import_and_analyze`, `get_usage_stats`, `validate_team_legality` |
| **Live battle** | `start_battle`, `record_turn`, `suggest_next_move`, `analyze_replay` |

`/mcp/full` adds breakpoints, KO thresholds, archetypes, game plans, spread
deltas, the tool router and more.

---

## Architecture

```
src/
├── vgc_mcp_core/         # Shared library (calc, models, API clients, data, state)
│   ├── calc/             # Pure functions — Gen 9 damage formula, stats, speed
│   ├── api/              # PokeAPI + Smogon Stats clients (cached)
│   ├── state/            # BuildStateManager, BattleStateManager
│   └── ...
└── vgc_mcp/              # MCP server — auto-discovers tool modules
    ├── profiles.py       # 34 core tools at /mcp; all 206 at /mcp/full
    └── tools/            # 50 auto-discovered modules
```

Auto-discovery means **adding a tool requires zero edits** to `server.py` — drop a `<area>_tools.py` in `vgc_mcp/tools/` exposing `register_<area>_tools(mcp, ...)` and it's picked up.

**Stack:** Python 3.11+, `mcp`, `httpx`, `pydantic`, `diskcache`, `openpyxl`, `fpdf2`. No MCP-UI dependency — works with every Claude / ChatGPT MCP transport today.

Interactive VGC views are a strong fit, but they will be delivered as an
optional sibling MCP Apps server so this endpoint stays universal. See the
[MCP-UI / MCP Apps architecture decision](docs/mcp-ui-decision.md).

[**Full architecture writeup →**](docs/technical-guide.md)

---

## Documentation

| Audience | Doc |
|---|---|
| **Just want to use it** | [User guide](docs/user-guide.md) · [FAQ](docs/faq.md) |
| **Want to deploy your own** | [Deploy](docs/deploy.md) · [CI/CD](docs/ci-cd.md) |
| **Want to contribute** | [Contributing](CONTRIBUTING.md) · [Development](docs/development.md) · [Architecture](docs/technical-guide.md) |
| **Building MCP clients** | [API reference](docs/api-reference.md) · [Tool catalog](docs/tools-catalog.md) |

---

## Contributing

PRs welcome. The fastest way to ship value is to add a new tool module:

1. Drop `vgc_mcp/tools/<area>_tools.py` exposing `register_<area>_tools(mcp, ...)`
2. Auto-discovery picks it up — no `server.py` edit
3. Add tests in `tests/tools/test_<area>_tools.py`

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/development.md](docs/development.md) for the full pattern (handlers in `vgc_mcp_core/tools/`, error contracts, presentation rules).

---

## Status

- ✅ Live at `https://vgc-mcp.onrender.com/mcp` (core) and `/mcp/full` (all 206 tools)
- ✅ Kept awake on the free tier by a chained keep-alive workflow
- ✅ Full offline test suite, strict lint and a ratcheting mypy gate in CI
- ✅ CI-gated deploys from `main`, followed by exact-revision production MCP verification
- ✅ MIT licensed — fork it, ship it, no strings

---

## License

MIT — see [LICENSE](LICENSE).

---

**Built with [Model Context Protocol](https://modelcontextprotocol.io/).** Questions? Open an [issue](https://github.com/MSS23/vgc-mcp/issues).
