"""The shared calc response contract."""

from vgc_mcp_core.models.pokemon import (
    BaseStats,
    EVSpread,
    Nature,
    PokemonBuild,
    StatPointSpread,
)
from vgc_mcp_core.tools.response_contract import (
    HEADLINE_MAX,
    CalcResult,
    apply_contract,
    data_source_from_meta,
    spread_label,
)


def _build(**kw):
    return PokemonBuild(
        name=kw.pop("name", "urshifu-rapid-strike"),
        base_stats=BaseStats(hp=100, attack=130, defense=100, special_attack=63, special_defense=60, speed=97),
        types=["fighting", "water"],
        **kw,
    )


def test_mainline_spread_label():
    b = _build(nature=Nature.ADAMANT, evs=EVSpread(hp=4, attack=252, speed=252),
               item="choice-scarf", ability="unseen-fist")
    assert spread_label(b) == "Adamant 4/252/0/0/0/252 Urshifu-Rapid-Strike @ Choice Scarf (Unseen Fist)"


def test_champions_spread_label_uses_stat_points():
    b = _build(nature=Nature.JOLLY, format_system="champions",
               sps=StatPointSpread(hp=2, attack=32, speed=32))
    assert spread_label(b) == "Jolly 2/32/0/0/0/32 SP Urshifu-Rapid-Strike"


def test_data_source_from_meta_keeps_contract_fields_only():
    meta = {"format": "gen9championsvgc2026regmc", "month": "2026-09", "rating": 1630,
            "month_display": "September", "source_url": "https://example"}
    assert data_source_from_meta(meta) == {
        "format": "gen9championsvgc2026regmc", "month": "2026-09", "rating": 1630,
    }
    assert data_source_from_meta(None) is None
    assert data_source_from_meta({}) is None


def test_apply_contract_clips_headline_and_keeps_existing_fields():
    result = {"damage": [1, 2], "data_source": {"month": "2026-09"}, "showdown_paste": "X"}
    apply_contract(result, headline="word " * 60, spreads_used={"attacker": "a"})
    assert len(result["headline"]) <= HEADLINE_MAX
    assert result["data_source"] == {"month": "2026-09"}
    assert result["showdown_paste"] == "X"
    assert result["damage"] == [1, 2]


def test_apply_contract_always_sets_all_four_fields():
    result = apply_contract({}, headline="Yes, it OHKOs.")
    assert set(result) == {"headline", "data_source", "showdown_paste"}
    assert result["data_source"] is None and result["showdown_paste"] is None


def test_calc_result_schema_allows_payload_and_errors():
    ok = CalcResult.model_validate({"headline": "h", "spreads_used": {"a": "b"}, "extra": 1})
    assert ok.model_dump()["extra"] == 1
    err = CalcResult.model_validate({"success": False, "error": "pokemon_not_found", "message": "m"})
    assert err.model_dump()["error"] == "pokemon_not_found"
    schema = CalcResult.model_json_schema()
    assert {"headline", "spreads_used", "data_source", "showdown_paste"} <= set(schema["properties"])
