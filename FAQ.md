# Frequently Asked Questions (FAQ)

Common questions and troubleshooting for the VGC MCP Server.

## Table of Contents

- [Setup & Installation](#setup--installation)
- [Usage Questions](#usage-questions)
- [Features & Capabilities](#features--capabilities)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

---

## Setup & Installation

### Does this work on FREE Claude Desktop?

**Yes!** The local setup works perfectly on the free version of Claude Desktop. No premium subscription required.

- **Local setup** (recommended): FREE ✅
- **Remote setup**: Requires Claude Desktop Premium 💎

See [LOCAL_SETUP.md](LOCAL_SETUP.md) for installation instructions.

---

### Claude doesn't see the VGC tools

**Solution 1: Verify configuration file**

1. Check your Claude Desktop config file exists:
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Linux**: `~/.config/claude/claude_desktop_config.json`

2. Verify it contains:
   ```json
   {
     "mcpServers": {
       "vgc": {
         "command": "python",
         "args": ["-m", "vgc_mcp"]
       }
     }
   }
   ```

**Solution 2: Reinstall package**

```bash
pip install -e .
```

**Solution 3: Restart Claude Desktop**

- Fully close Claude Desktop (check system tray/menu bar)
- Reopen and start a new conversation

**Solution 4: Check server runs manually**

```bash
python -m vgc_mcp
# Should start without errors
# Press Ctrl+C to stop
```

---

### Python not found

**Windows:**

1. Install Python 3.11+ from https://python.org
2. During installation, CHECK "Add Python to PATH"
3. Restart your terminal
4. Verify: `python --version`

**If still not found:**

Use full Python path in config:

```json
{
  "mcpServers": {
    "vgc": {
      "command": "C:\\Python313\\python.exe",
      "args": ["-m", "vgc_mcp"]
    }
  }
}
```

Find path with: `where python` (Windows) or `which python` (Mac/Linux)

---

### Module not found: vgc_mcp

**Solution:**

```bash
# Navigate to project directory
cd path/to/vgc-mcp

# Install in development mode
pip install -e .

# Verify installation
pip show vgc-mcp
```

**Still not working?**

Check you're using the correct Python:

```bash
python --version  # Should be 3.11+
pip --version     # Should match Python version
```

---

### How do I know if I'm using local vs remote?

**Check your config file:**

**Local setup (FREE):**
```json
{
  "mcpServers": {
    "vgc": {
      "command": "python",  // ← Has "command"
      "args": ["-m", "vgc_mcp"]
    }
  }
}
```

**Remote setup (Premium required):**
```json
{
  "mcpServers": {
    "vgc": {
      "url": "https://..."  // ← Has "url"
    }
  }
}
```

**Check response speed:**
- **Local**: Instant responses (<100ms)
- **Remote**: Noticeable delay (200-500ms)

**Check Claude Desktop MCP indicator:**
- Should show "vgc" server as connected

---

## Usage Questions

### How accurate are the damage calculations?

**100% accurate** - We use the exact Gen 9 damage formula that Pokemon Showdown uses.

All calculations are verified against Pokemon Showdown and include:
- STAB (Same Type Attack Bonus)
- Type effectiveness
- Weather and terrain modifiers
- Items (Life Orb, Choice items, type-boosting items)
- Abilities (Protosynthesis, Adaptability, etc.)
- Multi-hit moves (Surging Strikes always crits)
- Tera type mechanics (2x STAB when Tera matches move type)

If you get different results than Showdown, check:
1. Both Pokemon have same EVs, nature, item
2. Weather, terrain, and field effects match
3. Abilities are the same

---

### Where does the usage data come from?

**Smogon Stats** at 1760 ELO rating cutoff.

- **Source**: https://www.smogon.com/stats/
- **Format**: `{YYYY-MM}/chaos/gen9vgc2024regh-1760.json`
- **Rating**: 1760 (highest available, most competitive)
- **Available ratings**: 0, 1500, 1630, 1760
- **Update frequency**: Monthly
- **Auto-detection**: Automatically finds latest available month

This data represents the top ~10-15% of competitive players.

---

### Can I use this for singles format?

The server is optimized for VGC **doubles** format, but calculations work for singles too.

**What works in singles:**
- ✅ Damage calculations
- ✅ Speed comparisons
- ✅ EV optimization
- ✅ Type matchups

**What's VGC-specific:**
- ❌ Spread move reduction (0.75x in doubles)
- ❌ Team of 4 from 6 (singles is 3 from 6)
- ❌ Doubles-specific moves (Coaching, Decorate)

**To use for singles:**

Just specify singles-specific spreads and ignore team building tools.

---

### How do I paste a team?

**Showdown paste format:**

```
Flutter Mane @ Choice Specs
Ability: Protosynthesis
Tera Type: Fairy
EVs: 4 HP / 252 SpA / 252 Spe
Timid Nature
IVs: 0 Atk
- Moonblast
- Shadow Ball
- Dazzling Gleam
- Mystical Fire

Incineroar @ Assault Vest
Ability: Intimidate
...
```

**Usage:**

Say to Claude:
> "Analyze this team:" [paste]

Or:
> "Import this team:" [paste]

---

### What if a Pokemon has a specific EV spread?

Specify EVs in your question:

> "Does my **252 SpA Timid** Flutter Mane OHKO **252 HP / 60 SpD Adamant** Incineroar?"

The server will use your specified EVs instead of auto-fetching from Smogon.

**Tips:**
- Specify nature AND EVs for accuracy
- Mention items if relevant ("Choice Specs Flutter Mane")
- Include Tera type if active ("Tera Fairy Flutter Mane")

---

## Features & Capabilities

### Does it support Tera types?

**Yes!** Full Tera mechanics including:

- ✅ Tera type change (e.g., Landorus becomes pure Flying when Tera Flying)
- ✅ 2x STAB when Tera type matches move type
- ✅ Stellar type (2x boost vs Tera'd opponents, single-use per type)
- ✅ Tera Blast type and category changes
- ✅ Defensive typing changes

**Example:**

> "What's the damage if Tera Fire Landorus uses Earthquake?"

(Landorus becomes pure Fire when Tera'd, so loses STAB on Earthquake)

---

### Can it handle multi-hit moves?

**Yes!** Including:

- **Surging Strikes**: 3-hit move that always crits (Urshifu)
- **Population Bomb**: Up to 10 hits (Maushold)
- **Triple Axel**: 3 hits with increasing power
- **Icicle Spear, Bullet Seed**: 2-5 hits
- **Bone Rush**: 2-5 hits

**Example:**

> "Does Urshifu's Surging Strikes OHKO Ogerpon?"

The calculation accounts for 3 hits and guaranteed crits.

---

### Does it know about new Gen 9 abilities?

**Yes!** All Gen 9 abilities supported:

**Paradox Abilities:**
- **Protosynthesis** (Ancient Pokemon): Highest stat +30% or +1 stage in sun
- **Quark Drive** (Future Pokemon): Highest stat +30% or +1 stage in Electric Terrain

**Ogerpon Abilities:**
- **Embody Aspect**: Different stat boosts based on mask
  - Hearthflame: +Atk
  - Wellspring: +SpD
  - Cornerstone: +Def

**New Abilities:**
- **Mind's Eye**: Ignores accuracy/evasion, Normal/Fighting hit Ghost
- **Scrappy**: Normal/Fighting hit Ghost
- **Sheer Force**: Removes secondary effects, boosts power 1.3x (+ negates Life Orb recoil)

---

### Can I optimize for multiple survival benchmarks?

**Yes!** Use `optimize_multi_survival_spread` for 3-6 threats:

> "Design a spread for Ogerpon that survives Urshifu Surging Strikes, Flutter Mane Moonblast, AND Chi-Yu Heat Wave"

The tool finds optimal HP/Def/SpD EVs to survive ALL specified threats.

**Performance:**
- 3 threats: ~5-8 seconds
- 6 threats: ~15-30 seconds

**For 2 threats only**, use `optimize_dual_survival_spread` (faster).

---

## Troubleshooting

### Calculations seem wrong

**Check these common issues:**

1. **EVs differ from Showdown**
   - Verify exact EV spread matches
   - Check nature is the same
   - Confirm items match

2. **Modifiers not accounted for**
   - Weather (sun, rain, etc.)
   - Terrain (Electric, Grassy, etc.)
   - Screens (Reflect, Light Screen)
   - Abilities (Intimidate, Protosynthesis)

3. **Tera type active**
   - Tera type changes STAB and defensive typing
   - Specify Tera type if active

4. **Multi-hit moves**
   - Surging Strikes hits 3x and always crits
   - Population Bomb hits up to 10x

**Still incorrect?** Open an issue with:
- Expected result (from Showdown)
- Actual result (from VGC MCP)
- Full parameters (Pokemon, EVs, nature, item, etc.)

---

### Server is slow

**Local setup should be instant**. If it's slow:

**Issue 1: First request (cache warming)**
- First request fetches from PokeAPI/Smogon (500-1000ms)
- Subsequent requests use cache (<50ms)

**Issue 2: Using remote server instead of local**
- Check config has `"command": "python"`, not `"url": "..."`
- Remote server has network latency (200-500ms)

**Issue 3: Cache issues**
- Clear cache: `rm -rf data/cache/`
- Restart server

**Issue 4: Python performance**
- Use Python 3.11+ (faster than 3.9/3.10)
- Close other programs using CPU

---

### I get API errors

**PokeAPI errors:**

- **429 Too Many Requests**: Rate limited
  - Wait 60 seconds, try again
  - Cache should prevent this for repeated requests

- **404 Not Found**: Pokemon/move name incorrect
  - Check spelling (use lowercase, hyphens: "flutter-mane")
  - Use fuzzy matching: Server will suggest corrections

**Smogon Stats errors:**

- **404 Not Found**: Format or month doesn't exist
  - Server auto-detects latest month
  - Check format name is correct

**Network errors:**

- **Connection timeout**: Internet connectivity issue
  - Check internet connection
  - Try again

---

### How do I update to the latest version?

**Local setup:**

```bash
cd vgc-mcp
git pull origin main
pip install -e .
```

Then restart Claude Desktop.

**Check current version:**

```bash
pip show vgc-mcp
```

**Remote setup:**

Updates happen automatically on the server.

---

## Advanced Usage

### Can I run this on a server?

**Yes!** See [DEPLOYMENT.md](DEPLOYMENT.md) for:

- Docker deployment
- Fly.io deployment (production)
- Render deployment (easy, free tier)
- Self-hosted HTTP server (full control)

**Quick Docker setup:**

```bash
docker build -t vgc-mcp .
docker run -p 8000:8000 vgc-mcp
```

---

### How do I contribute?

See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup
- Code style guidelines
- Testing requirements
- Pull request process

**Quick start:**

```bash
git clone https://github.com/MSS23/vgc-mcp.git
cd vgc-mcp
pip install -e ".[dev]"
python -m pytest tests/
```

---

### Can I use this with other AI models?

**Yes!** Any MCP-compatible client can use this server.

**Compatible clients:**
- ✅ Claude Desktop (recommended)
- ✅ Claude.ai web (via remote server)
- ✅ Any MCP-compatible chat client
- ✅ Custom applications using MCP SDK

**Not compatible:**
- ❌ ChatGPT (OpenAI doesn't support MCP)
- ❌ Gemini (Google doesn't support MCP)
- ❌ Direct API access without MCP client

---

### Is there an API I can call directly?

**For programmatic access**, use the HTTP/SSE endpoint:

**Setup:**

```bash
pip install -e ".[remote]"
python -m vgc_mcp_http
```

**Server runs on:** `http://localhost:8000`

**Endpoints:**
- `/sse` - Server-Sent Events endpoint for MCP
- `/health` - Health check

**MCP Protocol:**

Send JSON-RPC messages to `/sse`:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "calculate_damage_output",
    "arguments": {
      "attacker_name": "flutter-mane",
      "defender_name": "incineroar",
      "move_name": "moonblast"
    }
  }
}
```

See [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md) for protocol details.

---

### Can I cache data longer than 7 days?

**Yes!** Edit the cache TTL:

```python
# api/cache.py
cache = Cache("data/cache", size_limit=100_000_000)

# Change TTL (in seconds)
# 7 days = 604800
# 30 days = 2592000
# 1 year = 31536000

def cached_get(key, fetch_func, ttl=2592000):  # 30 days
    # ...
```

**Trade-offs:**
- ✅ Fewer API calls
- ✅ Faster responses
- ❌ Outdated data (if Pokemon stats/moves change)
- ❌ Larger cache size

---

### How much disk space does the cache use?

**Typical cache size:**
- Fresh install: 0 MB
- After 100 damage calculations: ~10-20 MB
- After 1000 calculations: ~50-100 MB
- Max cache size: 100 MB (configurable)

**To check cache size:**

```bash
du -sh data/cache/
```

**To clear cache:**

```bash
rm -rf data/cache/
```

---

## Still Have Questions?

- **Technical details**: [TECHNICAL_GUIDE.md](TECHNICAL_GUIDE.md)
- **Development**: [DEVELOPMENT.md](DEVELOPMENT.md)
- **Deployment**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **API reference**: [API_REFERENCE.md](API_REFERENCE.md)
- **Report issues**: https://github.com/MSS23/vgc-mcp/issues
- **Discussions**: https://github.com/MSS23/vgc-mcp/discussions

---

**Last Updated**: 2026-01-28
