"""WRITE-2 thesis figures and tables from frozen FORMAL-3/4/5 artifacts only."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
from typing import Any, Iterable, Mapping, Sequence
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
from PIL import Image

from .formal_core_analysis import verify_formal3_authority, verify_formal4_output_hashes
from .formal_final_synthesis import verify_formal5_output_hashes
from .schemas import artifact_sha256


WRITE2_SCHEMA_VERSION = "write2_dissertation_assets_v1"
EXPECTED_DISPOSITION = "supported_with_limits"
FIGURE_COUNT = 7
TABLE_COUNT = 4
PNG_DPI = 300

FORMAL4_HASHES = {
    "repeatability_frequency.csv": "ed1855aeca704386473d124cafdcba696fab213a6bee5e8b12c57d2ea71306a0",
    "repeatability_summary.csv": "1f7166f10ce2fe3730e7d37505617202c7b56db03c952b9d2b34f1b703f1c5e1",
    "direction_pairwise_effects.csv": "b35e38bd928bca75f9509b95266fe71a06866c9e25504c99e896ecc58d726d35",
    "direction_gain_summary.csv": "8d7791041ccd55067ed4abe3f4f5d1bf6e4a7ce0167887e9d2b31ff3c02f7dbf",
    "direction_gain_contrasts.csv": "8f77db86d1e9eb7de8a6adae6215461cfe9318d1a815637e7a07e463b6827b52",
    "configuration_effects.csv": "9f96888e77f2964f6d2aedee7192c79ef449f31272a3773aeb95fcebb945de39",
    "configuration_difference_curves.csv": "9c54faeba5e08c027101da2b19a31ab9749ab2ed4dd26d727584b61ca5925b6d",
    "outlier_sensitivity.csv": "a4f9eecd6cc4c1d8338a44c14e427fdd55048bf5836feb5df3e6df37821683f7",
    "grouped_validation_metrics.csv": "c9df8527c0f0947c8fb2be75205d54d7480c28942ea1cac95870d1a1be9030da",
    "plots/block_direction_B01.png": "39289581397dade6265dcfffd9f960cef5d2482d747c44f03757480f1ea808a2",
    "plots/block_direction_B02.png": "81f010b62281313e814cde95cd2c7b12a1994fb2e2811cdf983970e5f280dd5d",
    "plots/block_direction_B03.png": "25c1ca95aef79b9efb4e771f7965f9d33c44942cf347a01ca7b504274cff729d",
    "plots/block_direction_B04.png": "27c1c8313c2a184db18a7fbfc78fe2652ad992733facdecee6613ce6fb0bc8b4",
    "plots/grouped_validation_confusion_matrix.png": "f7b82802750145780277433a46cf5ecac3951648c9b0c2453fa2a7dbe407a71a",
}

FORMAL5_HASHES = {
    "final_claim_boundary.json": "ff2f4e97edb841e48e6db246f8ec64a2115fd900437e1e88af3f446ac2e8384f",
    "final_analysis_manifest.json": "1541ba6b238f37eb69e6ed5012e949206b7ccd5be22558f4dad31b0d45f8e374",
}

COLORS = {
    "U4SYM": "#0072B2",
    "U4ENC": "#D55E00",
    "primary": "#009E73",
    "sensitivity": "#CC79A7",
    "neutral": "#4D4D4D",
    "secondary": "#999999",
}


class DissertationAssetError(ValueError):
    """Raised when a frozen source or generated thesis asset is invalid."""


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DissertationAssetError(f"JSON authority must be an object: {path}")
    return payload


def _one(rows: Sequence[Mapping[str, str]], **criteria: str) -> Mapping[str, str]:
    matched = [
        row for row in rows
        if all(row.get(field) == value for field, value in criteria.items())
    ]
    if len(matched) != 1:
        raise DissertationAssetError(
            f"expected one frozen row for {criteria}, found {len(matched)}"
        )
    return matched[0]


def _close(label: str, observed: Any, expected: float) -> None:
    if not math.isclose(float(observed), expected, rel_tol=0.0, abs_tol=5e-12):
        raise DissertationAssetError(
            f"{label} changed: expected {expected!r}, found {observed!r}"
        )


def _verify_source_hashes(root: Path, expected: Mapping[str, str]) -> None:
    for relative, digest in expected.items():
        path = root / relative
        if not path.is_file():
            raise DissertationAssetError(f"frozen source missing: {path}")
        actual = artifact_sha256(path)
        if actual != digest:
            raise DissertationAssetError(
                f"frozen source hash mismatch: {relative}; expected {digest}, found {actual}"
            )


def _source_entry(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative,
        "sha256": artifact_sha256(path),
        "bytes": path.stat().st_size,
    }


def _set_style() -> None:
    matplotlib.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "legend.fontsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "figure.titlesize": 12,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.hashsalt": "WRITE-2-frozen-formal-results",
    })


def _save_figure(fig: plt.Figure, figure_root: Path, stem: str) -> tuple[Path, Path]:
    png = figure_root / f"{stem}.png"
    svg = figure_root / f"{stem}.svg"
    metadata = {"Creator": "WRITE-2 frozen FORMAL-4/5 figure builder"}
    fig.savefig(png, dpi=PNG_DPI, bbox_inches="tight", facecolor="white", metadata=metadata)
    fig.savefig(
        svg, format="svg", bbox_inches="tight", facecolor="white",
        metadata={"Creator": metadata["Creator"], "Date": "2026-08-20"},
    )
    # Matplotlib emits path-data lines with trailing spaces. Normalise the
    # publication SVG to stable UTF-8/LF text so git diff --check remains a
    # meaningful release gate and hashes are platform-independent.
    svg_text = svg.read_text(encoding="utf-8")
    svg.write_bytes(
        ("\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n").encode("utf-8")
    )
    plt.close(fig)
    return png, svg


def _figure_1(formal4: Path, figure_root: Path, tables: Mapping[str, list[dict[str, str]]]) -> tuple[Path, Path]:
    frequency_rows = tables["repeatability_frequency.csv"]
    summary_rows = tables["repeatability_summary.csv"]
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 7.0), gridspec_kw={"height_ratios": [2.2, 1.0]})
    for configuration in ("U4SYM", "U4ENC"):
        groups: dict[tuple[str, str], list[Mapping[str, str]]] = {}
        for row in frequency_rows:
            if row["configuration"] == configuration:
                groups.setdefault((row["block_id"], row["direction_deg"]), []).append(row)
        first = True
        for rows in groups.values():
            ordered = sorted(rows, key=lambda row: float(row["frequency_hz"]))
            axes[0].plot(
                [float(row["frequency_hz"]) for row in ordered],
                [float(row["pointwise_mad_db"]) for row in ordered],
                color=COLORS[configuration], alpha=0.24, linewidth=0.65,
                label=f"{configuration}: block × direction cells" if first else None,
            )
            first = False
    axes[0].axvspan(4000, 8000, color=COLORS["secondary"], alpha=0.13, label="Secondary band")
    axes[0].axvline(4000, color=COLORS["neutral"], linewidth=0.9, linestyle="--")
    axes[0].set_xscale("log")
    axes[0].set_xlim(200, 8000)
    axes[0].set_ylim(bottom=0)
    axes[0].set_xlabel("Frequency (Hz)")
    axes[0].set_ylabel("Pointwise MAD (dB)")
    axes[0].set_title("A. Frozen pointwise repeat dispersion (24 block × direction cells)")
    axes[0].grid(True, which="both", linewidth=0.35, alpha=0.35)
    axes[0].legend(loc="upper left", ncols=2)

    bands = ("primary", "secondary", "full")
    labels = ("Primary\n200–4000 Hz", "Secondary\n4000–8000 Hz", "Full valid\nband")
    x = np.arange(3)
    width = 0.24
    metrics = (
        ("median_pairwise_rms_db", "Median", COLORS["primary"]),
        ("iqr_pairwise_rms_db", "IQR", COLORS["U4SYM"]),
        ("p95_pairwise_rms_db", "95th percentile", COLORS["U4ENC"]),
    )
    for index, (field, label, color) in enumerate(metrics):
        values = [float(_one(summary_rows, band_id=band)[field]) for band in bands]
        axes[1].bar(x + (index - 1) * width, values, width, label=label, color=color)
        for xpos, value in zip(x + (index - 1) * width, values, strict=True):
            axes[1].text(xpos, value + 0.025, f"{value:.3f}", ha="center", va="bottom", fontsize=7)
    axes[1].set_xticks(x, labels)
    axes[1].set_ylim(0, 1.55)
    axes[1].set_ylabel("Pairwise RMS difference (dB)")
    axes[1].set_title("B. Frozen repeatability summary (all CONT pairs)")
    axes[1].grid(True, axis="y", linewidth=0.35, alpha=0.35)
    axes[1].legend(loc="upper left", ncols=3)
    fig.suptitle("Figure 1. Continuous-repeat measurement floor")
    fig.tight_layout()
    return _save_figure(fig, figure_root, "figure_01_repeatability_floor")


def _figure_2(formal4: Path, figure_root: Path) -> tuple[Path, Path]:
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.8))
    panels = (
        ("B01", "U4SYM / AS01 / RP01"),
        ("B02", "U4SYM / AS01 / RP02"),
        ("B03", "U4ENC / AS01 / RP01"),
        ("B04", "U4ENC / AS01 / RP02"),
    )
    for panel, axis, (block, label) in zip("ABCD", axes.flat, panels, strict=True):
        image = mpimg.imread(formal4 / "plots" / f"block_direction_{block}.png")
        axis.imshow(image)
        axis.set_axis_off()
        axis.set_title(f"{panel}. {block} — {label}", loc="left", fontsize=9)
    fig.suptitle("Figure 2. AS01 direction spectra by acquisition block\nDescriptive block panels; CONT repeats are not independent scientific samples")
    fig.tight_layout()
    return _save_figure(fig, figure_root, "figure_02_as01_direction_spectra")


def _figure_3(figure_root: Path, rows: Sequence[Mapping[str, str]]) -> tuple[Path, Path]:
    primary = [row for row in rows if row["band_id"] == "primary"]
    blocks = ("B01", "B02", "B03", "B04", "B05", "B07")
    pairs = ((0, 90), (0, 180), (0, 270), (90, 180), (90, 270), (180, 270))
    max_ratio = max(float(row["effect_to_repeatability_ratio"]) for row in primary)
    norm = TwoSlopeNorm(vmin=0.0, vcenter=1.0, vmax=max(1.01, max_ratio))
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 6.7), sharex=True, sharey=True)
    last = None
    for axis, block in zip(axes.flat, blocks, strict=True):
        block_rows = [row for row in primary if row["block_id"] == block]
        configuration = block_rows[0]["configuration"]
        values = np.array([
            float(_one(block_rows, direction_a_deg=str(a), direction_b_deg=str(b))["effect_to_repeatability_ratio"])
            for a, b in pairs
        ])[None, :]
        last = axis.imshow(values, aspect="auto", cmap="RdBu_r", norm=norm)
        axis.set_yticks([0], [configuration])
        axis.set_xticks(range(6), [f"{a}–{b}°" for a, b in pairs], rotation=45, ha="right")
        axis.set_title(f"{block} / {block_rows[0]['assembly_id']} / {block_rows[0]['reposition_round_id']}")
        for index, value in enumerate(values[0]):
            mark = "*" if value > 1.0 else ""
            axis.text(index, 0, f"{value:.2f}{mark}", ha="center", va="center", fontsize=8)
    if last is not None:
        # Reserve a dedicated axis so the shared colour bar never obscures the
        # right-hand heatmaps or their block labels in the thesis export.
        fig.subplots_adjust(left=0.08, right=0.86, bottom=0.10, top=0.91, wspace=0.38, hspace=0.42)
        colorbar_axis = fig.add_axes([0.89, 0.20, 0.018, 0.58])
        colorbar = fig.colorbar(last, cax=colorbar_axis)
        colorbar.set_label("Effect / CONT p95 (ratio)")
    fig.suptitle("Figure 3. Primary-band pairwise direction effects\n* exceeds the frozen CONT p95 floor; AS02 panels are exploratory")
    fig.subplots_adjust(left=0.08, right=0.88, top=0.86, bottom=0.13, hspace=0.5, wspace=0.25)
    return _save_figure(fig, figure_root, "figure_03_pairwise_direction_effects")


def _figure_4(figure_root: Path, gains: Sequence[Mapping[str, str]], contrasts: Sequence[Mapping[str, str]]) -> tuple[Path, Path]:
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 4.1))
    configurations = ("U4SYM", "U4ENC")
    x = np.arange(2)
    g_rows = [
        _one(gains, configuration=config, assembly_scope="AS01", band_id="primary", normalization="demeaned")
        for config in configurations
    ]
    values = np.array([float(row["gain"]) for row in g_rows])
    lows = np.array([float(row["bootstrap_ci95_low"]) for row in g_rows])
    highs = np.array([float(row["bootstrap_ci95_high"]) for row in g_rows])
    axes[0].errorbar(
        x, values, yerr=np.vstack((values - lows, highs - values)), fmt="o", capsize=5,
        color=COLORS["neutral"], ecolor=COLORS["neutral"], markersize=7,
    )
    for index, config in enumerate(configurations):
        axes[0].plot(index, values[index], "o", color=COLORS[config], markersize=7)
        axes[0].text(index, highs[index] + 0.06, f"{values[index]:.4f}\n[{lows[index]:.4f}, {highs[index]:.4f}]", ha="center", fontsize=7)
    axes[0].axhline(1.0, color=COLORS["neutral"], linestyle="--", linewidth=1, label="Frozen threshold = 1")
    axes[0].set_xticks(x, configurations)
    axes[0].set_ylim(0, 2.05)
    axes[0].set_ylabel("G_demeaned (dimensionless)")
    axes[0].set_title("A. G_demeaned with 95% CI")
    axes[0].legend(loc="lower right")
    axes[0].grid(True, axis="y", linewidth=0.35, alpha=0.35)

    contrast = _one(contrasts, assembly_scope="AS01", band_id="primary", normalization="demeaned")
    delta = float(contrast["u4enc_minus_u4sym_gain"])
    delta_low = float(contrast["bootstrap_ci95_low"])
    delta_high = float(contrast["bootstrap_ci95_high"])
    axes[1].errorbar(
        [0], [delta], yerr=[[delta - delta_low], [delta_high - delta]], fmt="o",
        capsize=6, color=COLORS["U4ENC"], markersize=7,
    )
    limit = max(abs(delta_low), abs(delta_high), 1.1) * 1.18
    axes[1].axhline(0.0, color=COLORS["neutral"], linestyle="--", linewidth=1, label="Null = 0")
    axes[1].set_xlim(-0.7, 0.7)
    axes[1].set_ylim(-limit, limit)
    axes[1].set_xticks([0], ["U4ENC − U4SYM"])
    axes[1].set_ylabel("ΔG_demeaned (dimensionless)")
    axes[1].set_title("B. Configuration contrast with 95% CI")
    axes[1].text(0, delta_high + 0.08, f"{delta:.4f}\n[{delta_low:.4f}, {delta_high:.4f}]", ha="center", fontsize=7)
    axes[1].legend(loc="lower right")
    axes[1].grid(True, axis="y", linewidth=0.35, alpha=0.35)

    normalizations = ("raw", "demeaned", "zscore")
    for config in configurations:
        points = [
            float(_one(gains, configuration=config, assembly_scope="AS01", band_id="primary", normalization=norm_name)["gain"])
            for norm_name in normalizations
        ]
        axes[2].plot(normalizations, points, marker="o", linewidth=1.5, color=COLORS[config], label=config)
        for xpos, value in zip(range(3), points, strict=True):
            axes[2].text(xpos, value + 0.035, f"{value:.3f}", ha="center", fontsize=7)
    axes[2].axhline(1.0, color=COLORS["neutral"], linestyle="--", linewidth=1)
    axes[2].set_ylim(0, 1.55)
    axes[2].set_ylabel("Direction / REPOS gain (dimensionless)")
    axes[2].set_title("C. Frozen normalization views")
    axes[2].legend(loc="lower right")
    axes[2].grid(True, axis="y", linewidth=0.35, alpha=0.35)
    fig.suptitle("Figure 4. Direction-effect gain relative to repeatability\nPoint estimates favour U4ENC; confirmatory CI criteria were not fully met")
    fig.tight_layout()
    return _save_figure(fig, figure_root, "figure_04_direction_gain_and_ci")


def _figure_5(figure_root: Path, rows: Sequence[Mapping[str, str]]) -> tuple[Path, Path]:
    fig, axes = plt.subplots(2, 1, figsize=(7.4, 7.0), sharex=True)
    colors = {0: "#0072B2", 90: "#E69F00", 180: "#009E73", 270: "#CC79A7"}
    for axis, assembly in zip(axes, ("AS01", "AS02"), strict=True):
        assembly_rows = [row for row in rows if row["assembly_id"] == assembly]
        all_values: list[float] = []
        for direction in (0, 90, 180, 270):
            selected = sorted(
                (row for row in assembly_rows if int(row["direction_deg"]) == direction),
                key=lambda row: float(row["frequency_hz"]),
            )
            frequency = [float(row["frequency_hz"]) for row in selected]
            values = [float(row["u4enc_minus_u4sym_db"]) for row in selected]
            all_values.extend(values)
            axis.plot(frequency, values, color=colors[direction], linewidth=1.0, label=f"{direction}°")
        limit = max(abs(value) for value in all_values) * 1.05
        axis.axhline(0, color=COLORS["neutral"], linewidth=0.9, linestyle="--", label="No configuration difference")
        axis.axvspan(4000, 8000, color=COLORS["secondary"], alpha=0.13)
        axis.axvline(4000, color=COLORS["neutral"], linewidth=0.8, linestyle=":")
        axis.set_xscale("log")
        axis.set_xlim(200, 8000)
        axis.set_ylim(-limit, limit)
        axis.set_ylabel("U4ENC − U4SYM (dB)")
        suffix = " — exploratory; block/time confounded" if assembly == "AS02" else " — bounded AS01 result"
        axis.set_title(f"{assembly}{suffix}")
        axis.grid(True, which="both", linewidth=0.35, alpha=0.35)
        axis.legend(ncols=5, loc="upper center", fontsize=7)
    axes[-1].set_xlabel("Frequency (Hz); shaded region = secondary band")
    fig.suptitle("Figure 5. Frozen configuration-difference curves")
    fig.tight_layout()
    return _save_figure(fig, figure_root, "figure_05_configuration_difference")


def _sensitivity_value(rows: Sequence[Mapping[str, str]], variant: str, metric: str, scope: str, band: str) -> float:
    return float(_one(rows, analysis_variant=variant, metric_id=metric, scope_id=scope, band_id=band)["value"])


def _figure_6(figure_root: Path, rows: Sequence[Mapping[str, str]]) -> tuple[Path, Path]:
    metrics = (
        ("CONT floor", "CONT_floor_median", "all"),
        ("U4SYM G", "G_demeaned", "U4SYM"),
        ("U4ENC G", "G_demeaned", "U4ENC"),
        ("ΔG", "delta_G_demeaned", "U4ENC_minus_U4SYM"),
        ("Config/floor", "configuration_effect_to_CONT_floor", "AS01"),
    )
    variants = ("primary_all_active", "sensitivity_without_flagged_curves")
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2))
    x = np.arange(len(metrics)); width = 0.36
    for offset, variant, label, color in (
        (-width / 2, variants[0], "All 72 ACTIVE", COLORS["primary"]),
        (width / 2, variants[1], "Sensitivity without 10 flags", COLORS["sensitivity"]),
    ):
        values = [_sensitivity_value(rows, variant, metric, scope, "primary") for _, metric, scope in metrics]
        axes[0].bar(x + offset, values, width, label=label, color=color)
        for xpos, value in zip(x + offset, values, strict=True):
            axes[0].text(xpos, value + 0.025, f"{value:.3f}", ha="center", fontsize=7)
    axes[0].axhline(1.0, color=COLORS["neutral"], linestyle="--", linewidth=0.9, label="Ratio/G reference = 1")
    axes[0].set_xticks(x, [label for label, _, _ in metrics], rotation=25, ha="right")
    axes[0].set_ylim(0, 1.75)
    axes[0].set_ylabel("Frozen metric value")
    axes[0].text(
        0.99,
        0.98,
        "CONT floor: dB; other metrics: dimensionless",
        transform=axes[0].transAxes,
        ha="right",
        va="top",
        fontsize=7,
    )
    axes[0].set_title("A. Physical and repeatability metrics")
    axes[0].grid(True, axis="y", linewidth=0.35, alpha=0.35)
    axes[0].legend(fontsize=7)

    class_metrics = (("U4SYM BA", "grouped_balanced_accuracy", "U4SYM_AS01"), ("U4ENC BA", "grouped_balanced_accuracy", "U4ENC_AS01"))
    x2 = np.arange(2)
    for offset, variant, label, color in (
        (-width / 2, variants[0], "All 72 ACTIVE", COLORS["primary"]),
        (width / 2, variants[1], "Sensitivity without flags", COLORS["sensitivity"]),
    ):
        values = [_sensitivity_value(rows, variant, metric, scope, "primary") for _, metric, scope in class_metrics]
        axes[1].bar(x2 + offset, values, width, label=label, color=color)
        for xpos, value in zip(x2 + offset, values, strict=True):
            axes[1].text(xpos, value + 0.015, f"{value:.3f}", ha="center", fontsize=7)
    axes[1].axhline(0.25, color=COLORS["neutral"], linestyle=":", linewidth=1, label="Chance = 0.25")
    axes[1].axhline(0.50, color=COLORS["U4ENC"], linestyle="--", linewidth=1, label="Practical target = 0.50")
    axes[1].set_xticks(x2, [label for label, _, _ in class_metrics])
    axes[1].set_ylim(0, 0.6)
    axes[1].set_ylabel("Balanced accuracy")
    axes[1].set_title("B. Grouped classification")
    axes[1].grid(True, axis="y", linewidth=0.35, alpha=0.35)
    axes[1].legend(fontsize=7)
    fig.suptitle("Figure 6. Outlier-flag sensitivity\nTemporary omission changed no frozen threshold conclusion and did not edit ACTIVE/EXCLUDED")
    fig.tight_layout()
    return _save_figure(fig, figure_root, "figure_06_outlier_sensitivity")


def _figure_7(formal4: Path, figure_root: Path, rows: Sequence[Mapping[str, str]]) -> tuple[Path, Path]:
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.5), gridspec_kw={"width_ratios": [1.55, 1.0]})
    image = mpimg.imread(formal4 / "plots" / "grouped_validation_confusion_matrix.png")
    axes[0].imshow(image)
    axes[0].set_axis_off()
    axes[0].set_title("A. Frozen leave-one-block-out confusion matrices")

    scopes = ("U4SYM_AS01", "U4ENC_AS01")
    labels = ("U4SYM", "U4ENC")
    x = np.arange(2); width = 0.32
    ba = [float(_one(rows, scope_id=scope)["balanced_accuracy"]) for scope in scopes]
    f1 = [float(_one(rows, scope_id=scope)["macro_f1"]) for scope in scopes]
    axes[1].bar(x - width / 2, ba, width, label="Balanced accuracy", color=COLORS["U4SYM"])
    axes[1].bar(x + width / 2, f1, width, label="Macro-F1", color=COLORS["U4ENC"])
    for xpos, value in zip(np.concatenate((x - width / 2, x + width / 2)), ba + f1, strict=True):
        axes[1].text(xpos, value + 0.015, f"{value:.3f}", ha="center", fontsize=7)
    axes[1].axhline(0.25, color=COLORS["neutral"], linestyle=":", linewidth=1, label="Chance = 0.25")
    axes[1].axhline(0.50, color=COLORS["primary"], linestyle="--", linewidth=1, label="Practical target = 0.50")
    axes[1].set_xticks(x, labels)
    axes[1].set_ylim(0, 1.0)
    axes[1].set_ylabel("Score (0–1)")
    axes[1].set_title("B. Confirmatory AS01 performance")
    axes[1].grid(True, axis="y", linewidth=0.35, alpha=0.35)
    axes[1].legend(fontsize=7, loc="upper right")
    fig.suptitle("Figure 7. Grouped four-direction classification\nBoth AS01 balanced accuracies missed the frozen 0.50 practical target")
    fig.tight_layout()
    return _save_figure(fig, figure_root, "figure_07_grouped_classification")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _markdown_table(title: str, caption_en: str, caption_zh: str, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    lines = [f"# {title}", "", caption_en, "", caption_zh, "", "| " + " | ".join(fields) + " |", "|" + "|".join("---" for _ in fields) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join(lines) + "\n"


def _table_assets(table_root: Path, tables: Mapping[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    definitions: list[tuple[str, str, str, str, list[dict[str, Any]], tuple[str, ...], list[str]]] = []
    repeat_rows = []
    labels = {"primary": "Primary 200–4000 Hz", "secondary": "Secondary 4000–8000 Hz", "full": "Full valid band"}
    for band in ("primary", "secondary", "full"):
        row = _one(tables["repeatability_summary.csv"], band_id=band)
        repeat_rows.append({
            "band": labels[band], "median_rms_db": f"{float(row['median_pairwise_rms_db']):.4f}",
            "iqr_db": f"{float(row['iqr_pairwise_rms_db']):.4f}",
            "p95_rms_db": f"{float(row['p95_pairwise_rms_db']):.4f}", "unit": "dB",
            "interpretation": "confirmatory floor" if band == "primary" else "secondary/descriptive",
            "source_artifact": "FORMAL-4/repeatability_summary.csv",
        })
    definitions.append((
        "table_01_repeatability_floor", "Table 1. Continuous-repeat measurement floor",
        "Frozen distribution of all CONT pairwise RMS differences.",
        "表1：全部 CONT 配对 RMS 差的冻结重复性底线。",
        repeat_rows, tuple(repeat_rows[0]), ["repeatability_summary.csv"],
    ))

    gain_rows = []
    for config in ("U4SYM", "U4ENC"):
        by_norm = {
            norm: _one(tables["direction_gain_summary.csv"], configuration=config, assembly_scope="AS01", band_id="primary", normalization=norm)
            for norm in ("raw", "demeaned", "zscore")
        }
        gain_rows.append({
            "configuration_or_contrast": config, "assembly_scope": "AS01",
            "G_raw": f"{float(by_norm['raw']['gain']):.4f}",
            "G_demeaned_or_delta": f"{float(by_norm['demeaned']['gain']):.4f}",
            "ci95_low": f"{float(by_norm['demeaned']['bootstrap_ci95_low']):.4f}",
            "ci95_high": f"{float(by_norm['demeaned']['bootstrap_ci95_high']):.4f}",
            "G_zscore": f"{float(by_norm['zscore']['gain']):.4f}",
            "decision": "point estimate only; confirmatory CI criterion not fully met",
            "source_artifact": "FORMAL-4/direction_gain_summary.csv",
        })
    contrast = _one(tables["direction_gain_contrasts.csv"], assembly_scope="AS01", band_id="primary", normalization="demeaned")
    gain_rows.append({
        "configuration_or_contrast": "U4ENC − U4SYM", "assembly_scope": "AS01",
        "G_raw": "—", "G_demeaned_or_delta": f"{float(contrast['u4enc_minus_u4sym_gain']):.4f}",
        "ci95_low": f"{float(contrast['bootstrap_ci95_low']):.4f}",
        "ci95_high": f"{float(contrast['bootstrap_ci95_high']):.4f}", "G_zscore": "—",
        "decision": "CI includes 0; H1 not confirmed",
        "source_artifact": "FORMAL-4/direction_gain_contrasts.csv",
    })
    definitions.append((
        "table_02_direction_gain", "Table 2. Frozen direction-effect gains and confidence intervals",
        "AS01 direction-to-REPOS gains; ΔG is the U4ENC minus U4SYM contrast.",
        "表2：AS01 方向效应增益及 95% 置信区间；ΔG 为 U4ENC 减 U4SYM。",
        gain_rows, tuple(gain_rows[0]), ["direction_gain_summary.csv", "direction_gain_contrasts.csv"],
    ))

    class_rows = []
    for scope in ("U4SYM_AS01", "U4ENC_AS01"):
        row = _one(tables["grouped_validation_metrics.csv"], scope_id=scope)
        class_rows.append({
            "scope": scope, "protocol": row["protocol"], "folds": row["fold_count"],
            "predictions": row["prediction_count"], "balanced_accuracy": f"{float(row['balanced_accuracy']):.3f}",
            "macro_f1": f"{float(row['macro_f1']):.3f}", "chance": f"{float(row['chance_level']):.3f}",
            "practical_target": "0.500", "permutation_p": f"{float(row['permutation_p_value']):.3f}",
            "decision": "target not met", "source_artifact": "FORMAL-4/grouped_validation_metrics.csv",
        })
    definitions.append((
        "table_03_grouped_classification", "Table 3. AS01 grouped direction-classification performance",
        "Leave-one-block-out results; CONT repeats were aggregated before splitting.",
        "表3：AS01 留一 block 分组分类；CONT 重复在划分前聚合。",
        class_rows, tuple(class_rows[0]), ["grouped_validation_metrics.csv"],
    ))

    sensitivity_specs = (
        ("Primary CONT median floor", "CONT_floor_median", "all", "dB"),
        ("U4SYM G_demeaned", "G_demeaned", "U4SYM", "dimensionless"),
        ("U4ENC G_demeaned", "G_demeaned", "U4ENC", "dimensionless"),
        ("ΔG_demeaned", "delta_G_demeaned", "U4ENC_minus_U4SYM", "dimensionless"),
        ("AS01 configuration/floor", "configuration_effect_to_CONT_floor", "AS01", "dimensionless"),
        ("U4SYM grouped BA", "grouped_balanced_accuracy", "U4SYM_AS01", "score"),
        ("U4ENC grouped BA", "grouped_balanced_accuracy", "U4ENC_AS01", "score"),
    )
    sensitivity_rows = []
    for label, metric, scope, unit in sensitivity_specs:
        primary = _one(tables["outlier_sensitivity.csv"], analysis_variant="primary_all_active", metric_id=metric, scope_id=scope, band_id="primary")
        reduced = _one(tables["outlier_sensitivity.csv"], analysis_variant="sensitivity_without_flagged_curves", metric_id=metric, scope_id=scope, band_id="primary")
        sensitivity_rows.append({
            "metric": label, "all_72_active": f"{float(primary['value']):.4f}",
            "without_10_flags": f"{float(reduced['value']):.4f}", "unit": unit,
            "frozen_conclusion_changed": primary["conclusion_changed_between_variants"],
            "selection_changed": primary["selection_manifest_changed"],
            "source_artifact": "FORMAL-4/outlier_sensitivity.csv",
        })
    definitions.append((
        "table_04_outlier_sensitivity", "Table 4. Outlier-flag sensitivity",
        "Primary analysis retained all 72 ACTIVE curves; omission was temporary and changed no frozen conclusion.",
        "表4：主分析保留全部 72 条 ACTIVE；临时省略 flags 未改变冻结结论。",
        sensitivity_rows, tuple(sensitivity_rows[0]), ["outlier_sensitivity.csv"],
    ))

    entries: list[dict[str, Any]] = []
    for number, (stem, title, caption_en, caption_zh, rows, fields, sources) in enumerate(definitions, start=1):
        csv_path = table_root / f"{stem}.csv"
        md_path = table_root / f"{stem}.md"
        _write_csv(csv_path, rows, fields)
        md_path.write_bytes(
            _markdown_table(title, caption_en, caption_zh, rows, fields).encode("utf-8")
        )
        entries.append({
            "number": f"Table {number}", "stem": stem, "title_en": title,
            "title_zh": caption_zh, "caption_en": caption_en, "caption_zh": caption_zh,
            "files": [csv_path.name, md_path.name], "source_artifacts": sources,
        })
    return entries


def _figure_specs() -> list[dict[str, Any]]:
    return [
        {"number": "Figure 1", "stem": "figure_01_repeatability_floor", "title_en": "Continuous-repeat measurement floor", "title_zh": "连续重复测量误差底线", "caption_en": "Frequency-dependent pointwise MAD and frozen all-CONT pairwise RMS summaries. CONT repeats are technical repeats, not independent scientific samples.", "caption_zh": "逐频点 MAD 与全部 CONT 配对 RMS 的冻结摘要；CONT 是技术重复，不是独立科学样本。", "sources": ["repeatability_frequency.csv", "repeatability_summary.csv"]},
        {"number": "Figure 2", "stem": "figure_02_as01_direction_spectra", "title_en": "AS01 direction spectra by acquisition block", "title_zh": "AS01 各采集 block 的方向频谱", "caption_en": "Frozen block panels for two U4SYM and two U4ENC REPOS blocks. Visible separation is descriptive until assessed against floor and CI criteria.", "caption_zh": "两组 U4SYM 与两组 U4ENC REPOS block 的冻结面板；可见分离须结合底线和 CI 判定。", "sources": [f"plots/block_direction_{block}.png" for block in ("B01", "B02", "B03", "B04")]},
        {"number": "Figure 3", "stem": "figure_03_pairwise_direction_effects", "title_en": "Primary-band pairwise direction effects", "title_zh": "主频带方向两两效应", "caption_en": "Frozen demeaned effect-to-CONT-p95 ratios. U4ENC had 6/6 and U4SYM 3/6 stable AS01 pairs above the floor; this does not imply classification success.", "caption_zh": "冻结的 demeaned effect/CONT-p95 比值；U4ENC 6/6、U4SYM 3/6 稳定方向对超过底线，但不等于分类成功。", "sources": ["direction_pairwise_effects.csv"]},
        {"number": "Figure 4", "stem": "figure_04_direction_gain_and_ci", "title_en": "Direction-effect gain and confidence intervals", "title_zh": "方向效应增益及置信区间", "caption_en": "Frozen AS01 G values, 95% CIs, ΔG and normalization views. U4ENC and ΔG confidence intervals cross their confirmatory references.", "caption_zh": "冻结的 AS01 G、95% CI、ΔG 与归一化视图；U4ENC 和 ΔG 的区间跨越确认性参考线。", "sources": ["direction_gain_summary.csv", "direction_gain_contrasts.csv"]},
        {"number": "Figure 5", "stem": "figure_05_configuration_difference", "title_en": "U4ENC–U4SYM configuration-difference curves", "title_zh": "U4ENC–U4SYM 配置差值曲线", "caption_en": "Frozen differences across frequency. AS01 is bounded evidence; AS02 is exploratory because assembly, block and time are confounded.", "caption_zh": "冻结的频率差值；AS01 为有边界证据，AS02 因 assembly、block 与 time 混杂而仅为探索性。", "sources": ["configuration_difference_curves.csv", "configuration_effects.csv"]},
        {"number": "Figure 6", "stem": "figure_06_outlier_sensitivity", "title_en": "Outlier-flag sensitivity", "title_zh": "Outlier flag 敏感性", "caption_en": "All 72 ACTIVE results versus temporary omission of 10 flags. No frozen threshold conclusion or selection changed.", "caption_zh": "全部 72 条 ACTIVE 与临时省略 10 个 flags 的比较；冻结门槛结论和样本选择均未改变。", "sources": ["outlier_sensitivity.csv"]},
        {"number": "Figure 7", "stem": "figure_07_grouped_classification", "title_en": "Grouped four-direction classification", "title_zh": "四方向分组分类", "caption_en": "Frozen leave-one-block-out confusion matrices and scores. Both AS01 balanced accuracies were below the 0.50 practical target.", "caption_zh": "冻结的留一 block 混淆矩阵与分数；两项 AS01 balanced accuracy 均低于 0.50 实用目标。", "sources": ["plots/grouped_validation_confusion_matrix.png", "grouped_validation_metrics.csv"]},
    ]


def _git_commit(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def _manifest_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Figure and Table Manifest", "",
        "Status: frozen WRITE-2 dissertation assets", "",
        "中文状态：WRITE-2 论文图表已冻结。", "",
        f"- Source commit: `{payload['source_commit']}`",
        f"- Disposition: `{payload['disposition']}`",
        "- H0: `not_rejected`", "- H1: `not_confirmed`",
        "- ACTIVE/EXCLUDED: `72/19`", "- final-test: sealed and unread", "",
        "## Figures", "",
        "| No. | English / 中文 title | PNG | SVG | Sources | Boundary |", "|---|---|---|---|---|---|",
    ]
    for item in payload["figures"]:
        sources = "; ".join(source["path"] for source in item["source_artifacts"])
        png = next(file for file in item["files"] if file["path"].endswith(".png"))
        svg = next(file for file in item["files"] if file["path"].endswith(".svg"))
        lines.append(
            f"| {item['number']} | {item['title_en']} / {item['title_zh']} | "
            f"`{png['path']}`<br>`{png['sha256']}` | `{svg['path']}`<br>`{svg['sha256']}` | "
            f"{sources} | {item['claim_boundary']} |"
        )
        lines.extend(["", f"**Caption EN:** {item['caption_en']}", "", f"**图注中文：** {item['caption_zh']}", ""])
    lines.extend(["## Tables", "", "| No. | English / 中文 title | CSV | Markdown | Sources |", "|---|---|---|---|---|"])
    for item in payload["tables"]:
        sources = "; ".join(source["path"] for source in item["source_artifacts"])
        csv_file = next(file for file in item["files"] if file["path"].endswith(".csv"))
        md_file = next(file for file in item["files"] if file["path"].endswith(".md"))
        lines.append(
            f"| {item['number']} | {item['title_en']} / {item['title_zh']} | "
            f"`{csv_file['path']}`<br>`{csv_file['sha256']}` | `{md_file['path']}`<br>`{md_file['sha256']}` | {sources} |"
        )
    lines.extend([
        "", "## Reproduction", "",
        f"All assets were generated by `{payload['reproduction_script']['path']}` "
        f"(SHA-256 `{payload['reproduction_script']['sha256']}`).", "",
        "```powershell", "python scripts/build_dissertation_results_assets.py", "```", "",
        "The generator refuses existing output paths. It reads explicit frozen artifacts only and does not scan raw measurements.", "",
        "## Scientific boundary", "",
        "The figures and tables preserve `supported_with_limits`, H0 `not_rejected`, and H1 `not_confirmed`. AS02 and all-assembly content is exploratory. `scientifically_eligible=false` and `final_test_read=false` remain unchanged.", "",
    ])
    return "\n".join(lines)


def build_dissertation_assets(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    formal3 = root / "outputs" / "formal" / "FORMAL-3_REAL_IMPORT_QC"
    formal4 = root / "outputs" / "formal" / "FORMAL-4_CORE_ANALYSIS"
    formal5 = root / "outputs" / "formal" / "FORMAL-5_FINAL_SYNTHESIS"
    dissertation = root / "docs" / "dissertation"
    final_figures = dissertation / "figures"
    final_tables = dissertation / "tables"
    final_md = dissertation / "FIGURE_AND_TABLE_MANIFEST.md"
    final_json = dissertation / "FIGURE_AND_TABLE_MANIFEST.json"
    targets = (final_figures, final_tables, final_md, final_json)
    existing = [str(path) for path in targets if path.exists()]
    if existing:
        raise FileExistsError(f"refusing to overwrite WRITE-2 outputs: {existing}")

    authority3 = verify_formal3_authority(formal3)
    authority4 = verify_formal4_output_hashes(formal4)
    authority5 = verify_formal5_output_hashes(formal5)
    if (authority3.active_count, authority3.excluded_count, authority3.outlier_sample_count) != (72, 19, 10):
        raise DissertationAssetError("FORMAL-3 selection or flag count changed")
    if authority4["artifact_count"] != 28 or authority5["artifact_count"] != 6:
        raise DissertationAssetError("FORMAL-4/5 artifact closure changed")
    _verify_source_hashes(formal4, FORMAL4_HASHES)
    _verify_source_hashes(formal5, FORMAL5_HASHES)
    claim = _read_json(formal5 / "final_claim_boundary.json")
    analysis_manifest = _read_json(formal5 / "final_analysis_manifest.json")
    if claim.get("disposition") != EXPECTED_DISPOSITION:
        raise DissertationAssetError("FORMAL-5 disposition changed")
    if claim.get("hypothesis_decisions") != {"H0": "not_rejected", "H1": "not_confirmed"}:
        raise DissertationAssetError("FORMAL-5 hypothesis decision changed")
    if claim.get("final_test_read") is not False or analysis_manifest.get("final_test_read") is not False:
        raise DissertationAssetError("final-test must remain unread")
    if analysis_manifest.get("selection", {}).get("selection_changed") is not False:
        raise DissertationAssetError("ACTIVE/EXCLUDED selection changed")

    table_names = (
        "repeatability_frequency.csv", "repeatability_summary.csv",
        "direction_pairwise_effects.csv", "direction_gain_summary.csv",
        "direction_gain_contrasts.csv", "configuration_effects.csv",
        "configuration_difference_curves.csv", "outlier_sensitivity.csv",
        "grouped_validation_metrics.csv",
    )
    tables = {name: _read_csv(formal4 / name) for name in table_names}
    primary_floor = _one(tables["repeatability_summary.csv"], band_id="primary")
    _close("primary floor median", primary_floor["median_pairwise_rms_db"], 0.3782942415603068)
    _close("primary floor IQR", primary_floor["iqr_pairwise_rms_db"], 0.2190678991596497)
    _close("primary floor p95", primary_floor["p95_pairwise_rms_db"], 0.8792543414488713)
    enc = _one(tables["direction_gain_summary.csv"], configuration="U4ENC", assembly_scope="AS01", band_id="primary", normalization="demeaned")
    sym = _one(tables["direction_gain_summary.csv"], configuration="U4SYM", assembly_scope="AS01", band_id="primary", normalization="demeaned")
    contrast = _one(tables["direction_gain_contrasts.csv"], assembly_scope="AS01", band_id="primary", normalization="demeaned")
    for label, value, expected in (
        ("U4ENC G", enc["gain"], 1.2805414340255579),
        ("U4SYM G", sym["gain"], 0.6823847630714056),
        ("delta G", contrast["u4enc_minus_u4sym_gain"], 0.5981566709541523),
        ("delta CI lower", contrast["bootstrap_ci95_low"], -0.11310886268350098),
    ):
        _close(label, value, expected)

    staging = dissertation / ".write2_assets_staging"
    if staging.exists():
        raise FileExistsError(f"refusing existing WRITE-2 staging directory: {staging}")
    figure_root = staging / "figures"
    table_root = staging / "tables"
    figure_root.mkdir(parents=True)
    table_root.mkdir(parents=True)
    _set_style()
    moved: list[Path] = []
    try:
        _figure_1(formal4, figure_root, tables)
        _figure_2(formal4, figure_root)
        _figure_3(figure_root, tables["direction_pairwise_effects.csv"])
        _figure_4(figure_root, tables["direction_gain_summary.csv"], tables["direction_gain_contrasts.csv"])
        _figure_5(figure_root, tables["configuration_difference_curves.csv"])
        _figure_6(figure_root, tables["outlier_sensitivity.csv"])
        _figure_7(formal4, figure_root, tables["grouped_validation_metrics.csv"])
        table_specs = _table_assets(table_root, tables)
        figures: list[dict[str, Any]] = []
        for spec in _figure_specs():
            files = []
            for suffix in (".png", ".svg"):
                path = figure_root / f"{spec['stem']}{suffix}"
                files.append({
                    "path": f"figures/{path.name}", "sha256": artifact_sha256(path),
                    "bytes": path.stat().st_size,
                })
            figures.append({
                **{key: value for key, value in spec.items() if key not in {"sources", "stem"}},
                "stem": spec["stem"], "files": files,
                "source_artifacts": [_source_entry(formal4, source) for source in spec["sources"]],
                "reproduction_script": "scripts/build_dissertation_results_assets.py",
                "claim_boundary": "supported_with_limits; no superiority or reliable-classification claim",
            })
        table_entries: list[dict[str, Any]] = []
        for spec in table_specs:
            files = []
            for filename in spec["files"]:
                path = table_root / filename
                files.append({
                    "path": f"tables/{filename}", "sha256": artifact_sha256(path),
                    "bytes": path.stat().st_size,
                })
            table_entries.append({
                **{key: value for key, value in spec.items() if key not in {"files", "source_artifacts"}},
                "files": files,
                "source_artifacts": [_source_entry(formal4, source) for source in spec["source_artifacts"]],
                "reproduction_script": "scripts/build_dissertation_results_assets.py",
            })
        script = root / "scripts" / "build_dissertation_results_assets.py"
        generator_module = root / "src" / "acoustic_encoder" / "dissertation_assets.py"
        payload: dict[str, Any] = {
            "schema_version": WRITE2_SCHEMA_VERSION,
            "source_commit": _git_commit(root),
            "disposition": EXPECTED_DISPOSITION,
            "hypothesis_decisions": {"H0": "not_rejected", "H1": "not_confirmed"},
            "selection": {"active_count": 72, "excluded_count": 19, "outlier_flag_count": 10, "selection_changed": False},
            "provenance": {
                "data_origin": "real_experiment",
                "dataset_role": "research_analysis",
                "run_purpose": "research_analysis",
                "scientifically_eligible": False,
            },
            "final_test_read": False,
            "source_authorities": {
                "formal3_artifact_manifest_sha256": authority3.artifact_manifest_sha256,
                "formal4_artifact_manifest_sha256": authority4["artifact_manifest_sha256"],
                "formal5_artifact_manifest_sha256": authority5["artifact_manifest_sha256"],
            },
            "reproduction_script": {"path": "scripts/build_dissertation_results_assets.py", "sha256": artifact_sha256(script)},
            "generator_module": {
                "path": "src/acoustic_encoder/dissertation_assets.py",
                "sha256": artifact_sha256(generator_module),
            },
            "figure_count": FIGURE_COUNT, "figure_file_count": FIGURE_COUNT * 2,
            "table_count": TABLE_COUNT, "table_file_count": TABLE_COUNT * 2,
            "png_minimum_dpi": PNG_DPI,
            "figures": figures, "tables": table_entries,
        }
        md_path = staging / "FIGURE_AND_TABLE_MANIFEST.md"
        json_path = staging / "FIGURE_AND_TABLE_MANIFEST.json"
        md_path.write_bytes(_manifest_markdown(payload).encode("utf-8"))
        payload["manifest_markdown"] = {
            "path": "FIGURE_AND_TABLE_MANIFEST.md", "sha256": artifact_sha256(md_path),
            "bytes": md_path.stat().st_size,
        }
        json_path.write_bytes(
            (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        verify_dissertation_assets(staging, verify_sources=False)
        for source, target in (
            (figure_root, final_figures), (table_root, final_tables),
            (md_path, final_md), (json_path, final_json),
        ):
            source.rename(target)
            moved.append(target)
        staging.rmdir()
        return payload
    except Exception:
        for path in reversed(moved):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_dissertation_assets(dissertation_root: str | Path, *, verify_sources: bool = False) -> dict[str, Any]:
    root = Path(dissertation_root).resolve()
    payload = _read_json(root / "FIGURE_AND_TABLE_MANIFEST.json")
    if payload.get("figure_count") != FIGURE_COUNT or payload.get("table_count") != TABLE_COUNT:
        raise DissertationAssetError("WRITE-2 figure/table count mismatch")
    if payload.get("disposition") != EXPECTED_DISPOSITION:
        raise DissertationAssetError("WRITE-2 disposition changed")
    if payload.get("hypothesis_decisions") != {"H0": "not_rejected", "H1": "not_confirmed"}:
        raise DissertationAssetError("WRITE-2 hypothesis decisions changed")
    if payload.get("final_test_read") is not False or payload.get("selection", {}).get("selection_changed") is not False:
        raise DissertationAssetError("WRITE-2 final-test/selection gate failed")
    figure_files = [file for item in payload["figures"] for file in item["files"]]
    table_files = [file for item in payload["tables"] for file in item["files"]]
    if len(figure_files) != 14 or len(table_files) != 8:
        raise DissertationAssetError("WRITE-2 asset file count mismatch")
    for entry in [*figure_files, *table_files, payload["manifest_markdown"]]:
        path = root / entry["path"]
        if not path.is_file() or artifact_sha256(path) != entry["sha256"]:
            raise DissertationAssetError(f"WRITE-2 output hash mismatch: {entry['path']}")
    for entry in figure_files:
        path = root / entry["path"]
        if path.suffix == ".png":
            with Image.open(path) as image:
                dpi = image.info.get("dpi", (0, 0))
                if min(float(dpi[0]), float(dpi[1])) < 299.0:
                    raise DissertationAssetError(f"PNG below 300 dpi: {entry['path']} -> {dpi}")
                if image.width < 1200 or image.height < 900:
                    raise DissertationAssetError(f"PNG pixel dimensions too small: {entry['path']}")
        elif path.suffix == ".svg":
            if ET.parse(path).getroot().tag.split("}")[-1] != "svg":
                raise DissertationAssetError(f"invalid SVG: {entry['path']}")
    if verify_sources:
        for item in [*payload["figures"], *payload["tables"]]:
            for source in item["source_artifacts"]:
                source_path = Path(source["path"])
                if not source_path.is_absolute():
                    raise DissertationAssetError("source verification requires absolute resolved source paths")
                if artifact_sha256(source_path) != source["sha256"]:
                    raise DissertationAssetError(f"WRITE-2 source hash mismatch: {source_path}")
    return {
        "all_match": True,
        "figure_count": FIGURE_COUNT,
        "figure_file_count": len(figure_files),
        "table_count": TABLE_COUNT,
        "table_file_count": len(table_files),
        "minimum_png_dpi": PNG_DPI,
    }
