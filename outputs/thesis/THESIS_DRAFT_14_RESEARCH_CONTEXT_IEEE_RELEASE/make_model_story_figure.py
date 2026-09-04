"""Create four bilingual IEEE-sized figures from frozen model summaries.

The script only redraws archived results. It does not execute a solver,
change a response, search a parameter, or read sealed final-test data.
"""

from pathlib import Path
import json

import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.font_manager import FontProperties
import numpy as np


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
SUMMARY = ROOT / "outputs" / "gen_enc" / "GEN_ENC_33_PAPER_SECTION_SYNTHESIS" / "result_summary.json"
ZH_FONT = FontProperties(
    fname=r"C:\Users\Firefly\AppData\Local\Programs\MiKTeX\fonts\opentype\public\fandol\fandolsong-regular.otf"
)

BLUE = "#2b6cb0"
ORANGE = "#dd6b20"
GREEN = "#2f855a"
RED = "#c53030"
GREY = "#68737d"
GRID = "#cbd5e0"
FILLER = "#a0aec0"


def kw(zh=False):
    return {"fontproperties": ZH_FONT} if zh else {}


def legend_font(zh=False, size=8.0):
    return FontProperties(fname=ZH_FONT.get_file(), size=size) if zh else None


def style_axes(ax, zh=False):
    ax.tick_params(labelsize=9.0, width=0.7, length=3)
    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        if zh:
            tick.set_fontproperties(ZH_FONT)
    for spine in ax.spines.values():
        spine.set_linewidth(0.7)


def save(fig, out_dir, stem):
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{stem}.png", dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(out_dir / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def family_overlap(out_dir, zh=False):
    fig, ax = plt.subplots(figsize=(3.45, 2.30), constrained_layout=True)
    names = (["有效几何", "局部无噪声\n声学签名", "中央读出"] if zh else
             ["Effective\ngeometry", "Local noiseless\nacoustics", "Central\nreadout"])
    values = np.array([0.316132, 0.118752, 0.036682])
    y = np.arange(3)
    ax.barh(y, values, color=[GREEN, BLUE, RED], height=0.55)
    ax.axvline(1.0, color="#111111", lw=1.0, ls="--")
    ax.set_xlim(0, 1.06)
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xlabel("最小家族间/家族内比" if zh else
                  "Minimum between-/within-family ratio", fontsize=9.2, **kw(zh))
    for yi, value in zip(y, values):
        ax.text(value + 0.025, yi, f"{value:.3f}", va="center", ha="left",
                fontsize=9.0, fontweight="bold")
    ax.text(0.99, 0.96, "可分阈值 = 1" if zh else "separation threshold = 1",
            ha="right", va="top", fontsize=8.4, transform=ax.transAxes, **kw(zh))
    ax.grid(axis="x", color=GRID, lw=0.5, alpha=0.75)
    style_axes(ax, zh)
    save(fig, out_dir, "family_overlap")


def fullwave_geometry(out_dir, zh=False):
    fig, ax = plt.subplots(figsize=(3.45, 2.55), constrained_layout=True)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 70)
    ax.axis("off")

    ax.text(22, 67, "俯视图" if zh else "top view", ha="center", va="center",
            fontsize=8.5, fontweight="bold", **kw(zh))
    ax.text(76, 67, "侧视图" if zh else "side view", ha="center", va="center",
            fontsize=8.5, fontweight="bold", **kw(zh))
    px, py, size = 5, 19, 34
    ax.add_patch(patches.Rectangle((px, py), size, size, fc="#d9f0ff", ec=GREY, lw=1.0))
    corner = 8.0
    for x, y in ((px, py), (px + size - corner, py),
                 (px, py + size - corner), (px + size - corner, py + size - corner)):
        ax.add_patch(patches.Rectangle((x, y), corner, corner, fc=FILLER,
                                       ec="white", lw=0.6))
    for x1, y1, x2, y2 in ((px + size/2, py + size, px + size/2, py + size + 6),
                           (px + size/2, py, px + size/2, py - 6),
                           (px, py + size/2, px - 4, py + size/2),
                           (px + size, py + size/2, px + size + 5, py + size/2)):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", lw=1.0, color=BLUE))
    ax.add_patch(patches.Circle((px + size/2, py + size/2), 1.8,
                                fc=RED, ec="white", lw=0.7))
    ax.text(px + size/2, 11, "中央点读出" if zh else "central-point readout",
            ha="center", va="center", fontsize=8.4, **kw(zh))
    ax.text(px + size/2, 61, "四个边界激励" if zh else "four boundary excitations",
            ha="center", va="center", fontsize=8.3, **kw(zh))

    sx = 56
    ax.add_patch(patches.Rectangle((sx, 17), 38, 8, fc="#d9f0ff", ec=GREY, lw=1.0))
    ax.add_patch(patches.Rectangle((sx + 16.5, 25), 3.2, 17, fc=BLUE, ec=GREY, lw=0.8))
    ax.add_patch(patches.Rectangle((sx + 9, 42), 18, 16, fc="#b7e4c7", ec=GREY, lw=1.0))
    ax.text(sx + 19, 11, "36.21×36.21×9.2 mm汇流腔" if zh else
            "36.21 x 36.21 x 9.2 mm plenum",
            ha="center", va="center", fontsize=8.1, **kw(zh))
    ax.text(sx + 19, 32, "2×4×9 mm颈管" if zh else "2 x 4 x 9 mm neck",
            ha="center", va="center", fontsize=8.2, **kw(zh))
    ax.text(sx + 18, 62, "17×17 mm侧腔" if zh else "17 x 17 mm side cavity",
            ha="center", va="center", fontsize=8.2, **kw(zh))
    ax.text(98, 3, "非按比例" if zh else "not to scale",
            ha="right", va="center", fontsize=7.9, color=GREY, **kw(zh))
    save(fig, out_dir, "fullwave_geometry")


def five_level_tracking(out_dir, cases, zh=False):
    fig, ax = plt.subplots(figsize=(3.45, 2.55), constrained_layout=True)
    alphas = np.array([c["alpha"] for c in cases])
    targets = np.array([c["target_hz"] for c in cases])
    tracked = np.array([c["tracked_hz"] for c in cases])
    ax.plot(alphas, targets, "s--", color=GREY, lw=1.3, ms=5.0,
            label="目标" if zh else "Target")
    ax.plot(alphas, tracked, "o-", color=BLUE, lw=1.6, ms=5.8,
            label="全波跟踪" if zh else "Full-wave tracked")
    blind = np.isin(alphas, [0.04, 0.06])
    ax.scatter(alphas[blind], tracked[blind], s=68, facecolors="white",
               edgecolors=ORANGE, linewidths=1.5, zorder=5,
               label="盲测中间档" if zh else "Blind intermediate")
    for alpha, value in zip(alphas, tracked):
        ax.text(alpha, value + 22, f"{int(value)}", ha="center", va="bottom", fontsize=8.7)
    ax.set_xlim(0.027, 0.073)
    ax.set_ylim(700, 1220)
    ax.set_xlabel(r"编码参数 $\alpha$" if zh else r"Encoded parameter $\alpha$",
                  fontsize=9.2, **kw(zh))
    ax.set_ylabel("频率 (Hz)" if zh else "Frequency (Hz)", fontsize=9.2, **kw(zh))
    ax.text(0.029, 718, "最大误差10 Hz；$R^2=0.999694$" if zh else
            "maximum error 10 Hz; $R^2=0.999694$", ha="left", va="bottom",
            fontsize=8.5, **kw(zh))
    ax.legend(loc="upper right", frameon=False, fontsize=8.0, handlelength=1.8,
              prop=legend_font(zh, 8.0))
    ax.grid(color=GRID, lw=0.5, alpha=0.75)
    style_axes(ax, zh)
    save(fig, out_dir, "five_level_tracking")


def tolerance_intervals(out_dir, intervals, zh=False):
    fig, ax = plt.subplots(figsize=(3.45, 2.55), constrained_layout=True)
    intervals = list(reversed(intervals))
    y = np.arange(len(intervals))
    low = np.array([c["low_corner"]["tracked_hz"] for c in intervals])
    high = np.array([c["high_corner"]["tracked_hz"] for c in intervals])
    nominal = np.array([c["nominal_hz"] for c in intervals])
    target = np.array([c["target_hz"] for c in intervals])
    xerr = np.vstack([nominal - low, high - nominal])
    ax.errorbar(nominal, y, xerr=xerr, fmt="o", color=BLUE, ecolor=BLUE,
                elinewidth=3.0, capsize=4.0, ms=5.4,
                label="有界区间" if zh else "Bounded interval")
    ax.scatter(target, y, marker="D", s=34, color=ORANGE, zorder=5,
               label="目标" if zh else "Target")
    for lo, hi, yi in zip(low, high, y):
        ax.text((lo + hi) / 2, yi + 0.20, f"{int(lo)}-{int(hi)}",
                ha="center", va="bottom", fontsize=8.4)
    ax.set_yticks(y, [rf"$\alpha={c['alpha']:.02f}$" for c in intervals])
    ax.set_xlim(670, 1225)
    ax.set_ylim(-0.65, 4.65)
    ax.set_xlabel("跟踪频率 (Hz)" if zh else "Tracked frequency (Hz)",
                  fontsize=9.2, **kw(zh))
    ax.legend(loc="lower right", frameon=False, fontsize=8.0, handlelength=1.8,
              prop=legend_font(zh, 8.0))
    ax.grid(axis="x", color=GRID, lw=0.5, alpha=0.75)
    style_axes(ax, zh)
    save(fig, out_dir, "tolerance_intervals")


def generate(out_dir, zh=False):
    data = json.loads(SUMMARY.read_text(encoding="utf-8"))
    family_overlap(out_dir, zh)
    fullwave_geometry(out_dir, zh)
    five_level_tracking(out_dir, data["five_level"]["cases"], zh)
    tolerance_intervals(out_dir, data["tolerance"]["intervals"], zh)


if __name__ == "__main__":
    generate(PACKAGE / "english" / "figures", zh=False)
    generate(PACKAGE / "chinese" / "figures", zh=True)
