"""Tests for the priority-aware game plan generation."""

import pytest
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, BaseStats
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.calc.team_matchup import (
    build_pokemon_profile,
    generate_full_game_plan,
    _analyze_fake_out_war,
    _analyze_prankster_interactions,
    _analyze_terrain_interactions,
    _analyze_redirect_interactions,
    _predict_opponent_leads,
    _recommend_leads,
    _recommend_bring_4,
    _rank_threats,
    _determine_win_condition,
    _best_turn1_move,
    _score_lead_pair,
    build_matchup_matrix,
    PokemonProfile,
    GamePlanLeadRec,
)


def _make_build(name, types, base_hp=80, base_atk=80, base_def=80,
                base_spa=80, base_spd=80, base_spe=80,
                nature=Nature.SERIOUS, evs=None, item=None, ability=None):
    """Helper to create a PokemonBuild for testing."""
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(
            hp=base_hp, attack=base_atk, defense=base_def,
            special_attack=base_spa, special_defense=base_spd, speed=base_spe,
        ),
        types=types,
        nature=nature,
        evs=evs or EVSpread(),
        item=item,
        ability=ability,
    )


def _make_move(name, move_type, category=MoveCategory.PHYSICAL, power=90):
    """Helper to create a Move for testing."""
    return Move(name=name, type=move_type, category=category, power=power)


def _make_status_move(name, move_type="Normal"):
    """Helper to create a status Move."""
    return Move(name=name, type=move_type, category=MoveCategory.STATUS, power=None)


class TestBuildPokemonProfile:
    """Test profile building with priority/ability integration."""

    def test_fake_out_detected_from_moves(self):
        """Fake Out should be detected from the moves list, not ability."""
        build = _make_build("Incineroar", ["Fire", "Dark"],
                            base_atk=115, base_spe=60, ability="intimidate")
        moves = [
            _make_move("Fake Out", "Normal", power=40),
            _make_move("Flare Blitz", "Fire"),
        ]
        profile = build_pokemon_profile(build, moves, "intimidate")

        assert profile.has_fake_out is True
        assert profile.is_intimidate is True

    def test_fake_out_not_false_positive_from_ability(self):
        """Fake Out should NOT be detected from ability name (fixing lead_tools bug)."""
        build = _make_build("Tornadus", ["Flying"], base_spe=111, ability="prankster")
        moves = [
            _make_status_move("Tailwind"),
            _make_status_move("Taunt"),
        ]
        profile = build_pokemon_profile(build, moves, "prankster")

        assert profile.has_fake_out is False

    def test_prankster_moves_identified(self):
        """Prankster status moves should be identified with +1 priority."""
        build = _make_build("Tornadus", ["Flying"], base_spe=111, ability="prankster")
        moves = [
            _make_status_move("Tailwind"),
            _make_status_move("Taunt"),
            _make_move("Hurricane", "Flying", MoveCategory.SPECIAL, 110),
        ]
        profile = build_pokemon_profile(build, moves, "prankster")

        assert profile.is_prankster is True
        assert "Tailwind" in profile.prankster_moves
        assert "Taunt" in profile.prankster_moves
        # Hurricane is not a status move, should not be in prankster_moves
        assert "Hurricane" not in profile.prankster_moves

    def test_tailwind_setter_detected(self):
        """Tailwind setter should be detected from moves."""
        build = _make_build("Tornadus", ["Flying"], base_spe=111)
        moves = [_make_status_move("Tailwind")]
        profile = build_pokemon_profile(build, moves, "prankster")

        assert profile.is_tailwind_setter is True
        assert profile.is_trick_room_setter is False

    def test_trick_room_setter_detected(self):
        """Trick Room setter should be detected from moves."""
        build = _make_build("Porygon2", ["Normal"], base_spe=60)
        moves = [_make_status_move("Trick Room", "Psychic")]
        profile = build_pokemon_profile(build, moves, "download")

        assert profile.is_trick_room_setter is True
        assert profile.is_tailwind_setter is False

    def test_priority_moves_tracked(self):
        """Priority moves should be identified with correct priority values."""
        build = _make_build("Rillaboom", ["Grass"], base_atk=125, base_spe=85)
        moves = [
            _make_move("Fake Out", "Normal", power=40),
            _make_move("Grassy Glide", "Grass", power=55),
        ]
        profile = build_pokemon_profile(build, moves, "grassy-surge")

        assert profile.has_fake_out is True
        # Should have Fake Out at +3 priority
        fo_prio = next(
            (pm for pm in profile.priority_moves if "Fake Out" in pm["name"]),
            None,
        )
        assert fo_prio is not None
        assert fo_prio["priority"] == 3

    def test_role_classification_sweeper(self):
        """High attack Pokemon should be classified as sweeper."""
        build = _make_build("Flutter Mane", ["Ghost", "Fairy"],
                            base_spa=135, base_spe=135)
        moves = [_make_move("Moonblast", "Fairy", MoveCategory.SPECIAL)]
        profile = build_pokemon_profile(build, moves, "protosynthesis")

        assert profile.role == "sweeper"

    def test_role_classification_speed_control(self):
        """Pokemon with Tailwind/Trick Room should be classified as speed_control."""
        build = _make_build("Tornadus", ["Flying"], base_spe=111)
        moves = [_make_status_move("Tailwind")]
        profile = build_pokemon_profile(build, moves, "prankster")

        assert profile.role == "speed_control"


class TestPranksterPriority:
    """Test that Prankster priority is correctly calculated."""

    def test_prankster_tailwind_priority(self):
        """Prankster Tailwind should have priority +1, going before normal moves."""
        from vgc_mcp_core.calc.priority import get_move_priority

        prio = get_move_priority("tailwind", ability="prankster", is_status=True)
        assert prio == 1, f"Prankster Tailwind should be priority +1, got {prio}"

    def test_prankster_taunt_priority(self):
        """Prankster Taunt should have priority +1."""
        from vgc_mcp_core.calc.priority import get_move_priority

        prio = get_move_priority("taunt", ability="prankster", is_status=True)
        assert prio == 1

    def test_non_prankster_tailwind_priority(self):
        """Non-Prankster Tailwind should have priority 0."""
        from vgc_mcp_core.calc.priority import get_move_priority

        prio = get_move_priority("tailwind", ability="defiant", is_status=True)
        assert prio == 0

    def test_prankster_does_not_boost_attacking_moves(self):
        """Prankster should NOT boost attacking moves."""
        from vgc_mcp_core.calc.priority import get_move_priority

        prio = get_move_priority("hurricane", ability="prankster", is_status=False)
        assert prio == 0


class TestFakeOutWar:
    """Test Fake Out speed interaction analysis."""

    def test_faster_fake_out_wins(self):
        """Faster Pokemon should Fake Out first."""
        rillaboom = build_pokemon_profile(
            _make_build("Rillaboom", ["Grass"], base_spe=85,
                        nature=Nature.ADAMANT, evs=EVSpread(speed=252)),
            [_make_move("Fake Out", "Normal", power=40)],
            "grassy-surge",
        )
        incineroar = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"], base_spe=60,
                        nature=Nature.CAREFUL, evs=EVSpread(speed=0)),
            [_make_move("Fake Out", "Normal", power=40)],
            "intimidate",
        )

        notes = _analyze_fake_out_war([rillaboom], [incineroar])
        assert any("Rillaboom" in n and "FIRST" in n for n in notes)

    def test_no_fake_out_noted(self):
        """When neither side has Fake Out, no notes."""
        flutter = build_pokemon_profile(
            _make_build("Flutter Mane", ["Ghost", "Fairy"], base_spe=135),
            [_make_move("Moonblast", "Fairy", MoveCategory.SPECIAL)],
            "protosynthesis",
        )
        dragapult = build_pokemon_profile(
            _make_build("Dragapult", ["Dragon", "Ghost"], base_spe=142),
            [_make_move("Shadow Ball", "Ghost", MoveCategory.SPECIAL)],
            "clear-body",
        )

        notes = _analyze_fake_out_war([flutter], [dragapult])
        assert len(notes) == 0


class TestPranksterInteractions:
    """Test Prankster interaction analysis with Dark-type immunity."""

    def test_dark_type_blocks_prankster(self):
        """Dark-type Pokemon should be immune to Prankster-boosted moves."""
        tornadus = build_pokemon_profile(
            _make_build("Tornadus", ["Flying"], base_spe=111),
            [_make_status_move("Tailwind"), _make_status_move("Taunt")],
            "prankster",
        )
        kingambit = build_pokemon_profile(
            _make_build("Kingambit", ["Dark", "Steel"], base_spe=50),
            [_make_move("Sucker Punch", "Dark", power=70)],
            "supreme-overlord",
        )

        # Their Tornadus has Prankster, our Kingambit is Dark
        notes = _analyze_prankster_interactions([kingambit], [tornadus])

        # Should note that Tornadus has Prankster moves
        assert any("Prankster" in n and "Tornadus" in n for n in notes)
        # Should note Dark type immunity
        assert any("IMMUNE" in n and "Kingambit" in n for n in notes)

    def test_prankster_interaction_no_dark(self):
        """Without Dark type, Prankster moves should work normally."""
        tornadus = build_pokemon_profile(
            _make_build("Tornadus", ["Flying"], base_spe=111),
            [_make_status_move("Tailwind")],
            "prankster",
        )
        flutter = build_pokemon_profile(
            _make_build("Flutter Mane", ["Ghost", "Fairy"], base_spe=135),
            [_make_move("Moonblast", "Fairy", MoveCategory.SPECIAL)],
            "protosynthesis",
        )

        notes = _analyze_prankster_interactions([flutter], [tornadus])
        # Should note Prankster Tailwind
        assert any("Prankster" in n and "Tailwind" in n for n in notes)
        # Should NOT note immunity
        assert not any("IMMUNE" in n for n in notes)


class TestLeadRecommendations:
    """Test opponent-aware lead scoring."""

    def _make_team(self):
        """Create a test team with diverse roles."""
        incineroar = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"],
                        base_atk=115, base_spe=60, ability="intimidate"),
            [_make_move("Fake Out", "Normal", power=40),
             _make_move("Flare Blitz", "Fire")],
            "intimidate",
        )
        tornadus = build_pokemon_profile(
            _make_build("Tornadus", ["Flying"],
                        base_spa=125, base_spe=111, ability="prankster"),
            [_make_status_move("Tailwind"),
             _make_move("Hurricane", "Flying", MoveCategory.SPECIAL, 110)],
            "prankster",
        )
        flutter = build_pokemon_profile(
            _make_build("Flutter Mane", ["Ghost", "Fairy"],
                        base_spa=135, base_spe=135),
            [_make_move("Moonblast", "Fairy", MoveCategory.SPECIAL)],
            "protosynthesis",
        )
        kingambit = build_pokemon_profile(
            _make_build("Kingambit", ["Dark", "Steel"],
                        base_atk=135, base_spe=50),
            [_make_move("Sucker Punch", "Dark", power=70)],
            "supreme-overlord",
        )
        return [incineroar, tornadus, flutter, kingambit]

    def test_fake_out_plus_prankster_scores_high(self):
        """Lead with Fake Out + Prankster Tailwind should score highly."""
        team = self._make_team()
        opponent = [
            build_pokemon_profile(
                _make_build("Dragapult", ["Dragon", "Ghost"], base_spe=142),
                [_make_move("Shadow Ball", "Ghost", MoveCategory.SPECIAL)],
                "clear-body",
            ),
            build_pokemon_profile(
                _make_build("Rillaboom", ["Grass"], base_atk=125, base_spe=85),
                [_make_move("Wood Hammer", "Grass")],
                "grassy-surge",
            ),
        ]

        matrix, _ = build_matchup_matrix(
            [p.build for p in team], [p.build for p in opponent]
        )
        leads = _recommend_leads(team, opponent, matrix)

        # Incineroar + Tornadus should be among top leads
        top_lead_pairs = [(l.pokemon_1, l.pokemon_2) for l in leads]
        assert any(
            ("Incineroar" in pair and "Tornadus" in pair)
            for pair in [set(p) for p in top_lead_pairs]
        ), f"Incineroar + Tornadus should be a top lead pair. Got: {top_lead_pairs}"


class TestThreatRanking:
    """Test threat ranking logic."""

    def test_threatening_pokemon_ranked_higher(self):
        """Pokemon that threaten many of your team should be ranked CRITICAL/HIGH."""
        your_team = [
            build_pokemon_profile(
                _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
                [], "intimidate",
            ),
            build_pokemon_profile(
                _make_build("Rillaboom", ["Grass"], base_spe=85),
                [], "grassy-surge",
            ),
        ]
        their_team = [
            # Flutter Mane threatens both (super effective Fairy vs Dark, Ghost vs nothing)
            build_pokemon_profile(
                _make_build("Flutter Mane", ["Ghost", "Fairy"],
                            base_spa=135, base_spe=135),
                [_make_move("Moonblast", "Fairy", MoveCategory.SPECIAL, 95)],
                "protosynthesis",
            ),
        ]

        matrix, _ = build_matchup_matrix(
            [p.build for p in your_team], [p.build for p in their_team]
        )
        threats = _rank_threats(your_team, their_team, matrix)

        assert len(threats) == 1
        # Flutter Mane should be at least MEDIUM threat
        assert threats[0].threat_level in ("CRITICAL", "HIGH", "MEDIUM")


class TestFullGamePlan:
    """Test the full game plan generation end to end."""

    def test_game_plan_generates_all_sections(self):
        """Full game plan should include all required sections."""
        your_team = [
            build_pokemon_profile(
                _make_build("Incineroar", ["Fire", "Dark"],
                            base_atk=115, base_spe=60, ability="intimidate"),
                [_make_move("Fake Out", "Normal", power=40),
                 _make_move("Flare Blitz", "Fire")],
                "intimidate",
            ),
            build_pokemon_profile(
                _make_build("Tornadus", ["Flying"],
                            base_spa=125, base_spe=111, ability="prankster"),
                [_make_status_move("Tailwind"),
                 _make_move("Hurricane", "Flying", MoveCategory.SPECIAL, 110)],
                "prankster",
            ),
            build_pokemon_profile(
                _make_build("Flutter Mane", ["Ghost", "Fairy"],
                            base_spa=135, base_spe=135),
                [_make_move("Moonblast", "Fairy", MoveCategory.SPECIAL)],
                "protosynthesis",
            ),
            build_pokemon_profile(
                _make_build("Kingambit", ["Dark", "Steel"],
                            base_atk=135, base_spe=50),
                [_make_move("Sucker Punch", "Dark", power=70)],
                "supreme-overlord",
            ),
        ]
        their_team = [
            build_pokemon_profile(
                _make_build("Dragapult", ["Dragon", "Ghost"],
                            base_atk=120, base_spe=142),
                [_make_move("Shadow Ball", "Ghost", MoveCategory.SPECIAL)],
                "clear-body",
            ),
            build_pokemon_profile(
                _make_build("Rillaboom", ["Grass"],
                            base_atk=125, base_spe=85),
                [_make_move("Wood Hammer", "Grass"),
                 _make_move("Fake Out", "Normal", power=40)],
                "grassy-surge",
            ),
            build_pokemon_profile(
                _make_build("Urshifu", ["Fighting", "Water"],
                            base_atk=130, base_spe=97),
                [_make_move("Surging Strikes", "Water", power=25)],
                "unseen-fist",
            ),
        ]

        plan = generate_full_game_plan(your_team, their_team)

        # Check all sections exist
        assert len(plan.lead_recommendations) >= 1
        assert len(plan.turn_1_priority_order) >= 2
        assert len(plan.threat_assessment) == 3  # 3 opponents
        assert plan.win_condition != ""
        assert len(plan.win_condition_detail) >= 1
        assert len(plan.bring_recommendation.bring) >= 2
        assert plan.markdown_summary != ""
        assert plan.overall_matchup in ("Favorable", "Even", "Unfavorable")

    def test_turn_1_prankster_tailwind_goes_first(self):
        """In turn 1 analysis, Prankster Tailwind should be shown before normal moves."""
        your_team = [
            build_pokemon_profile(
                _make_build("Incineroar", ["Fire", "Dark"],
                            base_atk=115, base_spe=60),
                [_make_move("Fake Out", "Normal", power=40)],
                "intimidate",
            ),
            build_pokemon_profile(
                _make_build("Tornadus", ["Flying"],
                            base_spa=125, base_spe=111),
                [_make_status_move("Tailwind")],
                "prankster",
            ),
        ]
        their_team = [
            build_pokemon_profile(
                _make_build("Flutter Mane", ["Ghost", "Fairy"],
                            base_spa=135, base_spe=135),
                [_make_move("Moonblast", "Fairy", MoveCategory.SPECIAL)],
                "protosynthesis",
            ),
            build_pokemon_profile(
                _make_build("Rillaboom", ["Grass"],
                            base_atk=125, base_spe=85),
                [_make_move("Wood Hammer", "Grass")],
                "grassy-surge",
            ),
        ]

        plan = generate_full_game_plan(your_team, their_team)

        # Find turn 1 actions
        t1 = plan.turn_1_priority_order
        assert len(t1) >= 2

        # Fake Out (+3) should be first, then Prankster Tailwind (+1)
        fake_out_actions = [a for a in t1 if a.move == "Fake Out"]
        tailwind_actions = [a for a in t1 if a.move == "Tailwind"]

        assert len(fake_out_actions) >= 1, f"Should have Fake Out action. Actions: {[(a.move, a.priority) for a in t1]}"
        assert len(tailwind_actions) >= 1, f"Should have Tailwind action. Actions: {[(a.move, a.priority) for a in t1]}"

        # Fake Out at +3 should come before Tailwind at +1
        fo_idx = t1.index(fake_out_actions[0])
        tw_idx = t1.index(tailwind_actions[0])
        assert fo_idx < tw_idx, (
            f"Fake Out (+3) should appear before Tailwind (+1). "
            f"FO at index {fo_idx}, TW at index {tw_idx}"
        )

        # Prankster Tailwind (+1) should come before normal moves (0)
        normal_moves = [a for a in t1 if a.priority == 0]
        if normal_moves:
            nm_idx = t1.index(normal_moves[0])
            assert tw_idx < nm_idx, (
                f"Prankster Tailwind (+1) should appear before normal moves (0). "
                f"TW at index {tw_idx}, normal at index {nm_idx}"
            )

    def test_markdown_includes_priority_info(self):
        """Markdown summary should include priority brackets in turn 1 analysis."""
        your_team = [
            build_pokemon_profile(
                _make_build("Tornadus", ["Flying"], base_spe=111),
                [_make_status_move("Tailwind")],
                "prankster",
            ),
            build_pokemon_profile(
                _make_build("Flutter Mane", ["Ghost", "Fairy"], base_spe=135),
                [_make_move("Moonblast", "Fairy", MoveCategory.SPECIAL)],
                "protosynthesis",
            ),
        ]
        their_team = [
            build_pokemon_profile(
                _make_build("Rillaboom", ["Grass"], base_spe=85),
                [_make_move("Wood Hammer", "Grass")],
                "grassy-surge",
            ),
            build_pokemon_profile(
                _make_build("Dragapult", ["Dragon", "Ghost"], base_spe=142),
                [_make_move("Shadow Ball", "Ghost", MoveCategory.SPECIAL)],
                "clear-body",
            ),
        ]

        plan = generate_full_game_plan(your_team, their_team)
        md = plan.markdown_summary

        # Should contain priority bracket notation
        assert "Turn 1 Priority Order" in md
        assert "Prankster" in md or "+1" in md


class TestEdgeCases:
    """Test edge cases for robustness."""

    def test_small_team_bring_rec(self):
        """Team with 3 Pokemon should bring all 3, leave_behind = []."""
        team = [
            build_pokemon_profile(
                _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
                [_make_move("Fake Out", "Normal", power=40)],
                "intimidate",
            ),
            build_pokemon_profile(
                _make_build("Tornadus", ["Flying"], base_spe=111),
                [_make_status_move("Tailwind")],
                "prankster",
            ),
            build_pokemon_profile(
                _make_build("Flutter Mane", ["Ghost", "Fairy"], base_spe=135),
                [_make_move("Moonblast", "Fairy", MoveCategory.SPECIAL)],
                "protosynthesis",
            ),
        ]
        opponent = [
            build_pokemon_profile(
                _make_build("Rillaboom", ["Grass"], base_spe=85),
                [_make_move("Wood Hammer", "Grass")], "grassy-surge",
            ),
            build_pokemon_profile(
                _make_build("Dragapult", ["Dragon", "Ghost"], base_spe=142),
                [_make_move("Shadow Ball", "Ghost", MoveCategory.SPECIAL)], "clear-body",
            ),
        ]

        plan = generate_full_game_plan(team, opponent)
        assert len(plan.bring_recommendation.bring) == 3
        assert len(plan.bring_recommendation.leave_behind) == 0

    def test_trick_room_priority_formatting(self):
        """Trick Room should show [-7] not [+-7] in markdown."""
        team = [
            build_pokemon_profile(
                _make_build("Porygon2", ["Normal"], base_spe=60),
                [_make_status_move("Trick Room", "Psychic")],
                "download",
            ),
            build_pokemon_profile(
                _make_build("Dusclops", ["Ghost"], base_spe=25),
                [_make_status_move("Trick Room", "Psychic")],
                "frisk",
            ),
        ]
        opponent = [
            build_pokemon_profile(
                _make_build("Flutter Mane", ["Ghost", "Fairy"], base_spe=135),
                [_make_move("Moonblast", "Fairy", MoveCategory.SPECIAL)],
                "protosynthesis",
            ),
            build_pokemon_profile(
                _make_build("Dragapult", ["Dragon", "Ghost"], base_spe=142),
                [_make_move("Shadow Ball", "Ghost", MoveCategory.SPECIAL)],
                "clear-body",
            ),
        ]

        plan = generate_full_game_plan(team, opponent)
        md = plan.markdown_summary

        # Should have [-7] for Trick Room, NOT [+-7]
        assert "[-7]" in md, f"Trick Room should show [-7]. Got: {md}"
        assert "[+-7]" not in md, f"Should not show [+-7]. Got: {md}"

    def test_speed_tie_turn_1(self):
        """Two Pokemon with same speed at same priority should both appear in turn 1."""
        p1 = build_pokemon_profile(
            _make_build("PokemonA", ["Normal"], base_spe=100,
                        nature=Nature.SERIOUS, evs=EVSpread()),
            [_make_move("Tackle", "Normal", power=40)],
            "intimidate",
        )
        p2 = build_pokemon_profile(
            _make_build("PokemonB", ["Normal"], base_spe=100,
                        nature=Nature.SERIOUS, evs=EVSpread()),
            [_make_move("Tackle", "Normal", power=40)],
            "intimidate",
        )

        plan = generate_full_game_plan([p1, p2], [p1, p2])
        # All 4 actions should appear
        assert len(plan.turn_1_priority_order) == 4

    def test_no_moves_profile(self):
        """PokemonProfile should build cleanly with empty move list."""
        build = _make_build("Unknown", ["Normal"], base_spe=80)
        profile = build_pokemon_profile(build, [], "")

        assert profile.has_fake_out is False
        assert profile.has_protect is False
        assert profile.is_prankster is False
        assert profile.prankster_moves == []
        assert profile.priority_moves == []
        assert profile.is_trick_room_setter is False
        assert profile.is_tailwind_setter is False

    def test_no_ability_profile(self):
        """PokemonProfile should build cleanly with empty ability string."""
        build = _make_build("TestMon", ["Water"], base_spe=90)
        moves = [_make_move("Surf", "Water", MoveCategory.SPECIAL, 90)]
        profile = build_pokemon_profile(build, moves, "")

        assert profile.is_prankster is False
        assert profile.is_intimidate is False
        assert profile.is_weather_setter is False
        assert profile.ability == ""

    def test_minimum_opponent_team(self):
        """Game plan should work with exactly 2 opponent Pokemon (minimum)."""
        your_team = [
            build_pokemon_profile(
                _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
                [_make_move("Flare Blitz", "Fire")], "intimidate",
            ),
            build_pokemon_profile(
                _make_build("Tornadus", ["Flying"], base_spe=111),
                [_make_status_move("Tailwind")], "prankster",
            ),
        ]
        opponent = [
            build_pokemon_profile(
                _make_build("Rillaboom", ["Grass"], base_spe=85),
                [_make_move("Wood Hammer", "Grass")], "grassy-surge",
            ),
            build_pokemon_profile(
                _make_build("Dragapult", ["Dragon", "Ghost"], base_spe=142),
                [_make_move("Shadow Ball", "Ghost", MoveCategory.SPECIAL)], "clear-body",
            ),
        ]

        plan = generate_full_game_plan(your_team, opponent)
        assert len(plan.threat_assessment) == 2
        assert len(plan.lead_recommendations) >= 1
        assert plan.markdown_summary != ""

    def test_all_low_threats(self):
        """All threats should be ranked LOW when your team hard-counters."""
        # Water team vs Fire opponents - clear type advantage
        your_team = [
            build_pokemon_profile(
                _make_build("Kyogre", ["Water"], base_spa=150, base_spe=90),
                [_make_move("Water Spout", "Water", MoveCategory.SPECIAL, 150)],
                "drizzle",
            ),
            build_pokemon_profile(
                _make_build("Gastrodon", ["Water", "Ground"],
                            base_hp=111, base_def=68, base_spd=82, base_spe=39),
                [_make_move("Earth Power", "Ground", MoveCategory.SPECIAL, 90)],
                "storm-drain",
            ),
        ]
        opponent = [
            build_pokemon_profile(
                _make_build("Torkoal", ["Fire"], base_spa=85, base_spe=20),
                [_make_move("Eruption", "Fire", MoveCategory.SPECIAL, 150)],
                "drought",
            ),
            build_pokemon_profile(
                _make_build("Magcargo", ["Fire", "Rock"], base_spa=80, base_spe=30),
                [_make_move("Flamethrower", "Fire", MoveCategory.SPECIAL, 90)],
                "flame-body",
            ),
        ]

        plan = generate_full_game_plan(your_team, opponent)
        # With such a strong type advantage, threats should be LOW or MEDIUM
        for t in plan.threat_assessment:
            assert t.threat_level in ("LOW", "MEDIUM"), (
                f"{t.pokemon_name} should be LOW/MEDIUM threat, got {t.threat_level}"
            )

    def test_unfavorable_matchup_win_condition(self):
        """Unfavorable matchup should produce defensive/balanced win condition."""
        # Weak team vs strong team
        your_team = [
            build_pokemon_profile(
                _make_build("Magikarp", ["Water"], base_atk=10, base_spe=80),
                [_make_move("Splash", "Normal", MoveCategory.STATUS, 0)],
                "swift-swim",
            ),
            build_pokemon_profile(
                _make_build("Sunkern", ["Grass"], base_atk=30, base_spe=30),
                [_make_move("Absorb", "Grass", MoveCategory.SPECIAL, 20)],
                "chlorophyll",
            ),
        ]
        opponent = [
            build_pokemon_profile(
                _make_build("Kyogre", ["Water"], base_spa=150, base_spe=90),
                [_make_move("Water Spout", "Water", MoveCategory.SPECIAL, 150)],
                "drizzle",
            ),
            build_pokemon_profile(
                _make_build("Groudon", ["Ground"], base_atk=150, base_spe=90),
                [_make_move("Precipice Blades", "Ground", power=120)],
                "drought",
            ),
        ]

        plan = generate_full_game_plan(your_team, opponent)
        # Should NOT recommend "Offensive pressure" with such weak Pokemon
        assert plan.win_condition in ("Defensive pivoting", "Balanced play"), (
            f"Expected defensive/balanced with weak team, got: {plan.win_condition}"
        )


class TestOpponentLeadPrediction:
    """Test that opponent lead prediction uses VGC patterns, not just speed."""

    def test_fake_out_user_predicted_over_fast_sweeper(self):
        """Fake Out users should be predicted as leads over faster pure sweepers."""
        profiles = [
            build_pokemon_profile(
                _make_build("Flutter Mane", ["Ghost", "Fairy"], base_spe=135),
                [_make_move("Moonblast", "Fairy", MoveCategory.SPECIAL)],
                "protosynthesis",
            ),
            build_pokemon_profile(
                _make_build("Dragapult", ["Dragon", "Ghost"], base_spe=142),
                [_make_move("Shadow Ball", "Ghost", MoveCategory.SPECIAL)],
                "clear-body",
            ),
            build_pokemon_profile(
                _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
                [_make_move("Fake Out", "Normal", power=40),
                 _make_move("Flare Blitz", "Fire")],
                "intimidate",
            ),
            build_pokemon_profile(
                _make_build("Tornadus", ["Flying"], base_spe=111),
                [_make_status_move("Tailwind"),
                 _make_status_move("Taunt")],
                "prankster",
            ),
        ]

        predicted = _predict_opponent_leads(profiles)
        predicted_names = {p.name for p in predicted}

        # Incineroar (Fake Out + Intimidate) and Tornadus (Prankster Tailwind)
        # should be predicted over Flutter Mane and Dragapult
        assert "Incineroar" in predicted_names, (
            f"Incineroar (Fake Out + Intimidate) should be predicted as lead. "
            f"Got: {predicted_names}"
        )
        assert "Tornadus" in predicted_names, (
            f"Tornadus (Prankster Tailwind) should be predicted as lead. "
            f"Got: {predicted_names}"
        )

    def test_prankster_support_predicted_as_lead(self):
        """Prankster support Pokemon should be predicted as leads."""
        profiles = [
            build_pokemon_profile(
                _make_build("Whimsicott", ["Grass", "Fairy"], base_spe=116),
                [_make_status_move("Tailwind"),
                 _make_status_move("Encore")],
                "prankster",
            ),
            build_pokemon_profile(
                _make_build("Garchomp", ["Dragon", "Ground"], base_spe=102),
                [_make_move("Earthquake", "Ground")],
                "rough-skin",
            ),
        ]

        predicted = _predict_opponent_leads(profiles)
        # Whimsicott (Prankster TW) should be first
        assert predicted[0].name == "Whimsicott"

    def test_speed_tiebreaker_when_no_special_roles(self):
        """Without special roles, faster Pokemon should be predicted as leads."""
        profiles = [
            build_pokemon_profile(
                _make_build("SlowMon", ["Normal"], base_spe=30),
                [_make_move("Tackle", "Normal", power=40)],
                "",
            ),
            build_pokemon_profile(
                _make_build("FastMon", ["Normal"], base_spe=130),
                [_make_move("Tackle", "Normal", power=40)],
                "",
            ),
        ]

        predicted = _predict_opponent_leads(profiles)
        assert predicted[0].name == "FastMon"


class TestFull6v6GamePlan:
    """Test comprehensive 6v6 game plan generation - the primary use case."""

    def _make_meta_team_a(self):
        """Create a realistic VGC meta team."""
        return [
            build_pokemon_profile(
                _make_build("Incineroar", ["Fire", "Dark"],
                            base_hp=95, base_atk=115, base_def=90,
                            base_spa=80, base_spd=90, base_spe=60),
                [_make_move("Fake Out", "Normal", power=40),
                 _make_move("Flare Blitz", "Fire"),
                 _make_move("Knock Off", "Dark", power=65),
                 _make_status_move("Parting Shot")],
                "intimidate",
            ),
            build_pokemon_profile(
                _make_build("Tornadus", ["Flying"],
                            base_hp=79, base_atk=115, base_def=70,
                            base_spa=125, base_spd=80, base_spe=111),
                [_make_status_move("Tailwind"),
                 _make_status_move("Taunt"),
                 _make_move("Bleakwind Storm", "Flying", MoveCategory.SPECIAL, 100),
                 _make_status_move("Rain Dance")],
                "prankster",
            ),
            build_pokemon_profile(
                _make_build("Flutter Mane", ["Ghost", "Fairy"],
                            base_hp=55, base_atk=55, base_def=55,
                            base_spa=135, base_spd=135, base_spe=135),
                [_make_move("Moonblast", "Fairy", MoveCategory.SPECIAL, 95),
                 _make_move("Shadow Ball", "Ghost", MoveCategory.SPECIAL, 80),
                 _make_move("Dazzling Gleam", "Fairy", MoveCategory.SPECIAL, 80),
                 _make_status_move("Protect")],
                "protosynthesis",
            ),
            build_pokemon_profile(
                _make_build("Kingambit", ["Dark", "Steel"],
                            base_hp=100, base_atk=135, base_def=120,
                            base_spa=60, base_spd=85, base_spe=50),
                [_make_move("Sucker Punch", "Dark", power=70),
                 _make_move("Iron Head", "Steel", power=80),
                 _make_move("Kowtow Cleave", "Dark", power=85),
                 _make_status_move("Protect")],
                "supreme-overlord",
            ),
            build_pokemon_profile(
                _make_build("Rillaboom", ["Grass"],
                            base_hp=100, base_atk=125, base_def=90,
                            base_spa=60, base_spd=70, base_spe=85),
                [_make_move("Fake Out", "Normal", power=40),
                 _make_move("Wood Hammer", "Grass", power=120),
                 _make_move("Grassy Glide", "Grass", power=55),
                 _make_status_move("Protect")],
                "grassy-surge",
            ),
            build_pokemon_profile(
                _make_build("Landorus", ["Ground", "Flying"],
                            base_hp=89, base_atk=125, base_def=90,
                            base_spa=115, base_spd=80, base_spe=101),
                [_make_move("Earth Power", "Ground", MoveCategory.SPECIAL, 90),
                 _make_move("Sludge Bomb", "Poison", MoveCategory.SPECIAL, 90),
                 _make_status_move("Protect"),
                 _make_move("Sandsear Storm", "Ground", MoveCategory.SPECIAL, 100)],
                "sheer-force",
            ),
        ]

    def _make_meta_team_b(self):
        """Create a second realistic VGC meta team."""
        return [
            build_pokemon_profile(
                _make_build("Rillaboom", ["Grass"],
                            base_hp=100, base_atk=125, base_def=90,
                            base_spa=60, base_spd=70, base_spe=85),
                [_make_move("Fake Out", "Normal", power=40),
                 _make_move("Wood Hammer", "Grass", power=120),
                 _make_move("Grassy Glide", "Grass", power=55),
                 _make_status_move("Protect")],
                "grassy-surge",
            ),
            build_pokemon_profile(
                _make_build("Urshifu", ["Fighting", "Water"],
                            base_hp=100, base_atk=130, base_def=100,
                            base_spa=63, base_spd=60, base_spe=97),
                [_make_move("Surging Strikes", "Water", power=25),
                 _make_move("Close Combat", "Fighting", power=120),
                 _make_move("Aqua Jet", "Water", power=40),
                 _make_status_move("Detect")],
                "unseen-fist",
            ),
            build_pokemon_profile(
                _make_build("Ogerpon", ["Grass"],
                            base_hp=80, base_atk=120, base_def=84,
                            base_spa=60, base_spd=96, base_spe=110),
                [_make_move("Ivy Cudgel", "Grass", power=100),
                 _make_move("Horn Leech", "Grass", power=75),
                 _make_status_move("Spiky Shield")],
                "defiant",
            ),
            build_pokemon_profile(
                _make_build("Chi-Yu", ["Dark", "Fire"],
                            base_hp=55, base_atk=80, base_def=80,
                            base_spa=135, base_spd=120, base_spe=100),
                [_make_move("Heat Wave", "Fire", MoveCategory.SPECIAL, 95),
                 _make_move("Dark Pulse", "Dark", MoveCategory.SPECIAL, 80),
                 _make_move("Overheat", "Fire", MoveCategory.SPECIAL, 130),
                 _make_status_move("Protect")],
                "beads-of-ruin",
            ),
            build_pokemon_profile(
                _make_build("Whimsicott", ["Grass", "Fairy"],
                            base_hp=60, base_atk=67, base_def=85,
                            base_spa=77, base_spd=75, base_spe=116),
                [_make_status_move("Tailwind"),
                 _make_status_move("Encore"),
                 _make_status_move("Taunt"),
                 _make_move("Moonblast", "Fairy", MoveCategory.SPECIAL, 95)],
                "prankster",
            ),
            build_pokemon_profile(
                _make_build("Amoonguss", ["Grass", "Poison"],
                            base_hp=114, base_atk=85, base_def=70,
                            base_spa=85, base_spd=80, base_spe=30),
                [_make_status_move("Spore"),
                 _make_move("Pollen Puff", "Bug", MoveCategory.SPECIAL, 90),
                 _make_status_move("Rage Powder"),
                 _make_status_move("Protect")],
                "regenerator",
            ),
        ]

    def test_6v6_all_sections_populated(self):
        """Full 6v6 game plan should populate all sections correctly."""
        your_team = self._make_meta_team_a()
        opponent = self._make_meta_team_b()

        plan = generate_full_game_plan(your_team, opponent)

        # All 6 opponents in threat assessment
        assert len(plan.threat_assessment) == 6
        # Lead recommendations from C(6,2)=15 pairs, top 3
        assert len(plan.lead_recommendations) == 3
        # Bring 4, leave 2
        assert len(plan.bring_recommendation.bring) == 4
        assert len(plan.bring_recommendation.leave_behind) == 2
        # Turn 1 has exactly 4 actions (2 yours + 2 theirs)
        assert len(plan.turn_1_priority_order) == 4
        # Markdown has all sections
        assert "Lead Recommendations" in plan.markdown_summary
        assert "Turn 1 Priority Order" in plan.markdown_summary
        assert "Threat Assessment" in plan.markdown_summary
        assert "Win Condition" in plan.markdown_summary
        assert "Bring 4" in plan.markdown_summary

    def test_6v6_opponent_lead_prediction_uses_support(self):
        """With 6v6, opponent lead prediction should prefer Fake Out/support over sweepers."""
        your_team = self._make_meta_team_a()
        opponent = self._make_meta_team_b()

        plan = generate_full_game_plan(your_team, opponent)

        # Turn 1 should feature opponent's likely leads (Rillaboom FO + Whimsicott Prankster)
        # NOT their fastest sweepers
        their_actions = [a for a in plan.turn_1_priority_order if a.side == "theirs"]
        their_names = {a.pokemon for a in their_actions}

        # Rillaboom (Fake Out) and/or Whimsicott (Prankster Tailwind) should be predicted
        assert "Rillaboom" in their_names or "Whimsicott" in their_names, (
            f"Expected Rillaboom (Fake Out) or Whimsicott (Prankster TW) as opponent leads. "
            f"Got: {their_names}"
        )

    def test_6v6_turn_1_priority_ordering(self):
        """Turn 1 actions should be sorted by priority bracket then speed."""
        your_team = self._make_meta_team_a()
        opponent = self._make_meta_team_b()

        plan = generate_full_game_plan(your_team, opponent)
        t1 = plan.turn_1_priority_order

        # Verify ordering: each action should have priority >= next action's priority
        for i in range(len(t1) - 1):
            assert t1[i].priority >= t1[i + 1].priority or (
                t1[i].priority == t1[i + 1].priority and t1[i].speed >= t1[i + 1].speed
            ), (
                f"Turn 1 not sorted: [{t1[i].pokemon} {t1[i].move} p{t1[i].priority} s{t1[i].speed}] "
                f"before [{t1[i+1].pokemon} {t1[i+1].move} p{t1[i+1].priority} s{t1[i+1].speed}]"
            )

    def test_6v6_all_15_lead_pairs_evaluated(self):
        """With 6 Pokemon, all C(6,2)=15 lead pairs should be evaluated."""
        your_team = self._make_meta_team_a()
        opponent = self._make_meta_team_b()

        matrix, _ = build_matchup_matrix(
            [p.build for p in your_team], [p.build for p in opponent]
        )
        # Request more than 3 to verify all 15 exist
        leads = _recommend_leads(your_team, opponent, matrix, top_n=15)
        assert len(leads) == 15, f"Expected 15 lead pairs from 6 Pokemon, got {len(leads)}"


# ============================================================================
# VGC BATTLE MECHANIC INTERACTION TESTS
# ============================================================================


class TestFakeOutGhostImmunity:
    """Fake Out is a Normal-type move. Ghost types are immune."""

    def test_profile_detects_ghost_type(self):
        """PokemonProfile should flag Ghost-type Pokemon."""
        build = _make_build("Dragapult", ["Dragon", "Ghost"], base_spe=142)
        profile = build_pokemon_profile(build, [], "")
        assert profile.is_ghost_type is True

    def test_profile_non_ghost_not_flagged(self):
        build = _make_build("Incineroar", ["Fire", "Dark"], base_spe=60)
        profile = build_pokemon_profile(build, [], "")
        assert profile.is_ghost_type is False

    def test_fake_out_war_notes_ghost_immunity(self):
        """Fake Out analysis should note Ghost-type immunity."""
        incin = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
            [_make_move("Fake Out", "Normal", power=40)],
            "intimidate",
        )
        dragapult = build_pokemon_profile(
            _make_build("Dragapult", ["Dragon", "Ghost"], base_spe=142),
            [], "",
        )
        notes = _analyze_fake_out_war([incin], [dragapult])
        ghost_notes = [n for n in notes if "Ghost" in n and "immune" in n.lower()]
        assert len(ghost_notes) > 0, f"Expected Ghost immunity note, got: {notes}"

    def test_best_turn1_move_skips_fake_out_vs_all_ghosts(self):
        """When both opponent leads are Ghost, Fake Out user should pick another move."""
        incin = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
            [
                _make_move("Fake Out", "Normal", power=40),
                _make_move("Flare Blitz", "Fire", power=120),
            ],
            "intimidate",
        )
        ghost1 = build_pokemon_profile(
            _make_build("Dragapult", ["Dragon", "Ghost"], base_spe=142),
            [], "",
        )
        ghost2 = build_pokemon_profile(
            _make_build("Gengar", ["Ghost", "Poison"], base_spe=110),
            [], "",
        )
        move, prio, note = _best_turn1_move(incin, opponent_leads=[ghost1, ghost2])
        # Should NOT pick Fake Out since all opponents are Ghost
        assert move != "Fake Out", f"Should skip Fake Out vs all Ghost leads, got: {move}"

    def test_best_turn1_move_notes_ghost_when_partial(self):
        """When one opponent lead is Ghost, note should mention targeting non-Ghost."""
        incin = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
            [_make_move("Fake Out", "Normal", power=40)],
            "intimidate",
        )
        ghost = build_pokemon_profile(
            _make_build("Dragapult", ["Dragon", "Ghost"], base_spe=142),
            [], "",
        )
        non_ghost = build_pokemon_profile(
            _make_build("Flutter Mane", ["Ghost", "Fairy"], base_spe=135),
            [], "",
        )
        rillaboom = build_pokemon_profile(
            _make_build("Rillaboom", ["Grass"], base_spe=85),
            [], "",
        )
        move, prio, note = _best_turn1_move(incin, opponent_leads=[ghost, rillaboom])
        assert move == "Fake Out"
        assert "Ghost" in note or "immune" in note.lower()


class TestFakeOutFlinchImmunity:
    """Inner Focus, Shield Dust, Own Tempo, and Covert Cloak block flinch."""

    def test_inner_focus_detected(self):
        build = _make_build("Mienshao", ["Fighting"], base_spe=105)
        profile = build_pokemon_profile(build, [], "inner-focus")
        assert profile.is_flinch_immune is True

    def test_shield_dust_detected(self):
        build = _make_build("Vivillon", ["Bug", "Flying"], base_spe=89)
        profile = build_pokemon_profile(build, [], "shield-dust")
        assert profile.is_flinch_immune is True

    def test_covert_cloak_detected(self):
        build = _make_build("Amoonguss", ["Grass", "Poison"],
                            base_spe=30, item="covert-cloak")
        profile = build_pokemon_profile(build, [], "regenerator", item_name="covert-cloak")
        assert profile.is_flinch_immune is True

    def test_normal_ability_not_flinch_immune(self):
        build = _make_build("Rillaboom", ["Grass"], base_spe=85)
        profile = build_pokemon_profile(build, [], "grassy-surge")
        assert profile.is_flinch_immune is False

    def test_fake_out_war_notes_flinch_immunity(self):
        """Fake Out analysis should note flinch-immune Pokemon."""
        incin = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
            [_make_move("Fake Out", "Normal", power=40)],
            "intimidate",
        )
        inner_focus_mon = build_pokemon_profile(
            _make_build("Mienshao", ["Fighting"], base_spe=105),
            [], "inner-focus",
        )
        notes = _analyze_fake_out_war([incin], [inner_focus_mon])
        flinch_notes = [n for n in notes if "flinch" in n.lower() or "resist" in n.lower()]
        assert len(flinch_notes) > 0, f"Expected flinch immunity note, got: {notes}"


class TestPranksterDarkImmunity:
    """Dark types are immune to Prankster-boosted status moves."""

    def test_profile_detects_dark_type(self):
        build = _make_build("Kingambit", ["Dark", "Steel"], base_spe=50)
        profile = build_pokemon_profile(build, [], "")
        assert profile.is_dark_type is True

    def test_prankster_taunt_reduced_vs_dark_leads(self):
        """When opponent leads are Dark type, Prankster Taunt should score less."""
        tornadus = build_pokemon_profile(
            _make_build("Tornadus", ["Flying"], base_spe=111),
            [_make_status_move("Tailwind"), _make_status_move("Taunt")],
            "prankster",
        )
        # Partner
        flutter = build_pokemon_profile(
            _make_build("Flutter Mane", ["Ghost", "Fairy"], base_spe=135),
            [_make_move("Moonblast", "Fairy", category=MoveCategory.SPECIAL)],
            "protosynthesis",
        )
        # Opponent with Dark-type leads
        kingambit = build_pokemon_profile(
            _make_build("Kingambit", ["Dark", "Steel"], base_spe=50),
            [_make_move("Sucker Punch", "Dark")],
            "supreme-overlord",
        )
        incin_opp = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
            [_make_move("Fake Out", "Normal", power=40)],
            "intimidate",
        )
        filler = build_pokemon_profile(
            _make_build("Rillaboom", ["Grass"], base_spe=85),
            [], "grassy-surge",
        )

        your = [tornadus, flutter, filler]
        their = [kingambit, incin_opp, filler]

        # Build matchup matrix
        matrix, _ = build_matchup_matrix(
            [p.build for p in your], [p.build for p in their]
        )

        # Score with Dark leads
        rec_dark = _score_lead_pair(
            (tornadus, flutter), their, matrix, your
        )

        # Now score vs team with no Dark types
        non_dark = build_pokemon_profile(
            _make_build("Rillaboom2", ["Grass"], base_spe=85),
            [], "grassy-surge",
        )
        non_dark2 = build_pokemon_profile(
            _make_build("Amoonguss", ["Grass", "Poison"], base_spe=30),
            [], "regenerator",
        )
        their_no_dark = [non_dark, non_dark2, filler]
        matrix2, _ = build_matchup_matrix(
            [p.build for p in your], [p.build for p in their_no_dark]
        )
        rec_no_dark = _score_lead_pair(
            (tornadus, flutter), their_no_dark, matrix2, your
        )

        # Prankster Taunt should be worth less vs Dark-heavy team
        # The Dark team also blocks Prankster Taunt
        dark_has_taunt_note = any("Dark" in (rec_dark.prankster_note or "") for _ in [1])
        assert dark_has_taunt_note or rec_dark.score <= rec_no_dark.score, (
            f"Prankster Taunt should be less effective vs Dark leads. "
            f"Dark: {rec_dark.score}, No Dark: {rec_no_dark.score}"
        )

    def test_best_turn1_skips_taunt_vs_all_dark(self):
        """Prankster Taunt should be skipped when all opponents are Dark type."""
        tornadus = build_pokemon_profile(
            _make_build("Tornadus", ["Flying"], base_spe=111),
            [
                _make_status_move("Taunt"),
                _make_status_move("Tailwind"),
            ],
            "prankster",
        )
        dark1 = build_pokemon_profile(
            _make_build("Kingambit", ["Dark", "Steel"], base_spe=50),
            [], "",
        )
        dark2 = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
            [], "",
        )
        move, prio, note = _best_turn1_move(tornadus, opponent_leads=[dark1, dark2])
        # Should pick Tailwind instead of Taunt since all are Dark
        assert move == "Tailwind", f"Should pick Tailwind over Taunt vs all Dark leads, got: {move}"


class TestIntimidateCounters:
    """Intimidate should be penalized against Defiant/Competitive and noted for blockers."""

    def test_profile_detects_defiant(self):
        build = _make_build("Kingambit", ["Dark", "Steel"], base_spe=50)
        profile = build_pokemon_profile(build, [], "defiant")
        assert profile.intimidate_reaction == "punished"

    def test_profile_detects_competitive(self):
        build = _make_build("Milotic", ["Water"], base_spe=81)
        profile = build_pokemon_profile(build, [], "competitive")
        assert profile.intimidate_reaction == "punished"

    def test_profile_detects_clear_body(self):
        build = _make_build("Metagross", ["Steel", "Psychic"], base_spe=70)
        profile = build_pokemon_profile(build, [], "clear-body")
        assert profile.intimidate_reaction == "blocked"

    def test_profile_detects_inner_focus_blocks(self):
        build = _make_build("Mienshao", ["Fighting"], base_spe=105)
        profile = build_pokemon_profile(build, [], "inner-focus")
        assert profile.intimidate_reaction == "blocked"

    def test_profile_normal_intimidate_reaction(self):
        build = _make_build("Flutter Mane", ["Ghost", "Fairy"], base_spe=135)
        profile = build_pokemon_profile(build, [], "protosynthesis")
        assert profile.intimidate_reaction == "normal"

    def test_intimidate_penalized_vs_defiant(self):
        """Bringing Intimidate lead vs Defiant opponent should be penalized."""
        incin = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
            [_make_move("Fake Out", "Normal", power=40)],
            "intimidate",
        )
        partner = build_pokemon_profile(
            _make_build("Flutter Mane", ["Ghost", "Fairy"], base_spe=135),
            [_make_move("Moonblast", "Fairy", category=MoveCategory.SPECIAL)],
            "protosynthesis",
        )
        defiant_mon = build_pokemon_profile(
            _make_build("Kingambit", ["Dark", "Steel"], base_atk=135, base_spe=50),
            [_make_move("Iron Head", "Steel")],
            "defiant",
        )
        filler = build_pokemon_profile(
            _make_build("Rillaboom", ["Grass"], base_spe=85),
            [], "grassy-surge",
        )

        your = [incin, partner, filler]
        their = [defiant_mon, filler]

        matrix, _ = build_matchup_matrix(
            [p.build for p in your], [p.build for p in their]
        )
        rec = _score_lead_pair((incin, partner), their, matrix, your)
        # Should have a warning about triggering Defiant
        warning_reasons = [r for r in rec.reasoning if "WARNING" in r or "trigger" in r.lower()]
        assert len(warning_reasons) > 0, f"Should warn about Defiant. Reasons: {rec.reasoning}"


class TestFollowMeRedirect:
    """Follow Me and Rage Powder redirect support."""

    def test_profile_detects_follow_me(self):
        build = _make_build("Indeedee-F", ["Psychic", "Normal"], base_spe=95)
        moves = [_make_status_move("Follow Me")]
        profile = build_pokemon_profile(build, moves, "psychic-surge")
        assert profile.has_follow_me is True

    def test_profile_detects_rage_powder(self):
        build = _make_build("Amoonguss", ["Grass", "Poison"], base_spe=30)
        moves = [_make_status_move("Rage Powder")]
        profile = build_pokemon_profile(build, moves, "regenerator")
        assert profile.has_follow_me is True

    def test_follow_me_bonus_with_tr_setter(self):
        """Follow Me + Trick Room setter lead pair should get bonus."""
        indeedee = build_pokemon_profile(
            _make_build("Indeedee-F", ["Psychic", "Normal"], base_spe=95),
            [_make_status_move("Follow Me"), _make_status_move("Trick Room")],
            "psychic-surge",
        )
        dusclops = build_pokemon_profile(
            _make_build("Dusclops", ["Ghost"], base_spe=25),
            [_make_status_move("Trick Room")],
            "frisk",
        )
        filler = build_pokemon_profile(
            _make_build("Rillaboom", ["Grass"], base_spe=85),
            [], "grassy-surge",
        )

        your = [indeedee, dusclops, filler]
        their = [filler]

        matrix, _ = build_matchup_matrix(
            [p.build for p in your], [p.build for p in their]
        )
        rec = _score_lead_pair((indeedee, dusclops), their, matrix, your)
        redirect_reasons = [r for r in rec.reasoning if "redirect" in r.lower()]
        assert len(redirect_reasons) > 0, f"Should note redirect support. Reasons: {rec.reasoning}"

    def test_redirect_analysis_notes_rage_powder(self):
        """_analyze_redirect_interactions should note Rage Powder."""
        amoonguss = build_pokemon_profile(
            _make_build("Amoonguss", ["Grass", "Poison"], base_spe=30),
            [_make_status_move("Rage Powder"), _make_status_move("Spore")],
            "regenerator",
        )
        filler = build_pokemon_profile(
            _make_build("Rillaboom", ["Grass"], base_spe=85),
            [], "grassy-surge",
        )
        notes = _analyze_redirect_interactions([amoonguss, filler], [filler])
        rage_notes = [n for n in notes if "Rage Powder" in n]
        assert len(rage_notes) > 0, f"Expected Rage Powder note, got: {notes}"

    def test_safety_goggles_bypasses_rage_powder(self):
        """Safety Goggles user should be noted as bypassing Rage Powder."""
        amoonguss = build_pokemon_profile(
            _make_build("Amoonguss", ["Grass", "Poison"], base_spe=30),
            [_make_status_move("Rage Powder")],
            "regenerator",
        )
        goggles_mon = build_pokemon_profile(
            _make_build("Tornadus", ["Flying"], base_spe=111),
            [], "prankster",
            item_name="safety-goggles",
        )
        notes = _analyze_redirect_interactions([amoonguss], [goggles_mon])
        goggles_notes = [n for n in notes if "Safety Goggles" in n]
        assert len(goggles_notes) > 0, f"Expected Safety Goggles note, got: {notes}"


class TestQuickGuard:
    """Quick Guard blocks all priority moves for the turn."""

    def test_profile_detects_quick_guard(self):
        build = _make_build("Hitmontop", ["Fighting"], base_spe=70)
        moves = [
            _make_status_move("Quick Guard"),
            _make_move("Close Combat", "Fighting"),
        ]
        profile = build_pokemon_profile(build, moves, "intimidate")
        assert profile.has_quick_guard is True

    def test_quick_guard_noted_in_fake_out_war(self):
        """Quick Guard should be mentioned as Fake Out counter."""
        hitmontop = build_pokemon_profile(
            _make_build("Hitmontop", ["Fighting"], base_spe=70),
            [_make_status_move("Quick Guard")],
            "intimidate",
        )
        incin = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
            [_make_move("Fake Out", "Normal", power=40)],
            "intimidate",
        )
        notes = _analyze_fake_out_war([hitmontop], [incin])
        qg_notes = [n for n in notes if "Quick Guard" in n]
        assert len(qg_notes) > 0, f"Expected Quick Guard note, got: {notes}"


class TestWideGuard:
    """Wide Guard blocks spread moves for the turn."""

    def test_profile_detects_wide_guard(self):
        build = _make_build("Hitmontop", ["Fighting"], base_spe=70)
        moves = [_make_status_move("Wide Guard")]
        profile = build_pokemon_profile(build, moves, "intimidate")
        assert profile.has_wide_guard is True


class TestPsychicTerrain:
    """Psychic Terrain blocks priority moves on grounded targets."""

    def test_profile_detects_psychic_terrain_setter(self):
        build = _make_build("Indeedee-F", ["Psychic", "Normal"], base_spe=95)
        profile = build_pokemon_profile(build, [], "psychic-surge")
        assert profile.is_terrain_setter is True
        assert profile.terrain_type == "psychic"

    def test_profile_detects_grounded(self):
        """Non-Flying, non-Levitate Pokemon should be grounded."""
        build = _make_build("Incineroar", ["Fire", "Dark"], base_spe=60)
        profile = build_pokemon_profile(build, [], "intimidate")
        assert profile.is_grounded is True

    def test_profile_flying_not_grounded(self):
        build = _make_build("Tornadus", ["Flying"], base_spe=111)
        profile = build_pokemon_profile(build, [], "prankster")
        assert profile.is_grounded is False

    def test_profile_levitate_not_grounded(self):
        build = _make_build("Gengar", ["Ghost", "Poison"], base_spe=110)
        profile = build_pokemon_profile(build, [], "levitate")
        assert profile.is_grounded is False

    def test_profile_air_balloon_not_grounded(self):
        build = _make_build("Heatran", ["Fire", "Steel"], base_spe=77,
                            item="air-balloon")
        profile = build_pokemon_profile(build, [], "flash-fire", item_name="air-balloon")
        assert profile.is_grounded is False

    def test_terrain_analysis_notes_psychic_blocking_priority(self):
        """Psychic Terrain should be noted as blocking opponent's priority."""
        indeedee = build_pokemon_profile(
            _make_build("Indeedee-F", ["Psychic", "Normal"], base_spe=95),
            [_make_status_move("Follow Me")],
            "psychic-surge",
        )
        # Opponent with Fake Out
        incin = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
            [_make_move("Fake Out", "Normal", power=40)],
            "intimidate",
        )
        notes = _analyze_terrain_interactions([indeedee], [incin])
        terrain_notes = [n for n in notes if "Psychic Terrain" in n and "block" in n.lower()]
        assert len(terrain_notes) > 0, f"Expected Psychic Terrain blocking note, got: {notes}"

    def test_terrain_analysis_notes_electric_blocking_sleep(self):
        """Electric Terrain should block sleep moves."""
        rillaboom = build_pokemon_profile(
            _make_build("Rillaboom", ["Grass"], base_spe=85),
            [], "grassy-surge",
        )
        pincurchin = build_pokemon_profile(
            _make_build("Pincurchin", ["Electric"], base_spe=15),
            [], "electric-surge",
        )
        # Opponent with Spore
        amoonguss = build_pokemon_profile(
            _make_build("Amoonguss", ["Grass", "Poison"], base_spe=30),
            [_make_status_move("Spore")],
            "regenerator",
        )
        notes = _analyze_terrain_interactions([pincurchin], [amoonguss])
        sleep_notes = [n for n in notes if "sleep" in n.lower() or "Spore" in n]
        assert len(sleep_notes) > 0, f"Expected sleep blocking note, got: {notes}"


class TestMoldBreaker:
    """Mold Breaker bypasses defender abilities."""

    def test_profile_detects_mold_breaker(self):
        build = _make_build("Excadrill", ["Ground", "Steel"], base_spe=88)
        profile = build_pokemon_profile(build, [], "mold-breaker")
        assert profile.is_mold_breaker is True

    def test_teravolt_detected(self):
        build = _make_build("Zekrom", ["Dragon", "Electric"], base_spe=90)
        profile = build_pokemon_profile(build, [], "teravolt")
        assert profile.is_mold_breaker is True

    def test_non_mold_breaker(self):
        build = _make_build("Flutter Mane", ["Ghost", "Fairy"], base_spe=135)
        profile = build_pokemon_profile(build, [], "protosynthesis")
        assert profile.is_mold_breaker is False


class TestSafetyGoggles:
    """Safety Goggles blocks powder moves and Rage Powder redirect."""

    def test_profile_detects_safety_goggles(self):
        build = _make_build("Tornadus", ["Flying"], base_spe=111,
                            item="safety-goggles")
        profile = build_pokemon_profile(build, [], "prankster",
                                         item_name="safety-goggles")
        assert profile.has_safety_goggles is True

    def test_non_goggles_not_flagged(self):
        build = _make_build("Tornadus", ["Flying"], base_spe=111)
        profile = build_pokemon_profile(build, [], "prankster")
        assert profile.has_safety_goggles is False


class TestFullGamePlanWithMechanics:
    """Integration tests - full game plan correctly accounts for mechanics."""

    def test_game_plan_ghost_vs_fake_out(self):
        """Game plan with Ghost leads vs Fake Out should mention Ghost immunity."""
        # Your team: Incineroar (Fake Out) + Flutter Mane + Rillaboom
        incin = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"],
                        base_atk=115, base_spe=60),
            [_make_move("Fake Out", "Normal", power=40),
             _make_move("Flare Blitz", "Fire")],
            "intimidate",
        )
        flutter = build_pokemon_profile(
            _make_build("Flutter Mane", ["Ghost", "Fairy"],
                        base_spa=135, base_spe=135),
            [_make_move("Moonblast", "Fairy", category=MoveCategory.SPECIAL)],
            "protosynthesis",
        )
        rilla = build_pokemon_profile(
            _make_build("Rillaboom", ["Grass"],
                        base_atk=125, base_spe=85),
            [_make_move("Grassy Glide", "Grass")],
            "grassy-surge",
        )

        # Opponent: Dragapult (Ghost) + Gengar (Ghost) + filler
        dragapult = build_pokemon_profile(
            _make_build("Dragapult", ["Dragon", "Ghost"],
                        base_spa=100, base_spe=142),
            [_make_move("Shadow Ball", "Ghost", category=MoveCategory.SPECIAL)],
            "clear-body",
        )
        gengar = build_pokemon_profile(
            _make_build("Gengar", ["Ghost", "Poison"],
                        base_spa=130, base_spe=110),
            [_make_move("Shadow Ball", "Ghost", category=MoveCategory.SPECIAL)],
            "cursed-body",
        )
        filler = build_pokemon_profile(
            _make_build("Garchomp", ["Dragon", "Ground"],
                        base_atk=130, base_spe=102),
            [_make_move("Earthquake", "Ground")],
            "rough-skin",
        )

        plan = generate_full_game_plan(
            [incin, flutter, rilla],
            [dragapult, gengar, filler],
        )

        # Check speed control notes mention Ghost immunity
        ghost_notes = [n for n in plan.speed_control_notes
                       if "ghost" in n.lower() and "immune" in n.lower()]
        assert len(ghost_notes) > 0, (
            f"Game plan should note Ghost immunity to Fake Out. "
            f"Notes: {plan.speed_control_notes}"
        )

    def test_game_plan_psychic_terrain_in_notes(self):
        """Game plan with Psychic Terrain setter should include terrain notes."""
        indeedee = build_pokemon_profile(
            _make_build("Indeedee-F", ["Psychic", "Normal"], base_spe=95),
            [_make_status_move("Follow Me"), _make_status_move("Trick Room")],
            "psychic-surge",
        )
        dusclops = build_pokemon_profile(
            _make_build("Dusclops", ["Ghost"], base_spe=25),
            [_make_status_move("Trick Room")],
            "frisk",
        )
        filler = build_pokemon_profile(
            _make_build("Rillaboom", ["Grass"], base_spe=85),
            [_make_move("Grassy Glide", "Grass")],
            "grassy-surge",
        )

        # Opponent has Fake Out
        incin = build_pokemon_profile(
            _make_build("Incineroar", ["Fire", "Dark"], base_spe=60),
            [_make_move("Fake Out", "Normal", power=40)],
            "intimidate",
        )
        opp_filler = build_pokemon_profile(
            _make_build("Flutter Mane", ["Ghost", "Fairy"], base_spe=135),
            [_make_move("Moonblast", "Fairy", category=MoveCategory.SPECIAL)],
            "protosynthesis",
        )

        plan = generate_full_game_plan(
            [indeedee, dusclops, filler],
            [incin, opp_filler, filler],
        )

        terrain_notes = [n for n in plan.speed_control_notes
                         if "Psychic Terrain" in n]
        assert len(terrain_notes) > 0, (
            f"Game plan should include Psychic Terrain notes. "
            f"Notes: {plan.speed_control_notes}"
        )
