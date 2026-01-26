"""Starter prompts for user onboarding and UI integration."""

STARTER_PROMPTS = [
    {
        "title": "Build a Team",
        "prompt": "Help me build a competitive VGC team",
        "category": "team",
        "description": "Get step-by-step team building guidance"
    },
    {
        "title": "Check Damage",
        "prompt": "Does Flutter Mane OHKO Incineroar?",
        "category": "damage",
        "description": "Calculate damage between Pokemon"
    },
    {
        "title": "Optimize EVs",
        "prompt": "What EVs does Amoonguss need to survive Flutter Mane?",
        "category": "evs",
        "description": "Find optimal EV spreads"
    },
    {
        "title": "Analyze Team",
        "prompt": "Analyze my team (I'll paste it)",
        "category": "team",
        "description": "Check team weaknesses and matchups"
    },
    {
        "title": "Learn VGC",
        "prompt": "I'm new to VGC. What should I know?",
        "category": "learn",
        "description": "Learn competitive Pokemon basics"
    },
    {
        "title": "What Can You Do?",
        "prompt": "Show me what you can help with",
        "category": "discover",
        "description": "See all available capabilities"
    },
    {
        "title": "Compare Speed",
        "prompt": "Is Landorus faster than Tornadus?",
        "category": "speed",
        "description": "Compare Pokemon speeds"
    },
    {
        "title": "Explain Term",
        "prompt": "Explain what EVs are",
        "category": "learn",
        "description": "Learn VGC terminology"
    },
    {
        "title": "Nature Optimization",
        "prompt": "Can I save EVs with a different nature?",
        "category": "evs",
        "description": "Find nature changes that save EVs"
    },
    {
        "title": "Tera Type Help",
        "prompt": "What's the best Tera type for Flutter Mane?",
        "category": "team",
        "description": "Optimize Tera type selection"
    }
]

# Grouped by category for easier access
PROMPTS_BY_CATEGORY = {
    "damage": [p for p in STARTER_PROMPTS if p["category"] == "damage"],
    "team": [p for p in STARTER_PROMPTS if p["category"] == "team"],
    "evs": [p for p in STARTER_PROMPTS if p["category"] == "evs"],
    "speed": [p for p in STARTER_PROMPTS if p["category"] == "speed"],
    "learn": [p for p in STARTER_PROMPTS if p["category"] == "learn"],
    "discover": [p for p in STARTER_PROMPTS if p["category"] == "discover"]
}
