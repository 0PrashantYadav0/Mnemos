"""Player-facing task/quest system.

Tasks are the objectives the player is given at the start and as each act opens.
They are a thin, ordered view over the story's milestone flags -- the story
engine still owns the actual branching; tasks just make progression legible and
give the AI advisor something concrete to reason about.
"""
from __future__ import annotations

# Each task maps to a milestone flag the story sets when the objective resolves.
# category drives the advisor's scoring; hint seeds its reasoning.
TASKS = [
    # ---- Act 1: The Waking ----
    {"id": "t_mira", "act": 1, "npc": "npc:mira", "done_flag": "done_mira",
     "category": "reputation", "title": "The Baker's Debt",
     "desc": "Mira faces ruin over a 10-coin debt. Decide her fate.",
     "hint": "A first friend costs little and pays off for acts to come."},
    {"id": "t_dorin", "act": 1, "npc": "npc:dorin", "done_flag": "done_dorin",
     "category": "reputation", "title": "The Stolen Tongs",
     "desc": "Dorin's heirloom tongs are in your hands. Return or keep them.",
     "hint": "Dorin's favour later forges a key to the Archive."},
    {"id": "t_voss", "act": 1, "npc": "npc:voss", "done_flag": "done_voss",
     "category": "reputation", "title": "The Guard's Seal",
     "desc": "Captain Voss dropped his seal. Return it, or pocket it.",
     "hint": "Voss guards the only gate to the Archon."},
    # ---- Act 2: Reputation Travels ----
    {"id": "t_sela", "act": 2, "npc": "npc:sela", "done_flag": "done_sela",
     "category": "item", "title": "The Healer's Trust",
     "desc": "Sela holds the Memory Potion recipe. Earn it.",
     "hint": "No recipe, no potion, no forget() showpiece later."},
    {"id": "t_faction", "act": 2, "npc": "npc:crier", "done_flag": "done_faction",
     "category": "faction", "title": "Choose Your Banner",
     "desc": "The Watch and the Free Market court you. Or stand alone.",
     "hint": "Independence keeps every ending open."},
    {"id": "t_crispin", "act": 2, "npc": "npc:crispin", "done_flag": "done_crispin",
     "category": "reputation", "title": "The Liar's Gambit",
     "desc": "Crispin wants you to lie for him. Lie, or expose him.",
     "hint": "Exposing him earns Sela's trust and a future ally."},
    # ---- Act 3: The Reckoning ----
    {"id": "t_dorinkey", "act": 3, "npc": "npc:dorin", "done_flag": "done_dorinkey",
     "category": "item", "title": "A Key to the Archive",
     "desc": "You need into the sealed Archive. Dorin can forge a key.",
     "hint": "Requires Dorin's favour from Act 1."},
    {"id": "t_renna", "act": 3, "npc": "npc:renna", "done_flag": "done_renna",
     "category": "reputation", "title": "The Old Friend",
     "desc": "Renna knows who you were. Keep faith, or betray her.",
     "hint": "Renna's loyalty is required for the true ending."},
    {"id": "t_crispin2", "act": 3, "npc": "npc:crispin", "done_flag": "done_crispin2",
     "category": "reputation", "title": "Spare or Strike",
     "desc": "You've cornered Crispin. Mercy could make an ally.",
     "hint": "A spared enemy returns to disarm the Archon."},
    # ---- Act 4: The Town That Remembers ----
    {"id": "t_gate", "act": 4, "npc": "npc:voss", "done_flag": "done_gate",
     "category": "finale", "title": "Reach the Archon",
     "desc": "Pass the Watch Gate: by trust, a key, the seal, or a potion.",
     "hint": "Brew the potion at Sela's first if you need it."},
    # ---- Act 5: Restoration or Ruin ----
    {"id": "t_finale", "act": 5, "npc": "npc:archon", "done_flag": None,
     "category": "finale", "title": "Face the Archon",
     "desc": "Let the town's memory decide your fate.",
     "hint": "Everything you built converges here."},
]

TASKS_BY_ID = {t["id"]: t for t in TASKS}


def tasks_for_act(act: int) -> list[dict]:
    return [t for t in TASKS if t["act"] == act]
