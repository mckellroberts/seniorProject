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
            "WHAT TO DO:\n"
            "The narrator is a distinct character — wry, quietly opinionated, gently amused by everyone including the protagonist. "
            "Use free indirect discourse: slip into a character's thoughts but keep the narrator's ironic distance layered over them. "
            "Let irony do the work — the real meaning is often the opposite of what is stated on the surface. "
            "Reveal character entirely through dialogue, social behavior, and what people fail to notice — not through inner analysis. "
            "Describe appearance only with social judgment attached ('her dress was handsome, though she was not'). "
            "Alternate short, crisp declarative sentences with longer, clause-heavy reflections. "
            "Let dialogue carry class signals, wit, and subtle condescension — characters expose themselves by how they speak.\n\n"
            "WHAT NOT TO DO — violations of Austen's style:\n"
            "Do NOT use lush, sensory, or gothic imagery ('ethereal in the flickering light', 'voice low as silk'). Austen understates appearance.\n"
            "Do NOT write explicit psychological analysis ('a glimmer of wariness', 'guardedness behind the facade', 'true motivations'). "
            "Austen never narrates psychology directly — she shows it through behavior and dialogue.\n"
            "Do NOT use modern-sounding emotional vocabulary. No 'chemistry', no 'tension', no cinematic interiority.\n"
            "Do NOT make the narrator invisible or neutral. The narrator has opinions and quiet judgments.\n"
            "Do NOT take characters at face value. Everyone is slightly absurd, slightly self-deceived, or both.\n"
            "Do NOT use generic polite dialogue. Every line should carry social nuance, class awareness, or ironic subtext."
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
            "WHAT TO DO:\n"
            "The narrator is external and observational — like Nick Carraway, they are watching from slightly outside, "
            "socially grounded, personally restrained. They notice details. They do not explain what those details mean.\n"
            "Tie every emotion to a concrete physical detail: a gesture, a color of light, a sound, a specific object. "
            "Pick one strong image and let it carry weight — then move on. Do not return to the same image.\n"
            "Vary rhythm: plain almost blunt sentences ('People came and went without knowing his name.') "
            "followed by sudden lyrical spikes. The contrast is the technique.\n"
            "Let the meaning emerge from what is shown, never from what is stated. "
            "The reader should feel the disillusionment without being told about it.\n"
            "Ground every scene in specific sensory detail tied to the Jazz Age: "
            "wealth, light, music, beautiful surfaces concealing emptiness.\n\n"
            "WHAT NOT TO DO — violations of Fitzgerald's style:\n"
            "Do NOT use abstract philosophical language. Never write 'disillusionment', 'fragility of existence', "
            "'erosion of conviction', 'crushing reality of human experience', or similar abstractions. "
            "These are conclusions. Fitzgerald shows; he does not conclude.\n"
            "Do NOT repeat the same metaphor or concept. If you use fragility once, never use it again. "
            "Stacking the same image ('fragile vessel', 'fragile glass', 'shards of fragility') kills the effect.\n"
            "Do NOT write an internal, philosophizing narrator. The narrator watches from outside. "
            "They do not analyze their own psychology or drift into isolated introspection.\n"
            "Do NOT state the moral or meaning at the end. No explicit conclusions about disappointment, illusion, or the human condition. "
            "End on a concrete image or action, not a summary.\n"
            "Do NOT use modern settings (fluorescent-lit libraries, contemporary spaces). "
            "Stay in the sensory world of the 1920s — parties, water, light, old money, beautiful ruin.\n"
            "Do NOT pile metaphors. One precise image beats three ornate ones every time."
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
