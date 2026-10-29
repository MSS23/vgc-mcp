"""Discover new Smogon VGC / Champions formats and add provisional regulations.

Smogon publishes one chaos file per format per month at
``https://www.smogon.com/stats/YYYY-MM/chaos/<format>-<rating>.json``. A new
regulation shows up there as a format name (``gen9championsvgc2026regmc``,
``gen9vgc2026regj``) that ``regulations.json`` does not know yet. This script
lists the most recent months, finds such formats, and appends a *provisional*
regulation entry for each one:

- rules (caps, clauses, level, rating) are cloned from the newest regulation of
  the same family (Champions or mainline);
- a Champions roster is the previous roster plus every species seen in the new
  format's chaos data (zero-usage species are therefore missed — the entry is
  flagged ``"provisional": true`` and its description says so);
- a mainline reg keeps the previous ban/restricted lists, which usage data
  cannot reveal — review them by hand;
- the previous reg's ``end_date`` is closed and ``current_regulation`` moves to
  the new reg when it is in the same family as the current default.

The router picks the newest Champions reg by ``start_date`` and resolves
``Reg MX`` / ``MX`` phrasings by pattern, so a JSON-only change is enough for
the server to start serving the new format.

Stdlib only. Run weekly by ``.github/workflows/sync-regulations.yml``; the
workflow opens a pull request when this script changes the file.

Usage::

    python scripts/sync_regulations.py [--dry-run] [--months 2] [--summary FILE]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
REG_PATH = ROOT / "src" / "vgc_mcp_core" / "data" / "regulations.json"
STATS_URL = "https://www.smogon.com/stats/"

# gen9championsvgc2026regmc / gen9vgc2026regj — bo3 variants are excluded on
# purpose: they are the same regulation and regulations.json lists the bo1 file.
FORMAT_RE = re.compile(r"^gen\d+(?P<family>championsvgc|vgc)(?P<year>\d{4})reg(?P<letters>[a-z]{1,2})$")

Fetch = Callable[[str], str]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "vgc-mcp sync_regulations"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 — fixed https host
        return resp.read().decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #

def latest_months(index_html: str, count: int) -> list[str]:
    """Most recent ``YYYY-MM`` directories on the stats index, oldest first."""
    return sorted(set(re.findall(r"(\d{4}-\d{2})/", index_html)))[-count:]


def chaos_formats(listing_html: str) -> set[str]:
    """Format names on a ``chaos/`` listing (every format has a rating-0 file)."""
    return set(re.findall(r"([a-z0-9]+)-0\.json", listing_html))


def discover(known: set[str], months: list[str], fetch: Fetch = fetch) -> dict[str, str]:
    """Return ``{format: first month it was seen}`` for unknown VGC formats.

    Formats from a season year older than the newest known one are ignored:
    Smogon keeps legacy ladders (``gen9vgc2024regg``) listed for years.
    """
    min_year = max((int(m.group("year")) for m in map(FORMAT_RE.match, known) if m), default=0)
    found: dict[str, str] = {}
    for month in months:
        for fmt in sorted(chaos_formats(fetch(f"{STATS_URL}{month}/chaos/"))):
            m = FORMAT_RE.match(fmt)
            if m and int(m.group("year")) >= min_year and fmt not in known and fmt not in found:
                found[fmt] = month
    return found


def chaos_species(chaos_json: str) -> set[str]:
    """Normalised species names present in a chaos file."""
    return {normalize(name) for name in json.loads(chaos_json)["data"]}


def normalize(name: str) -> str:
    """'Mr. Mime' -> 'mr-mime', "Farfetch'd" -> 'farfetchd', 'Rotom-Wash' -> 'rotom-wash'."""
    return re.sub(r"[^a-z0-9-]", "", name.lower().replace(". ", "-").replace(" ", "-"))


# --------------------------------------------------------------------------- #
# Entry construction
# --------------------------------------------------------------------------- #

def code_for(fmt: str) -> tuple[str, str, str]:
    """``(code, family, letters)`` for a Smogon format name."""
    m = FORMAT_RE.match(fmt)
    if not m:
        raise ValueError(f"not a VGC regulation format: {fmt!r}")
    letters = m.group("letters")
    if m.group("family") == "championsvgc":
        return f"reg_{letters}_champs", "champions", letters
    return f"reg_{letters}", "mainline", letters


def family_of(reg: dict) -> str:
    return reg.get("format_system", "mainline")


def newest_code(regs: dict, family: str) -> str | None:
    """Newest regulation of ``family`` by start_date (code as tie-break)."""
    codes = [c for c, r in regs.items() if family_of(r) == family]
    if not codes:
        return None
    return max(codes, key=lambda c: (regs[c].get("start_date") or "", c))


def _covered(name: str, roster: set[str]) -> bool:
    # Mirrors RegulationConfig.is_pokemon_legal: exact match or base species
    # (first hyphen segment) — "rotom-wash" -> "rotom", "absol-mega-z" -> "absol".
    return name in roster or name.split("-")[0] in roster


def merge_roster(previous: list[str], species: set[str]) -> tuple[list[str], list[str]]:
    """Previous roster plus unseen species, shortest names first so a base form
    lands before its own alternate forms. Returns ``(roster, added)``."""
    roster = list(previous)
    have = set(previous)
    added: list[str] = []
    for name in sorted({normalize(s) for s in species}, key=lambda s: (len(s), s)):
        if not _covered(name, have):
            roster.append(name)
            have.add(name)
            added.append(name)
    return roster, added


def build_entry(
    regs: dict, fmt: str, month: str, species: set[str] | None, today: date
) -> tuple[str, dict, str, list[str]]:
    """Return ``(code, entry, previous_code, added_species)`` for a new format."""
    code, family, letters = code_for(fmt)
    prev_code = newest_code(regs, family)
    if prev_code is None:
        raise ValueError(f"no existing {family} regulation to clone for {fmt}")
    prev = regs[prev_code]
    entry = {k: v for k, v in prev.items() if k != "legal_pokemon"}
    added: list[str] = []
    label = f"Champions Regulation {letters.upper()}" if family == "champions" else f"Regulation {letters.upper()}"
    if family == "champions":
        entry["legal_pokemon"], added = merge_roster(prev["legal_pokemon"], species or set())
        roster_note = (
            f"roster = {prev_code} roster plus {len(added)} species seen in that month's "
            "chaos data (species with zero usage are missing)"
        )
    else:
        roster_note = f"ban/restricted lists copied unchanged from {prev_code} (usage data cannot reveal them)"
    entry["name"] = f"{label} (provisional)"
    entry["description"] = (
        f"PROVISIONAL - auto-generated by scripts/sync_regulations.py on {today.isoformat()} "
        f"after Smogon listed format {fmt} (first seen {month}). Rules cloned from {prev_code}; "
        f"{roster_note}. Replace with the official list, fix the dates, and remove "
        f"'provisional' once verified."
    )
    entry["smogon_formats"] = [fmt]
    entry["start_date"] = f"{month}-01"
    entry["provisional"] = True
    return code, entry, prev_code, added


# --------------------------------------------------------------------------- #
# Text-level application (keeps the hand-formatted file diff-friendly)
# --------------------------------------------------------------------------- #

def _render_entry(code: str, entry: dict) -> str:
    lines = [f'    "{code}": {{']
    items = list(entry.items())
    for i, (key, value) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        if key == "legal_pokemon":
            rows = [
                "        " + ", ".join(json.dumps(n) for n in value[j : j + 6])
                for j in range(0, len(value), 6)
            ]
            lines.append(f'      "{key}": [\n' + ",\n".join(rows) + f"\n      ]{comma}")
        else:
            lines.append(f'      "{key}": {json.dumps(value)}{comma}')
    lines.append("    }")
    return "\n".join(lines)


def _set_field_in_entry(text: str, code: str, field: str, value: str) -> str:
    start = text.index(f'"{code}": {{')
    pattern = re.compile(rf'("{field}":\s*)"[^"]*"')
    m = pattern.search(text, start)
    if not m:
        raise ValueError(f"{code} has no {field} field")
    return text[: m.start()] + f'{m.group(1)}"{value}"' + text[m.end() :]


def apply(text: str, new_formats: dict[str, str], species_for: Callable[[str, str], set[str]],
          today: date | None = None) -> tuple[str, list[str]]:
    """Return ``(new_text, summary_lines)`` with one provisional entry per format."""
    today = today or date.today()
    data = json.loads(text)
    regs = data["regulations"]
    current = data["current_regulation"]
    summary: list[str] = []
    for fmt, month in sorted(new_formats.items(), key=lambda kv: kv[1]):
        code, family, _ = code_for(fmt)
        if code in regs:
            summary.append(f"- `{fmt}`: regulation `{code}` already exists, skipped")
            continue
        species = species_for(month, fmt) if family == "champions" else None
        code, entry, prev_code, added = build_entry(regs, fmt, month, species, today)
        prev_end = (datetime.strptime(entry["start_date"], "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
        text = _set_field_in_entry(text, prev_code, "end_date", prev_end)
        closing = text.rstrip().rfind("\n  }\n}")
        text = text[:closing] + ",\n" + _render_entry(code, entry) + text[closing:]
        regs[code] = entry  # so a second new format of the same family clones this one
        regs[prev_code]["end_date"] = prev_end
        summary.append(
            f"- `{fmt}` (first seen {month}) -> new provisional `{code}` cloned from `{prev_code}`; "
            f"`{prev_code}` now ends {prev_end}"
            + (f"; roster +{len(added)}: {', '.join(added)}" if added else "")
        )
        if family_of(regs[current]) == family:
            text = text.replace(f'"current_regulation": "{current}"', f'"current_regulation": "{code}"', 1)
            summary.append(f"- `current_regulation`: `{current}` -> `{code}`")
            current = code
    json.loads(text)  # must still parse
    return text, summary


# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--months", type=int, default=2, help="how many recent stats months to scan")
    ap.add_argument("--dry-run", action="store_true", help="report only; do not write regulations.json")
    ap.add_argument("--summary", type=Path, help="write a Markdown summary here (used as the PR body)")
    args = ap.parse_args(argv)

    text = REG_PATH.read_text(encoding="utf-8")
    regs = json.loads(text)["regulations"]
    known = {f for reg in regs.values() for f in reg.get("smogon_formats", [])}
    months = latest_months(fetch(STATS_URL), args.months)
    new_formats = {f: m for f, m in discover(known, months, fetch).items() if code_for(f)[0] not in regs}

    if not new_formats:
        summary = [f"No new VGC formats on Smogon for {', '.join(months)}."]
    else:
        def species_for(month: str, fmt: str) -> set[str]:
            return chaos_species(fetch(f"{STATS_URL}{month}/chaos/{fmt}-0.json"))

        text, summary = apply(text, new_formats, species_for)
        summary.insert(0, f"Scanned Smogon stats for {', '.join(months)}.")
        summary.append(
            "\nThe new entry is provisional: verify the roster against the official "
            "regulation announcement, fix the start date, then remove `\"provisional\": true`."
        )
        if not args.dry_run:
            REG_PATH.write_text(text, encoding="utf-8")

    report = "\n".join(summary)
    print(report)
    if args.summary:
        args.summary.write_text(report + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
