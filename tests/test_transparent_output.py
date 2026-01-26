"""Tests for transparent output formatting."""

import pytest
from vgc_mcp.tools.damage_tools import format_transparent_output
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, BaseStats
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.calc.damage import DamageResult


class TestTransparentOutput:
    """Test transparent output formatting."""
    
    @pytest.fixture
    def sample_attacker(self):
        """Create a sample attacker Pokemon."""
        return PokemonBuild(
            name="Flutter Mane",
            base_stats=BaseStats(
                hp=55, attack=55, defense=55,
                special_attack=135, special_defense=135, speed=135
            ),
            types=["Ghost", "Fairy"],
            nature=Nature.TIMID,
            evs=EVSpread(hp=4, special_attack=252, speed=252),
            item="choice-specs",
            ability="protosynthesis"
        )
    
    @pytest.fixture
    def sample_defender(self):
        """Create a sample defender Pokemon."""
        return PokemonBuild(
            name="Incineroar",
            base_stats=BaseStats(
                hp=95, attack=115, defense=90,
                special_attack=80, special_defense=90, speed=60
            ),
            types=["Fire", "Dark"],
            nature=Nature.CAREFUL,
            evs=EVSpread(hp=252, defense=4, special_defense=252),
            item="assault-vest",
            ability="intimidate"
        )
    
    @pytest.fixture
    def sample_move(self):
        """Create a sample move."""
        return Move(
            name="Moonblast",
            type="Fairy",
            category=MoveCategory.SPECIAL,
            power=95,
            accuracy=100
        )
    
    @pytest.fixture
    def sample_damage_result(self):
        """Create a sample damage result."""
        return DamageResult(
            min_damage=147,
            max_damage=173,
            min_percent=72.8,
            max_percent=85.6,
            rolls=[147, 150, 153, 156, 159, 162, 165, 168, 171, 174, 177, 180, 183, 186, 189, 192],
            defender_hp=202,
            ko_chance="2HKO",
            is_guaranteed_ohko=False,
            is_possible_ohko=False,
            details={
                "modifiers_applied": ["STAB (1.5x)", "Choice Specs (1.3x)"],
                "type_effectiveness": 1.0
            }
        )
    
    def test_includes_all_evs(self, sample_attacker, sample_defender, sample_move, sample_damage_result):
        """Output should show all 6 EV values."""
        output = format_transparent_output(
            sample_attacker,
            sample_defender,
            sample_move,
            sample_damage_result,
            sample_damage_result.details.get("modifiers_applied", [])
        )
        
        # Check that EV table includes all stats
        assert "| EVs  |" in output
        assert "4" in output  # HP EVs
        assert "252" in output  # SpA and Spe EVs
    
    def test_shows_calculation_steps(self, sample_attacker, sample_defender, sample_move, sample_damage_result):
        """Output should show step-by-step calculation if provided."""
        calculation_steps = [
            {"name": "Base Damage", "value": "89", "notes": "Base calculation"},
            {"name": "STAB", "value": "133", "notes": "×1.5"}
        ]
        
        output = format_transparent_output(
            sample_attacker,
            sample_defender,
            sample_move,
            sample_damage_result,
            sample_damage_result.details.get("modifiers_applied", []),
            calculation_steps
        )
        
        assert "Calculation Breakdown" in output
        assert "Base Damage" in output
        assert "STAB" in output
    
    def test_shows_pokemon_details(self, sample_attacker, sample_defender, sample_move, sample_damage_result):
        """Output should show full Pokemon details."""
        output = format_transparent_output(
            sample_attacker,
            sample_defender,
            sample_move,
            sample_damage_result,
            sample_damage_result.details.get("modifiers_applied", [])
        )
        
        # Check attacker section
        assert "Attacker: Flutter Mane" in output
        assert "Timid" in output
        assert "choice-specs" in output
        assert "protosynthesis" in output
        
        # Check defender section
        assert "Defender: Incineroar" in output
        assert "Careful" in output
        assert "assault-vest" in output
    
    def test_shows_move_details(self, sample_attacker, sample_defender, sample_move, sample_damage_result):
        """Output should show move details."""
        output = format_transparent_output(
            sample_attacker,
            sample_defender,
            sample_move,
            sample_damage_result,
            sample_damage_result.details.get("modifiers_applied", [])
        )
        
        assert "Move: Moonblast" in output
        assert "95" in output  # Base power
        assert "Fairy" in output
        assert "Special" in output
    
    def test_shows_result_table(self, sample_attacker, sample_defender, sample_move, sample_damage_result):
        """Output should show result table with damage range."""
        output = format_transparent_output(
            sample_attacker,
            sample_defender,
            sample_move,
            sample_damage_result,
            sample_damage_result.details.get("modifiers_applied", [])
        )
        
        assert "Result" in output
        assert "147" in output  # Min damage
        assert "173" in output  # Max damage
        assert "72.8" in output  # Min percent
        assert "85.6" in output  # Max percent
    
    def test_shows_modifiers_applied(self, sample_attacker, sample_defender, sample_move, sample_damage_result):
        """Output should list all modifiers applied."""
        modifiers = ["STAB (1.5x)", "Choice Specs (1.3x)", "Super Effective (2x)"]
        
        output = format_transparent_output(
            sample_attacker,
            sample_defender,
            sample_move,
            sample_damage_result,
            modifiers
        )
        
        assert "Modifiers Applied" in output
        assert "STAB (1.5x)" in output
        assert "Choice Specs (1.3x)" in output
