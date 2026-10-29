# Tool Catalog

Auto-generated from the running server. **206 tools** organized by module.

★ marks the **34 core tools** that `/mcp` serves by default. `/mcp/full` (or `VGC_MCP_PROFILE=full`) serves all of them.

To regenerate: `PYTHONPATH=src python scripts/build_catalog.py`

## ability_tools  (10 tools)

- **`analyze_team_abilities`** — Perform full ability synergy analysis for the current team.
- **`analyze_terrain_synergy`** — Analyze the current team's terrain setting potential.
- **`analyze_weather_synergy`** — Analyze the current team's weather setting and abuse potential.
- **`check_intimidate_answers`** — Check if the current team has answers to opposing Intimidate.
- **`check_partner_abilities`** — Check the current team for abilities that benefit partner Pokemon.
- **`check_redirect_abilities`** — Check the current team for redirection abilities.
- **`find_ability_conflicts`** — Check the current team for conflicting abilities.
- **`get_common_intimidate_pokemon`** — Get the list of common Intimidate Pokemon in VGC.
- **`get_weather_ability_info`** — Get reference information about all weather-related abilities.
- **`suggest_ability_additions`** — Suggest abilities that would improve the current team's synergy.

## archetype_tools  (1 tools)

- **`classify_team_archetype`** — Classify a team's archetype and return its win condition + bring-3 patterns.

## battle_tools  (5 tools)

- **`end_battle`** ★ — Close the active battle and return its final state.
- **`get_battle_state`** — Return the full structured snapshot of the active battle.
- **`record_turn`** ★ — Record one turn of an active battle.
- **`start_battle`** ★ — Begin a new battle. Replaces any active battle.
- **`suggest_next_move`** ★ — Best next turn for the active battle, with reasoning and alternatives.

## breakpoint_tools  (1 tools)

- **`find_breakpoint`** — Find the cheapest spread change to hit a specific benchmark.

## build_checker_tools  (1 tools)

- **`check_build_for_mistakes`** — Check a Pokemon build for common beginner mistakes.

## build_tools  (5 tools)

- **`change_move`** — Change a specific move on a Pokemon build.
- **`create_build`** — Create a Pokemon build with state tracking.
- **`get_build_state`** — Get the current state of a Pokemon build.
- **`list_builds`** — List all active Pokemon builds in the current session.
- **`modify_build`** — Modify an existing Pokemon build.

## bulk_calc_tools  (2 tools)

- **`calculate_bulk_offensive_calcs`** ★ — Run bulk offensive damage calculations: 1 attacker x N moves x M defenders x K scenarios.
- **`export_damage_report`** ★ — Export bulk damage calculations as an Excel spreadsheet or PDF file on disk.

## chip_damage_tools  (6 tools)

- **`calculate_grassy_terrain_healing`** — Calculate Grassy Terrain healing for a Pokemon.
- **`calculate_leftovers_healing`** — Calculate Leftovers or Black Sludge recovery.
- **`calculate_status_chip`** — Calculate status condition damage for a Pokemon.
- **`calculate_survival_with_chip`** — Calculate if a Pokemon survives an attack plus chip damage.
- **`calculate_weather_damage`** — Calculate weather chip damage for a Pokemon.
- **`simulate_chip_over_turns`** — Simulate chip damage/healing over multiple turns.

## context_tools  (7 tools)

- **`clear_my_pokemon`** — Clear stored Pokemon context.
- **`get_my_pokemon`** — Get details of a stored Pokemon.
- **`list_my_pokemon`** — List all stored Pokemon with their key stats (nature, Speed, HP).
- **`reset_session`** — Start fresh by clearing all stored Pokemon and team data.
- **`session_status`** — Check what's currently stored in this session.
- **`set_my_pokemon`** — Store a Pokemon spread for future calculations.
- **`update_my_pokemon`** — Update an existing stored Pokemon's spread or attributes.

## core_tools  (6 tools)

- **`analyze_team_synergy`** — Analyze how well the current team members work together.
- **`get_pokemon_roles`** — Get the competitive roles a Pokemon can fill.
- **`get_popular_cores`** — Get popular 2-Pokemon cores from the current metagame.
- **`list_role_pokemon`** — List Pokemon that can fill a specific role.
- **`suggest_partners_with_synergy`** — Suggest Pokemon that pair well with a given Pokemon (enhanced analysis).
- **`suggest_team_completion`** — Suggest Pokemon to complete the current team.

## coverage_tools  (6 tools)

- **`analyze_team_move_coverage`** — Analyze the current team's move-based offensive coverage.
- **`check_coverage_vs_target`** — Check if the current team has super-effective coverage against a specific Pokemon.
- **`check_team_quad_weaknesses`** — Find Pokemon on the current team with 4x type weaknesses.
- **`find_team_coverage_holes`** — Find types that no current team member can hit super-effectively.
- **`get_coverage_move_options`** — Get available coverage moves of a specific type.
- **`suggest_team_coverage_moves`** — Suggest moves to fill the current team's coverage gaps.

## damage_tools  (6 tools)

- **`calculate_damage_output`** ★ — Damage range, % HP and KO verdict for one move: the main damage tool.
- **`find_bulk_to_survive_hits`** — Find minimum HP/Def EVs to survive multiple hits of an attack.
- **`find_ko_evs`** — Find minimum offensive EVs needed to achieve a certain KO probability.
- **`find_survival_evs`** ★ — Minimum HP and Def/SpD investment to survive one specific attack.
- **`survive_double_up`** — Check if a Pokemon survives combined damage from two attackers in one turn (double-up).
- **`survive_multiple_hits`** — Calculate if a Pokemon can survive multiple hits of an attack.

## delta_tools  (1 tools)

- **`compare_build_changes`** — Show what changed between two builds against a fixed threat list.

## diff_tools  (1 tools)

- **`compare_team_versions`** — Compare two versions of a Pokemon team and show what changed.

## education_tools  (1 tools)

- **`explain_pokemon`** — Explain a Pokemon's strengths, weaknesses, and competitive role.

## game_plan_tools  (1 tools)

- **`generate_game_plan`** — Generate a comprehensive game plan against a specific opponent team.

## glossary_tools  (1 tools)

- **`explain_vgc_term`** ★ — Explain a VGC/Pokemon competitive term in simple language.

## help_tools  (1 tools)

- **`get_help`** — Get help on using this server. Shows available commands and examples.

## import_export_tools  (4 tools)

- **`export_pokemon_to_paste`** — Export a single Pokemon from the team to Showdown paste format.
- **`export_team_to_paste`** ★ — Export the current team to Showdown paste format.
- **`import_showdown_pokemon`** — Parse a single Pokemon from Showdown paste format and optionally add it to the team.
- **`import_showdown_team`** ★ — Parse a full team from Showdown paste format and add each Pokemon to the team.

## item_optimization_tools  (3 tools)

- **`analyze_item_ev_tradeoff`** — Find the optimal item + EV distribution to maximize useful stats.
- **`compare_item_damage_output`** — Compare damage output across multiple items (Life Orb vs Choice items vs Expert Belt).
- **`optimize_life_orb_sustainability`** — Analyze Life Orb sustainability with different HP investments.

## item_tools  (8 tools)

- **`calculate_assault_vest`** — Calculate the Assault Vest Special Defense boost.
- **`calculate_booster_energy`** — Calculate the Booster Energy stat boost for a Paradox Pokemon.
- **`calculate_choice_item`** — Calculate a Choice item's 1.5x stat boost.
- **`calculate_eviolite`** — Calculate Eviolite defensive boosts for a not-fully-evolved Pokemon.
- **`calculate_life_orb_damage`** — Calculate the Life Orb damage boost and recoil cost.
- **`check_berry_activation_threshold`** — Check when a berry would activate based on its HP threshold.
- **`check_focus_sash`** — Check if Focus Sash would save a Pokemon from an attack.
- **`get_item_damage_boost`** — Get the damage multiplier a held item applies to a move.

## lead_tools  (1 tools)

- **`analyze_lead_pairs`** — Analyze and rank all 15 lead pair combinations for a 6-Pokemon team.

## legality_tools  (14 tools)

- **`auto_detect_regulation_from_pokemon`** ★ — Infer the regulation from the Pokemon mentioned and set it for the session.
- **`check_item_clause_tool`** — Check if the current team violates the item clause (no duplicate items).
- **`check_pokemon_legality`** — Check if a specific Pokemon is legal, restricted, or banned.
- **`check_restricted_count`** — Check how many restricted (box legend) Pokemon are on the team.
- **`clear_session_regulation`** — Clear the session regulation override.
- **`get_current_regulation_info`** — Get information about the currently active VGC regulation.
- **`get_format_rules`** — Get the full rule set for a specific VGC regulation.
- **`infer_regulation_from_team`** — Infer the most likely VGC regulation from the Pokemon mentioned in a team.
- **`list_available_regulations`** — List all available VGC regulations with key parameters and date ranges.
- **`list_banned_pokemon`** — List all banned Pokemon for a VGC regulation.
- **`list_restricted_pokemon`** — List all restricted (box legend) Pokemon for a VGC regulation.
- **`set_session_regulation`** ★ — Set the regulation from the user's wording ("Reg F", "Champions", "Reg MB").
- **`suggest_item_alternatives`** — Suggest alternative items when the item clause flags a duplicate.
- **`validate_team_legality`** ★ — Validate full team legality for VGC tournament play.

## matchup_tools  (6 tools)

- **`analyze_matchup`** — Analyze how the current team handles a specific common threat Pokemon.
- **`check_defensive_matchup`** — Check how well the current team resists a specific attacking type.
- **`check_offensive_coverage`** — Check whether the current team can hit a specific type super effectively.
- **`find_threats_to_team`** — Identify the biggest metagame threats to the current team.
- **`full_matchup_report`** — Generate a comprehensive matchup report for the current team.
- **`get_available_threats`** — List all common threat Pokemon available for matchup analysis.

## meta_threat_tools  (3 tools)

- **`analyze_spread_vs_threats`** — Analyze a spread against the top meta threats.
- **`analyze_stored_pokemon_threats`** — Analyze a stored Pokemon's spread against the top meta threats.
- **`check_survival_benchmark`** — ⚠️ NARROW USE ONLY. Prefer `calculate_damage_output` for general damage/survival.

## move_tools  (7 tools)

- **`check_egg_moves`** — Check which moves require breeding (egg moves) for a Pokemon.
- **`check_team_movesets`** — Validate movesets for all Pokemon on the current team.
- **`check_tm_moves`** — Check which moves a Pokemon can learn via TM/TR.
- **`find_move_learners`** — Find which Pokemon can learn a specific move.
- **`get_pokemon_learnable_moves`** — Get all moves a Pokemon can learn, grouped by learn method.
- **`suggest_competitive_moves`** — Suggest competitive moves for a Pokemon based on usage data.
- **`validate_pokemon_moveset`** — Check if all moves are legal for a Pokemon.

## multicalc_tools  (3 tools)

- **`calculate_defensive_threats`** — Calculate damage from multiple attackers vs one defender (threat analysis).
- **`calculate_offensive_coverage`** — Calculate damage from one attacker vs multiple defenders (offensive coverage analysis).
- **`calculate_team_coverage_matrix`** — Calculate a team coverage matrix: team of up to 6 vs meta threats.

## onboarding_tools  (3 tools)

- **`get_starter_prompts`** — Get a list of starter prompts for UI integration.
- **`show_capabilities`** ★ — Show what this server can do, with example prompts.
- **`welcome_new_user`** ★ — Show the welcome message for first-time users.

## pokepaste_tools  (3 tools)

- **`analyze_pokepaste`** — Fetch a PokePaste and provide a comprehensive team analysis.
- **`fetch_pokepaste`** — Fetch a team from a PokePaste URL and parse it.
- **`optimize_pokepaste_pokemon`** — Analyze a specific Pokemon from a PokePaste and suggest optimizations.

## preparation_tools  (5 tools)

- **`calculate_move_outcomes`** ★ — Calculate independent hit rolls, misses, berries and Parental Bond from exact Showdown pastes.
- **`import_reference_team`** ★ — Store complete user-supplied sets with attribution in this MCP session.
- **`prepare_team`** ★ — Prepare a Showdown team or current session team in one MCP call.
- **`recommend_verified_spreads`** ★ — Offer minimum-investment, offensive and bulky spreads that pass final exact verification.
- **`verify_spread_benchmarks`** ★ — Recalculate survive, KO and outspeed constraints against exact or chaos opponents.

## preset_tools  (4 tools)

- **`get_smogon_spreads`** — Get the most popular EV spreads from LIVE Smogon Chaos data.
- **`get_spread_presets`** — Get curated EV spread presets with benchmark explanations.
- **`list_pokemon_with_presets`** — List all Pokemon that have curated preset spreads available.
- **`suggest_spread_for_role`** — Suggest a curated spread preset matching the role you want the Pokemon to fill.

## priority_tools  (8 tools)

- **`analyze_turn_order`** — Determine which Pokemon moves first considering priority.
- **`check_fake_out_interaction`** — Analyze Fake Out speed interaction with an opponent.
- **`check_prankster_interaction`** — Check if a Prankster-boosted move will affect the target.
- **`find_priority_threats`** — Identify common priority move threats in the VGC meta.
- **`get_move_priority_info`** — Get priority information for a specific move.
- **`get_priority_overview`** — Get a complete overview of all priority brackets and their moves.
- **`list_priority_bracket`** — List all moves at a specific priority bracket.
- **`list_team_priority_moves`** — List all priority moves available on the current team.

## readiness_tools  (1 tools)

- **`check_tournament_readiness`** — Comprehensive tournament readiness assessment for a full team of 6.

## replay_tools  (1 tools)

- **`analyze_replay`** ★ — Pull a public Showdown replay and produce a turn-by-turn breakdown.

## report_tools  (1 tools)

- **`generate_build_report`** — Generate a shareable team build report showing the building journey.

## router_tools  (1 tools)

- **`what_tool_should_i_use`** — Suggest the right tools for a free-text VGC question.

## sample_team_tools  (4 tools)

- **`get_sample_team`** — Get sample tournament-proven teams matching the given filters.
- **`get_team_paste`** — Get the full Showdown-importable paste for a sample team by name.
- **`list_sample_team_archetypes`** — List all available team archetypes in the sample database, with descriptions.
- **`suggest_team_for_playstyle`** — Suggest a sample team based on your preferred playstyle.

## speed_analysis_tools  (12 tools)

- **`analyze_paralysis_matchup`** — Analyze what your team outspeeds when opponents are paralyzed.
- **`analyze_speed_drops`** — Analyze what your team can outspeed after using Icy Wind/Electroweb.
- **`analyze_speed_spread`** — Analyze what a specific speed spread outspeeds and underspeeds.
- **`analyze_team_tailwind`** — Analyze how the current team performs with Tailwind active.
- **`analyze_team_trick_room`** — Analyze how the current team performs under Trick Room.
- **`calculate_speed_after_modifier`** — Calculate what a speed stat becomes after various modifiers.
- **`compare_speed`** ★ — Compare speed between two Pokemon to determine who moves first.
- **`find_speed_benchmark`** — Find what Pokemon/spreads hit a specific speed stat.
- **`find_speed_evs_to_outspeed`** ★ — Find minimum Speed EVs needed to reach or exceed a target Speed stat.
- **`get_full_speed_analysis`** — Get comprehensive speed control analysis for the current team.
- **`get_speed_tiers`** — Get speed tier benchmarks for common VGC Pokemon.
- **`visualize_speed_tiers`** — Visualize speed tiers as a text-based chart.

## speed_probability_tools  (3 tools)

- **`compare_speed_investment`** — Compare different Speed EV investments against a target.
- **`meta_outspeed_analysis`** — Analyze what percentage of the top meta Pokemon you outspeed.
- **`speed_creep_calculator`** — Calculate how many Speed EVs are needed to outspeed a target.

## speed_tools  (1 tools)

- **`analyze_outspeed_probability`** ★ — Analyze what percentage of a target Pokemon's common spreads you outspeed.

## spread_tools  (9 tools)

- **`analyze_bulk_diminishing_returns`** — Analyze diminishing returns for HP, Def, and SpD investment.
- **`analyze_hp_number`** — Analyze HP EV options for optimal item-based recovery or recoil.
- **`check_spread_efficiency`** — Check an EV spread for efficiency (wasted EVs, optimal distribution).
- **`design_spread_with_benchmarks`** ★ — Spread that outspeeds a target and survives ONE attack (or maxes offense).
- **`optimize_bulk`** — Optimize HP/Def/SpD EVs for maximum effective bulk.
- **`optimize_dual_survival_spread`** ★ — Cheapest spread that survives TWO different attackers and hits a speed target.
- **`optimize_multi_survival_spread`** ★ — Cheapest spread that survives 3-6 different attacks and hits a speed target.
- **`suggest_nature_optimization`** — Suggest a nature change that achieves the same stats with fewer EVs.
- **`suggest_spread`** — Suggest an EV spread based on role, with a Showdown paste.

## stats_tools  (2 tools)

- **`get_pokemon_speed`** — Calculate the Speed stat for a Pokemon, with min/max reference values.
- **`get_pokemon_stats`** ★ — Calculate all six final stats for a Pokemon at level 50 (VGC standard).

## team_matchup_tools  (1 tools)

- **`analyze_team_matchup`** — Analyze how your full team matches up against opponents.

## team_tools  (8 tools)

- **`add_to_team`** — Add a Pokemon to the current team (max 6, species clause enforced).
- **`analyze_team`** — Perform comprehensive analysis of the current team.
- **`clear_team`** — Clear all Pokemon from the current team.
- **`remove_from_team`** — Remove a Pokemon from the team by slot number.
- **`remove_pokemon_by_name`** — Remove a Pokemon from the team by name.
- **`reorder_team`** — Swap the positions of two Pokemon in the team.
- **`swap_team_pokemon`** — Replace the Pokemon in a specific team slot with a new one.
- **`view_team`** — View the current team with full details.

## tera_tools  (1 tools)

- **`optimize_tera_type`** — Find the optimal Tera type for a Pokemon build.

## tournament_tools  (5 tools)

- **`analyze_paste_bulk`** — Analyze what common meta attacks a Pokemon survives based on its paste.
- **`analyze_team_vs_meta`** — Analyze your team against top tournament meta teams.
- **`analyze_vs_specific_team`** — Analyze your team against a specific meta archetype.
- **`compare_two_teams`** — Compare two teams head-to-head with detailed matchup analysis.
- **`get_meta_teams`** — List available tournament meta teams for matchup analysis.

## type_tools  (1 tools)

- **`explain_type_matchup`** — Explain type effectiveness for attacks or Pokemon matchups.

## usage_tools  (6 tools)

- **`compare_pokemon_month_over_month`** — Compare a Pokemon's usage between the current and previous month.
- **`get_common_sets`** ★ — Get the most common competitive sets for a Pokemon.
- **`get_current_format_info`** — Get information about the currently detected VGC format.
- **`get_top_pokemon`** — Get the top used Pokemon in the current VGC format.
- **`get_usage_stats`** ★ — Get Smogon usage statistics for a Pokemon in VGC.
- **`suggest_teammates`** — Get suggested teammates based on Smogon usage data.

## wizard_tools  (1 tools)

- **`team_building_wizard`** — Interactive step-by-step team building guide for beginners.

## workflow_tools  (14 tools)

- **`add_pokemon_smart`** ★ — Add a Pokemon to the team with an intelligently suggested build.
- **`analyze_speed_matchup`** — Compare Speed between two Pokemon across various scenarios.
- **`calc_damage_vs_smogon_sets`** ★ — Damage from YOUR exact spread against each of the top Smogon sets.
- **`check_team_vs_threat`** — Check how your currently loaded team handles a specific threat.
- **`compare_pokemon_options`** — Compare two Pokemon to help decide which fits your team better.
- **`design_pokemon_for_role`** — Design a complete Pokemon build for a specific role in ONE call.
- **`evaluate_core`** — Evaluate a Pokemon core (2-4 Pokemon) for synergy.
- **`find_counter_for`** — Find counters for a threatening Pokemon.
- **`fix_team_issues`** — Identify team legality/structure issues and suggest specific fixes.
- **`full_team_check`** — Team analysis with configurable detail level.
- **`import_and_analyze`** ★ — Import a Showdown team paste and immediately analyze it.
- **`optimize_spread`** — Optimize or fix an EV spread to meet specific stat/benchmark targets.
- **`quick_damage_check`** — Quick damage calculation with smart defaults - ONE call for damage info.
- **`suggest_ev_spread`** — Design an optimal EV spread meeting multiple constraints in ONE call.
