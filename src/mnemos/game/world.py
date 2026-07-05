"""Static world data for Mnemos: a larger, explorable town.

Positions are tile coordinates. Nothing here is memory -- memory lives entirely
in the Brain graph. Districts are spread across a big map with grass between them
and cobblestone paths connecting a central plaza, so there is real space to walk
and a follow-camera has room to breathe (no more "everything zoomed in").

Tile indices (see scripts/gen_assets.py tiles.png):
  0 cobblestone (paths/plaza/market)  1 grass  2 forge floor
  3 archive marble  4 gate stone  5 wall
"""
from __future__ import annotations

MAP_W = 44
MAP_H = 30

# Ground regions. `tile` is the base tile index painted across the rectangle.
DISTRICTS = {
    "market":  {"label": "Market Row",       "x0": 2,  "y0": 2,  "x1": 15, "y1": 10, "tile": 0},
    "forge":   {"label": "The Forge Quarter", "x0": 28, "y0": 2,  "x1": 41, "y1": 10, "tile": 2},
    "gate":    {"label": "The Watch Gate",    "x0": 2,  "y0": 19, "x1": 15, "y1": 27, "tile": 4},
    "archive": {"label": "The Archive",       "x0": 28, "y0": 19, "x1": 41, "y1": 27, "tile": 3},
    "plaza":   {"label": "Remembrance Plaza",  "x0": 18, "y0": 12, "x1": 25, "y1": 17, "tile": 0},
}

# Cobblestone paths (tile 0) that connect the districts to the central plaza.
PATHS = [
    {"x0": 15, "y0": 5,  "x1": 28, "y1": 6},    # market <-> forge (top corridor)
    {"x0": 8,  "y0": 10, "x1": 9,  "y1": 22},   # market <-> gate (left corridor)
    {"x0": 34, "y0": 10, "x1": 35, "y1": 22},   # forge <-> archive (right corridor)
    {"x0": 8,  "y0": 22, "x1": 35, "y1": 23},   # gate <-> archive (bottom corridor)
    {"x0": 21, "y0": 6,  "x1": 22, "y1": 22},   # vertical spine to plaza
    {"x0": 15, "y0": 14, "x1": 28, "y1": 15},   # horizontal spine to plaza
]

# Decorations rendered client-side as procedural shapes (no extra assets):
#   tree, water, lamp, stall, anvil, pillar, crate, flowers
DECOR = [
    # market stalls + flowers
    {"type": "stall", "x": 4, "y": 4}, {"type": "stall", "x": 12, "y": 4},
    {"type": "flowers", "x": 6, "y": 8}, {"type": "flowers", "x": 13, "y": 9},
    {"type": "crate", "x": 3, "y": 9},
    # forge anvils + glow
    {"type": "anvil", "x": 32, "y": 4}, {"type": "anvil", "x": 38, "y": 8},
    {"type": "crate", "x": 40, "y": 4},
    # gate walls + lamps
    {"type": "lamp", "x": 3, "y": 20}, {"type": "lamp", "x": 14, "y": 20},
    {"type": "crate", "x": 12, "y": 26},
    # archive pillars
    {"type": "pillar", "x": 29, "y": 20}, {"type": "pillar", "x": 40, "y": 20},
    {"type": "pillar", "x": 29, "y": 26}, {"type": "pillar", "x": 40, "y": 26},
    # plaza fountain + lamps
    {"type": "water", "x": 21, "y": 14}, {"type": "lamp", "x": 18, "y": 12},
    {"type": "lamp", "x": 25, "y": 17},
    # scattered trees on the grass borders
    {"type": "tree", "x": 0, "y": 0}, {"type": "tree", "x": 43, "y": 0},
    {"type": "tree", "x": 0, "y": 29}, {"type": "tree", "x": 43, "y": 29},
    {"type": "tree", "x": 17, "y": 3}, {"type": "tree", "x": 26, "y": 9},
    {"type": "tree", "x": 16, "y": 25}, {"type": "tree", "x": 27, "y": 18},
    {"type": "tree", "x": 22, "y": 27}, {"type": "tree", "x": 21, "y": 1},
    {"type": "tree", "x": 1, "y": 15}, {"type": "tree", "x": 42, "y": 15},
]

# NPC roster. `spawn` is the tile they stand on (spread across the bigger town).
NPCS = [
    {"id": "npc:mira", "name": "Mira", "role": "Baker",
     "district": "market", "faction": "faction:free_market", "spawn": [6, 5], "color": "#e8a33d"},
    {"id": "npc:sela", "name": "Sela", "role": "Healer",
     "district": "market", "faction": None, "spawn": [11, 8], "color": "#5fa86e"},
    {"id": "npc:crispin", "name": "Crispin", "role": "Con Artist",
     "district": "market", "faction": None, "spawn": [4, 9], "color": "#9b59b6"},
    {"id": "npc:crier", "name": "Town Crier", "role": "Keeper of the Day",
     "district": "plaza", "faction": None, "spawn": [21, 15], "color": "#c9a227"},
    {"id": "npc:dorin", "name": "Dorin", "role": "Blacksmith",
     "district": "forge", "faction": "faction:free_market", "spawn": [33, 5], "color": "#b0603a"},
    {"id": "npc:voss", "name": "Capt. Voss", "role": "Guard Captain",
     "district": "gate", "faction": "faction:watch", "spawn": [7, 22], "color": "#4a6fa5"},
    {"id": "npc:renna", "name": "Renna", "role": "Old Ally",
     "district": "archive", "faction": None, "spawn": [31, 22], "color": "#d64a6f"},
    {"id": "npc:archon", "name": "The Archon", "role": "Corrupt Keeper",
     "district": "archive", "faction": "faction:watch", "spawn": [38, 25], "color": "#8f6fd6"},
]

FACTIONS = {
    "faction:watch": {"label": "The Watch"},
    "faction:free_market": {"label": "The Free Market"},
}


def npc_by_id(npc_id: str) -> dict | None:
    for n in NPCS:
        if n["id"] == npc_id:
            return n
    return None
