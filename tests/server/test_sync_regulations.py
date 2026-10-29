"""Tests for scripts/sync_regulations.py (offline; Smogon fetches are faked)."""

import json
from datetime import date

from scripts import sync_regulations as sync

LISTING = """
<a href="gen9championsvgc2026regmb-0.json">x</a>
<a href="gen9championsvgc2026regmb-1630.json">x</a>
<a href="gen9championsvgc2026regmc-0.json">x</a>
<a href="gen9championsvgc2026regmcbo3-0.json">x</a>
<a href="gen9championsvgc2026regmd-0.json">x</a>
<a href="gen9championsvgc2026regmdbo3-0.json">x</a>
<a href="gen9vgc2026regj-0.json">x</a>
<a href="gen9vgc2026regjbo3-0.json">x</a>
<a href="gen9vgc2024regg-0.json">x</a>
<a href="gen9ou-0.json">x</a>
"""


def test_discover_skips_known_bo3_legacy_years_and_non_vgc():
    months = ["2026-10", "2026-11"]
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return LISTING

    known = {"gen9championsvgc2026regmb", "gen9championsvgc2026regmc"}
    found = sync.discover(known, months, fake_fetch)
    assert found == {"gen9championsvgc2026regmd": "2026-10", "gen9vgc2026regj": "2026-10"}
    assert calls == [f"{sync.STATS_URL}2026-10/chaos/", f"{sync.STATS_URL}2026-11/chaos/"]


def test_latest_months_sorted_tail():
    html = '<a href="2026-07/">x</a><a href="2026-09/">x</a><a href="2026-08/">x</a>'
    assert sync.latest_months(html, 2) == ["2026-08", "2026-09"]


def test_merge_roster_adds_base_forms_once():
    species = {"rotom-wash", "mr-mime", "indeedee", "indeedee-f", "absol-mega-z", "newmon-mega"}
    roster, added = sync.merge_roster(["absol", "rotom"], species)
    assert added == ["mr-mime", "indeedee", "newmon-mega"]
    assert roster == ["absol", "rotom", "mr-mime", "indeedee", "newmon-mega"]


def test_apply_adds_provisional_champions_and_mainline_entries():
    text = sync.REG_PATH.read_text(encoding="utf-8")
    before = json.loads(text)
    assert before["current_regulation"] == "reg_mc_champs"

    def species_for(month, fmt):
        return {"Rillaboom", "Mr. Mime", "Brandnewmon", "Brandnewmon-Mega"} | {
            sync.normalize(n) for n in before["regulations"]["reg_mc_champs"]["legal_pokemon"][:10]
        }

    new_text, summary = sync.apply(
        text,
        {"gen9championsvgc2026regmd": "2026-11", "gen9vgc2026regj": "2026-11"},
        species_for,
        today=date(2026, 11, 20),
    )
    after = json.loads(new_text)
    regs = after["regulations"]

    md = regs["reg_md_champs"]
    assert md["provisional"] is True
    assert md["smogon_formats"] == ["gen9championsvgc2026regmd"]
    assert md["start_date"] == "2026-11-01"
    assert md["format_system"] == "champions"
    assert md["sp_total_max"] == 66 and md["legality_mode"] == "allowlist"
    mc_roster = before["regulations"]["reg_mc_champs"]["legal_pokemon"]
    assert md["legal_pokemon"][: len(mc_roster)] == mc_roster
    assert md["legal_pokemon"][len(mc_roster):] == ["brandnewmon"]
    assert regs["reg_mc_champs"]["end_date"] == "2026-10-31"
    assert after["current_regulation"] == "reg_md_champs"

    rj = regs["reg_j"]
    assert rj["provisional"] is True
    assert rj.get("format_system", "mainline") == "mainline"
    assert rj["banned_pokemon"] == before["regulations"]["reg_i"]["banned_pokemon"]
    assert rj["restricted_pokemon"] == before["regulations"]["reg_i"]["restricted_pokemon"]
    assert regs["reg_i"]["end_date"] == "2026-10-31"

    # Every pre-existing regulation is untouched apart from the closed end_date.
    for code, reg in before["regulations"].items():
        expected = dict(reg)
        if code in ("reg_mc_champs", "reg_i"):
            expected["end_date"] = "2026-10-31"
        assert regs[code] == expected, code

    assert any("reg_md_champs" in line and "brandnewmon" in line for line in summary)
    assert any("`current_regulation`" in line for line in summary)


def test_apply_is_idempotent_for_existing_code():
    text = sync.REG_PATH.read_text(encoding="utf-8")
    new_text, summary = sync.apply(text, {"gen9championsvgc2026regmc": "2026-09"}, lambda m, f: set())
    assert json.loads(new_text) == json.loads(text)
    assert summary == ["- `gen9championsvgc2026regmc`: regulation `reg_mc_champs` already exists, skipped"]
