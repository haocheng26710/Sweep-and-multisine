"""Generate the bilingual IEEE physical-workflow and full-wave figures.

This is a presentation-only script.  It combines an author-supplied staged
photograph, schematic geometry, and images exported from an already-solved
COMSOL model.  It does not evaluate a model or change any reported value.
"""

from __future__ import annotations

from pathlib import Path
import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import rcParams
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Arc, Circle, FancyBboxPatch, Polygon, Rectangle
from PIL import Image

rcParams["pdf.fonttype"] = 42
rcParams["ps.fonttype"] = 42


ROOT = Path(__file__).resolve().parent
PHOTO = ROOT / "source_photos" / "representative_staged_arrangement.jpg"
MESH = ROOT / "figure_sources" / "stored_fullwave_geometry.png"
FIELD = ROOT / "figure_sources" / "stored_pressure_field_954hz.png"
ZH_FONT = FontProperties(
    fname=r"C:\Users\Firefly\AppData\Local\Programs\MiKTeX\fonts\opentype\public\fandol\fandolsong-regular.otf"
)

INK = "#20252a"
MUTED = "#58636f"
SHELL = "#e7eaed"
SHELL_EDGE = "#63707c"
BLUE = "#2878b5"
GREEN = "#3a9d78"
PURPLE = "#8267ad"
MAGENTA = "#c6538c"
RED = "#b33d49"
SEALED = "#aab2b9"
GOLD = "#d29424"


def fk(zh: bool) -> dict:
    return {"fontproperties": ZH_FONT} if zh else {}


def tx(ax, x, y, en, zh_text, zh=False, **kwargs):
    return ax.text(x, y, zh_text if zh else en, **kwargs, **fk(zh))


def panel_label(ax, label, zh=False):
    ax.text(
        0.015,
        0.965,
        label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9.0,
        fontweight="bold",
        color=INK,
        bbox=dict(boxstyle="round,pad=0.14", fc="white", ec="none", alpha=0.88),
        zorder=30,
        **fk(zh),
    )


def draw_speaker(ax, cx, cy):
    ax.add_patch(
        FancyBboxPatch(
            (cx - 0.63, cy - 0.88),
            1.26,
            1.76,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            fc="#3b4147",
            ec=INK,
            lw=0.8,
            zorder=5,
        )
    )
    for yy, rr in ((cy + 0.37, 0.30), (cy - 0.38, 0.42)):
        ax.add_patch(Circle((cx, yy), rr, fc="#15191d", ec="#707981", lw=0.6, zorder=6))
        ax.add_patch(Circle((cx, yy), rr * 0.38, fc="#4d555d", ec="none", zorder=7))


def octagon(cx, cy, r):
    a = np.deg2rad(np.arange(22.5, 382.5, 45.0))
    return np.column_stack((cx + r * np.cos(a), cy + r * np.sin(a)))


def draw_device_top(ax, cx, cy, r=0.8, rotation=0.0):
    ax.add_patch(Polygon(octagon(cx, cy, r), closed=True, fc=SHELL, ec=SHELL_EDGE, lw=0.8, zorder=5))
    for deg, color in zip((0, 90, 180, 270), (BLUE, GREEN, PURPLE, MAGENTA)):
        theta = math.radians(deg + rotation)
        ux, uy = math.sin(theta), math.cos(theta)
        ax.plot(
            [cx + 0.18 * ux, cx + 0.73 * ux],
            [cy + 0.18 * uy, cy + 0.73 * uy],
            color=color,
            lw=5.2,
            solid_capstyle="butt",
            zorder=7,
        )
    ax.add_patch(Circle((cx, cy), 0.19, fc="#f2b6bd", ec=RED, lw=0.7, zorder=8))
    ax.add_patch(Circle((cx, cy), 0.065, fc=RED, ec="white", lw=0.35, zorder=9))


def draw_setup(ax, zh=False):
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.6)
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 10, 5.6, fc="#fbfcfd", ec="#cbd1d6", lw=0.7))
    panel_label(ax, "(a)", zh)
    ax.plot([0.45, 9.55], [0.34, 0.34], color="#707982", lw=0.85)
    # Mirror the schematic horizontally so its source/device order matches the
    # staged photograph in panel (b): device left, loudspeaker right.
    draw_device_top(ax, 2.55, 3.18, 0.86)
    draw_speaker(ax, 8.20, 3.18)
    tx(ax, 8.20, 4.18, "Logitech Z207", "Logitech Z207", zh, ha="center", va="bottom", fontsize=7.8, color=INK)
    ax.annotate("", xy=(3.48, 3.18), xytext=(7.48, 3.18), arrowprops=dict(arrowstyle="-|>", lw=1.25, color=GOLD))
    tx(ax, 5.48, 3.38, "incident sweep", "入射扫频", zh, ha="center", va="bottom", fontsize=8.0, color="#75500f")
    ax.annotate("", xy=(7.48, 1.58), xytext=(3.62, 1.58), arrowprops=dict(arrowstyle="<->", lw=0.75, color=MUTED))
    tx(ax, 5.55, 1.71, "centre spacing: 0.8 m", "声学中心间距：0.8 m", zh, ha="center", va="bottom", fontsize=7.7, color=MUTED)
    ax.annotate("", xy=(9.38, 3.18), xytext=(9.38, 0.34), arrowprops=dict(arrowstyle="<->", lw=0.75, color=MUTED))
    tx(ax, 9.58, 1.76, "0.8 m", "0.8 m", zh, rotation=90, ha="center", va="center", fontsize=8.0, color=MUTED)
    # Offset east and south labels from the acoustic and microphone callout
    # arrows so that every annotation remains legible at IEEE page width.
    cardinal_positions = {
        "N": (2.55, 4.48),
        "E": (3.70, 2.76),
        "S": (2.55, 1.87),
        "W": (1.23, 3.18),
    }
    for lab, (xx, yy) in cardinal_positions.items():
        tx(ax, xx, yy, lab, {"N": "北", "E": "东", "S": "南", "W": "西"}[lab], zh,
           ha="center", va="center", fontsize=7.8, color=MUTED)
    ax.add_patch(Arc((2.55, 3.18), 2.35, 2.35, theta1=152, theta2=250, lw=0.8, color=MUTED))
    ax.annotate("", xy=(1.50, 2.66), xytext=(1.67, 2.44), arrowprops=dict(arrowstyle="-|>", lw=0.8, color=MUTED))
    tx(ax, 1.10, 4.90, "indexed rotation", "索引旋转", zh, ha="left", va="center", fontsize=7.6, color=MUTED)
    ax.annotate("", xy=(2.43, 2.98), xytext=(2.20, 1.24), arrowprops=dict(arrowstyle="->", lw=0.75, color=RED))
    ax.add_patch(FancyBboxPatch((0.62, 0.45), 2.16, 0.82, boxstyle="round,pad=0.05", fc="white", ec="#818a93", lw=0.7))
    tx(ax, 1.70, 0.86, "central mic\nREW, 48 kHz", "中央麦克风\nREW，48 kHz", zh,
       ha="center", va="center", fontsize=7.1, color=INK, linespacing=1.08)


def crop_photo():
    im = Image.open(PHOTO).convert("RGB")
    # Retain the device and source while removing most blank wall and hanging cable.
    return im.crop((120, 80, 2250, 1160))


def draw_photo(ax, zh=False):
    ax.imshow(crop_photo())
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#cbd1d6")
        s.set_linewidth(0.7)
    panel_label(ax, "(b)", zh)
    tx(
        ax,
        0.985,
        0.035,
        "representative staged arrangement",
        "代表性摆放示例",
        zh,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8.0,
        color=INK,
        bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="none", alpha=0.86),
    )


def draw_small_head(ax, mode, zh=False):
    ax.set_aspect("equal")
    ax.set_xlim(-1.23, 1.23)
    ax.set_ylim(-1.08, 1.35)
    ax.axis("off")
    ax.add_patch(Polygon(octagon(0, 0.08, 0.91), closed=True, fc=SHELL, ec=SHELL_EDGE, lw=0.75, zorder=1))
    for deg in (45, 135, 225, 315):
        t = math.radians(deg)
        u = np.array([math.sin(t), math.cos(t)])
        ax.plot([0.69*u[0], 0.87*u[0]], [0.08+0.69*u[1], 0.08+0.87*u[1]], color=SEALED,
                lw=6.0, solid_capstyle="butt", zorder=3)
    colors = (BLUE, GREEN, PURPLE, MAGENTA)
    for idx, deg in enumerate((0, 90, 180, 270)):
        t = math.radians(deg)
        u = np.array([math.sin(t), math.cos(t)])
        v = np.array([math.cos(t), -math.sin(t)])
        if mode == "straight":
            pts = np.array([0.18*u, 0.82*u])
        elif mode == "heterogeneous" and idx == 1:
            rr = np.linspace(0.18, 0.82, 7)
            pts = np.array([r*u + (0.07 if k % 2 else -0.07)*v for k, r in enumerate(rr)])
        elif mode == "heterogeneous" and idx == 2:
            pts = np.array([0.18*u, 0.47*u, 0.47*u+0.14*v, 0.67*u+0.14*v, 0.67*u, 0.82*u])
        elif mode == "heterogeneous" and idx == 3:
            pts = np.array([0.18*u, 0.44*u, 0.44*u+0.13*v, 0.61*u+0.13*v, 0.61*u, 0.82*u])
        else:
            pts = np.array([0.18*u, 0.35*u, 0.52*u, 0.69*u, 0.82*u])
        ax.plot(pts[:,0], 0.08+pts[:,1], color=colors[idx], lw=5.2, solid_capstyle="butt",
                solid_joinstyle="round", zorder=5)
        if mode == "frequency":
            c = 0.55*u
            ax.add_patch(Circle((c[0], 0.08+c[1]), 0.12+0.015*idx, fc=colors[idx], ec="white", lw=0.4, zorder=6))
    ax.add_patch(Circle((0, 0.08), 0.15, fc="#f2b6bd", ec=RED, lw=0.6, zorder=7))
    ax.add_patch(Circle((0, 0.08), 0.052, fc=RED, ec="white", lw=0.3, zorder=8))
    if mode == "straight":
        title = ("Straight-path reference", "直通参考配置")
        result = ("shared-junction baseline", "共享汇合基线")
    elif mode == "heterogeneous":
        title = ("Heterogeneous paths", "异质声路配置")
        result = ("held-block BA = 0.250", "留块 BA = 0.250")
    else:
        title = ("Frequency-selective", "选频配置")
        result = ("0/4 bands ranked first", "0/4 频带排名第一")
    tx(ax, 0, 1.24, *title, zh, ha="center", va="top", fontsize=8.1, fontweight="bold", color=INK)


def draw_integrated(ax, zh=False):
    ax.set_aspect("equal")
    ax.set_xlim(-1.23, 1.23)
    ax.set_ylim(-1.08, 1.35)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((-0.53, -0.97), 1.06, 1.94, boxstyle="round,pad=0.04,rounding_size=0.22",
                                fc=SHELL, ec=SHELL_EDGE, lw=0.75))
    ax.plot([0, 0], [0.11, 0.87], color=GREEN, lw=8.0, solid_capstyle="butt", zorder=4)
    ax.plot([0, 0], [-0.11, -0.87], color=MAGENTA, lw=8.0, solid_capstyle="butt", zorder=4)
    ax.add_patch(Circle((0, 0.52), 0.20, fc=GREEN, ec="white", lw=0.5, zorder=5))
    ax.add_patch(Circle((0, -0.52), 0.14, fc=MAGENTA, ec="white", lw=0.5, zorder=5))
    ax.add_patch(Circle((0, 0), 0.13, fc="#f2b6bd", ec=RED, lw=0.6, zorder=6))
    ax.add_patch(Circle((0, 0), 0.047, fc=RED, ec="white", lw=0.3, zorder=7))
    ax.annotate("", xy=(0.18, 0), xytext=(0.57, 0), arrowprops=dict(arrowstyle="->", lw=0.7, color=MUTED))
    tx(ax, 0.63, 0, "junction\ncavity", "麦克风\n汇合腔", zh, ha="left", va="center", fontsize=7.3, color=MUTED)
    tx(ax, 0, 1.24, "Two-branch device", "双支路装置", zh, ha="center", va="top", fontsize=8.1,
       fontweight="bold", color=INK)


def physical_figure(out_dir: Path, zh=False):
    fig = plt.figure(figsize=(7.16, 4.48), constrained_layout=True, facecolor="white")
    gs = fig.add_gridspec(2, 12, height_ratios=(1.0, 0.98))
    a = fig.add_subplot(gs[0, :6])
    b = fig.add_subplot(gs[0, 6:])
    draw_setup(a, zh)
    draw_photo(b, zh)
    axes = [fig.add_subplot(gs[1, 0:3]), fig.add_subplot(gs[1, 3:6]),
            fig.add_subplot(gs[1, 6:9]), fig.add_subplot(gs[1, 9:12])]
    draw_small_head(axes[0], "straight", zh)
    draw_small_head(axes[1], "heterogeneous", zh)
    draw_small_head(axes[2], "frequency", zh)
    draw_integrated(axes[3], zh)
    # The lower row is one architecture progression panel with four subpanels.
    axes[0].text(-0.08, 1.04, "(c1)", transform=axes[0].transAxes, fontsize=8.6, fontweight="bold", **fk(zh))
    axes[1].text(-0.08, 1.04, "(c2)", transform=axes[1].transAxes, fontsize=8.6, fontweight="bold", **fk(zh))
    axes[2].text(-0.08, 1.04, "(c3)", transform=axes[2].transAxes, fontsize=8.6, fontweight="bold", **fk(zh))
    axes[3].text(-0.08, 1.04, "(d)", transform=axes[3].transAxes, fontsize=8.6, fontweight="bold", **fk(zh))
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "physical_workflow_and_architectures.png", dpi=450, bbox_inches="tight", pad_inches=0.015)
    fig.savefig(out_dir / "physical_workflow_and_architectures.pdf", bbox_inches="tight", pad_inches=0.015)
    plt.close(fig)


def nonwhite_crop(path: Path, threshold=246, padding=14):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im)
    mask = np.any(a < threshold, axis=2)
    ys, xs = np.where(mask)
    x0, x1 = max(0, xs.min() - padding), min(im.width, xs.max() + padding + 1)
    y0, y1 = max(0, ys.min() - padding), min(im.height, ys.max() + padding + 1)
    return im.crop((x0, y0, x1, y1))


def fullwave_figure(out_dir: Path, zh=False):
    # Crop only exported white margins.  The model geometry and field pixels
    # remain unchanged; a larger, typeset colour bar replaces the small COMSOL
    # screen legend so labels remain legible at IEEE page width.
    mesh = Image.open(MESH).convert("RGB").crop((120, 145, 660, 475))
    field = Image.open(FIELD).convert("RGB").crop((105, 155, 665, 480))
    fig = plt.figure(figsize=(7.16, 2.72), facecolor="white")
    axes = [fig.add_axes((0.02, 0.08, 0.41, 0.80)), fig.add_axes((0.46, 0.08, 0.445, 0.80))]
    for ax in axes:
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color("#cbd1d6")
            s.set_linewidth(0.7)
    def place_preserving_aspect(ax, im):
        pos = ax.get_position()
        axis_ratio = (pos.width * fig.get_figwidth()) / (pos.height * fig.get_figheight())
        image_ratio = im.width / im.height
        if image_ratio >= axis_ratio:
            h = axis_ratio / image_ratio
            extent = (0.0, 1.0, (1.0-h)/2.0, (1.0+h)/2.0)
        else:
            w = image_ratio / axis_ratio
            extent = ((1.0-w)/2.0, (1.0+w)/2.0, 0.0, 1.0)
        ax.imshow(im, extent=extent, aspect="auto")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    place_preserving_aspect(axes[0], mesh)
    place_preserving_aspect(axes[1], field)
    axes[0].set_title("(a) Stored computational mesh" if not zh else "(a) 已存储计算网格",
                      fontsize=8.8, pad=3, **fk(zh))
    axes[1].set_title("(b) Pressure magnitude at 954 Hz ($\\alpha=0.05$)" if not zh else
                      "(b) 954 Hz 压力幅值（$\\alpha=0.05$）", fontsize=8.8, pad=3, **fk(zh))
    tx(axes[0], 0.06, 0.10, "lossy 3-D full-wave domain", "有损三维全波域", zh,
       transform=axes[0].transAxes, ha="left", va="bottom", fontsize=7.8, color=INK,
       bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="none", alpha=0.88))
    tx(axes[1], 0.05, 0.08, "active input: port 270° (source 3)", "主动输入：270°端口（源3）", zh,
       transform=axes[1].transAxes, ha="left", va="bottom", fontsize=7.8, color=INK,
       bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="none", alpha=0.90))
    axes[1].annotate("", xy=(0.75, 0.28), xytext=(0.57, 0.14), xycoords="axes fraction",
                     arrowprops=dict(arrowstyle="->", lw=0.85, color=MUTED))
    thermal = LinearSegmentedColormap.from_list(
        "comsol_thermal_like", ("#6b0000", "#d01800", "#ff6b00", "#ffd600", "#ffffb8")
    )
    cax = fig.add_axes((0.925, 0.13, 0.018, 0.68))
    cb = fig.colorbar(ScalarMappable(norm=Normalize(0, 2000), cmap=thermal), cax=cax)
    cb.set_ticks((0, 500, 1000, 1500, 2000))
    cb.ax.tick_params(labelsize=7.8, length=2.5, width=0.55)
    cb.outline.set_linewidth(0.6)
    cb.ax.set_title("$|p|$ (Pa)", fontsize=8.0, pad=3)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "fullwave_model_and_field.png", dpi=450, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(out_dir / "fullwave_model_and_field.pdf", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    for language, zh in (("english", False), ("chinese", True)):
        out = ROOT / language / "figures"
        physical_figure(out, zh)
        fullwave_figure(out, zh)
