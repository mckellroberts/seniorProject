"""
Demo Author Definitions
Each entry defines a Project Gutenberg author used in tester mode.
Files are expected in rag/data/demo/<dir>/.
Run scripts/setup_demo.py to ingest them before using demo mode.
"""

from __future__ import annotations

# Keys must match the filename prefix convention: demo_<key>
DEMO_AUTHORS: dict[str, dict] = {
    "edgarAllenPoe": {
        "name":   "Edgar Allan Poe",
        "era":    "1809 – 1849",
        "style":  "Gothic horror · psychological suspense · dark atmosphere · unreliable narrators",
        "dir":    "edgarAllenPoe",
        "files":  ["pg2147.txt", "pg2148.txt"],
        "voiceInstructions": (
            "Write in a dense, rhythmic first-person voice on the edge of sanity. "
            "The narrator insists on their own rationality even while describing irrational, obsessive behavior. "
            "Build dread through accumulation — repeat key words and phrases to create mounting tension. "
            "Never state the horror outright; circle around it with increasingly agitated logic. "
            "Use long, clause-heavy sentences that accelerate toward short, stopped confessions. "
            "Gothic atmosphere is essential: decaying architecture, strange sounds, failing light, isolation. "
            "The narrator's precision of detail is itself a sign of their unraveling."
        ),
        "prompts": [
            "Write an opening paragraph for a gothic horror story set in a decaying mansion",
            "Describe a narrator who begins hearing sounds that no one else can hear",
            "Write a confession from someone who is certain they committed the perfect crime",
            "Describe the moment a character realizes something has gone terribly wrong",
        ],
    },
    "janeAusten": {
        "name":   "Jane Austen",
        "era":    "1775 – 1817",
        "style":  "Sharp social irony · elegant prose · wit · romantic tension · acute character observation",
        "dir":    "janeAusten",
        "files":  ["pg158.txt"],    # Emma
        "voiceInstructions": (
            "Use free indirect discourse — narrate from inside the character's perspective but with the author's quiet irony layered over it. "
            "The real meaning is often the opposite of what's stated on the surface. "
            "Social observation is the true subject; romance is merely the vehicle. "
            "Alternate short, crisp declarative sentences with longer, clause-heavy reflections. "
            "Characters expose themselves through small social missteps, word choices, and what they fail to notice. "
            "The narrator is always gently amused, never savage. Irony should feel like politeness turned inside out. "
            "Never editorialize — let the situation deliver the judgment."
        ),
        "prompts": [
            "Write a scene where two characters meet at a formal ball for the first time",
            "Write a letter from a character torn between love and social obligation",
            "Describe a character making a quietly devastating observation about someone at a party",
            "Write an exchange where a character refuses a proposal without losing their composure",
        ],
    },
    "fScottFitzgerald": {
        "name":   "F. Scott Fitzgerald",
        "era":    "1896 – 1940",
        "style":  "Lyrical prose · Jazz Age glamour · longing and disillusionment · vivid sensory detail · tragic romanticism",
        "dir":    "fScottFitzgerald",
        "files":  ["pg64317.txt"],  # The Great Gatsby
        "voiceInstructions": (
            "Write in lyrical, sensory prose — every scene should have a texture of light, sound, and smell. "
            "The narrator is simultaneously inside and outside the action: longing, observing, slightly melancholy. "
            "Sentences build with rhythm and then break on a quietly devastating note. "
            "Ground scenes in Jazz Age specificity: wealth, parties, beautiful people in beautiful ruin. "
            "The underlying theme is always nostalgia and the impossibility of recapturing the past. "
            "Alternate long, music-like sentences with short, stopped ones for emotional impact. "
            "Beauty should feel slightly tragic — the more perfect something appears, the more doomed it is."
        ),
        "prompts": [
            "Write a scene describing a lavish party where the host seems oddly detached from it all",
            "Write a character gazing across the water at a light they can never quite reach",
            "Describe the moment a character realizes the dream they chased was always an illusion",
            "Write a narrator observing two wealthy characters destroy something beautiful without noticing",
        ],
    },
    "oscarWilde": {
        "name":   "Oscar Wilde",
        "era":    "1854 – 1900",
        "style":  "Ornate prose · biting wit · paradox · aestheticism · decadence",
        "dir":    "oscarWilde",
        "files":  ["pg844.txt"],    # The Importance of Being Earnest
        "voiceInstructions": (
            "Every key idea must be compressed into a short, epigrammatic sentence that snaps. "
            "Use paradox and ironic reversal constantly — state something beautiful or sincere, then undercut it with wit. "
            "The narrator is always slightly amused, never earnest; sincerity is treated as mildly suspect. "
            "Favor precise, polished aphorisms over extended metaphors or layered imagery. "
            "Contradiction is a virtue: 'She did not love men — only the idea that they might adore her.' "
            "Avoid explaining. Trust the epigram to land. If a sentence needs more than one clause, ask whether it needs the second one. "
            "Wit is not decoration — it is the argument. The style is the meaning."
        ),
        "prompts": [
            "Write a witty exchange between two aristocrats at a London dinner party",
            "Write a character's philosophical meditation on the relationship between beauty and corruption",
            "Describe a character who is entirely in love with the idea of love, not the person",
            "Write an aphorism-laden monologue about the nature of sin and virtue",
        ],
    },
    "hermanMelville": {
        "name":   "Herman Melville",
        "era":    "1819 – 1891",
        "style":  "Epic digression · philosophical depth · dense imagery · obsession · man vs. nature",
        "dir":    "hermanMelville",
        "files":  ["pg15.txt"],     # Moby-Dick; or, The Whale
        "voiceInstructions": (
            "Begin with digression — philosophical, encyclopedic tangents are not interruptions, they are the point. "
            "Sentences accumulate: clauses pile onto clauses, building toward a grand, slightly exhausting weight. "
            "Obsession and fate are the undercurrent of every physical description. "
            "Address the reader directly where it feels natural ('Call me Ishmael'). "
            "The sea, ships, whales, and weather are never merely themselves — they are symbols of something cosmic. "
            "Weave biblical and classical allusions naturally into the prose, as if they require no explanation. "
            "The narrator is learned, melancholy, and slightly doomed — wise about the world but helpless before fate."
        ),
        "prompts": [
            "Write an opening monologue from a narrator about to embark on a life-changing voyage",
            "Describe an obsessive character explaining why their singular pursuit justifies all sacrifice",
            "Write a digressive passage that moves from a physical observation into a meditation on fate",
            "Describe the open sea at night from the perspective of someone who has spent years on it",
        ],
    },
}
