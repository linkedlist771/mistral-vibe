"""Loading verbs cycled by the assistant spinner.

Mirrors claude-code/src/constants/spinnerVerbs.ts. Used both when Claude is
thinking and while a tool is running.
"""
from __future__ import annotations

import random


SPINNER_VERBS: tuple[str, ...] = (
    "Accomplishing", "Actioning", "Actualizing", "Architecting", "Baking",
    "Beaming", "Beboppin'", "Befuddling", "Billowing", "Blanching",
    "Bloviating", "Boogieing", "Boondoggling", "Booping", "Bootstrapping",
    "Brewing", "Bunning", "Burrowing", "Calculating", "Canoodling",
    "Caramelizing", "Cascading", "Catapulting", "Cerebrating", "Channeling",
    "Channelling", "Choreographing", "Churning", "Clauding", "Coalescing",
    "Cogitating", "Combobulating", "Composing", "Computing", "Concocting",
    "Considering", "Contemplating", "Cooking", "Crafting", "Creating",
    "Crunching", "Crystallizing", "Cultivating", "Deciphering",
    "Deliberating", "Determining", "Dilly-dallying", "Discombobulating",
    "Doing", "Doodling", "Drizzling", "Ebbing", "Effecting", "Elucidating",
    "Embellishing", "Enchanting", "Envisioning", "Evaporating", "Fermenting",
    "Fiddle-faddling", "Finagling", "Flambéing", "Flibbertigibbeting",
    "Flowing", "Frolicking", "Fusing", "Galloping", "Generating", "Glimmering",
    "Glistening", "Gnashing", "Grokking", "Grooving", "Hatching",
    "Herding cats", "Hibernating", "Honking", "Honing", "Humming", "Imagining",
    "Inferring", "Innovating", "Inspecting", "Jiving", "Jollifying",
    "Kerfuffling", "Kneading", "Lollygagging", "Manifesting", "Marinating",
    "Meandering", "Meditating", "Mentalizing", "Mixing", "Moseying",
    "Mulling", "Mustering", "Mystifying", "Nimbleizing", "Noodling",
    "Optimizing", "Orchestrating", "Origamiing", "Outsmarting", "Percolating",
    "Pickling", "Plotting", "Plumbing", "Pondering", "Pontificating",
    "Prepping", "Procrastinating", "Processing", "Producing", "Puttering",
    "Puzzling", "Quibbling", "Razzmatazzing", "Reasoning", "Reconciling",
    "Refining", "Rendering", "Reticulating splines", "Riffing", "Ruminating",
    "Schlepping", "Schmoozing", "Sculpting", "Shenaniganing",
    "Shimmying", "Simmering", "Sizzling", "Skedaddling", "Skylarking",
    "Smelting", "Smooshing", "Sniffling", "Snoodling", "Sonic-booming",
    "Spelunking", "Spinning", "Steeping", "Sweating", "Swirling", "Synthesizing",
    "Tapdancing", "Thinkering", "Thinking", "Tinkering", "Tussling",
    "Twirling", "Unfurling", "Unraveling", "Vibing", "Vortexing",
    "Wandering", "Whirling", "Whisking", "Whittling", "Whomping", "Wibbling",
    "Wibblywobblying", "Wizarding", "Wondering", "Woolgathering",
    "Wrangling", "Zazzing", "Zhushing",
)


def random_verb(rng: random.Random | None = None) -> str:
    r = rng or random
    return r.choice(SPINNER_VERBS)
