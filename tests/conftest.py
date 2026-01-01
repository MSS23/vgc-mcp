"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from vgc_mcp.api.cache import APICache
from vgc_mcp.api.pokeapi import PokeAPIClient
from vgc_mcp.team.manager import TeamManager
from vgc_mcp.models.pokemon import BaseStats


@pytest.fixture
def mock_cache():
    """Mock cache that returns None (cache miss)."""
    cache = MagicMock(spec=APICache)
    cache.get.return_value = None
    return cache


@pytest.fixture
def team_manager():
    """Fresh team manager for each test."""
    return TeamManager()


# Sample Pokemon data for testing
FLUTTER_MANE_STATS = BaseStats(
    hp=55,
    attack=55,
    defense=55,
    special_attack=135,
    special_defense=135,
    speed=135
)

DRAGAPULT_STATS = BaseStats(
    hp=88,
    attack=120,
    defense=75,
    special_attack=100,
    special_defense=75,
    speed=142
)

URSHIFU_STATS = BaseStats(
    hp=100,
    attack=130,
    defense=100,
    special_attack=63,
    special_defense=60,
    speed=97
)

INCINEROAR_STATS = BaseStats(
    hp=95,
    attack=115,
    defense=90,
    special_attack=80,
    special_defense=90,
    speed=60
)

IRON_HANDS_STATS = BaseStats(
    hp=154,
    attack=140,
    defense=108,
    special_attack=50,
    special_defense=68,
    speed=50
)

AMOONGUSS_STATS = BaseStats(
    hp=114,
    attack=85,
    defense=70,
    special_attack=85,
    special_defense=80,
    speed=30
)


@pytest.fixture
def flutter_mane_stats():
    return FLUTTER_MANE_STATS


@pytest.fixture
def dragapult_stats():
    return DRAGAPULT_STATS


@pytest.fixture
def urshifu_stats():
    return URSHIFU_STATS
