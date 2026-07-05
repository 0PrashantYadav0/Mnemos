"""Generate game assets (sprite sheets + tileset) with Pillow.

Fully local, deterministic pixel art -- no downloads. Produces:
  ui/assets/tiles.png              a 6-tile, 32px tileset
  ui/assets/char_<key>.png         128x128 sheet: 4 dirs x 4 frames of 32px

Run: python scripts/gen_assets.py
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(__file__)
OUT = os.path.abspath(os.path.join(HERE, "..", "src", "mnemos", "ui", "assets"))
os.makedirs(OUT, exist_ok=True)

T = 32  # tile / frame size

# direction rows for Phaser: 0=down 1=left 2=right 3=up
DIRS = ["down", "left", "right", "up"]

# per-character palette: (tunic, tunic_dark, hair, skin, accent)
CHARS = {
    "player": ("#e9e4f2", "#b9b2cf", "#5b4a2f", "#f0c9a0", "#c9a227"),
    "mira":   ("#e8a33d", "#b57c22", "#7a4a1e", "#f0c9a0", "#fff2cf"),
    "dorin":  ("#b0603a", "#7d4126", "#2c2018", "#e2b48c", "#c0c0c0"),
    "voss":   ("#4a6fa5", "#324d78", "#20242c", "#e8c39e", "#cdd6e6"),
    "sela":   ("#5fa86e", "#3f7a4c", "#3a2c1e", "#f0c9a0", "#d8f0dc"),
    "crispin":("#9b59b6", "#6f3d84", "#1e1620", "#e8c39e", "#d0a8e0"),
    "renna":  ("#d64a6f", "#a5324e", "#3a1220", "#f0c9a0", "#f0c0d0"),
    "archon": ("#2c2140", "#1a1330", "#101018", "#c9b8d6", "#8f6fd6"),
    "crier":  ("#c9a227", "#96781a", "#3a2c14", "#f0c9a0", "#fff2cf"),
}


def hx(c: str):
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)


def draw_char(d: ImageDraw.ImageDraw, ox: int, oy: int, dirn: str, frame: int,
              pal: tuple):
    tunic, tunic_d, hair, skin, accent = (hx(c) for c in pal)
    outline = (24, 20, 34, 255)
    cx = ox + 16
    # walk state
    step = frame in (1, 3)
    bob = -1 if step else 0
    # ---- legs ----
    ly = oy + 30
    lfoot, rfoot = ly, ly
    if dirn in ("down", "up"):
        if frame == 1: lfoot = ly - 3
        if frame == 3: rfoot = ly - 3
    else:
        if step: lfoot = ly - 2; rfoot = ly - 2
    d.rectangle([cx - 5, oy + 24, cx - 1, lfoot], fill=tunic_d, outline=outline)
    d.rectangle([cx + 1, oy + 24, cx + 5, rfoot], fill=tunic_d, outline=outline)
    # ---- torso ----
    ty = oy + 15 + bob
    d.rounded_rectangle([cx - 7, ty, cx + 7, ty + 10], radius=3,
                        fill=tunic, outline=outline)
    d.rectangle([cx - 2, ty + 1, cx + 2, ty + 9], fill=accent)  # placket
    # ---- arms ----
    aoff = 2 if step else 0
    d.rectangle([cx - 9, ty + 1 - aoff, cx - 7, ty + 8 - aoff], fill=tunic_d, outline=outline)
    d.rectangle([cx + 7, ty + 1 + aoff, cx + 9, ty + 8 + aoff], fill=tunic_d, outline=outline)
    # ---- head ----
    hy = oy + 6 + bob
    d.ellipse([cx - 7, hy, cx + 7, hy + 14], fill=skin, outline=outline)
    # hair by direction
    if dirn == "up":
        d.chord([cx - 7, hy - 1, cx + 7, hy + 13], 180, 360, fill=hair)
        d.rectangle([cx - 7, hy + 5, cx + 7, hy + 8], fill=hair)
    else:
        d.chord([cx - 7, hy - 1, cx + 7, hy + 11], 180, 360, fill=hair)
    # eyes
    ey = hy + 8
    eye = (28, 24, 40, 255)
    if dirn == "down":
        d.ellipse([cx - 4, ey, cx - 2, ey + 2], fill=eye)
        d.ellipse([cx + 2, ey, cx + 4, ey + 2], fill=eye)
    elif dirn == "left":
        d.ellipse([cx - 5, ey, cx - 3, ey + 2], fill=eye)
    elif dirn == "right":
        d.ellipse([cx + 3, ey, cx + 5, ey + 2], fill=eye)


def make_char_sheet(key: str, pal: tuple):
    img = Image.new("RGBA", (T * 4, T * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for row, dirn in enumerate(DIRS):
        for frame in range(4):
            draw_char(d, frame * T, row * T, dirn, frame, pal)
    img.save(os.path.join(OUT, f"char_{key}.png"))


def make_tiles():
    tiles = [
        # (base, speck, name)
        ("#3a3326", "#4a4234"),   # 0 cobblestone (market)
        ("#2e3a22", "#3c4a2c"),   # 1 grass
        ("#3a241c", "#5a2e1e"),   # 2 forge floor
        ("#2a1f3e", "#3c2c54"),   # 3 archive marble
        ("#22303e", "#2e4054"),   # 4 gate stone
        ("#20202c", "#30303e"),   # 5 wall
    ]
    img = Image.new("RGBA", (T * len(tiles), T), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    import random
    random.seed(7)
    for i, (base, speck) in enumerate(tiles):
        x0 = i * T
        d.rectangle([x0, 0, x0 + T - 1, T - 1], fill=hx(base))
        for _ in range(26):
            px = x0 + random.randint(1, T - 2)
            py = random.randint(1, T - 2)
            d.point((px, py), fill=hx(speck))
        # subtle border
        d.rectangle([x0, 0, x0 + T - 1, T - 1], outline=(0, 0, 0, 40))
    img.save(os.path.join(OUT, "tiles.png"))


def main():
    make_tiles()
    for key, pal in CHARS.items():
        make_char_sheet(key, pal)
    print(f"Assets written to {OUT}: tiles.png + {len(CHARS)} character sheets")


if __name__ == "__main__":
    main()
