"""Presentation-only annotation of archived raster exports and CAD-defined details.

No acoustic solver, mesher, statistical resampling, or research-data loader is run.
The input field pixels and their original colour-bar gradient are preserved.
"""
from pathlib import Path
import hashlib
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
SOURCE = ROOT.parent / "THESIS_DRAFT_18_METHODS_CLARITY_IEEE_RELEASE"
MESH = SOURCE / "figure_sources/stored_fullwave_geometry.png"
FIELD = SOURCE / "figure_sources/stored_pressure_field_954hz.png"
EXPECTED = {
    MESH: "533D144354830CADAB6FC06A4DA5676C9AB797DB278BA3FA77C2598D5E87FADD",
    FIELD: "AA5A7B0411D5ACC980BB9504FAC3F6DD08A69C9D4F2CA53B3B389B862C589BAF",
}
for path, expected in EXPECTED.items():
    assert hashlib.sha256(path.read_bytes()).hexdigest().upper() == expected, path

# Exact geometry definitions in scripts/gen_enc_24_print_comp/GenEnc24PrintComp.java.
# Coordinates below are millimetres; the source Java uses metres.
HALF = 36.2053299278368 / 2
HEIGHT = 9.2
NECK_X, NECK_Y, NECK_W, NECK_D, NECK_L = 11.0, -2.0, 2.0, 4.0, 9.0
CAV_X, CAV_Y, CAV_W = 3.5, -8.5, 17.0
VC = (8e-6 * 343.0**2 / (0.012 * (2 * math.pi * 950.0)**2)) * 1e9
CAV_H = VC / CAV_W**2
FILLER_SIDE = math.sqrt(VC / (4 * HEIGHT))
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                     "mathtext.fontset": "dejavusans", "axes.linewidth": .65})
ZH = FontProperties(fname=r"C:\Users\Firefly\AppData\Local\Programs\MiKTeX\fonts\opentype\public\fandol\fandolsong-regular.otf")
AIR, EDGE, SOLID, RESONATOR = "#e7f0f7", "#355a74", "#a4a9ae", "#af5d16"


def generate(lang):
    chinese = lang == "zh"
    font = {"fontproperties": ZH} if chinese else {}
    def label(ax, x, y, en, zh, **kwargs):
        return ax.text(x, y, zh if chinese else en, **font, **kwargs)
    def callout(ax, en, zh, xy, xytext, **kwargs):
        return ax.annotate(zh if chinese else en, xy=xy, xytext=xytext,
                           fontsize=9, color="#172731", **font,
                           arrowprops={"arrowstyle": "->", "lw": .75,
                                       "color": "#172731", "shrinkA": 3, "shrinkB": 2},
                           **kwargs)
    fig = plt.figure(figsize=(7.16, 4.36), facecolor="white")
    mesh = fig.add_axes((.01, .53, .48, .43))
    field = fig.add_axes((.505, .53, .397, .43))
    for ax in (mesh, field):
        ax.axis("off")
    # Display only; use native pixel coordinates for auditable screenshot callouts.
    mesh.imshow(Image.open(MESH), interpolation="nearest")
    mesh.set_xlim(110, 675)
    mesh.set_ylim(460, 145)
    callout(mesh, "Dedicated side cavity", "专属共振侧腔", (423, 246), (122, 159), va="top")
    callout(mesh, "Neck", "颈管", (420, 280), (568, 191), ha="center", va="top")
    # This box identifies the region, not an exact projected location of a hidden point.
    mesh.add_patch(Rectangle((326, 269), 147, 84, fill=False,
                             ec=EDGE, lw=.85, ls=(0, (3, 2))))
    callout(mesh, "Central junction: see (c)", "中央汇合区：详见(c)",
            (343, 350), (126, 449), va="bottom")
    field.imshow(Image.open(FIELD), interpolation="nearest")
    field.set_xlim(120, 578)
    field.set_ylim(447, 175)
    callout(field, "Driven port: 270°", "激励端口：270°", (509, 399), (276, 435),
            ha="center", va="bottom")
    # Retain the actual exported gradient rather than approximating its colormap.
    cax = fig.add_axes((.921, .570, .013, .320))
    field_pixels = np.asarray(Image.open(FIELD).convert("RGB"))
    cax.imshow(field_pixels[71:565, 731:740], extent=(0, 1, 0, 2000),
               aspect="auto", interpolation="nearest")
    cax.set_xticks([])
    cax.yaxis.tick_right()
    cax.set_yticks([0, 500, 1000, 1500, 2000])
    cax.tick_params(axis="y", labelsize=8.5, length=2, pad=2)
    cax.set_title(r"$|p|$ (Pa)", fontsize=9, pad=5)

    fig.text(.017, .982, "(a) 全波几何与表面网格" if chinese else "(a) Full-wave geometry and surface mesh",
             va="top", fontsize=9.1, **font)
    fig.text(.517, .982, "(b) 954 Hz处的已存储压力场" if chinese else "(b) Stored pressure field at 954 Hz",
             va="top", fontsize=9.1, **font)
    fig.text(.017, .480, "(c) 中央汇合腔与共振器（α = 0.05）" if chinese else
             "(c) Central junction and resonator (α = 0.05)",
             va="top", fontsize=9.1, **font)

    plan = fig.add_axes((.022, .053, .44, .363))
    section = fig.add_axes((.503, .053, .47, .363))
    for ax in (plan, section):
        ax.set_aspect("equal")
        ax.axis("off")
    plan.set_xlim(-39, 39)
    plan.set_ylim(-30, 36)
    plan.add_patch(Rectangle((-HALF, -HALF), 2*HALF, 2*HALF,
                             fc=AIR, ec=EDGE, lw=1.0))
    for x, y in ((HALF-FILLER_SIDE, HALF-FILLER_SIDE),
                 (-HALF, HALF-FILLER_SIDE), (-HALF, -HALF),
                 (HALF-FILLER_SIDE, -HALF)):
        plan.add_patch(Rectangle((x, y), FILLER_SIDE, FILLER_SIDE,
                                 fc=SOLID, ec="#545b61", lw=.6, hatch="///"))
    # The vertical neck footprint is shown in plan; the raised cavity is omitted
    # here to keep the four subtraction solids visible. It appears in the section.
    plan.add_patch(Rectangle((NECK_X, NECK_Y), NECK_W, NECK_D,
                             fc="#f7dec8", ec=RESONATOR, lw=1.0))
    plan.plot(0, 0, "o", ms=4.2, color="#173c59", zorder=8)
    plan.plot([-HALF, HALF], [0, 0], ls=(0, (3, 3)), lw=.7, color=EDGE)
    callout(plan, "Four compensation\nsolids (full height)", "四个补偿实体\n（贯穿腔体全高）",
            (-HALF+FILLER_SIDE/2, HALF-FILLER_SIDE/2), (-37, 34), va="top")
    callout(plan, "Central\nreadout", "中央\n读出点", (0, 0), (-43, -9), va="center")
    callout(plan, "Neck\nfootprint", "颈管\n截面", (12, 0), (22, -12), va="center")
    label(plan, 0, -23, "Plan view", "俯视图", ha="center", va="top", fontsize=9)

    section.set_xlim(-30, 40)
    section.set_ylim(-9, 36)
    section.add_patch(Rectangle((-HALF, 0), 2*HALF, HEIGHT,
                                fc=AIR, ec=EDGE, lw=1.0))
    section.add_patch(Rectangle((NECK_X, HEIGHT), NECK_W, NECK_L,
                                fc="#f7dec8", ec=RESONATOR, lw=1.0))
    section.add_patch(Rectangle((CAV_X, HEIGHT+NECK_L), CAV_W, CAV_H,
                                fc="#f7dec8", ec=RESONATOR, lw=1.0))
    # Open the internal fluid interfaces in this explanatory section.
    section.plot([11.04, 12.96], [HEIGHT, HEIGHT], color="#f7dec8", lw=1.8)
    section.plot([11.04, 12.96], [HEIGHT+NECK_L, HEIGHT+NECK_L], color="#f7dec8", lw=1.8)
    section.plot(0, HEIGHT/2, "o", ms=4.2, color="#173c59", zorder=8)
    callout(section, "Side cavity\n17 × 17 mm footprint", "专属侧腔\n17 × 17 mm平面尺寸",
            (7, HEIGHT+NECK_L+CAV_H*.72), (-29, 36), va="top")
    callout(section, "Neck: 2 × 4 mm\nLength: 9 mm", "颈管：2 × 4 mm\n长度：9 mm",
            (12, 14), (21, 14), va="center")
    callout(section, "Readout at mid-height", "腔高中点处读出", (0, HEIGHT/2),
            (-28, -7), va="bottom")
    callout(section, "Junction cavity", "汇合腔", (-13, 7), (-29, 14), va="center")
    label(section, 6, -9, "Section at y = 0", "y = 0处的剖面", ha="center", va="top", fontsize=9)

    output = ROOT / f"fullwave_model_and_field_annotated_{lang}.png"
    fig.savefig(output, dpi=600, facecolor="white")
    # A lighter preview is not intended for the manuscript.
    fig.savefig(ROOT / f"preview_{lang}.png", dpi=180, facecolor="white")
    plt.close(fig)
    print(f"Created {output.name}; 4296 x 2616 pixels; 600 dpi")


if __name__ == "__main__":
    generate("en")
    generate("zh")
