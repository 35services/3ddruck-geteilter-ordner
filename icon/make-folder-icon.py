#!/usr/bin/env python3
# Draws folder-icon.png: a folder in GNOME's folder blue with the KJG logo
# (ktg_logo.png) on a white label on its front, so it's recognizable as a
# folder. Needs Pillow: python3 -m pip install pillow
#
# Usage, in geteilter-ordner/icon/: python3 make-folder-icon.py

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512
# drawn at 4x and scaled down, for smooth edges
SCALE = 4

BACK = (26, 95, 180)     # the back panel and its tab
FRONT = (53, 132, 228)   # the front, a bit lighter
LABEL = (255, 255, 255)

here = Path(__file__).parent


def box(x0, y0, x1, y1):
    return [v * SCALE for v in (x0, y0, x1, y1)]


canvas = Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE), (0, 0, 0, 0))
draw = ImageDraw.Draw(canvas)

# back panel with the tab at the top left
draw.rounded_rectangle(box(40, 92, 216, 160), radius=20 * SCALE, fill=BACK)
draw.rounded_rectangle(box(40, 124, 472, 436), radius=28 * SCALE, fill=BACK)
# front
draw.rounded_rectangle(box(40, 168, 472, 436), radius=28 * SCALE, fill=FRONT)
# white label for the logo
label = (76, 200, 436, 404)
draw.rounded_rectangle(box(*label), radius=22 * SCALE, fill=LABEL)

icon = canvas.resize((SIZE, SIZE), Image.LANCZOS)

# the logo, as large as fits on the label with a margin
logo = Image.open(here / "ktg_logo.png").convert("RGBA")
margin = 18
max_w = label[2] - label[0] - 2 * margin
max_h = label[3] - label[1] - 2 * margin
factor = min(max_w / logo.width, max_h / logo.height)
logo = logo.resize((round(logo.width * factor), round(logo.height * factor)), Image.LANCZOS)
x = label[0] + (label[2] - label[0] - logo.width) // 2
y = label[1] + (label[3] - label[1] - logo.height) // 2
icon.alpha_composite(logo, (x, y))

icon.save(here / "folder-icon.png")
print(f"Wrote {here / 'folder-icon.png'} ({SIZE}x{SIZE})")
