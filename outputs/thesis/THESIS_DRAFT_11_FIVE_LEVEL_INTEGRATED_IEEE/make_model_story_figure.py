"""Create bilingual journal figures from frozen model summaries only.

This script redraws existing diagnostic and full-wave results.  It does not
run a solver, alter a response, search a parameter, or read final-test data.
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
LIGHT = "#edf2f7"
FILLER = "#a0aec0"


def kw(zh=False):
    return {"fontproperties": ZH_FONT} if zh else {}


def label(ax, x, y, text, zh=False, **kwargs):
    options = dict(ha="center", va="center", fontsize=8.3, color="#20252b")
    options.update(kwargs)
    ax.text(x, y, text, **options, **kw(zh))


def style_axes(ax, zh=False):
    ax.tick_params(labelsize=8.2, width=0.7, length=3)
    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        if zh:
            tick.set_fontproperties(ZH_FONT)
    for spine in ax.spines.values():
        spine.set_linewidth(0.7)


def diagnostic_panel(ax, zh=False):
    names = (["有效几何", "局部无噪声声学", "中央读出"] if zh else
             ["Effective geometry", "Local noiseless acoustics", "Central readout"])
    values = np.array([0.316132, 0.118752, 0.036682])
    colors = [GREEN, BLUE, RED]
    y = np.arange(3)
    ax.barh(y, values, color=colors, height=0.55)
    ax.axvline(1.0, color="#111111", lw=1.0, ls="--")
    ax.set_xlim(0, 1.08)
    ax.set_yticks(y, names)
    ax.invert_yaxis()
    ax.set_xlabel("最小家族间/家族内比" if zh else "Minimum between-/within-family ratio",
                  fontsize=8.6, **kw(zh))
    ax.set_title("(a) 家族标签在有效声学空间中重叠" if zh else
                 "(a) Family labels overlap\nin effective acoustic space",
                 fontsize=8.8, pad=4, **kw(zh))
    for yi, value in zip(y, values):
        ax.text(value + 0.018, yi, f"{value:.3f}", va="center", ha="left",
                fontsize=8.2, fontweight="bold")
    ax.text(0.97, 0.97, "可分阈值 = 1" if zh else "separation threshold = 1",
            ha="right", va="top", fontsize=7.7, transform=ax.transAxes, **kw(zh))
    ax.text(0.54, 1.58, ("80/80模型可行，但未形成稳定家族分离" if zh else
                         "80/80 model-feasible, but no stable family separation"),
            ha="center", va="center", fontsize=7.7, color="#20252b",
            bbox=dict(boxstyle="round,pad=0.22", fc="#fff7d6", ec="#9b7b16", lw=0.6),
            **kw(zh))
    ax.grid(axis="x", color="#cbd5e0", lw=0.5, alpha=0.7)
    style_axes(ax, zh)


def geometry_panel(ax, zh=False):
    ax.set_title("(b) 以专属局部共振坐标重新设计" if zh else
                 "(b) Redesign around a\ndedicated local resonance",
                 fontsize=8.8, pad=4, **kw(zh))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 70)
    ax.axis("off")

    # Top view: 36.205 mm square plenum with four full-height corner fillers.
    px, py, size = 7, 16, 35
    ax.add_patch(patches.Rectangle((px, py), size, size, fc="#d9f0ff", ec=GREY, lw=1.0))
    corner = 8.3
    for x, y in ((px, py), (px + size - corner, py),
                 (px, py + size - corner), (px + size - corner, py + size - corner)):
        ax.add_patch(patches.Rectangle((x, y), corner, corner, fc=FILLER, ec="white", lw=0.6))
    for x1, y1, x2, y2 in ((px + size/2, py + size, px + size/2, py + size + 5),
                           (px + size/2, py, px + size/2, py - 5),
                           (px, py + size/2, px - 5, py + size/2),
                           (px + size, py + size/2, px + size + 5, py + size/2)):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", lw=1.0, color=BLUE))
    ax.add_patch(patches.Circle((px + size/2, py + size/2), 1.8, fc=RED, ec="white", lw=0.7))
    label(ax, px + size/2, py + size/2 - 7,
          "中央点读出" if zh else "central-point readout", zh, fontsize=7.6)
    label(ax, 19, 61 if zh else 55,
          "四个边界激励" if zh else "four boundary\nexcitations", zh, fontsize=7.2)
    label(ax, px + size/2, 6,
          "36.21 mm方形汇流腔；四角等体积补偿" if zh else
          "36.21-mm square plenum; four-corner volume compensation",
          zh, fontsize=7.5)

    # Side view: full-height plenum, out-of-plane neck and top cavity.
    sx = 59
    ax.add_patch(patches.Rectangle((sx, 14), 31, 8, fc="#d9f0ff", ec=GREY, lw=1.0))
    ax.add_patch(patches.Rectangle((sx + 13.5, 22), 3, 17, fc=BLUE, ec=GREY, lw=0.8))
    ax.add_patch(patches.Rectangle((sx + 8, 39), 14, 16, fc="#b7e4c7", ec=GREY, lw=1.0))
    label(ax, sx + 15, 9, "汇流腔高 9.2 mm" if zh else "9.2-mm plenum height", zh, fontsize=7.3)
    label(ax, 82, 30, "2×4 mm截面\n9.00 mm物理颈长" if zh else
          "2 x 4 mm section\n9.00-mm physical neck", zh, ha="left", fontsize=7.4)
    label(ax, 78, 62 if zh else 64, "17×17 mm侧腔平面\n体积设定目标频率" if zh else
          "17 x 17 mm cavity footprint\nvolume sets target frequency", zh, fontsize=7.4)
    label(ax, 75, 3.5, "示意图，非按比例" if zh else "schematic, not to scale", zh,
          fontsize=7.2, color=GREY)


def mapping_panel(ax, cases, zh=False):
    alphas = np.array([c["alpha"] for c in cases])
    targets = np.array([c["target_hz"] for c in cases])
    tracked = np.array([c["tracked_hz"] for c in cases])
    ax.plot(alphas, targets, "s--", color=GREY, lw=1.3, ms=5.0,
            label="目标" if zh else "Target")
    ax.plot(alphas, tracked, "o-", color=BLUE, lw=1.5, ms=5.5,
            label="全波跟踪" if zh else "Full-wave tracked")
    blind = np.isin(alphas, [0.04, 0.06])
    ax.scatter(alphas[blind], tracked[blind], s=62, facecolors="white", edgecolors=ORANGE,
               linewidths=1.5, zorder=5, label="盲测中间档" if zh else "Blind intermediate")
    for alpha, f in zip(alphas, tracked):
        ax.text(alpha, f + 19, f"{int(f)}", ha="center", va="bottom", fontsize=7.8)
    ax.set_xlim(0.0275, 0.0725)
    ax.set_ylim(700, 1215)
    ax.set_xlabel(r"编码参数 $\alpha$" if zh else r"Encoded parameter $\alpha$",
                  fontsize=8.6, **kw(zh))
    ax.set_ylabel("频率 (Hz)" if zh else "Frequency (Hz)", fontsize=8.6, **kw(zh))
    ax.set_title("(c) 冻结后五档单调跟踪" if zh else
                 "(c) Frozen five-level\nmonotonic tracking", fontsize=8.8, pad=4, **kw(zh))
    ax.text(0.029, 725, ("最大误差 10 Hz；$R^2=0.999694$" if zh else
                         "maximum error 10 Hz; $R^2=0.999694$"),
            ha="left", va="bottom", fontsize=7.8, **kw(zh))
    ax.grid(color="#cbd5e0", lw=0.5, alpha=0.75)
    ax.text(0.98, 0.96,
            ("实心：公开档\n空心：盲测档\n虚线：目标" if zh else
             "filled: public\nopen: blind\ndashed: target"),
            transform=ax.transAxes, ha="right", va="top", fontsize=7.0, **kw(zh))
    style_axes(ax, zh)


def tolerance_panel(ax, intervals, zh=False):
    intervals = list(reversed(intervals))
    y = np.arange(len(intervals))
    low = np.array([c["low_corner"]["tracked_hz"] for c in intervals])
    high = np.array([c["high_corner"]["tracked_hz"] for c in intervals])
    nominal = np.array([c["nominal_hz"] for c in intervals])
    target = np.array([c["target_hz"] for c in intervals])
    xerr = np.vstack([nominal - low, high - nominal])
    ax.errorbar(nominal, y, xerr=xerr, fmt="o", color=BLUE, ecolor=BLUE,
                elinewidth=3.1, capsize=4.0, ms=5.2, label="有界区间" if zh else "Bounded interval")
    ax.scatter(target, y, marker="D", s=31, color=ORANGE, zorder=5,
               label="目标" if zh else "Target")
    for lo, hi, yi in zip(low, high, y):
        ax.text(lo - 7, yi, f"{int(lo)}", ha="right", va="center", fontsize=7.6)
        ax.text(hi + 7, yi, f"{int(hi)}", ha="left", va="center", fontsize=7.6)
    ax.set_yticks(y, [rf"$\alpha={c['alpha']:.02f}$" for c in intervals])
    ax.set_xlim(700, 1225)
    ax.set_ylim(-0.65, 4.65)
    ax.set_xlabel("跟踪频率 (Hz)" if zh else "Tracked frequency (Hz)",
                  fontsize=8.6, **kw(zh))
    ax.set_title("(d) 有效几何公差角点仍保持分离" if zh else
                 "(d) Effective-geometry tolerance\ncorners remain separated",
                 fontsize=8.8, pad=4, **kw(zh))
    ax.text(712, 4.34, ("全部区间互不重叠；最小净间隔 26 Hz" if zh else
                        "all intervals disjoint; minimum residual gap 26 Hz"),
            ha="left", va="top", fontsize=7.8, **kw(zh))
    ax.grid(axis="x", color="#cbd5e0", lw=0.5, alpha=0.75)
    ax.text(0.98, 0.05,
            ("菱形：目标\n横线：有界区间" if zh else
             "diamond: target\nbar: bounded interval"),
            transform=ax.transAxes, ha="right", va="bottom", fontsize=7.0, **kw(zh))
    style_axes(ax, zh)


def generate(out_dir, zh=False):
    data = json.loads(SUMMARY.read_text(encoding="utf-8"))
    fig, axes = plt.subplots(2, 2, figsize=(7.15, 6.20), constrained_layout=True)
    diagnostic_panel(axes[0, 0], zh)
    geometry_panel(axes[0, 1], zh)
    mapping_panel(axes[1, 0], data["five_level"]["cases"], zh)
    tolerance_panel(axes[1, 1], data["tolerance"]["intervals"], zh)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "model_diagnosis_and_five_level_design.png", dpi=500,
                bbox_inches="tight", facecolor="white")
    fig.savefig(out_dir / "model_diagnosis_and_five_level_design.pdf",
                bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    generate(PACKAGE / "english" / "figures", zh=False)
    generate(PACKAGE / "chinese" / "figures", zh=True)
