"""Redraw balanced manuscript figures from frozen evidence only.

This script performs presentation-only reanalysis. It does not run a solver,
change any measured or simulated result, search parameters, or read final-test
material.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np


PACKAGE = Path(__file__).resolve().parent
EVIDENCE = PACKAGE / "evidence"
ZH_FONT = FontProperties(
    fname=r"C:\Users\Firefly\AppData\Local\Programs\MiKTeX\fonts\opentype\public\fandol\fandolsong-regular.otf"
)

BLUE = "#2b6cb0"
ORANGE = "#dd6b20"
GREEN = "#2f855a"
RED = "#c53030"
GREY = "#66717e"
LIGHT = "#d9e2ec"
GRID = "#cbd5e0"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8.4,
        "axes.labelsize": 8.7,
        "xtick.labelsize": 8.0,
        "ytick.labelsize": 8.0,
        "legend.fontsize": 7.2,
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


def zh_kw(zh: bool) -> dict:
    return {"fontproperties": ZH_FONT} if zh else {}


def zh_legend(zh: bool, size: float = 7.2):
    if not zh:
        return None
    return FontProperties(fname=ZH_FONT.get_file(), size=size)


def style_axis(ax, zh: bool) -> None:
    ax.tick_params(width=0.7, length=3)
    for spine in ax.spines.values():
        spine.set_linewidth(0.7)
    if zh:
        for tick in ax.get_xticklabels() + ax.get_yticklabels():
            tick.set_fontproperties(ZH_FONT)


def save(fig, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{stem}.png", dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(out_dir / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def four_state_validation(out_dir: Path, zh: bool = False) -> None:
    gain_rows = rows(EVIDENCE / "four_state_direction_gain_summary.csv")
    selected = {
        row["configuration"]: row
        for row in gain_rows
        if row["assembly_scope"] == "AS01"
        and row["band_id"] == "primary"
        and row["normalization"] == "demeaned"
    }
    metric_rows = rows(EVIDENCE / "four_state_grouped_validation_metrics.csv")
    metrics = {
        row["configuration"]: row
        for row in metric_rows
        if row["assembly_scope"] == "AS01"
    }

    labels = (["直通参考", "异构支路"] if zh else
              ["Straight", "Heterogeneous"])
    codes = ["U4SYM", "U4ENC"]
    gain = np.array([float(selected[c]["gain"]) for c in codes])
    low = np.array([float(selected[c]["bootstrap_ci95_low"]) for c in codes])
    high = np.array([float(selected[c]["bootstrap_ci95_high"]) for c in codes])
    accuracy = np.array([float(metrics[c]["balanced_accuracy"]) for c in codes])

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(3.45, 3.35), gridspec_kw={"height_ratios": [1.05, 1.0]},
        constrained_layout=True
    )
    y = np.arange(2)
    ax1.errorbar(
        gain, y, xerr=np.vstack([gain - low, high - gain]), fmt="o", ms=5.8,
        color=BLUE, ecolor=BLUE, capsize=3.5, elinewidth=1.6
    )
    ax1.axvline(1.0, color=GREY, ls="--", lw=1.0)
    ax1.set_yticks(y, labels)
    ax1.invert_yaxis()
    ax1.set_xlim(0.45, 1.92)
    ax1.set_xlabel("方向增益 $G_C$" if zh else "Direction gain $G_C$", **zh_kw(zh))
    ax1.grid(axis="x", color=GRID, lw=0.5, alpha=0.8)
    ax1.text(0.02, 0.94, "(a)", transform=ax1.transAxes, va="top", fontweight="bold")
    for value, yi in zip(gain, y):
        ax1.text(value + 0.035, yi - 0.12, f"{value:.3f}", va="bottom", fontsize=7.7)
    style_axis(ax1, zh)

    x = np.arange(2)
    bars = ax2.bar(x, accuracy, width=0.58, color=["#9fb3c8", BLUE],
                   edgecolor="#34495e", linewidth=0.7)
    bars[0].set_hatch("//")
    bars[1].set_hatch("xx")
    ax2.axhline(0.25, color=GREY, ls=":", lw=1.1,
                label="随机水平 0.25" if zh else "Chance 0.25")
    ax2.axhline(0.50, color=GREEN, ls="--", lw=1.1,
                label="预定目标 0.50" if zh else "Declared target 0.50")
    ax2.set_xticks(x, labels)
    ax2.set_ylim(0, 0.58)
    ax2.set_ylabel("分组平衡准确率" if zh else "Grouped balanced accuracy", **zh_kw(zh))
    ax2.grid(axis="y", color=GRID, lw=0.5, alpha=0.8)
    ax2.text(0.02, 0.94, "(b)", transform=ax2.transAxes, va="top", fontweight="bold")
    for rect, value in zip(bars, accuracy):
        ax2.text(rect.get_x() + rect.get_width()/2, value + 0.018, f"{value:.3f}",
                 ha="center", va="bottom", fontsize=7.8)
    ax2.legend(loc="upper right", frameon=False, handlelength=2.0,
               prop=zh_legend(zh, 7.0))
    style_axis(ax2, zh)
    save(fig, out_dir, "four_state_physical_validation")


def two_state_response(out_dir: Path, zh: bool = False) -> None:
    spectrum = rows(EVIDENCE / "two_state_representative_spectra.csv")
    usable = [r for r in spectrum if r["valid"].lower() == "true" and float(r["frequency_hz"]) <= 4000]
    freq = np.array([float(r["frequency_hz"]) for r in usable])
    initial = np.array([float(r["n_minus_s_shape_db"]) for r in usable])
    returned = np.array([float(r["nreturn_minus_s_shape_db"]) for r in usable])
    metric = rows(EVIDENCE / "two_state_direction_effect_metrics.csv")[0]
    values = np.array([
        float(metric["current_within_condition_pairwise_shape_p95_db"]),
        float(metric["return_drift_primary_shape_rms_db"]),
        float(metric["direction_effect_primary_shape_rms_db"]),
    ])

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(3.45, 3.95), gridspec_kw={"height_ratios": [1.65, 1.0]},
        constrained_layout=True
    )
    p95 = values[0]
    ax1.axhspan(-p95, p95, color=LIGHT, alpha=0.55,
                label="状态内 p95" if zh else "Within-state p95")
    ax1.axvspan(1670.84, 2074.94, color=ORANGE, alpha=0.10)
    ax1.axvspan(3390.28, 4000.0, color=GREEN, alpha=0.10)
    ax1.plot(freq, initial, color=BLUE, lw=1.25,
             label="初始 北-南" if zh else "Initial north-south")
    ax1.plot(freq, returned, color=ORANGE, lw=1.10, ls="--",
             label="回程 北-南" if zh else "Returned north-south")
    ax1.set_xscale("log")
    ax1.set_xlim(200, 4000)
    ax1.set_xticks([200, 500, 1000, 2000, 4000])
    ax1.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax1.set_ylim(-6.2, 10.0)
    ax1.set_ylabel("去均值差分 (dB)" if zh else "Demeaned difference (dB)", **zh_kw(zh))
    ax1.set_xlabel("频率 (Hz)" if zh else "Frequency (Hz)", **zh_kw(zh))
    ax1.grid(color=GRID, lw=0.45, alpha=0.7)
    ax1.text(0.02, 0.96, "(a)", transform=ax1.transAxes, va="top", fontweight="bold")
    ax1.text(1850, -5.75, "1.85 kHz", ha="center", va="bottom", fontsize=7.0)
    ax1.text(3700, -5.75, "3.80 kHz", ha="center", va="bottom", fontsize=7.0)
    ax1.legend(loc="upper left", ncol=1, frameon=False, handlelength=2.2,
               prop=zh_legend(zh, 6.8))
    style_axis(ax1, zh)

    labels = (["状态内 p95", "北向回程漂移", "北-南效应"] if zh else
              ["Within-state p95", "North return drift", "North-south effect"])
    y = np.arange(3)
    bars = ax2.barh(y, values, height=0.55, color=[GREY, ORANGE, BLUE],
                    edgecolor="#34495e", linewidth=0.6)
    bars[0].set_hatch("//")
    bars[1].set_hatch("..")
    ax2.set_yticks(y, labels)
    ax2.invert_yaxis()
    ax2.set_xlim(0, 2.32)
    ax2.set_xlabel("主频带形状 RMS (dB)" if zh else "Primary-band shape RMS (dB)", **zh_kw(zh))
    ax2.grid(axis="x", color=GRID, lw=0.5, alpha=0.75)
    ax2.text(0.02, 0.94, "(b)", transform=ax2.transAxes, va="top", fontweight="bold")
    for rect, value in zip(bars, values):
        ax2.text(value + 0.035, rect.get_y() + rect.get_height()/2, f"{value:.3f}",
                 va="center", ha="left", fontsize=7.8, fontweight="bold")
    style_axis(ax2, zh)
    save(fig, out_dir, "two_state_physical_response")


def five_level_bounded_tracking(out_dir: Path, zh: bool = False) -> None:
    data = json.loads((EVIDENCE / "fullwave_five_level_result_summary.json").read_text(encoding="utf-8"))
    cases = data["five_level"]["cases"]
    intervals = {round(float(item["alpha"]), 2): item for item in data["tolerance"]["intervals"]}
    ordered = sorted(cases, key=lambda item: float(item["alpha"]))
    alphas = np.array([float(item["alpha"]) for item in ordered])
    nominal = np.array([float(item["tracked_hz"]) for item in ordered])
    targets = np.array([float(item["target_hz"]) for item in ordered])
    low = np.array([float(intervals[round(a, 2)]["low_corner"]["tracked_hz"]) for a in alphas])
    high = np.array([float(intervals[round(a, 2)]["high_corner"]["tracked_hz"]) for a in alphas])
    y = np.arange(len(alphas))[::-1]

    fig, ax = plt.subplots(figsize=(3.45, 2.80), constrained_layout=True)
    ax.errorbar(nominal, y, xerr=np.vstack([nominal-low, high-nominal]), fmt="none",
                ecolor=BLUE, elinewidth=2.5, capsize=3.5, zorder=1)
    public = ~np.isin(alphas, [0.04, 0.06])
    blind = ~public
    ax.scatter(nominal[public], y[public], s=38, color=BLUE, marker="o", zorder=3,
               label="公开档位" if zh else "Public levels")
    ax.scatter(nominal[blind], y[blind], s=45, facecolors="white", edgecolors=ORANGE,
               linewidths=1.4, marker="o", zorder=4,
               label="盲测中间档" if zh else "Blind intermediates")
    ax.scatter(targets, y, s=30, color=GREY, marker="D", zorder=2,
               label="规定目标" if zh else "Prescribed targets")
    for value, yi in zip(nominal, y):
        ax.text(value + 12, yi + 0.15, f"{int(value)}", fontsize=7.6, va="bottom")
    ax.set_yticks(y, [rf"$\alpha={a:.02f}$" for a in alphas])
    ax.set_xlim(690, 1225)
    ax.set_ylim(-0.55, 4.65)
    ax.set_xlabel("跟踪频率 (Hz)" if zh else "Tracked frequency (Hz)", **zh_kw(zh))
    ax.grid(axis="x", color=GRID, lw=0.5, alpha=0.8)
    ax.legend(loc="upper left", frameon=False, handletextpad=0.5,
              prop=zh_legend(zh, 6.9))
    ax.text(0.98, 0.04, "最大误差 10 Hz\n最小净间隔 26 Hz" if zh else
            "max. error 10 Hz\nminimum gap 26 Hz", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=7.5, **zh_kw(zh))
    style_axis(ax, zh)
    save(fig, out_dir, "five_level_bounded_tracking")


def generate(language: str, zh: bool) -> None:
    out_dir = PACKAGE / language / "figures"
    four_state_validation(out_dir, zh)
    two_state_response(out_dir, zh)
    five_level_bounded_tracking(out_dir, zh)


if __name__ == "__main__":
    generate("english", False)
    generate("chinese", True)
