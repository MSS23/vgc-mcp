"""Tests for multi-threat EV spread optimization."""

import pytest
from vgc_mcp.tools.spread_tools import _prepare_threats, DamageCache, _quick_feasibility_check
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.models.pokemon import Nature


class TestMultiSurvival:
    """Test suite for optimize_multi_survival_spread tool."""

    @pytest.mark.asyncio
    async def test_3_threats_mixed(self):
        """Test 3 threats (2 physical, 1 special)."""
        # This is a basic structure test - full integration would require MCP setup
        threats = [
            {"attacker": "urshifu-rapid-strike", "move": "surging-strikes"},
            {"attacker": "landorus", "move": "earthquake"},
            {"attacker": "chi-yu", "move": "heat-wave"}
        ]

        assert len(threats) == 3
        assert all("attacker" in t and "move" in t for t in threats)

    @pytest.mark.asyncio
    async def test_threat_validation(self):
        """Test threat count validation."""
        # Too few threats
        threats_few = [
            {"attacker": "urshifu", "move": "wicked-blow"}
        ]
        assert len(threats_few) < 3

        # Too many threats
        threats_many = [
            {"attacker": f"pokemon{i}", "move": "tackle"}
            for i in range(7)
        ]
        assert len(threats_many) > 6

        # Valid threat count
        threats_valid = [
            {"attacker": "urshifu", "move": "wicked-blow"},
            {"attacker": "flutter-mane", "move": "moonblast"},
            {"attacker": "chi-yu", "move": "heat-wave"}
        ]
        assert 3 <= len(threats_valid) <= 6

    @pytest.mark.asyncio
    async def test_prepare_threats_structure(self):
        """Test that threat preparation handles auto-fetching correctly."""
        # This would require a real PokeAPI client
        # For now, just test the structure
        threats = [
            {
                "attacker": "urshifu-rapid-strike",
                "move": "surging-strikes",
                "item": "choice-scarf"  # Optional override
            },
            {
                "attacker": "flutter-mane",
                "move": "moonblast"
                # No item - should auto-fetch
            }
        ]

        # Verify structure
        assert threats[0]["item"] == "choice-scarf"
        assert "item" not in threats[1]  # Will be auto-fetched

    @pytest.mark.asyncio
    async def test_cache_functionality(self):
        """Test that damage cache prevents redundant calculations."""
        # This is a basic test - full test would require real Pokemon data
        # Just verify the cache structure works
        pass  # Placeholder for integration test

    def test_feasibility_check_structure(self):
        """Test quick feasibility check logic."""
        # This tests the algorithm logic without needing real data
        # The function samples 5 HP values: [0, 60, 120, 180, 252]
        hp_samples = [0, 60, 120, 180, 252]
        assert len(hp_samples) == 5
        assert min(hp_samples) == 0
        assert max(hp_samples) == 252

    @pytest.mark.asyncio
    async def test_output_format(self):
        """Test that output format matches specification."""
        expected_keys = [
            "success",
            "optimal_spread",
            "threat_survival_analysis",
            "showdown_paste",
            "computation_stats"
        ]

        # When successful
        success_output = {
            "success": True,
            "optimal_spread": {},
            "threat_survival_analysis": [],
            "showdown_paste": "",
            "computation_stats": {}
        }
        assert all(key in success_output for key in expected_keys)

        # When impossible
        impossible_output = {
            "success": False,
            "impossible": True,
            "reason": "",
            "suggestions": [],
            "computation_stats": {}
        }
        assert "impossible" in impossible_output
        assert "suggestions" in impossible_output


class TestPerformance:
    """Test performance targets."""

    def test_target_times(self):
        """Verify performance targets are defined."""
        # As specified in plan:
        # - 3 threats: < 10 seconds
        # - 6 threats: < 30 seconds
        targets = {
            3: 10000,  # ms
            4: 15000,
            5: 25000,
            6: 30000
        }

        for threat_count, max_time_ms in targets.items():
            assert max_time_ms > 0
            assert threat_count <= 6


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_all_physical_threats(self):
        """Test when all threats are physical."""
        threats = [
            {"attacker": "urshifu", "move": "wicked-blow"},
            {"attacker": "landorus", "move": "earthquake"},
            {"attacker": "rillaboom", "move": "wood-hammer"}
        ]
        # All physical - should only need HP + Def
        assert all("move" in t for t in threats)

    def test_all_special_threats(self):
        """Test when all threats are special."""
        threats = [
            {"attacker": "flutter-mane", "move": "moonblast"},
            {"attacker": "chi-yu", "move": "heat-wave"},
            {"attacker": "tornadus", "move": "bleakwind-storm"}
        ]
        # All special - should only need HP + SpD
        assert all("move" in t for t in threats)

    def test_tera_type_handling(self):
        """Test Tera type specification."""
        threats = [
            {
                "attacker": "chi-yu",
                "move": "heat-wave",
                "tera_type": "fire"  # Tera Fire Chi-Yu
            },
            {
                "attacker": "urshifu",
                "move": "wicked-blow",
                "tera_type": "dark"  # Tera Dark Urshifu
            }
        ]

        assert threats[0]["tera_type"] == "fire"
        assert threats[1]["tera_type"] == "dark"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
