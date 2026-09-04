from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
source = Image.open(ROOT / "geometry_surface_inspection.png").convert("RGB")
canvas = Image.new("RGB", (1200, 760), "white")
source.thumbnail((740, 680))
canvas.paste(source, (20, 40))
draw = ImageDraw.Draw(canvas)
font = ImageFont.load_default(size=20)
small = ImageFont.load_default(size=16)
draw.text((790, 45), "COMSOL P02 mesh inspection", fill="black", font=font)
lines = [
    "Actual COMSOL 6.4 FreeTet statistics",
    "",
    "COARSE (auto size 6; 25 kHz control)",
    "Elements: 42,495",
    "Vertices: 10,170",
    "Min / mean quality: 0.1336 / 0.6448",
    "hmax bound: 2.2867 mm",
    "9.4 mm width: >= 4.111 elements",
    "",
    "NORMAL (auto size 5; 37.5 kHz control)",
    "Elements: 101,196",
    "Vertices: 21,834",
    "Min / mean quality: 0.2019 / 0.6769",
    "hmax bound: 1.5244 mm",
    "9.4 mm width: >= 6.166 elements",
    "normal/coarse hmax = 0.667 (pass <= 0.75)",
    "",
    "Accepted solve mesh: NORMAL",
    "Sparse solve fmax: 7 kHz",
]
y = 90
for line in lines:
    draw.text((790, y), line, fill="black", font=small)
    y += 30
draw.text((20, 720), "Left: final COMSOL geometry surface rendering. Right: actual mesh statistics returned by mesh_info.", fill="black", font=small)
canvas.save(ROOT / "mesh_inspection_summary.png")
