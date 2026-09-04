"""Rebuild Figure 1 from the archived print-package geometry definitions.

The common-head panels reproduce the millimetre coordinates frozen in the
V2.0.1 and V2.5 generators. The integrated panel reproduces the frozen V1
airspace and the component construction of the V1C compact outer silhouette.
This script performs drawing only; it does not run an acoustic model.
"""

from pathlib import Path
import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle


ROOT = Path(__file__).resolve().parent
OUT_EN = ROOT / "english" / "figures"
OUT_ZH = ROOT / "chinese" / "figures"
ZH_FONT = FontProperties(
    fname=r"C:\Users\Firefly\AppData\Local\Programs\MiKTeX\fonts\opentype\public\fandol\fandolsong-regular.otf"
)

SHELL = "#e5e7e9"
SHELL_EDGE = "#59636e"
AIR = "#2b83ba"
STRAIGHT = "#2b83ba"
SERPENTINE = "#4daf8a"
BRANCH = "#8c6bb1"
EXPANSION = "#d95f9f"
MIC = "#b23a48"
DUMMY = "#bfc5ca"
HR_COLORS = {
    "HR01": "#2b83ba",
    "HR03": "#4daf8a",
    "HR05": "#8c6bb1",
    "HR07": "#d95f9f",
}

APOTHEM = 105.0
CORNER_RADIUS = APOTHEM / math.cos(math.pi / 8.0)
MODULE_CENTRE_RADIUS = 60.0
X0, X1 = -28.6, 28.6


def font_kwargs(zh=False):
    return {"fontproperties": ZH_FONT} if zh else {}


def xy_local(points, angle_deg, radius=MODULE_CENTRE_RADIUS):
    """Map local +x outward to archive angle convention: 0 deg=N, 90 deg=E."""
    theta = math.radians(angle_deg)
    outward = np.array([math.sin(theta), math.cos(theta)])
    lateral = np.array([math.cos(theta), -math.sin(theta)])
    centre = radius * outward
    return np.asarray([centre + x * outward + y * lateral for x, y in points])


def octagon_points():
    angles = np.deg2rad([22.5 + 45.0 * i for i in range(8)])
    return np.column_stack((CORNER_RADIUS * np.cos(angles), CORNER_RADIUS * np.sin(angles)))


def radial_polygon(r0, r1, width0, width1, angle_deg):
    theta = math.radians(angle_deg)
    u = np.array([math.sin(theta), math.cos(theta)])
    v = np.array([math.cos(theta), -math.sin(theta)])
    return np.asarray([
        r0 * u + width0 / 2.0 * v,
        r1 * u + width1 / 2.0 * v,
        r1 * u - width1 / 2.0 * v,
        r0 * u - width0 / 2.0 * v,
    ])


def add_polygon(ax, points, color, edge="none", lw=0.0, z=3, hatch=None):
    ax.add_patch(Polygon(points, closed=True, facecolor=color, edgecolor=edge,
                         linewidth=lw, hatch=hatch, zorder=z))


def add_local_box(ax, x0, y0, x1, y1, angle, color, z=4, edge="none", lw=0.0):
    points = xy_local([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], angle)
    add_polygon(ax, points, color, edge=edge, lw=lw, z=z)


def add_local_taper(ax, x0, x1, w0, w1, angle, color, z=4):
    points = xy_local([(x0, w0 / 2), (x1, w1 / 2),
                       (x1, -w1 / 2), (x0, -w0 / 2)], angle)
    add_polygon(ax, points, color, z=z)


def rounded_rect_points(x0, y0, x1, y1, radius):
    points = []
    for cx, cy, start, stop in [
        (x1 - radius, y1 - radius, 0, 90),
        (x0 + radius, y1 - radius, 90, 180),
        (x0 + radius, y0 + radius, 180, 270),
        (x1 - radius, y0 + radius, 270, 360),
    ]:
        for degrees in np.linspace(start, stop, 8, endpoint=False):
            points.append((cx + radius * math.cos(math.radians(degrees)),
                           cy + radius * math.sin(math.radians(degrees))))
    return points


def add_local_rounded_rect(ax, x0, y0, x1, y1, radius, angle, color, z=4):
    add_polygon(ax, xy_local(rounded_rect_points(x0, y0, x1, y1, radius), angle),
                color, z=z)


def data_linewidth(ax, width_mm):
    """Convert millimetres in data coordinates to typographic points."""
    fig = ax.figure
    fig.canvas.draw()
    p0 = ax.transData.transform((0.0, 0.0))
    p1 = ax.transData.transform((width_mm, 0.0))
    return abs(p1[0] - p0[0]) * 72.0 / fig.dpi


def add_local_polyline(ax, points, width, angle, color, z=5):
    global_points = xy_local(points, angle)
    ax.plot(global_points[:, 0], global_points[:, 1], color=color,
            linewidth=data_linewidth(ax, width), solid_capstyle="butt",
            solid_joinstyle="round", zorder=z)


def setup_head(ax, title, zh=False):
    ax.set_aspect("equal")
    ax.set_xlim(-127, 127)
    ax.set_ylim(-137, 127)
    ax.axis("off")
    add_polygon(ax, octagon_points(), SHELL, edge=SHELL_EDGE, lw=0.75, z=0)
    ax.set_title(title, fontsize=9.5, pad=2, **font_kwargs(zh))


def draw_module_envelope(ax, angle):
    body = xy_local([(-28.6, -8.5), (28.6, -18.0),
                     (28.6, 18.0), (-28.6, 8.5)], angle)
    add_polygon(ax, body, "none", edge="#9aa2aa", lw=0.35, z=2)


def draw_open_interface(ax, angle, color):
    add_polygon(ax, radial_polygon(17.0, 32.0, 8.0, 8.0, angle), color, z=3)
    add_polygon(ax, radial_polygon(88.0, 105.0, 8.0, 16.0, angle), color, z=3)


def draw_dummy(ax, angle):
    # P09 is a solid insert.  Show the absence of an air path rather than a
    # grey tube, and retain only the outer sealed face as a visible cue.
    add_polygon(ax, radial_polygon(91.0, 105.0, 12.5, 15.0, angle), DUMMY,
                edge="#757d85", lw=0.45, z=2)
    add_polygon(ax, radial_polygon(89.2, 91.3, 12.2, 12.2, angle), "#737b83",
                edge="#59636e", lw=0.35, z=3)


def draw_central_chamber(ax):
    ax.add_patch(Circle((0, 0), 18.0, facecolor=AIR, edgecolor="none", zorder=3))
    ax.add_patch(Circle((0, 0), 3.0, facecolor=MIC, edgecolor="white",
                        linewidth=0.45, zorder=8))


def label_cardinal(ax, angle, text, zh=False, radius=77, color="#222222"):
    theta = math.radians(angle)
    x, y = radius * math.sin(theta), radius * math.cos(theta)
    ax.text(x, y, text, ha="center", va="center", fontsize=8.4, color=color,
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.82),
            zorder=10, **font_kwargs(zh))


def add_orientation_and_scale(ax, zh=False, show_scale=True):
    ax.annotate("", xy=(-108, 108), xytext=(-108, 88),
                arrowprops=dict(arrowstyle="-|>", lw=0.65, color="#333333"), zorder=12)
    ax.text(-108, 112, "北" if zh else "N", ha="center", va="bottom",
            fontsize=8.3, **font_kwargs(zh))
    if show_scale:
        ax.plot([-112, -62], [-128, -128], color="#222222", lw=1.1, zorder=12)
        ax.plot([-112, -112], [-131, -125], color="#222222", lw=0.7, zorder=12)
        ax.plot([-62, -62], [-131, -125], color="#222222", lw=0.7, zorder=12)
        ax.text(-87, -124, "50 mm", ha="center", va="bottom", fontsize=8.1)


def add_outcome(ax, text, zh=False):
    """Place one high-level result inside each panel without obscuring geometry."""
    ax.text(16, -111, text, ha="center", va="center", fontsize=8.1,
            color="#111111", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.22", fc="#fff7d6", ec="#9b7b16",
                      lw=0.55, alpha=0.96), zorder=20, **font_kwargs(zh))


def draw_reference(ax, zh=False):
    setup_head(ax, "(a) 四支路直通参考" if zh else "(a) Four-branch straight reference", zh)
    for angle in (45, 135, 225, 315):
        draw_dummy(ax, angle)
    for angle in (0, 90, 180, 270):
        draw_module_envelope(ax, angle)
        draw_open_interface(ax, angle, STRAIGHT)
        add_local_box(ax, X0, -4.7, X1, 4.7, angle, STRAIGHT)
        label_cardinal(ax, angle, "直通" if zh else "straight", zh)
    draw_central_chamber(ax)
    ax.annotate("密封的对角安装位" if zh else "sealed diagonal mount",
                xy=(-72, 72), xytext=(-112, 52), ha="left", va="center",
                fontsize=8.0, arrowprops=dict(arrowstyle="->", lw=0.55,
                                              color="#59636e"),
                color="#303840", zorder=15, **font_kwargs(zh))
    add_outcome(ax, "共同腔体与方向基线" if zh else "Common-cavity orientation baseline", zh)
    add_orientation_and_scale(ax, zh, show_scale=False)


def draw_broadband(ax, zh=False):
    setup_head(ax, "(b) 异质宽带四支路阵列" if zh else "(b) Heterogeneous broadband array", zh)
    for angle in (45, 135, 225, 315):
        draw_dummy(ax, angle)
    for angle in (0, 90, 180, 270):
        draw_module_envelope(ax, angle)

    # Archive mapping: N short straight, E serpentine,
    # S straight with folded side branch, W expansion + side branch.
    draw_open_interface(ax, 0, STRAIGHT)
    add_local_polyline(ax, [(X0, 0), (X1, 0)], 9.4, 0, STRAIGHT)
    label_cardinal(ax, 0, "短直通" if zh else "short straight", zh)

    draw_open_interface(ax, 90, SERPENTINE)
    serpentine = [(-28.6, 0), (-23, 0), (-18, 4.8), (-11, 4.8),
                  (-6, -4.8), (1, -4.8), (6, 4.8), (13, 4.8),
                  (18, -4.8), (24, -4.8), (28.6, 0)]
    add_local_polyline(ax, serpentine, 7.2, 90, SERPENTINE)
    label_cardinal(ax, 90, "蛇形" if zh else "serpentine", zh)

    draw_open_interface(ax, 180, BRANCH)
    add_local_polyline(ax, [(X0, 0), (X1, 0)], 9.0, 180, BRANCH)
    add_local_polyline(ax, [(8, 0), (8, 9), (22, 9), (22, 12.5), (24, 12.5)],
                       4.5, 180, BRANCH)
    label_cardinal(ax, 180, "折叠侧支" if zh else "folded side branch", zh)

    draw_open_interface(ax, 270, EXPANSION)
    add_local_polyline(ax, [(X0, 0), (-8, 0), (18, 0), (X1, 0)],
                       8.8, 270, EXPANSION)
    add_local_rounded_rect(ax, 5, -7, 19, 7, 2.5, 270, EXPANSION)
    add_local_polyline(ax, [(-5, 0), (-5, 8), (-1, 8), (1, 8)],
                       4.5, 270, EXPANSION)
    label_cardinal(ax, 270, "扩张腔+侧支" if zh else "expansion + branch", zh)
    draw_central_chamber(ax)
    add_outcome(ax, "留一采集块平衡准确率 = 0.250" if zh else "Held-block balanced accuracy = 0.250", zh)
    add_orientation_and_scale(ax, zh, show_scale=False)


HR_SPECS = {
    0: ("HR01", 1200, 4.0, 32.0, 19.0, 2.0, 2.4),
    90: ("HR03", 1850, 8.0, 26.0, 15.0, 2.8, 4.4),
    180: ("HR05", 2700, 5.0, 31.0, 7.0, 2.8, 5.6),
    270: ("HR07", 3800, 8.0, 23.0, 5.0, 2.8, 7.2),
}


def draw_hr_channel(ax, angle, spec, color, z=5):
    _, _, xc, length, width, inner_w, outer_w = spec
    x_left, x_right = xc - length / 2.0, xc + length / 2.0
    corner = min(1.2, width / 4.0)
    add_local_rounded_rect(ax, x_left, -width / 2.0, x_right, width / 2.0,
                           corner, angle, color, z=z)
    add_local_box(ax, -29.0, -4.0, -24.6, 4.0, angle, color, z=z)
    add_local_taper(ax, -24.6, -20.6, 8.0, inner_w, angle, color, z=z)
    add_local_box(ax, -20.6, -inner_w / 2.0, x_left + 0.15, inner_w / 2.0,
                  angle, color, z=z)
    add_local_box(ax, x_right - 0.15, -outer_w / 2.0, 21.0, outer_w / 2.0,
                  angle, color, z=z)
    add_local_taper(ax, 21.0, 25.0, outer_w, 8.0, angle, color, z=z)
    add_local_box(ax, 25.0, -4.0, 29.0, 4.0, angle, color, z=z)


def draw_frequency_array(ax, zh=False):
    setup_head(ax, "(c) 四支路双颈选频阵列" if zh else "(c) Four-branch two-neck array", zh)
    for angle in (45, 135, 225, 315):
        draw_dummy(ax, angle)
    for angle, spec in HR_SPECS.items():
        name, target, *_ = spec
        color = HR_COLORS[name]
        draw_module_envelope(ax, angle)
        draw_open_interface(ax, angle, color)
        draw_hr_channel(ax, angle, spec, color)
        label_cardinal(ax, angle, f"{target / 1000:.2f} kHz", zh, radius=78)
    draw_central_chamber(ax)
    add_outcome(ax, "0/4 预设方向频带排名第一" if zh else "0/4 assigned direction bands ranked first", zh)
    add_orientation_and_scale(ax, zh, show_scale=False)


def integrated_transform(points, north):
    angle = 0 if north else 180
    theta = math.radians(angle)
    u = np.array([math.sin(theta), math.cos(theta)])
    v = np.array([math.cos(theta), -math.sin(theta)])
    centre = np.array([0.0, 60.0 if north else -60.0])
    return np.asarray([centre + x * u + y * v for x, y in points])


def add_integrated_hr(ax, north, color, shell_layer=False):
    spec = HR_SPECS[90] if north else HR_SPECS[270]
    _, _, xc, length, width, inner_w, outer_w = spec
    x_left, x_right = xc - length / 2.0, xc + length / 2.0
    if shell_layer:
        pieces = [
            ([(-29, 0), (-24.6, 0)], 8),
            ([(-24.6, 0), (-20.6, 0)], 8),
            ([(-20.6, 0), (x_left + 0.15, 0)], inner_w),
            ([(x_right - 0.15, 0), (21, 0)], outer_w),
            ([(21, 0), (25, 0)], 8),
            ([(25, 0), (29, 0)], 8),
        ]
        for line, width0 in pieces:
            pts = integrated_transform(line, north)
            ax.plot(pts[:, 0], pts[:, 1], color=SHELL,
                    linewidth=data_linewidth(ax, width0 + 8),
                    solid_capstyle="round", zorder=1)
        centre = integrated_transform([(xc, 0)], north)[0]
        cavity_w = width
        cavity_h = length
        ax.add_patch(FancyBboxPatch((centre[0] - cavity_w / 2 - 4,
                                     centre[1] - cavity_h / 2 - 4),
                                    cavity_w + 8, cavity_h + 8,
                                    boxstyle="round,pad=0,rounding_size=5.2",
                                    facecolor=SHELL, edgecolor="none", zorder=1))
        return

    def poly(points):
        add_polygon(ax, integrated_transform(points, north), color, z=5)
    poly([(-29, -4), (-24.6, -4), (-24.6, 4), (-29, 4)])
    poly([(-24.6, -4), (-20.6, -inner_w/2), (-20.6, inner_w/2), (-24.6, 4)])
    poly([(-20.6, -inner_w/2), (x_left+0.15, -inner_w/2),
          (x_left+0.15, inner_w/2), (-20.6, inner_w/2)])
    poly(rounded_rect_points(x_left, -width/2, x_right, width/2,
                             min(1.2, width/4)))
    poly([(x_right-0.15, -outer_w/2), (21, -outer_w/2),
          (21, outer_w/2), (x_right-0.15, outer_w/2)])
    poly([(21, -outer_w/2), (25, -4), (25, 4), (21, outer_w/2)])
    poly([(25, -4), (29, -4), (29, 4), (25, 4)])


def draw_integrated(ax, zh=False):
    ax.set_aspect("equal")
    ax.set_xlim(-127, 127)
    ax.set_ylim(-137, 127)
    ax.axis("off")
    ax.set_title("(d) 一体化相对双通道装置" if zh else "(d) Integrated opposed two-channel device",
                 fontsize=9.5, pad=2, **font_kwargs(zh))

    # V1C outer construction: 50-mm hub, 4-mm branch envelope, ten bosses,
    # and 2-mm-radius structural spokes. Overdraw produces their union.
    ax.add_patch(Circle((0, 0), 50.0, facecolor=SHELL, edgecolor="none", zorder=0))
    screw_positions = [(-16, 0), (16, 0), (-14, 60), (14, 60),
                       (-14, -60), (14, -60), (-15, 104), (15, 104),
                       (-15, -104), (15, -104)]
    for x, y in screw_positions:
        ax.plot([0, x], [0, y], color=SHELL, linewidth=data_linewidth(ax, 4.0),
                solid_capstyle="round", zorder=0)
        ax.add_patch(Circle((x, y), 6.0, facecolor=SHELL, edgecolor="none", zorder=0))
    add_integrated_hr(ax, True, HR_COLORS["HR03"], shell_layer=True)
    add_integrated_hr(ax, False, HR_COLORS["HR07"], shell_layer=True)
    ax.add_patch(Rectangle((-8, 101), 16, 20, facecolor=SHELL, edgecolor="none", zorder=0))
    ax.add_patch(Rectangle((-8, -121), 16, 20, facecolor=SHELL, edgecolor="none", zorder=0))

    # Frozen V1 airspace: HR03 north, HR07 south, readout necks, horns, plenum.
    add_integrated_hr(ax, True, HR_COLORS["HR03"])
    add_integrated_hr(ax, False, HR_COLORS["HR07"])
    ax.add_patch(Rectangle((-4, 4.6), 8, 27.5, facecolor=HR_COLORS["HR03"], edgecolor="none", zorder=4))
    ax.add_patch(Rectangle((-4, -32.1), 8, 27.5, facecolor=HR_COLORS["HR07"], edgecolor="none", zorder=4))
    north_horn = [(-4, 88), (4, 88), (8, 105), (10, 117), (-10, 117), (-8, 105)]
    add_polygon(ax, north_horn, HR_COLORS["HR03"], z=4)
    add_polygon(ax, [(-x, -y) for x, y in north_horn], HR_COLORS["HR07"], z=4)
    ax.add_patch(Circle((0, 0), 5.2, facecolor="#f3b6bd", edgecolor=MIC,
                        linewidth=0.55, zorder=7))
    ax.add_patch(Circle((0, 0), 2.2, facecolor=MIC, edgecolor="white",
                        linewidth=0.4, zorder=8))
    ax.text(24, 61, "北通道 1.85 kHz" if zh else "north channel 1.85 kHz",
            ha="left", va="center", fontsize=8.3, color="#222222", **font_kwargs(zh))
    ax.text(24, -61, "南通道 3.80 kHz" if zh else "south channel 3.80 kHz",
            ha="left", va="center", fontsize=8.3, color="#222222", **font_kwargs(zh))
    ax.annotate("", xy=(7, 0), xytext=(40, 0),
                arrowprops=dict(arrowstyle="->", lw=0.55, color="#333333"), zorder=10)
    ax.text(42, 0, "麦克风微型汇合腔" if zh else "microphone microplenum",
            ha="left", va="center", fontsize=8.1, **font_kwargs(zh))
    add_outcome(ax, ("南北距离 2.069 dB > 回返 1.131 dB" if zh
                     else "N-S distance 2.069 dB > return 1.131 dB"), zh)
    add_orientation_and_scale(ax, zh, show_scale=False)


def generate(out_dir, zh=False):
    # IEEE page-width artwork: 7.15 in wide, with labels designed to render at
    # approximately 8--9.5 pt at final size.  The reduced depth leaves room for
    # prose and a caption on the same page.
    fig, axes = plt.subplots(2, 2, figsize=(7.15, 5.25), constrained_layout=True)
    draw_reference(axes[0, 0], zh)
    draw_broadband(axes[0, 1], zh)
    draw_frequency_array(axes[1, 0], zh)
    draw_integrated(axes[1, 1], zh)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "architecture_evolution.png", dpi=450,
                bbox_inches="tight", facecolor="white")
    fig.savefig(out_dir / "architecture_evolution.pdf",
                bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    generate(OUT_EN, zh=False)
    generate(OUT_ZH, zh=True)
