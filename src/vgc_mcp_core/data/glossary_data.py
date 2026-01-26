"""VGC glossary data for beginner education."""

VGC_GLOSSARY = {
    "evs": {
        "term": "EVs (Effort Values)",
        "simple_explanation": "EVs are bonus stat points you can give to your Pokemon. You have 508 total points to distribute, with a maximum of 252 per stat.",
        "why_it_matters": "4 EVs = +1 stat point at level 50. 252 EVs in Speed can mean outspeeding a threat. Proper EV investment is the difference between surviving a hit or not.",
        "common_patterns": [
            {"pattern": "252/252/4", "name": "Max Offensive", "use_case": "Fast sweepers like Flutter Mane"},
            {"pattern": "252 HP / 252 Def or SpD", "name": "Max Bulk", "use_case": "Defensive Pokemon like Amoonguss"},
            {"pattern": "Custom spreads", "name": "Benchmark", "use_case": "Survive specific attacks + outspeed threats"}
        ],
        "example": '"252 SpA Flutter Mane" means Flutter Mane with 252 EVs invested in Special Attack.',
        "related_terms": ["IVs", "Nature", "Base Stats"]
    },
    "ivs": {
        "term": "IVs (Individual Values)",
        "simple_explanation": "IVs are hidden stat values (0-31) that Pokemon are born with. At level 50, each IV point adds 1 to that stat.",
        "why_it_matters": "Most competitive Pokemon use 31 IVs in all stats (called 'perfect IVs'). Lower IVs are only used for specific strategies like Trick Room.",
        "common_patterns": [
            {"pattern": "31/31/31/31/31/31", "name": "Perfect IVs", "use_case": "Standard for most Pokemon"},
            {"pattern": "0 Speed IVs", "name": "Trick Room", "use_case": "Slow Pokemon for Trick Room teams"}
        ],
        "example": "A Pokemon with 31 Speed IVs will be faster than one with 0 Speed IVs.",
        "related_terms": ["EVs", "Nature", "Base Stats"]
    },
    "nature": {
        "term": "Nature",
        "simple_explanation": "Nature increases one stat by 10% and decreases another by 10%. There are 25 natures total.",
        "why_it_matters": "Nature is crucial for optimization. Timid (+Spe, -Atk) is common on fast attackers, while Bold (+Def, -Atk) is common on defensive Pokemon.",
        "common_patterns": [
            {"pattern": "Timid", "name": "+Speed, -Attack", "use_case": "Fast special attackers"},
            {"pattern": "Modest", "name": "+SpA, -Attack", "use_case": "Slow but powerful special attackers"},
            {"pattern": "Jolly", "name": "+Speed, -SpA", "use_case": "Fast physical attackers"},
            {"pattern": "Adamant", "name": "+Attack, -SpA", "use_case": "Physical attackers"},
            {"pattern": "Bold", "name": "+Defense, -Attack", "use_case": "Defensive Pokemon"}
        ],
        "example": "Timid Flutter Mane moves faster than Modest Flutter Mane, but Modest hits harder.",
        "related_terms": ["EVs", "IVs", "Base Stats"]
    },
    "base stats": {
        "term": "Base Stats",
        "simple_explanation": "Base stats are the Pokemon's natural stat values before EVs, IVs, and Nature are applied. Each Pokemon species has unique base stats.",
        "why_it_matters": "Base stats determine a Pokemon's role. High Speed + Attack = sweeper. High HP + Defense = tank.",
        "common_patterns": [
            {"pattern": "High Speed + Attack", "name": "Sweeper", "use_case": "Fast attackers like Flutter Mane"},
            {"pattern": "High HP + Defense", "name": "Tank", "use_case": "Defensive Pokemon like Amoonguss"},
            {"pattern": "Balanced stats", "name": "Utility", "use_case": "Support Pokemon like Incineroar"}
        ],
        "example": "Flutter Mane has base 135 Speed, meaning it's naturally very fast.",
        "related_terms": ["EVs", "IVs", "Nature"]
    },
    "stab": {
        "term": "STAB (Same Type Attack Bonus)",
        "simple_explanation": "STAB gives a 1.5x damage boost when a Pokemon uses a move matching its type.",
        "why_it_matters": "STAB makes type-matching moves 50% stronger. This is why Pokemon usually use moves of their own type.",
        "common_patterns": [
            {"pattern": "Normal STAB", "name": "1.5x boost", "use_case": "Standard STAB bonus"},
            {"pattern": "Tera STAB", "name": "2.0x boost", "use_case": "When Terastallized into same type"}
        ],
        "example": "Flutter Mane's Moonblast (Fairy-type) gets STAB because Flutter Mane is Fairy-type, dealing 1.5x damage.",
        "related_terms": ["Type Effectiveness", "Tera Type", "Super Effective"]
    },
    "type effectiveness": {
        "term": "Type Effectiveness",
        "simple_explanation": "Type effectiveness determines how much damage a move does based on type matchups. Can be 0x (immune), 0.5x (resisted), 1x (neutral), 2x (super effective), or 4x (double super effective).",
        "why_it_matters": "Type effectiveness can double or halve damage. A super effective move deals 2x damage, while a resisted move deals 0.5x.",
        "common_patterns": [
            {"pattern": "Super Effective (2x)", "name": "Strong", "use_case": "Deal double damage"},
            {"pattern": "Resisted (0.5x)", "name": "Weak", "use_case": "Deal half damage"},
            {"pattern": "Immune (0x)", "name": "No damage", "use_case": "Ghost vs Normal, Ground vs Flying"}
        ],
        "example": "Fire is super effective against Grass (2x), but resisted by Water (0.5x).",
        "related_terms": ["STAB", "Super Effective", "Resisted"]
    },
    "super effective": {
        "term": "Super Effective",
        "simple_explanation": "Super effective means a move deals 2x damage due to type advantage. Some matchups are 4x super effective.",
        "why_it_matters": "Super effective moves deal double damage, often turning 2HKOs into OHKOs.",
        "common_patterns": [
            {"pattern": "2x Super Effective", "name": "Standard", "use_case": "Most type advantages"},
            {"pattern": "4x Super Effective", "name": "Double weakness", "use_case": "Grass vs Fire/Steel, Ice vs Fire/Rock"}
        ],
        "example": "Fire moves are super effective against Grass types, dealing 2x damage.",
        "related_terms": ["Type Effectiveness", "Resisted", "STAB"]
    },
    "resisted": {
        "term": "Resisted",
        "simple_explanation": "Resisted means a move deals 0.5x damage due to type disadvantage. Some matchups are 4x resisted (0.25x).",
        "why_it_matters": "Resisted moves deal half damage, making them much weaker.",
        "common_patterns": [
            {"pattern": "0.5x Resisted", "name": "Standard", "use_case": "Most type disadvantages"},
            {"pattern": "0.25x Resisted", "name": "Double resist", "use_case": "Grass vs Fire/Steel"}
        ],
        "example": "Fire moves are resisted by Water types, dealing only 0.5x damage.",
        "related_terms": ["Type Effectiveness", "Super Effective", "STAB"]
    },
    "ohko": {
        "term": "OHKO (One-Hit Knock Out)",
        "simple_explanation": "OHKO means a Pokemon is knocked out in a single hit. This is the goal for attackers.",
        "why_it_matters": "OHKOs are powerful because they eliminate threats immediately without giving them a chance to attack.",
        "common_patterns": [
            {"pattern": "Guaranteed OHKO", "name": "100% chance", "use_case": "Minimum damage roll still KOs"},
            {"pattern": "Possible OHKO", "name": "Variable chance", "use_case": "High damage roll can KO"}
        ],
        "example": "Flutter Mane's Moonblast OHKOs most Dragapult sets.",
        "related_terms": ["2HKO", "3HKO", "Damage Calculation"]
    },
    "2hko": {
        "term": "2HKO (Two-Hit Knock Out)",
        "simple_explanation": "2HKO means a Pokemon is knocked out in two hits. This is common for bulkier Pokemon.",
        "why_it_matters": "2HKOs are reliable ways to eliminate threats. Many defensive Pokemon are designed to survive one hit but not two.",
        "common_patterns": [
            {"pattern": "Guaranteed 2HKO", "name": "Always 2HKO", "use_case": "Two hits always KO"},
            {"pattern": "Possible 2HKO", "name": "Variable", "use_case": "High rolls can 2HKO"}
        ],
        "example": "Most Pokemon can 2HKO Incineroar with super effective moves.",
        "related_terms": ["OHKO", "3HKO", "Damage Calculation"]
    },
    "3hko": {
        "term": "3HKO (Three-Hit Knock Out)",
        "simple_explanation": "3HKO means a Pokemon is knocked out in three hits. This indicates high bulk.",
        "why_it_matters": "3HKOs show a Pokemon is very bulky. These Pokemon can often survive multiple attacks.",
        "common_patterns": [
            {"pattern": "Guaranteed 3HKO", "name": "Always 3HKO", "use_case": "Very bulky Pokemon"},
            {"pattern": "Possible 3HKO", "name": "Variable", "use_case": "High rolls can 3HKO"}
        ],
        "example": "Defensive Amoonguss often survives 3 hits from special attackers.",
        "related_terms": ["OHKO", "2HKO", "Damage Calculation"]
    },
    "spread": {
        "term": "Spread (EV Spread)",
        "simple_explanation": "A spread is how you distribute your 508 EVs across your Pokemon's stats. Common spreads include '252/252/4' or custom benchmarks.",
        "why_it_matters": "The right spread can make your Pokemon survive specific attacks or outspeed specific threats.",
        "common_patterns": [
            {"pattern": "252/252/4", "name": "Max/Max/4", "use_case": "Maximum offense"},
            {"pattern": "252 HP / 252 Def", "name": "Max Bulk", "use_case": "Defensive Pokemon"},
            {"pattern": "Custom benchmarks", "name": "Optimized", "use_case": "Survive specific attacks"}
        ],
        "example": "A '252 SpA / 252 Spe / 4 HP' spread maximizes Flutter Mane's offense and speed.",
        "related_terms": ["EVs", "Benchmark", "Nature"]
    },
    "benchmark": {
        "term": "Benchmark",
        "simple_explanation": "A benchmark is a specific stat value you aim for, like 'survive Flutter Mane Moonblast' or 'outspeed Tornadus'.",
        "why_it_matters": "Benchmarks ensure your Pokemon can accomplish specific goals, like surviving common attacks or outspeeding threats.",
        "common_patterns": [
            {"pattern": "Survival benchmarks", "name": "Bulk", "use_case": "Survive specific attacks"},
            {"pattern": "Speed benchmarks", "name": "Speed", "use_case": "Outspeed specific threats"}
        ],
        "example": "A benchmark might be '252 HP / 156 Def Amoonguss survives Flutter Mane Moonblast'.",
        "related_terms": ["Spread", "EVs", "Damage Calculation"]
    },
    "tailwind": {
        "term": "Tailwind",
        "simple_explanation": "Tailwind is a move that doubles your team's Speed for 4 turns. It's a form of speed control.",
        "why_it_matters": "Tailwind lets slower Pokemon outspeed faster opponents, changing the speed dynamic of the battle.",
        "common_patterns": [
            {"pattern": "Tornadus Tailwind", "name": "Standard setter", "use_case": "Most common Tailwind setter"},
            {"pattern": "Tailwind + Sweeper", "name": "Offensive", "use_case": "Use Tailwind to enable slow sweepers"}
        ],
        "example": "Under Tailwind, a base 100 Speed Pokemon outspeeds a base 150 Speed Pokemon.",
        "related_terms": ["Speed Control", "Trick Room", "Priority"]
    },
    "trick room": {
        "term": "Trick Room",
        "simple_explanation": "Trick Room reverses Speed order for 5 turns - slower Pokemon move first. It's used by slow, bulky teams.",
        "why_it_matters": "Trick Room lets slow, powerful Pokemon attack first, making them much more dangerous.",
        "common_patterns": [
            {"pattern": "Trick Room team", "name": "Slow offense", "use_case": "Slow, powerful attackers"},
            {"pattern": "Trick Room counter", "name": "Imprison", "use_case": "Prevent opponent's Trick Room"}
        ],
        "example": "Under Trick Room, Amoonguss (base 30 Speed) moves before Flutter Mane (base 135 Speed).",
        "related_terms": ["Speed Control", "Tailwind", "Priority"]
    },
    "speed control": {
        "term": "Speed Control",
        "simple_explanation": "Speed control is using moves or abilities to change turn order. Includes Tailwind, Trick Room, and priority moves.",
        "why_it_matters": "Speed control determines who attacks first, which is crucial in VGC.",
        "common_patterns": [
            {"pattern": "Tailwind", "name": "Double Speed", "use_case": "Make your team faster"},
            {"pattern": "Trick Room", "name": "Reverse Speed", "use_case": "Make slow Pokemon fast"},
            {"pattern": "Priority moves", "name": "Always first", "use_case": "Attack before opponent"}
        ],
        "example": "Using Tailwind lets your slower Pokemon outspeed opponents.",
        "related_terms": ["Tailwind", "Trick Room", "Priority"]
    },
    "protect": {
        "term": "Protect",
        "simple_explanation": "Protect is a move that blocks all attacks for one turn. It's essential for scouting and stalling.",
        "why_it_matters": "Protect lets you avoid damage, scout opponent's moves, and waste opponent's turns.",
        "common_patterns": [
            {"pattern": "Protect on non-Choice", "name": "Standard", "use_case": "Almost all non-Choice Pokemon"},
            {"pattern": "Protect + Partner", "name": "Double Protect", "use_case": "Both Pokemon Protect"}
        ],
        "example": "Using Protect lets you avoid damage while your partner attacks.",
        "related_terms": ["Fake Out", "Priority", "Scouting"]
    },
    "fake out": {
        "term": "Fake Out",
        "simple_explanation": "Fake Out is a priority move that flinches the opponent, making them unable to move that turn.",
        "why_it_matters": "Fake Out gives you a free turn by preventing the opponent from acting.",
        "common_patterns": [
            {"pattern": "Fake Out + Sweeper", "name": "Standard", "use_case": "Fake Out enables sweeper"},
            {"pattern": "Fake Out lead", "name": "Common", "use_case": "Incineroar, Rillaboom"}
        ],
        "example": "Incineroar uses Fake Out to flinch the opponent, giving Flutter Mane a free turn to attack.",
        "related_terms": ["Protect", "Priority", "Lead"]
    },
    "priority": {
        "term": "Priority",
        "simple_explanation": "Priority moves always go first, regardless of Speed. Fake Out, Extreme Speed, and Sucker Punch are priority moves.",
        "why_it_matters": "Priority moves let slower Pokemon attack first, bypassing Speed differences.",
        "common_patterns": [
            {"pattern": "+1 Priority", "name": "Standard", "use_case": "Fake Out, Extreme Speed"},
            {"pattern": "+2 Priority", "name": "Rare", "use_case": "Extreme Speed (some abilities)"}
        ],
        "example": "Fake Out always goes first, even if the opponent is faster.",
        "related_terms": ["Fake Out", "Speed Control", "Protect"]
    },
    "tera type": {
        "term": "Tera Type (Terastallization)",
        "simple_explanation": "Terastallization changes a Pokemon's type to its Tera Type, boosting moves of that type and changing defensive typing.",
        "why_it_matters": "Tera Type can turn resisted moves into super effective moves, or provide defensive utility.",
        "common_patterns": [
            {"pattern": "STAB Tera", "name": "Same type", "use_case": "Boost existing STAB moves"},
            {"pattern": "Defensive Tera", "name": "Different type", "use_case": "Remove weaknesses"}
        ],
        "example": "Tera Fairy Flutter Mane gets 2x STAB on Fairy moves instead of 1.5x.",
        "related_terms": ["STAB", "Type Effectiveness", "Terastallization"]
    },
    "terastallization": {
        "term": "Terastallization",
        "simple_explanation": "Terastallization is the mechanic where a Pokemon changes to its Tera Type, gaining new STAB and defensive typing.",
        "why_it_matters": "Terastallization is a one-time per battle transformation that can change matchups dramatically.",
        "common_patterns": [
            {"pattern": "Offensive Tera", "name": "Boost damage", "use_case": "Turn 2HKOs into OHKOs"},
            {"pattern": "Defensive Tera", "name": "Survive hits", "use_case": "Remove weaknesses"}
        ],
        "example": "Terastallizing Flutter Mane to Fairy type boosts its Fairy moves and changes its defensive typing.",
        "related_terms": ["Tera Type", "STAB", "Type Effectiveness"]
    },
    "check": {
        "term": "Check",
        "simple_explanation": "A check is a Pokemon that can outspeed and KO a threat, but might not be able to switch in safely.",
        "why_it_matters": "Checks are important for revenge killing threats, but require careful positioning.",
        "common_patterns": [
            {"pattern": "Speed check", "name": "Outspeed", "use_case": "Faster Pokemon that can KO"},
            {"pattern": "Priority check", "name": "Priority move", "use_case": "Use priority to KO"}
        ],
        "example": "Flutter Mane checks Dragapult because it outspeeds and OHKOs it.",
        "related_terms": ["Counter", "Lead", "Pivot"]
    },
    "counter": {
        "term": "Counter",
        "simple_explanation": "A counter is a Pokemon that can switch in safely against a threat and then KO it.",
        "why_it_matters": "Counters are safer than checks because they can switch in and take hits.",
        "common_patterns": [
            {"pattern": "Defensive counter", "name": "Tank", "use_case": "Survive hits and KO back"},
            {"pattern": "Type counter", "name": "Resist", "use_case": "Resist attacks and KO"}
        ],
        "example": "Incineroar counters Flutter Mane because it resists Fairy and can KO with Dark moves.",
        "related_terms": ["Check", "Lead", "Pivot"]
    },
    "lead": {
        "term": "Lead",
        "simple_explanation": "A lead is one of the two Pokemon you send out at the start of a battle.",
        "why_it_matters": "Good leads set up your strategy, whether that's Tailwind, Fake Out, or immediate offense.",
        "common_patterns": [
            {"pattern": "Fake Out lead", "name": "Support", "use_case": "Incineroar, Rillaboom"},
            {"pattern": "Tailwind lead", "name": "Speed control", "use_case": "Tornadus"},
            {"pattern": "Offensive lead", "name": "Sweeper", "use_case": "Flutter Mane"}
        ],
        "example": "Incineroar + Flutter Mane is a common lead pairing.",
        "related_terms": ["Back", "Pivot", "Fake Out"]
    },
    "back": {
        "term": "Back",
        "simple_explanation": "Back Pokemon are the four Pokemon you keep in reserve at the start of battle.",
        "why_it_matters": "Back Pokemon provide flexibility and counterplay options for different matchups.",
        "common_patterns": [
            {"pattern": "Sweeper in back", "name": "Late game", "use_case": "Bring out after setup"},
            {"pattern": "Counter in back", "name": "Answer", "use_case": "Switch in to counter threats"}
        ],
        "example": "Keeping a counter to the opponent's sweeper in the back provides safety.",
        "related_terms": ["Lead", "Pivot", "Team Building"]
    },
    "pivot": {
        "term": "Pivot",
        "simple_explanation": "A pivot is a Pokemon that can switch in safely and then switch out, often using moves like U-turn or Parting Shot.",
        "why_it_matters": "Pivots provide safe switches and momentum, letting you bring in the right Pokemon for the situation.",
        "common_patterns": [
            {"pattern": "U-turn pivot", "name": "Offensive", "use_case": "Landorus, Rillaboom"},
            {"pattern": "Parting Shot pivot", "name": "Defensive", "use_case": "Incineroar"}
        ],
        "example": "Incineroar uses Parting Shot to lower opponent's stats and switch out safely.",
        "related_terms": ["Lead", "Back", "Switch"]
    },
    "doubles": {
        "term": "Doubles",
        "simple_explanation": "Doubles format means both players send out two Pokemon at once. VGC is a doubles format.",
        "why_it_matters": "Doubles changes strategy significantly - spread moves, partner abilities, and positioning matter more.",
        "common_patterns": [
            {"pattern": "Spread moves", "name": "Hit both", "use_case": "Dazzling Gleam, Earthquake"},
            {"pattern": "Partner support", "name": "Synergy", "use_case": "Fake Out + Sweeper"}
        ],
        "example": "In doubles, Earthquake hits both opponents, but also hits your partner unless they're Flying-type.",
        "related_terms": ["VGC Format", "Singles", "Spread Moves"]
    },
    "singles": {
        "term": "Singles",
        "simple_explanation": "Singles format means both players send out one Pokemon at a time. This is different from VGC.",
        "why_it_matters": "Singles has different strategies than doubles - no spread moves, different team building.",
        "common_patterns": [
            {"pattern": "1v1 format", "name": "Standard", "use_case": "Most Pokemon games"},
            {"pattern": "Different meta", "name": "Strategy", "use_case": "Different viable Pokemon"}
        ],
        "example": "Singles format doesn't use spread moves like Dazzling Gleam.",
        "related_terms": ["Doubles", "VGC Format", "Team Building"]
    },
    "vgc format": {
        "term": "VGC Format",
        "simple_explanation": "VGC (Video Game Championships) is the official Pokemon competitive format. It's doubles format with specific rules.",
        "why_it_matters": "VGC has specific rules about allowed Pokemon, items, and moves that change each season.",
        "common_patterns": [
            {"pattern": "Regulation H", "name": "Current", "use_case": "Current VGC format"},
            {"pattern": "Restricted Pokemon", "name": "Limited", "use_case": "Some Pokemon banned"}
        ],
        "example": "VGC Regulation H allows certain Legendary Pokemon but restricts others.",
        "related_terms": ["Doubles", "Singles", "Team Building"]
    }
}
