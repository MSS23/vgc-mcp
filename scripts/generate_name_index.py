"""Refresh canonical move/item/ability names from PokeAPI's public name lists."""

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx


def main() -> None:
    snapshot: dict = {"fetched_at": datetime.now(timezone.utc).isoformat(), "sources": {}}
    with httpx.Client(timeout=45, follow_redirects=True) as client:
        for kind in ("move", "ability", "item"):
            url = f"https://pokeapi.co/api/v2/{kind}?limit=10000"
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
            if payload.get("next") or len(payload["results"]) != payload["count"]:
                raise ValueError(f"Incomplete {kind} name index")
            snapshot[kind] = sorted(entry["name"] for entry in payload["results"])
            snapshot["sources"][kind] = url
    path = Path(__file__).resolve().parents[1] / "src/vgc_mcp_core/data/canonical_names.json"
    path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path.name}: " + ", ".join(f"{len(snapshot[k])} {k}s" for k in ("move", "ability", "item")))


if __name__ == "__main__":
    main()
