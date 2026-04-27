# VGC Team Builder - Complete Guide

Your AI-powered Pokemon VGC team building assistant with 138+ tools!

---

## Quick Start

### Just Ask Naturally

The easiest way to use VGC Team Builder is to ask questions in plain English:

| What You Want | Just Say... |
|---------------|-------------|
| Check damage | "Does Flutter Mane OHKO Incineroar?" |
| Build a team | "Help me build a Rain team" |
| Optimize EVs | "What EVs does Incineroar need to survive Flutter Mane?" |
| Compare speeds | "Is Landorus faster than Tornadus?" |
| Learn VGC | "Explain what EVs are" |
| Analyze team | "Analyze my team" (then paste it) |

---

## Quick Action Buttons (Claude Desktop)

Click these buttons in Claude Desktop to get started:

| Button | What It Does |
|--------|--------------|
| **Check Damage** | Calculate if one Pokemon can KO another |
| **Build Team** | Step-by-step team building guidance |
| **Analyze Paste** | Analyze a team you paste from Showdown |
| **Learn VGC** | Learn competitive Pokemon basics |
| **Optimize Spread** | Find the best EV spread for your Pokemon |
| **Compare Speeds** | See who outspeeds who |

---

## All Features by Category

### Damage Calculations

Calculate damage, find KO thresholds, and optimize survival.

| Say This... | To Do This |
|-------------|------------|
| "Does Flutter Mane OHKO Incineroar?" | Full damage calculation |
| "Can Amoonguss survive Flutter Mane's Moonblast?" | Check survival |
| "What EVs does Incineroar need to survive Flutter Mane?" | Find survival EVs |
| "What attack EVs to OHKO Incineroar?" | Find offensive EVs |
| "Show damage over multiple turns with chip" | Multi-turn damage |
| "Analyze my Pokemon's bulk vs the meta" | Bulk analysis vs threats |

**Available Tools:**
- `calculate_damage_output` - Full damage calculation with all modifiers
- `check_survival` - Can a Pokemon survive an attack?
- `find_survival_evs` - Minimum EVs to survive
- `find_ko_evs` - Attack EVs needed to KO
- `calculate_chip_damage` - Multi-turn chip damage
- `analyze_paste_bulk` - Bulk analysis vs meta threats

---

### Speed Analysis

Compare speeds, find tiers, and analyze speed control.

| Say This... | To Do This |
|-------------|------------|
| "Is Landorus faster than Tornadus?" | Compare two speeds |
| "What speed tier is 252 Spe Timid Flutter Mane?" | Find speed tier |
| "Show speed tiers under Tailwind" | Tailwind speed chart |
| "What EVs to outspeed Dragapult?" | Find speed EVs |
| "Show my team's speed tiers" | Team speed visualization |
| "What's my chance of outspeeding Landorus?" | Outspeed probability |
| "Analyze my team under Trick Room" | Trick Room analysis |

**Available Tools:**
- `compare_speed` - Who outspeeds who
- `find_speed_evs_to_outspeed` - EVs to outspeed a target
- `get_speed_tiers` - Speed tier benchmarks
- `visualize_speed_tiers` - Speed tier chart
- `analyze_team_trick_room` - Trick Room performance
- `analyze_team_tailwind` - Tailwind performance
- `analyze_speed_drops` - Icy Wind/Electroweb analysis
- `analyze_paralysis_matchup` - Paralysis speed analysis
- `outspeed_probability` - Probability of outspeeding (using Smogon data)
- `calculate_meta_outspeed_rate` - Outspeed rate vs meta
- `speed_creep_analysis` - EVs to outspeed common threats

---

### Team Building & Management

Build teams, add Pokemon, analyze synergy.

| Say This... | To Do This |
|-------------|------------|
| "Help me build a Rain team" | Start building a team |
| "Add Flutter Mane to my team" | Add Pokemon |
| "Show my team" | View current team |
| "What Pokemon pair well with Flutter Mane?" | Find partners |
| "Analyze my team's synergy" | Check how team works together |
| "Suggest Pokemon to complete my team" | Fill team gaps |
| "Clear my team" | Start over |

**Available Tools:**
- `add_to_team` - Add Pokemon (max 6, species clause enforced)
- `remove_from_team` - Remove Pokemon
- `view_team` - Display current team
- `clear_team` - Remove all Pokemon
- `show_team_summary` - Quick team overview
- `suggest_partners_with_synergy` - Find good partners
- `get_popular_cores` - Popular 2-Pokemon cores
- `analyze_team_synergy` - Team synergy analysis
- `suggest_team_completion` - Fill team gaps
- `team_building_wizard` - Step-by-step team building

---

### Matchup Analysis

Find threats, check coverage, analyze matchups.

| Say This... | To Do This |
|-------------|------------|
| "What are my team's weaknesses?" | Find team weaknesses |
| "How does my team handle Flutter Mane?" | Threat analysis |
| "What threatens my team?" | Find major threats |
| "Can my team hit Steel types?" | Check type coverage |
| "Analyze matchup vs this opponent team" | Full matchup analysis |

**Available Tools:**
- `analyze_matchup` - How team handles a threat
- `find_threats_to_team` - Identify major threats
- `check_offensive_coverage` - Can you hit a type?
- `analyze_defensive_matchup` - Defensive analysis
- `analyze_team_matchup_vs_opponent` - Full matchup vs opponent
- `calculate_matchup_probability` - Win probability

---

### EV Optimization

Optimize spreads, check efficiency, save EVs.

| Say This... | To Do This |
|-------------|------------|
| "Is my spread efficient?" | Check for wasted EVs |
| "What EVs to survive multiple threats?" | Multi-threat bulk |
| "Can I save EVs with a different nature?" | Nature optimization |
| "Find optimal speed tier for Incineroar" | Best speed investment |
| "Suggest spreads for Amoonguss" | Competitive spread suggestions |
| "Show diminishing returns on HP investment" | EV efficiency analysis |

**Available Tools:**
- `check_spread_efficiency` - Find wasted EVs
- `find_bulk_evs` - Survive specific attacks
- `find_multi_threat_bulk_evs` - Survive multiple threats
- `suggest_nature_optimization` - Save EVs with better nature
- `find_optimal_speed_tier` - Best speed tier
- `optimize_defensive_spread` - Multi-threat bulk optimization
- `analyze_diminishing_returns` - Where EVs become inefficient
- `suggest_viable_spreads` - Competitive spread suggestions

---

### Usage Data & Meta

Get Smogon usage stats, common sets, meta info.

| Say This... | To Do This |
|-------------|------------|
| "What's Flutter Mane's usage?" | Usage percentage |
| "What's the most common Flutter Mane set?" | Popular sets |
| "What items does Flutter Mane usually run?" | Common items |
| "What are the top 10 Pokemon in the meta?" | Meta overview |
| "What spreads does Incineroar use?" | Popular EV spreads |

**Available Tools:**
- `get_usage_stats` - Smogon usage with items/abilities/moves
- `get_common_sets` - Most popular competitive sets
- `suggest_teammates` - Teammates based on usage data
- `get_common_spreads` - Popular EV spreads
- `get_smogon_spreads` - Live Smogon spread data

---

### Import & Export

Parse Showdown pastes, export teams.

| Say This... | To Do This |
|-------------|------------|
| "Analyze this team" (paste Showdown format) | Import and analyze |
| "Import this Pokemon" (paste single Pokemon) | Parse Pokemon |
| "Export my team to Showdown format" | Get pasteable team |
| "Fetch team from pokepast.es/abc123" | Import from PokePaste |

**Available Tools:**
- `import_showdown_pokemon` - Parse single Pokemon
- `import_showdown_team` - Parse full team
- `export_team_to_showdown` - Export to Showdown format
- `validate_paste_syntax` - Check paste format
- `fetch_pokepaste` - Fetch from pokepast.es URL
- `analyze_pokepaste` - Full PokePaste analysis

---

### Legality Checking

Verify tournament legality.

| Say This... | To Do This |
|-------------|------------|
| "Is my team legal?" | Full legality check |
| "Do I have too many restricted Pokemon?" | Check restricted count |
| "Do I have duplicate items?" | Check item clause |
| "Is Koraidon restricted?" | Check Pokemon status |

**Available Tools:**
- `validate_team_legality` - Full tournament legality check
- `check_restricted_count` - Restricted Pokemon count
- `check_item_clause_tool` - No duplicate items
- `check_species_clause` - No duplicate species
- `get_legality_status` - Pokemon legality status

---

### Move Analysis

Check movesets, coverage, priority.

| Say This... | To Do This |
|-------------|------------|
| "Can Flutter Mane learn Moonblast?" | Check move learnability |
| "What moves should Flutter Mane run?" | Suggest competitive moves |
| "What priority moves does my team have?" | List priority moves |
| "Analyze turn order for this scenario" | Turn order analysis |
| "Does my team have good Fake Out coverage?" | Fake Out analysis |

**Available Tools:**
- `validate_pokemon_moveset` - Check all moves are legal
- `get_pokemon_learnable_moves` - All learnable moves
- `suggest_competitive_moves` - Popular competitive moves
- `analyze_turn_order` - Move order with priority
- `find_team_priority_moves` - Priority moves on team
- `analyze_fake_out_coverage` - Fake Out analysis

---

### Ability Synergy

Check ability interactions, weather, terrain.

| Say This... | To Do This |
|-------------|------------|
| "Analyze my team's abilities" | Full ability analysis |
| "Can my team handle Intimidate?" | Intimidate answers |
| "Does my team have weather synergy?" | Weather analysis |
| "Are there ability conflicts on my team?" | Ability conflicts |

**Available Tools:**
- `analyze_team_abilities` - Full ability synergy analysis
- `check_intimidate_answers` - Intimidate counters
- `analyze_weather_synergy` - Weather setter/abuser check
- `analyze_terrain_synergy` - Terrain analysis
- `find_redirect_abilities` - Redirection abilities
- `check_ability_conflicts` - Problematic combinations

---

### Type Coverage

Analyze offensive and defensive type coverage.

| Say This... | To Do This |
|-------------|------------|
| "What types can't my team hit?" | Find coverage holes |
| "Suggest coverage moves" | Improve coverage |
| "Does my team have quad weaknesses?" | 4x weakness check |
| "Explain Fire type matchups" | Type effectiveness |

**Available Tools:**
- `analyze_team_move_coverage` - Offensive coverage analysis
- `find_coverage_holes` - Types you can't hit
- `suggest_coverage_moves` - Moves for better coverage
- `check_quad_weaknesses` - 4x weak defensive types
- `explain_type_matchup` - Type effectiveness explained

---

### Item & Tera Analysis

Calculate item effects, optimize Tera types.

| Say This... | To Do This |
|-------------|------------|
| "What stat does Booster Energy boost?" | Booster Energy calc |
| "How much does Choice Specs boost?" | Choice item effect |
| "Will Focus Sash save me?" | Focus Sash check |
| "What's the best Tera type for Flutter Mane?" | Tera optimization |

**Available Tools:**
- `calculate_booster_energy` - Protosynthesis/Quark Drive boost
- `calculate_assault_vest_boost` - Assault Vest SpD
- `calculate_choice_item_boost` - Choice Band/Specs/Scarf
- `calculate_eviolite_boost` - Eviolite defenses
- `calculate_life_orb_effect` - Life Orb damage/recoil
- `check_focus_sash_survival` - Focus Sash activation
- `optimize_tera_type` - Best Tera type

---

### Chip Damage

Calculate residual damage over turns.

| Say This... | To Do This |
|-------------|------------|
| "How much damage does Sandstorm do?" | Weather chip |
| "How much does Burn do per turn?" | Status chip |
| "How much does Grassy Terrain heal?" | Terrain healing |
| "Simulate chip damage over 5 turns" | Multi-turn simulation |

**Available Tools:**
- `calculate_weather_damage` - Sandstorm/Hail damage
- `calculate_status_chip` - Burn/Poison/Toxic damage
- `calculate_grassy_terrain_healing` - Grassy Terrain heal
- `calculate_leftovers_healing` - Leftovers recovery
- `simulate_chip_over_turns` - Multi-turn chip simulation
- `calculate_survival_with_chip` - Survival with chip damage

---

### Lead Analysis

Optimize lead combinations.

| Say This... | To Do This |
|-------------|------------|
| "What's my best lead pair?" | Rank lead combinations |
| "Analyze Flutter Mane + Incineroar lead" | Specific lead analysis |
| "What should I lead vs Trick Room?" | Counter-lead suggestions |

**Available Tools:**
- `analyze_lead_pairs` - Rank lead combinations
- `suggest_best_lead` - Optimal lead vs threats
- `analyze_lead_matchup` - Specific lead pair analysis

---

### Tournament Preparation

Get ready for tournaments.

| Say This... | To Do This |
|-------------|------------|
| "Is my team tournament ready?" | Full readiness check |
| "What are my team's critical issues?" | Find problems to fix |
| "Generate a team report" | Shareable team report |

**Available Tools:**
- `check_tournament_readiness` - Comprehensive assessment
- `full_team_check` - Complete team analysis
- `quick_team_analysis` - Fast summary with issues
- `generate_build_report` - Shareable team report
- `suggest_team_changes` - Recommended improvements

---

### Learning VGC

Learn competitive Pokemon basics.

| Say This... | To Do This |
|-------------|------------|
| "Explain what EVs are" | VGC term explanation |
| "What makes Flutter Mane good?" | Pokemon explanation |
| "Explain Fire type matchups" | Type effectiveness |
| "Check my build for mistakes" | Build error check |
| "Show me a beginner team" | Sample team |
| "I'm new to VGC, where do I start?" | Getting started guide |

**Available Tools:**
- `explain_vgc_term` - Explain competitive terms (EVs, STAB, OHKO, etc.)
- `explain_pokemon` - Pokemon strengths, weaknesses, role
- `explain_type_matchup` - Type effectiveness
- `check_build_for_mistakes` - Find beginner errors
- `get_sample_team` - Tournament-proven sample teams
- `get_help` - Interactive help menu
- `show_capabilities` - See all features
- `welcome_new_user` - Getting started guide

---

## Glossary of VGC Terms

| Term | Meaning |
|------|---------|
| **EVs** | Effort Values - bonus stat points (508 total, 252 max per stat) |
| **IVs** | Individual Values - hidden 0-31 stats |
| **Nature** | Boosts one stat by 10%, lowers another by 10% |
| **STAB** | Same Type Attack Bonus - 1.5x damage for matching type moves |
| **OHKO** | One-Hit KO - knock out in one attack |
| **2HKO** | Two-Hit KO - knock out in two attacks |
| **Spread** | EV distribution (e.g., "252 HP / 252 Def / 4 SpD") |
| **Benchmark** | Specific stat threshold to survive/outspeed something |
| **Tailwind** | Doubles Speed for 4 turns |
| **Trick Room** | Slower Pokemon move first for 5 turns |
| **Priority** | Moves that go first regardless of Speed (Fake Out, Protect) |
| **Tera Type** | Type you transform into when Terastallizing |
| **Check** | Pokemon that can switch in and threaten |
| **Counter** | Pokemon that beats another reliably |
| **Lead** | First two Pokemon you send out |
| **Back** | Reserved Pokemon not sent out initially |
| **Pivot** | Pokemon that switches out after acting (U-turn, Parting Shot) |
| **Spread Move** | Move that hits multiple targets (0.75x damage in Doubles) |
| **Restricted** | Box legendaries limited to 1-2 per team |

---

## Example Conversations

### Building a Team

> **You:** Help me build a team around Flutter Mane
>
> **Claude:** Great choice! Flutter Mane is a fast special attacker. Let me suggest some partners...
> - Incineroar (Fake Out support, Intimidate)
> - Landorus (Ground coverage, handles Steel types)
> - Rillaboom (Priority Grassy Glide, Fake Out)
>
> Would you like me to add these to your team with suggested spreads?

### Damage Calculation

> **You:** Does my Timid 252 SpA Flutter Mane OHKO Incineroar?
>
> **Claude:** Let me calculate that...
>
> **Flutter Mane** (Timid 252 SpA Choice Specs) vs **Incineroar** (Careful 252 HP / 252 SpD)
> Moonblast: 72-85% damage
>
> **Result:** Not an OHKO. You need Helping Hand or a crit.

### EV Optimization

> **You:** What EVs does Incineroar need to survive Flutter Mane?
>
> **Claude:** For Incineroar to survive Choice Specs Timid 252 SpA Flutter Mane's Moonblast:
>
> **Minimum spread:** 252 HP / 180 SpD with Careful nature
>
> This lets you survive with ~5% HP remaining.

### Speed Comparison

> **You:** Is my Jolly 252 Spe Landorus faster than Tornadus?
>
> **Claude:** Let me compare:
>
> - Your Landorus: 168 Speed (Jolly 252)
> - Common Tornadus: 179 Speed (Timid 252)
>
> **Result:** Tornadus outspeeds you by 11 points. Consider Tailwind or Choice Scarf.

### Learning VGC

> **You:** Explain what EVs are
>
> **Claude:** EVs (Effort Values) are bonus stat points you can give your Pokemon.
>
> **The basics:**
> - You have 508 total EVs to distribute
> - Maximum 252 per stat
> - Every 4 EVs = +1 stat point at Level 50
>
> **Common patterns:**
> - 252/252/4 - Max offense (sweepers)
> - 252 HP / 252 Def or SpD - Max bulk
> - Custom benchmarks - Survive specific attacks

---

## Tips for Best Results

1. **Be specific about spreads** - "252 SpA Timid Flutter Mane" gives better results than just "Flutter Mane"

2. **Mention items and abilities** - "Choice Specs Flutter Mane" or "Assault Vest Incineroar"

3. **Use Tera when relevant** - "Tera Fairy Flutter Mane Moonblast"

4. **Paste full teams** - More context = better analysis

5. **Ask follow-up questions** - "What if I use Modest instead?" or "Show me under Tailwind"

---

## Need Help?

- Say **"What can you do?"** to see all capabilities
- Say **"Help damage"** for damage calculation help
- Say **"Help team"** for team building help
- Say **"/help"** to see slash commands
- Say **"Explain [term]"** to learn VGC vocabulary

For bugs or feature requests: https://github.com/MSS23/vgc-mcp/issues

---

*Powered by live Smogon usage data and the Gen 9 damage formula*
