"""
Demo Author Definitions
Each entry defines a Project Gutenberg author used in tester mode.
Files are expected in rag/data/demo/<dir>/.
Run scripts/setup_demo.py to ingest them before using demo mode.
"""

from __future__ import annotations

# Keys must match the filename prefix convention: demo_<key>
DEMO_AUTHORS: dict[str, dict] = {
    "poe": {
        "name":   "Edgar Allan Poe",
        "era":    "1809 – 1849",
        "style":  "Gothic horror · psychological suspense · dark atmosphere · unreliable narrators",
        "dir":    "edgarAllenPoe",
        "files":  ["pg2147.txt", "pg2148.txt"],
        "prompts": [
            "Write an opening paragraph for a gothic horror story set in a decaying mansion",
            "Describe a narrator who begins hearing sounds that no one else can hear",
            "Write a confession from someone who is certain they committed the perfect crime",
            "Describe the moment a character realizes something has gone terribly wrong",
        ],
    },
    "austen": {
        "name":   "Jane Austen",
        "era":    "1775 – 1817",
        "style":  "Sharp social irony · elegant prose · wit · romantic tension · acute character observation",
        "dir":    "janeAusten",
        "files":  ["pg158.txt"],    # Emma
        "prompts": [
            "Write a scene where two characters meet at a formal ball for the first time",
            "Write a letter from a character torn between love and social obligation",
            "Describe a character making a quietly devastating observation about someone at a party",
            "Write an exchange where a character refuses a proposal without losing their composure",
        ],
    },
    "fitzgerald": {
        "name":   "F. Scott Fitzgerald",
        "era":    "1896 – 1940",
        "style":  "Lyrical prose · Jazz Age glamour · longing and disillusionment · vivid sensory detail · tragic romanticism",
        "dir":    "fScottFitzgerald",
        "files":  ["pg64317.txt"],  # The Great Gatsby
        "prompts": [
            "Write a scene describing a lavish party where the host seems oddly detached from it all",
            "Write a character gazing across the water at a light they can never quite reach",
            "Describe the moment a character realizes the dream they chased was always an illusion",
            "Write a narrator observing two wealthy characters destroy something beautiful without noticing",
        ],
    },
    "wilde": {
        "name":   "Oscar Wilde",
        "era":    "1854 – 1900",
        "style":  "Ornate prose · biting wit · paradox · aestheticism · decadence",
        "dir":    "oscarWilde",
        "files":  ["pg844.txt"],    # The Importance of Being Earnest
        "prompts": [
            "Write a witty exchange between two aristocrats at a London dinner party",
            "Write a character's philosophical meditation on the relationship between beauty and corruption",
            "Describe a character who is entirely in love with the idea of love, not the person",
            "Write an aphorism-laden monologue about the nature of sin and virtue",
        ],
    },
    "melville": {
        "name":   "Herman Melville",
        "era":    "1819 – 1891",
        "style":  "Epic digression · philosophical depth · dense imagery · obsession · man vs. nature",
        "dir":    "hermanMelville",
        "files":  ["pg15.txt"],     # Moby-Dick; or, The Whale
        "prompts": [
            "Write an opening monologue from a narrator about to embark on a life-changing voyage",
            "Describe an obsessive character explaining why their singular pursuit justifies all sacrifice",
            "Write a digressive passage that moves from a physical observation into a meditation on fate",
            "Describe the open sea at night from the perspective of someone who has spent years on it",
        ],
    },
}
