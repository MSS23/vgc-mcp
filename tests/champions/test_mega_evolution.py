"""Tests for the Mega Evolution ability lookup.

Mega forms swap to a single fixed ability that the damage calc must use.
Without this, e.g. Mega Manectric is silently treated as Static when it's
actually Intimidate, and physical attackers' damage is overstated.
"""

from vgc_mcp_core.calc.mega_evolution import (
    MEGA_FORM_ABILITY,
    get_mega_ability,
    is_mega_form,
)


def test_manectric_mega_is_intimidate():
    assert get_mega_ability("manectric-mega") == "Intimidate"


def test_charizard_x_vs_y_have_different_abilities():
    assert get_mega_ability("charizard-mega-x") == "Tough Claws"
    assert get_mega_ability("charizard-mega-y") == "Drought"


def test_kangaskhan_mega_is_parental_bond():
    assert get_mega_ability("kangaskhan-mega") == "Parental Bond"


def test_rayquaza_mega_is_delta_stream():
    assert get_mega_ability("rayquaza-mega") == "Delta Stream"


def test_base_form_returns_none():
    assert get_mega_ability("manectric") is None
    assert get_mega_ability("charizard") is None


def test_non_mega_returns_none():
    assert get_mega_ability("excadrill") is None
    assert get_mega_ability("flutter-mane") is None


def test_handles_mega_prefix_form():
    # "mega-manectric" should normalize to "manectric-mega".
    assert get_mega_ability("mega-manectric") == "Intimidate"
    assert get_mega_ability("mega-charizard-x") == "Tough Claws"


def test_is_mega_form_predicate():
    assert is_mega_form("manectric-mega") is True
    assert is_mega_form("excadrill") is False
    assert is_mega_form("") is False
    assert is_mega_form(None) is False  # type: ignore[arg-type]


def test_lookup_table_is_complete():
    # If this fails, MEGA_FORM_ABILITY has a duplicate that didn't get
    # caught at write time; every Mega has exactly one ability post-mega.
    assert len(MEGA_FORM_ABILITY) >= 40, "Mega lookup table has fewer entries than expected"
    for form, ability in MEGA_FORM_ABILITY.items():
        assert form.endswith("-mega") or form.endswith("-mega-x") or form.endswith("-mega-y"), form
        assert ability and isinstance(ability, str), form
