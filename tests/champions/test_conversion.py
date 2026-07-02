"""Tests for the EV <-> SP conversion module.

These pin the math: 32 SP saturates at 252 EV, every other SP step is
8 EVs of stat output. The roundtrip and trim behaviors are also covered
so regressions don't silently swap saturation modes.
"""


from vgc_mcp_core.calc.conversion import (
    EV_MAX_PER_STAT,
    EV_PER_SP,
    SP_MAX_PER_STAT,
    SP_MAX_TOTAL,
    describe_conversion,
    ev_to_sp,
    evs_to_sps_spread,
    regulation_uses_champions,
    sp_to_ev,
    sps_to_evs_spread,
)
from vgc_mcp_core.formats.showdown import build_dual_paste_payload
from vgc_mcp_core.models.pokemon import EVSpread, StatPointSpread

# ---------- Scalar conversion ----------

def test_252_evs_round_trips_to_32_sps():
    assert ev_to_sp(252) == 32
    assert sp_to_ev(32) == 252


def test_zero_round_trips():
    assert ev_to_sp(0) == 0
    assert sp_to_ev(0) == 0


def test_4_evs_ceils_to_1_sp():
    # 4 EVs is half of one SP; ceil rounds up so we don't lose stat output.
    assert ev_to_sp(4, round_mode="ceil") == 1
    assert ev_to_sp(4, round_mode="floor") == 0


def test_8_evs_is_exactly_1_sp():
    assert ev_to_sp(8) == 1
    assert sp_to_ev(1) == EV_PER_SP


def test_intermediate_values():
    # 100 EVs / 8 = 12.5 -> ceil 13, floor 12, nearest 13
    assert ev_to_sp(100, round_mode="ceil") == 13
    assert ev_to_sp(100, round_mode="floor") == 12
    assert ev_to_sp(100, round_mode="nearest") == 13


def test_clamping():
    assert ev_to_sp(-50) == 0
    assert ev_to_sp(9999) == SP_MAX_PER_STAT
    assert sp_to_ev(-1) == 0
    assert sp_to_ev(99) == EV_MAX_PER_STAT


# ---------- Spread conversion ----------

def test_max_invest_spread_converts_cleanly():
    evs = EVSpread(hp=252, defense=252, speed=4)
    sps = evs_to_sps_spread(evs)
    assert sps.hp == 32
    assert sps.defense == 32
    assert sps.speed == 1
    assert sps.is_valid()


def test_overfull_spread_trims_to_66():
    # All-252 EVs is impossible in mainline (508 cap) but model allows raw
    # construction; converter must clamp to the 66-SP champions budget.
    evs = EVSpread.model_construct(
        hp=252, attack=252, defense=252, special_attack=252, special_defense=252, speed=252,
    )
    sps = evs_to_sps_spread(evs)
    assert sps.total <= SP_MAX_TOTAL
    # Speed is preserved (highest priority in trim_order).
    assert sps.speed == 32
    # HP also preserved.
    assert sps.hp == 32


def test_sps_to_evs_roundtrip_at_saturation():
    sps = StatPointSpread(hp=32, attack=32, defense=2)
    evs = sps_to_evs_spread(sps)
    assert evs.hp == 252
    assert evs.attack == 252
    assert evs.defense == 16


# ---------- describe_conversion ----------

def test_describe_conversion_with_evs():
    evs = EVSpread(hp=252, special_attack=252, speed=4)
    out = describe_conversion(evs=evs)
    assert out["evs"]["hp"] == 252
    assert out["sps"]["hp"] == 32
    assert out["sps"]["sp"] == 1  # speed key in NCP shape


def test_describe_conversion_with_sps():
    sps = StatPointSpread(hp=32, attack=20, speed=14)
    out = describe_conversion(sps=sps)
    assert out["sps"]["hp"] == 32
    assert out["evs"]["hp"] == 252
    assert out["evs"]["spe"] == sp_to_ev(14)


# ---------- regulation_uses_champions ----------

def test_regulation_predicate():
    assert regulation_uses_champions("reg_ma_champs") is True
    assert regulation_uses_champions("champions") is True
    assert regulation_uses_champions("reg_f") is False
    assert regulation_uses_champions(None) is False


# ---------- build_dual_paste_payload ----------

def test_dual_paste_emits_both_formats():
    payload = build_dual_paste_payload(
        species="manectric-mega",
        nature="Timid",
        evs={"hp": 252, "def": 124, "spd": 132},
        format_system="champions",
    )

    assert "SPs:" in payload["champions_showdown_paste"]
    assert "EVs:" in payload["mainline_showdown_paste"]

    # Format-aware primary paste
    assert payload["showdown_paste"] == payload["champions_showdown_paste"]
    assert payload["spread_evs"]["hp"] == 252
    assert payload["spread_sps"]["hp"] == 32


def test_dual_paste_mainline_picks_evs_primary():
    payload = build_dual_paste_payload(
        species="incineroar",
        nature="Adamant",
        evs={"hp": 252, "atk": 252, "spd": 4},
        format_system="mainline",
    )
    assert payload["showdown_paste"] == payload["mainline_showdown_paste"]
    assert "EVs:" in payload["showdown_paste"]
