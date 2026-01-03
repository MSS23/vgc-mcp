"""Pattern-based reason generation for team changes.

Generates human-readable explanations for why a change might have been made,
based on the nature of the change itself (not meta knowledge).
"""

from typing import Optional
from ..models.pokemon import Nature, NATURE_MODIFIERS


# Stat display names
STAT_DISPLAY = {
    "hp": "HP",
    "atk": "Atk",
    "attack": "Atk",
    "def": "Def",
    "defense": "Def",
    "spa": "SpA",
    "special_attack": "SpA",
    "spd": "SpD",
    "special_defense": "SpD",
    "spe": "Spe",
    "speed": "Spe",
}

# Item categories for contextual explanations
ITEM_CATEGORIES = {
    "offensive": [
        "choice-band", "choice-specs", "life-orb", "expert-belt",
        "muscle-band", "wise-glasses", "charcoal", "mystic-water",
        "miracle-seed", "never-melt-ice", "black-glasses", "dragon-fang",
        "punching-glove", "loaded-dice",
    ],
    "defensive": [
        "assault-vest", "leftovers", "sitrus-berry", "rocky-helmet",
        "safety-goggles", "covert-cloak", "clear-amulet", "shed-shell",
        "eviolite", "weakness-policy", "aguav-berry", "figy-berry",
        "iapapa-berry", "mago-berry", "wiki-berry",
    ],
    "speed": [
        "choice-scarf", "booster-energy", "quick-claw",
    ],
    "focus": [
        "focus-sash",
    ],
    "utility": [
        "eject-button", "red-card", "eject-pack", "mental-herb",
        "lum-berry", "chesto-berry", "light-clay", "terrain-extender",
        "grip-claw", "binding-band",
    ],
    "resist-berry": [
        "occa-berry", "passho-berry", "wacan-berry", "rindo-berry",
        "yache-berry", "chople-berry", "kebia-berry", "shuca-berry",
        "coba-berry", "payapa-berry", "tanga-berry", "charti-berry",
        "kasib-berry", "haban-berry", "colbur-berry", "babiri-berry",
        "roseli-berry", "chilan-berry",
    ],
}


def _get_item_category(item: Optional[str]) -> str:
    """Get the category of an item."""
    if not item:
        return "none"
    item_norm = item.lower().replace(" ", "-")
    for category, items in ITEM_CATEGORIES.items():
        if item_norm in items:
            return category
    return "other"


def _get_nature_stats(nature_name: str) -> tuple[Optional[str], Optional[str]]:
    """Get the boosted and lowered stats for a nature.

    Returns: (boosted_stat, lowered_stat) - None if neutral
    """
    try:
        nature = Nature(nature_name.lower())
        mods = NATURE_MODIFIERS.get(nature, {})

        boosted = None
        lowered = None
        for stat, mod in mods.items():
            if mod > 1:
                boosted = stat
            elif mod < 1:
                lowered = stat
        return boosted, lowered
    except (ValueError, KeyError):
        return None, None


def explain_nature_change(before: str, after: str) -> str:
    """Generate explanation for nature change.

    Examples:
        "Adamant -> Jolly" => "+Spe, -Atk (trades power for speed)"
        "Modest -> Timid" => "+Spe, -SpA (prioritizes speed over SpA)"
    """
    before_boost, before_lower = _get_nature_stats(before)
    after_boost, after_lower = _get_nature_stats(after)

    # Both neutral
    if before_boost is None and after_boost is None:
        return "Neutral nature swap"

    # From neutral to boosting
    if before_boost is None and after_boost:
        stat = STAT_DISPLAY.get(after_boost, after_boost)
        return f"Now boosts {stat}"

    # From boosting to neutral
    if before_boost and after_boost is None:
        return "Switched to neutral nature"

    # Both boosting - check what changed
    if before_boost and after_boost:
        if before_boost == after_boost:
            # Same boost, different penalty
            before_pen = STAT_DISPLAY.get(before_lower, before_lower) if before_lower else "?"
            after_pen = STAT_DISPLAY.get(after_lower, after_lower) if after_lower else "?"
            return f"Same +{STAT_DISPLAY.get(before_boost, before_boost)}, now -{after_pen} instead of -{before_pen}"
        else:
            # Different boost
            before_stat = STAT_DISPLAY.get(before_boost, before_boost)
            after_stat = STAT_DISPLAY.get(after_boost, after_boost)

            # Common patterns
            if after_boost in ("speed", "spe") and before_boost in ("attack", "atk", "special_attack", "spa"):
                return f"+{after_stat}, -{STAT_DISPLAY.get(after_lower, '?')} (prioritizes speed)"
            elif before_boost in ("speed", "spe") and after_boost in ("attack", "atk", "special_attack", "spa"):
                return f"+{after_stat}, -{STAT_DISPLAY.get(after_lower, '?')} (trades speed for power)"
            else:
                return f"+{after_stat} instead of +{before_stat}"

    return "Nature changed"


def explain_ev_change(stat_changes: list[dict]) -> str:
    """Generate explanation for EV reallocation.

    Args:
        stat_changes: List of {"stat": str, "before": int, "after": int, "delta": int}

    Examples:
        [+252 HP, -252 Spe] => "Moved 252 EVs from Spe to HP (bulk over speed)"
        [+132 Def, +68 SpD, -200 Atk] => "Reduced Atk for mixed bulk"
    """
    gains = [c for c in stat_changes if c.get("delta", c.get("after", 0) - c.get("before", 0)) > 0]
    losses = [c for c in stat_changes if c.get("delta", c.get("after", 0) - c.get("before", 0)) < 0]

    if not gains and not losses:
        return "Minor EV adjustment"

    # Get display names
    def get_stat_name(stat: str) -> str:
        return STAT_DISPLAY.get(stat.lower(), stat)

    def get_delta(c: dict) -> int:
        return c.get("delta", c.get("after", 0) - c.get("before", 0))

    # Simple 1:1 swap
    if len(gains) == 1 and len(losses) == 1:
        gain = gains[0]
        loss = losses[0]
        gain_stat = get_stat_name(gain["stat"])
        loss_stat = get_stat_name(loss["stat"])
        amount = abs(get_delta(loss))

        # Pattern detection
        if loss["stat"] in ("spe", "speed") and gain["stat"] in ("hp", "def", "spd", "defense", "special_defense"):
            return f"Moved {amount} EVs from {loss_stat} to {gain_stat} (bulk over speed)"
        elif loss["stat"] in ("atk", "attack", "spa", "special_attack") and gain["stat"] in ("hp", "def", "spd", "defense", "special_defense"):
            return f"Moved {amount} EVs from {loss_stat} to {gain_stat} (bulk over offense)"
        elif gain["stat"] in ("spe", "speed"):
            return f"Moved {amount} EVs from {loss_stat} to {gain_stat} (more speed)"
        else:
            return f"Moved {amount} EVs from {loss_stat} to {gain_stat}"

    # Multiple changes
    gain_stats = [get_stat_name(g["stat"]) for g in gains]
    loss_stats = [get_stat_name(l["stat"]) for l in losses]

    # Categorize
    bulk_stats = {"HP", "Def", "SpD"}
    offense_stats = {"Atk", "SpA"}

    gained_bulk = bool(set(gain_stats) & bulk_stats)
    lost_offense = bool(set(loss_stats) & offense_stats)
    lost_speed = "Spe" in loss_stats

    if gained_bulk and lost_offense:
        return f"Reallocated EVs for more bulk (-{'/'.join(loss_stats)})"
    elif gained_bulk and lost_speed:
        return f"Traded speed for bulk (+{'/'.join(gain_stats)})"
    elif "Spe" in gain_stats:
        return f"Invested more in Speed (-{'/'.join(loss_stats)})"
    else:
        return f"Reallocated EVs: +{'/'.join(gain_stats)}, -{'/'.join(loss_stats)}"


def explain_item_change(before: Optional[str], after: Optional[str]) -> str:
    """Generate explanation for item change.

    Examples:
        "Choice Scarf -> Assault Vest" => "Trades speed control for special bulk"
        "Life Orb -> Choice Band" => "Locks move for extra power (no recoil)"
    """
    before_cat = _get_item_category(before)
    after_cat = _get_item_category(after)

    # Same category
    if before_cat == after_cat and before_cat != "none" and before_cat != "other":
        return f"Item swap within {before_cat} category"

    # Category transitions
    transitions = {
        ("speed", "defensive"): "Trades speed control for bulk",
        ("speed", "offensive"): "Trades speed control for raw power",
        ("offensive", "defensive"): "Trades damage output for survivability",
        ("offensive", "speed"): "Trades raw power for speed control",
        ("defensive", "offensive"): "Trades bulk for damage output",
        ("defensive", "speed"): "Trades bulk for speed control",
        ("focus", "offensive"): "Trades OHKO protection for damage",
        ("focus", "defensive"): "Trades OHKO protection for sustained bulk",
        ("focus", "speed"): "Trades OHKO protection for speed",
        ("offensive", "focus"): "Trades damage for OHKO protection",
        ("defensive", "focus"): "Trades bulk for OHKO protection",
        ("none", "offensive"): f"Added offensive item ({after})",
        ("none", "defensive"): f"Added defensive item ({after})",
        ("none", "speed"): f"Added speed item ({after})",
        ("none", "focus"): f"Added Focus Sash",
        ("resist-berry", "defensive"): "Switched from type resist to general bulk",
        ("defensive", "resist-berry"): "Added specific type resistance",
    }

    reason = transitions.get((before_cat, after_cat))
    if reason:
        return reason

    # Fallback
    if before and after:
        return f"Changed from {before} to {after}"
    elif after:
        return f"Added {after}"
    elif before:
        return f"Removed {before}"

    return "Item changed"


def explain_move_change(added: list[str], removed: list[str]) -> str:
    """Generate explanation for moveset changes.

    Args:
        added: List of moves added
        removed: List of moves removed

    Examples:
        ["Protect"], ["Taunt"] => "Replaced Protect with Taunt"
        ["Shadow Ball", "Psychic"], ["Psyshock"] => "Added Shadow Ball, Psychic; removed Psyshock"
    """
    # Simple 1:1 swap
    if len(added) == 1 and len(removed) == 1:
        return f"Replaced {removed[0]} with {added[0]}"

    # Only additions
    if added and not removed:
        if len(added) == 1:
            return f"Added {added[0]}"
        return f"Added: {', '.join(added)}"

    # Only removals
    if removed and not added:
        if len(removed) == 1:
            return f"Removed {removed[0]}"
        return f"Removed: {', '.join(removed)}"

    # Multiple changes
    parts = []
    if added:
        parts.append(f"+{', '.join(added)}")
    if removed:
        parts.append(f"-{', '.join(removed)}")

    return "; ".join(parts)


def explain_ability_change(before: Optional[str], after: Optional[str]) -> str:
    """Generate explanation for ability change."""
    if before and after:
        return f"Changed from {before} to {after}"
    elif after:
        return f"Set ability to {after}"
    elif before:
        return f"Removed {before}"
    return "Ability changed"


def explain_tera_change(before: Optional[str], after: Optional[str]) -> str:
    """Generate explanation for tera type change."""
    if before and after:
        return f"Changed Tera from {before} to {after}"
    elif after:
        return f"Set Tera type to {after}"
    elif before:
        return f"Removed Tera type"
    return "Tera type changed"
