"""Smogon usage stats client with caching and retry logic."""

from datetime import datetime, timedelta
from typing import Optional

import httpx

from .cache import APICache
from ..config import settings, logger
from ..rules.regulation_loader import get_regulation_config, RegulationConfig


# Map form names to Smogon's naming convention
# Smogon uses the base form name for certain Pokemon
FORM_ALIASES = {
    # Forces of Nature - base form is Incarnate
    "landorus-incarnate": "landorus",
    "tornadus-incarnate": "tornadus",
    "thundurus-incarnate": "thundurus",
    "enamorus-incarnate": "enamorus",
    # Urshifu - base form is Single Strike
    "urshifu-single-strike": "urshifu",
    # Ogerpon - base form is Teal Mask
    "ogerpon-teal-mask": "ogerpon",
    "ogerpon-teal": "ogerpon",
    # Indeedee - base form is Male
    "indeedee-m": "indeedee",
    "indeedee-male": "indeedee",
    # Basculegion - base form is Male
    "basculegion-m": "basculegion",
    "basculegion-male": "basculegion",
    # Ursaluna - base form is regular (not Bloodmoon)
    "ursaluna-normal": "ursaluna",
}


class SmogonStatsError(Exception):
    """Error fetching Smogon stats."""
    pass


class SmogonStatsClient:
    """Client for Smogon usage stats (chaos JSON format)."""

    def __init__(
        self,
        cache: Optional[APICache] = None,
        regulation_config: Optional[RegulationConfig] = None
    ):
        """Initialize client with optional cache and regulation config."""
        self.cache = cache or APICache()
        self._regulation_config = regulation_config
        self._client: Optional[httpx.AsyncClient] = None
        self._current_format: Optional[str] = None
        self._current_month: Optional[str] = None
        # Session-level data freshness tracking
        self._session_first_month: Optional[str] = None
        self._data_upgraded: bool = False
        self._upgrade_notice: Optional[str] = None

    @property
    def regulation_config(self) -> RegulationConfig:
        """Get regulation config, using global singleton if not provided."""
        if self._regulation_config is None:
            self._regulation_config = get_regulation_config()
        return self._regulation_config

    @property
    def VGC_FORMATS(self) -> list[str]:
        """Get VGC formats dynamically from current regulation config."""
        return self.regulation_config.get_all_smogon_formats()

    @property
    def RATING_CUTOFFS(self) -> list[int]:
        """Get available Smogon rating cutoffs.

        Returns:
            List of available ratings: [0, 1500, 1630, 1760]
            - 0: All players (broadest data)
            - 1500: 1500+ ELO players
            - 1630: 1630+ ELO players
            - 1760: Top competitive players (default)
        """
        return settings.SMOGON_RATING_CUTOFFS

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.API_TIMEOUT_SECONDS),
                headers={"User-Agent": "VGC-MCP-Server/0.1.0"},
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._client

    def _get_recent_months(self, count: int = 4) -> list[str]:
        """Get list of recent months in YYYY-MM format.

        Smogon stats are typically released ~2 weeks after month end.
        So on Jan 1, December stats likely aren't available yet.
        We try current month -1, -2, -3, etc. to find latest available.
        """
        months = []
        now = datetime.now()
        # Start from previous month (current month stats won't exist yet)
        # and go back several months to ensure we find available data
        for i in range(1, count + 1):
            date = now - timedelta(days=30 * i)
            months.append(date.strftime("%Y-%m"))
        return months

    async def _try_fetch_stats(
        self,
        month: str,
        format_name: str,
        rating: int
    ) -> Optional[dict]:
        """Try to fetch stats for a specific month/format/rating combination."""
        cache_key = f"{month}/{format_name}/{rating}"
        cached = self.cache.get("smogon", cache_key)
        if cached is not None:
            return cached

        client = await self._get_client()
        url = f"{settings.SMOGON_STATS_BASE_URL}/{month}/chaos/{format_name}-{rating}.json"

        try:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                self.cache.set("smogon", cache_key, value=data)
                logger.debug(f"Fetched Smogon stats: {month}/{format_name}/{rating}")
                return data
            elif response.status_code == 404:
                logger.debug(f"Smogon stats not found: {month}/{format_name}/{rating}")
        except httpx.RequestError as e:
            logger.warning(f"Smogon request error for {url}: {e}")

        return None

    async def get_usage_stats(
        self,
        format_name: Optional[str] = None,
        rating: int = 1760,
        month: Optional[str] = None
    ) -> dict:
        """
        Fetch chaos.json usage stats with auto-detection.

        Args:
            format_name: e.g., "gen9vgc2025regg". If None, auto-detect latest.
            rating: Rating cutoff (0, 1500, 1630, 1760)
            month: Format "YYYY-MM", defaults to latest available

        Returns:
            Usage stats data with metadata about source
        """
        months = [month] if month else self._get_recent_months(3)
        formats = [format_name] if format_name else self.VGC_FORMATS

        # Try combinations until we find one that works
        for m in months:
            for fmt in formats:
                data = await self._try_fetch_stats(m, fmt, rating)
                if data:
                    self._current_format = fmt
                    self._current_month = m
                    self._check_for_data_upgrade(m)  # Track data freshness

                    # Format month for display (e.g., "2025-12" -> "December 2025")
                    try:
                        month_display = datetime.strptime(m, "%Y-%m").strftime("%B %Y")
                    except ValueError:
                        month_display = m

                    data["_meta"] = {
                        "format": fmt,
                        "month": m,
                        "month_display": f"{month_display} Usage Stats",
                        "rating": rating
                    }

                    # Add notice if data source upgraded mid-session
                    notice = self.check_data_freshness()
                    if notice:
                        data["_meta"]["notice"] = notice

                    return data

        raise SmogonStatsError(
            f"Could not find usage stats. Tried formats: {formats[:3]}, months: {months}"
        )

    async def get_pokemon_usage(
        self,
        pokemon_name: str,
        format_name: Optional[str] = None,
        rating: int = 1760
    ) -> Optional[dict]:
        """Get usage stats for a specific Pokemon."""
        stats = await self.get_usage_stats(format_name, rating)

        # Apply form aliases (e.g., "landorus-incarnate" -> "landorus")
        name_lower = pokemon_name.lower().replace(" ", "-")
        pokemon_name = FORM_ALIASES.get(name_lower, pokemon_name)

        # Normalize name for matching
        name_normalized = pokemon_name.lower().replace(" ", "").replace("-", "")

        data = stats.get("data", {})
        for mon_name, mon_data in data.items():
            if mon_name.lower().replace(" ", "").replace("-", "") == name_normalized:
                # Process raw data into percentages
                usage_raw = mon_data.get("usage", 0)

                # Process items
                items = mon_data.get("Items", {})
                item_total = sum(items.values()) or 1
                items_pct = {
                    k: round(v / item_total * 100, 1)
                    for k, v in sorted(items.items(), key=lambda x: -x[1])
                    if v / item_total > 0.01
                }

                # Process moves
                moves = mon_data.get("Moves", {})
                move_total = sum(moves.values()) or 1
                moves_pct = {
                    k: round(v / move_total * 100, 1)
                    for k, v in sorted(moves.items(), key=lambda x: -x[1])
                    if v / move_total > 0.01
                }

                # Process abilities
                abilities = mon_data.get("Abilities", {})
                ability_total = sum(abilities.values()) or 1
                abilities_pct = {
                    k: round(v / ability_total * 100, 1)
                    for k, v in sorted(abilities.items(), key=lambda x: -x[1])
                    if v / ability_total > 0.01
                }

                # Process spreads
                spreads = mon_data.get("Spreads", {})
                spread_total = sum(spreads.values()) or 1
                spreads_processed = []
                for spread_str, weight in sorted(spreads.items(), key=lambda x: -x[1]):
                    pct = weight / spread_total
                    if pct < 0.01:
                        continue
                    parsed = self._parse_spread(spread_str)
                    parsed["usage"] = round(pct * 100, 1)
                    spreads_processed.append(parsed)

                # Process teammates
                teammates = mon_data.get("Teammates", {})
                teammate_total = sum(teammates.values()) or 1
                teammates_pct = {
                    k: round(v / teammate_total * 100, 1)
                    for k, v in sorted(teammates.items(), key=lambda x: -x[1])[:15]
                    if v / teammate_total > 0.01
                }

                # Process Tera types
                tera_types = mon_data.get("Tera Types", {})
                tera_total = sum(tera_types.values()) or 1
                tera_pct = {
                    k: round(v / tera_total * 100, 1)
                    for k, v in sorted(tera_types.items(), key=lambda x: -x[1])
                    if v / tera_total > 0.01
                }

                return {
                    "name": mon_name,
                    "usage_percent": round(usage_raw * 100, 2),
                    "abilities": abilities_pct,
                    "items": items_pct,
                    "moves": moves_pct,
                    "spreads": spreads_processed[:10],
                    "teammates": teammates_pct,
                    "tera_types": tera_pct,
                    "_meta": stats.get("_meta", {})
                }

        return None

    def _parse_spread(self, spread_str: str) -> dict:
        """Parse spread string like 'Modest:252/0/4/252/0/0' into structured data."""
        try:
            nature, evs = spread_str.split(":")
            hp, atk, def_, spa, spd, spe = map(int, evs.split("/"))
            return {
                "nature": nature,
                "evs": {
                    "hp": hp,
                    "attack": atk,
                    "defense": def_,
                    "special_attack": spa,
                    "special_defense": spd,
                    "speed": spe
                },
                "spread_string": spread_str
            }
        except Exception:
            return {"raw": spread_str}

    async def get_common_sets(
        self,
        pokemon_name: str,
        format_name: Optional[str] = None,
        rating: int = 1760,
        limit: int = 5
    ) -> Optional[dict]:
        """Get the most common competitive sets for a Pokemon."""
        usage = await self.get_pokemon_usage(pokemon_name, format_name, rating)
        if not usage:
            return None

        # Get top items
        top_items = list(usage["items"].items())[:3]
        # Get top abilities
        top_abilities = list(usage["abilities"].items())[:2]
        # Get top moves
        top_moves = list(usage["moves"].items())[:8]
        # Get top spreads
        top_spreads = usage["spreads"][:limit]
        # Get top tera types
        top_tera = list(usage["tera_types"].items())[:3]

        return {
            "pokemon": usage["name"],
            "usage_percent": usage["usage_percent"],
            "top_items": [{"name": k, "usage": v} for k, v in top_items],
            "top_abilities": [{"name": k, "usage": v} for k, v in top_abilities],
            "top_moves": [{"name": k, "usage": v} for k, v in top_moves],
            "top_spreads": top_spreads,
            "top_tera_types": [{"type": k, "usage": v} for k, v in top_tera],
            "_meta": usage.get("_meta", {})
        }

    async def suggest_teammates(
        self,
        pokemon_name: str,
        format_name: Optional[str] = None,
        rating: int = 1760,
        limit: int = 10
    ) -> Optional[dict]:
        """Get suggested teammates based on usage data."""
        usage = await self.get_pokemon_usage(pokemon_name, format_name, rating)
        if not usage:
            return None

        teammates = list(usage["teammates"].items())[:limit]

        return {
            "pokemon": usage["name"],
            "suggested_teammates": [
                {"name": name, "usage_with": rate}
                for name, rate in teammates
            ],
            "_meta": usage.get("_meta", {})
        }

    @property
    def current_format(self) -> Optional[str]:
        """Get the last successfully used format."""
        return self._current_format

    @property
    def current_month(self) -> Optional[str]:
        """Get the last successfully used month."""
        return self._current_month

    def check_data_freshness(self) -> Optional[str]:
        """Check if newer data became available since session started.

        Returns:
            Notice message if newer data was found, None otherwise.
            Notice is cleared after being read (shown once per upgrade).
        """
        if self._data_upgraded and self._upgrade_notice:
            notice = self._upgrade_notice
            self._upgrade_notice = None  # Clear after reading (show once)
            return notice
        return None

    def _check_for_data_upgrade(self, new_month: str) -> None:
        """Check if we've upgraded to a newer month mid-session.

        Called each time stats are fetched. If the month is newer than
        the first month used in this session, sets a notification.
        """
        if self._session_first_month is None:
            self._session_first_month = new_month
        elif new_month > self._session_first_month and not self._data_upgraded:
            self._data_upgraded = True
            # Format: "2024-12" -> "December 2024"
            try:
                month_name = datetime.strptime(new_month, "%Y-%m").strftime("%B %Y")
                prev_name = datetime.strptime(
                    self._session_first_month, "%Y-%m"
                ).strftime("%B %Y")
                self._upgrade_notice = (
                    f"New data available! Now using {month_name} Smogon stats "
                    f"(previously {prev_name}). Spreads and usage rates are updated."
                )
            except ValueError:
                # Fallback if date parsing fails
                self._upgrade_notice = (
                    f"New data available! Now using {new_month} stats "
                    f"(previously {self._session_first_month})."
                )

    async def compare_pokemon_usage(
        self,
        pokemon_name: str,
        format_name: Optional[str] = None,
        rating: int = 1760
    ) -> Optional[dict]:
        """
        Compare a Pokemon's usage between current and previous month.

        Useful for identifying meta shifts - shows changes in:
        - Overall usage percentage
        - Popular spreads (speed tiers shifting)
        - Item preferences
        - Move preferences
        - Tera type preferences

        Args:
            pokemon_name: The Pokemon to analyze
            format_name: Specific format (auto-detects if None)
            rating: Rating cutoff (0, 1500, 1630, or 1760). Default 1760 for high-level play.

        Returns:
            Comparison data showing current vs previous month
        """
        months = self._get_recent_months(2)

        if len(months) < 2:
            return None

        current_month = months[0]
        previous_month = months[1]

        # Get current month stats
        current_stats = None
        previous_stats = None

        try:
            current_stats = await self.get_pokemon_usage(
                pokemon_name, format_name, rating
            )
        except SmogonStatsError:
            pass

        # Try to get previous month stats
        try:
            # Temporarily override to get previous month
            formats = [format_name] if format_name else self.VGC_FORMATS

            for fmt in formats:
                data = await self._try_fetch_stats(previous_month, fmt, rating)
                if data:
                    # Extract Pokemon data from previous month
                    name_normalized = pokemon_name.lower().replace(" ", "").replace("-", "")

                    for mon_name, mon_data in data.get("data", {}).items():
                        if mon_name.lower().replace(" ", "").replace("-", "") == name_normalized:
                            # Process previous month data
                            usage_raw = mon_data.get("usage", 0)

                            spreads = mon_data.get("Spreads", {})
                            spread_total = sum(spreads.values()) or 1
                            spreads_processed = []
                            for spread_str, weight in sorted(spreads.items(), key=lambda x: -x[1])[:5]:
                                pct = weight / spread_total
                                parsed = self._parse_spread(spread_str)
                                parsed["usage"] = round(pct * 100, 1)
                                spreads_processed.append(parsed)

                            items = mon_data.get("Items", {})
                            item_total = sum(items.values()) or 1
                            items_pct = {
                                k: round(v / item_total * 100, 1)
                                for k, v in sorted(items.items(), key=lambda x: -x[1])[:5]
                            }

                            previous_stats = {
                                "name": mon_name,
                                "usage_percent": round(usage_raw * 100, 2),
                                "spreads": spreads_processed,
                                "items": items_pct,
                                "month": previous_month,
                                "format": fmt
                            }
                            break
                    if previous_stats:
                        break
        except Exception:
            pass

        if not current_stats and not previous_stats:
            return None

        # Build comparison
        comparison = {
            "pokemon": pokemon_name,
            "current_month": current_month,
            "previous_month": previous_month,
            "current": current_stats,
            "previous": previous_stats,
            "changes": []
        }

        if current_stats and previous_stats:
            # Usage change
            usage_change = current_stats["usage_percent"] - previous_stats["usage_percent"]
            if abs(usage_change) >= 1:
                direction = "increased" if usage_change > 0 else "decreased"
                comparison["changes"].append(
                    f"Usage {direction} by {abs(usage_change):.1f}% "
                    f"({previous_stats['usage_percent']:.1f}% → {current_stats['usage_percent']:.1f}%)"
                )

            # Compare top spreads for speed tier shifts
            if current_stats.get("spreads") and previous_stats.get("spreads"):
                current_top_spread = current_stats["spreads"][0] if current_stats["spreads"] else None
                prev_top_spread = previous_stats["spreads"][0] if previous_stats["spreads"] else None

                if current_top_spread and prev_top_spread:
                    curr_spe = current_top_spread.get("evs", {}).get("speed", 0)
                    prev_spe = prev_top_spread.get("evs", {}).get("speed", 0)

                    if curr_spe != prev_spe:
                        if curr_spe > prev_spe:
                            comparison["changes"].append(
                                f"Speed investment increased: {prev_spe} EVs → {curr_spe} EVs (running faster)"
                            )
                        else:
                            comparison["changes"].append(
                                f"Speed investment decreased: {prev_spe} EVs → {curr_spe} EVs (running slower/bulkier)"
                            )

        return comparison

    async def get_speed_distribution(
        self,
        pokemon_name: str,
        base_speed: int,
        format_name: Optional[str] = None,
        rating: int = 1760
    ) -> Optional[dict]:
        """
        Get speed distribution from Smogon spreads.

        Parses all spreads for a Pokemon and calculates the final speed stat
        for each, then builds a usage-weighted distribution.

        Args:
            pokemon_name: Pokemon name to look up
            base_speed: Pokemon's base speed stat (from PokeAPI)
            format_name: Specific format (auto-detects if None)
            rating: Rating cutoff (default 1760)

        Returns:
            Distribution data or None if not found:
            {
                "pokemon": "Flutter Mane",
                "base_speed": 135,
                "distribution": [
                    {"speed": 205, "usage": 44.0},
                    {"speed": 187, "usage": 30.0},
                    ...
                ],
                "stats": {
                    "min": 135, "max": 205, "median": 187,
                    "mean": 183.5, "iqr_low": 157, "iqr_high": 205
                }
            }
        """
        from ..calc.stats import calculate_speed
        from ..models.pokemon import Nature

        # Nature name -> Nature enum mapping
        NATURE_MAP = {
            "adamant": Nature.ADAMANT, "bashful": Nature.BASHFUL, "bold": Nature.BOLD,
            "brave": Nature.BRAVE, "calm": Nature.CALM, "careful": Nature.CAREFUL,
            "docile": Nature.DOCILE, "gentle": Nature.GENTLE, "hardy": Nature.HARDY,
            "hasty": Nature.HASTY, "impish": Nature.IMPISH, "jolly": Nature.JOLLY,
            "lax": Nature.LAX, "lonely": Nature.LONELY, "mild": Nature.MILD,
            "modest": Nature.MODEST, "naive": Nature.NAIVE, "naughty": Nature.NAUGHTY,
            "quiet": Nature.QUIET, "quirky": Nature.QUIRKY, "rash": Nature.RASH,
            "relaxed": Nature.RELAXED, "sassy": Nature.SASSY, "serious": Nature.SERIOUS,
            "timid": Nature.TIMID,
        }

        usage = await self.get_pokemon_usage(pokemon_name, format_name, rating)
        if not usage or not usage.get("spreads"):
            return None

        # Calculate speed for each spread and aggregate by speed value
        speed_usage: dict[int, float] = {}
        for spread in usage["spreads"]:
            nature_str = spread.get("nature", "Serious").lower()
            evs = spread.get("evs", {})
            spread_usage = spread.get("usage", 0)

            nature = NATURE_MAP.get(nature_str, Nature.SERIOUS)
            speed_evs = evs.get("speed", 0)

            # Calculate final speed stat (level 50, 31 IVs)
            final_speed = calculate_speed(base_speed, 31, speed_evs, 50, nature)

            if final_speed in speed_usage:
                speed_usage[final_speed] += spread_usage
            else:
                speed_usage[final_speed] = spread_usage

        if not speed_usage:
            return None

        # Build distribution sorted by speed
        distribution = [
            {"speed": speed, "usage": round(usage_pct, 1)}
            for speed, usage_pct in sorted(speed_usage.items())
        ]

        # Calculate statistics
        speeds = list(speed_usage.keys())
        usages = list(speed_usage.values())
        total_usage = sum(usages)

        # Weighted mean
        weighted_sum = sum(s * u for s, u in zip(speeds, usages))
        mean_speed = weighted_sum / total_usage if total_usage > 0 else speeds[0]

        # Median (by usage weight)
        cumulative = 0
        median_speed = speeds[0]
        for s, u in sorted(zip(speeds, usages)):
            cumulative += u
            if cumulative >= total_usage / 2:
                median_speed = s
                break

        # IQR (25th and 75th percentile by usage)
        cumulative = 0
        iqr_low = speeds[0]
        iqr_high = speeds[-1]
        for s, u in sorted(zip(speeds, usages)):
            cumulative += u
            if cumulative >= total_usage * 0.25 and iqr_low == speeds[0]:
                iqr_low = s
            if cumulative >= total_usage * 0.75:
                iqr_high = s
                break

        return {
            "pokemon": usage["name"],
            "base_speed": base_speed,
            "distribution": distribution,
            "stats": {
                "min": min(speeds),
                "max": max(speeds),
                "median": median_speed,
                "mean": round(mean_speed, 1),
                "iqr_low": iqr_low,
                "iqr_high": iqr_high,
            },
            "_meta": usage.get("_meta", {})
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "SmogonStatsClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
