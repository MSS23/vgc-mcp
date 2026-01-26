# VGC MCP - Your Pokemon Teambuilding Assistant

This is a tool that works inside Claude Desktop to help you build competitive Pokemon VGC teams. Just chat naturally and it will do all the complex math for you!

---

## What Can It Do?

### 1. Speed Calculations
**"Will my Pokemon outspeed theirs?"**

Ask things like:
- "What's the chance my Entei outspeeds Landorus?"
- "How much Speed do I need to outspeed Tailwind Gholdengo?"
- "Show me a speed tier list for the current meta"

It checks real tournament data from Smogon to see what spreads people actually use, then tells you:
- **X% chance to outspeed** (based on common spreads)
- **X% chance to speed tie**
- **X% chance to be outsped**

### 2. Damage Calculations
**"Will this attack KO?"**

Ask things like:
- "Does my Entei's Sacred Fire OHKO Rillaboom?"
- "How much damage does Icicle Crash do to Flutter Mane?"
- "Can my Incineroar survive a Close Combat from Urshifu?"

It calculates:
- Damage range (e.g., "78-92%")
- KO chance (e.g., "guaranteed 2HKO" or "31% chance to OHKO")
- All 16 damage rolls

### 3. EV Spread Builder
**"Build me a spread that survives X and outspeeds Y"**

This is the magic feature. Ask things like:
- "Build a Flutter Mane that survives Icicle Crash from Chien-Pao and outspeeds Tailwind Gholdengo"
- "I want my Entei to live Earthquake from Landorus and outspeed Tornadus"

It will:
1. Figure out exactly how much Speed you need
2. Calculate the minimum bulk to survive
3. Put leftover EVs into offense
4. Give you a complete spread like: `44 HP / 252 Def / 0 SpA / 0 SpD / 212 Spe`

### 4. Team Analysis
**"What threatens my team?"**

- Import a Pokepaste and get analysis
- See type weaknesses across your team
- Identify speed tiers you're missing
- Find coverage gaps

### 5. Usage Stats
**"What's popular right now?"**

- Top Pokemon in the current meta
- Most common moves, items, abilities
- Common EV spreads people are running
- All pulled from live Smogon data

---

## How to Use It

Just open Claude Desktop and chat naturally! Examples:

> "I'm building a Flutter Mane. I want it to outspeed max speed Gholdengo under Tailwind while having Booster Energy boost its Speed. What spread should I use?"

> "Calculate damage: 252 Atk Adamant Chien-Pao Icicle Crash vs my Flutter Mane"

> "What's the probability my 252 Speed Jolly Entei outspeeds Landorus?"

> "Show me the most common Urshifu spreads"

---

## Key Terms

| Term | Meaning |
|------|---------|
| **EVs** | Effort Values - points you allocate to stats (max 508 total, 252 per stat) |
| **Nature** | Boosts one stat by 10%, lowers another by 10% (e.g., Adamant = +Atk -SpA) |
| **OHKO** | One-Hit Knock Out |
| **2HKO** | Two-Hit Knock Out |
| **Tailwind** | Doubles your team's Speed for 4 turns |
| **Booster Energy** | Item that boosts highest stat by 50% (30% for Speed) |
| **Spread** | Your Pokemon's EV distribution |

---

## Example Conversation

**You:** I want to build a bulky Flutter Mane that can survive Chien-Pao's Icicle Crash and Ogerpon's Ivy Cudgel, while still outspeeding Tailwind Gholdengo with Booster Energy.

**Claude:** I'll calculate that for you...

**Result:**
```
Flutter Mane @ Timid
44 HP / 252 Def / 0 SpA / 0 SpD / 212 Spe

- Survives Icicle Crash: 83.8-99.2% (100% survival)
- Survives Ivy Cudgel: 88.2-104.4% (68.75% survival)
- Speed: 200 (300 with Booster) > outspeeds 298 Tailwind Gholdengo
```

---

## Tips

1. **Be specific** - Include natures, items, and EV investments when asking about opponents
2. **Use Pokemon names** - "Lando-T" or "Landorus-Therian" both work
3. **Ask follow-ups** - "What if they have Choice Band?" or "What about Adamant nature?"
4. **Import pastes** - Share a Pokepaste URL and ask for analysis

---

*Powered by live Smogon usage data from VGC 2025 (Reg F)*
