"""Build the paper-ready GEN-ENC-4 M0/M1 figure pack.

This script only reads sealed reduced-model artefacts.  It does not rerun M0,
M1, M2, M3, COMSOL, or any physical model.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "outputs/gen_enc/GEN_ENC_4_TOPOLOGY_PRESERVING_M0_M1"
OUT = ROOT / "figures"
COMPARISON = ROOT / "comparison/comparison_summary.json"
CONTRACT = ROOT / "mapping_contract.json"
TERMINAL = ROOT / "terminal.json"

FAMILIES = (
    "HAND_DESIGNED",
    "NEAR_INDEPENDENT",
    "FIXED_SEED_RANDOM_DISORDERED",
    "PHYSICS_METAMATERIAL_INSPIRED",
)
SHORT = {
    "HAND_DESIGNED": "HAND",
    "NEAR_INDEPENDENT": "NEAR",
    "FIXED_SEED_RANDOM_DISORDERED": "RANDOM",
    "PHYSICS_METAMATERIAL_INSPIRED": "PHYSICS",
}
COLORS = {
    "HAND_DESIGNED": "#4c78a8",
    "NEAR_INDEPENDENT": "#59a14f",
    "FIXED_SEED_RANDOM_DISORDERED": "#f28e2b",
    "PHYSICS_METAMATERIAL_INSPIRED": "#e15759",
}
STATE_COLORS = ("#4c78a8", "#f28e2b", "#59a14f", "#e15759")
STATE_LABELS = ("0°", "90°", "180°", "270°")
DISCLAIMER = (
    "Five-node lumped-parameter reduced model; not a COMSOL spatial field, "
    "fabricated-device result, or physical measurement."
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def configure() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.5,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9.5,
            "legend.fontsize": 8.5,
            "figure.titlesize": 14,
            "axes.linewidth": 0.8,
            "svg.fonttype": "none",
            "svg.hashsalt": "gen-enc-4-m0-m1-figure-pack-v1",
        }
    )


def save_pair(fig: plt.Figure, stem: str) -> list[Path]:
    png = OUT / f"{stem}.png"
    svg = OUT / f"{stem}.svg"
    metadata = {"Creator": "GEN-ENC-4 M0/M1 figure pack"}
    fig.savefig(png, dpi=300, bbox_inches="tight", facecolor="white", metadata=metadata)
    fig.savefig(svg, bbox_inches="tight", facecolor="white", metadata=metadata)
    plt.close(fig)
    return [png, svg]


def footer(fig: plt.Figure) -> None:
    fig.text(0.5, 0.012, DISCLAIMER, ha="center", va="bottom", fontsize=8, color="#555555")


def draw_network(ax: plt.Axes, local_edges: list[tuple[int, int]], *, weak: bool = False) -> None:
    positions = {
        0: np.array([0.0, 1.0]),
        90: np.array([1.0, 0.0]),
        180: np.array([0.0, -1.0]),
        270: np.array([-1.0, 0.0]),
        "C": np.array([0.0, 0.0]),
    }
    for angle in (0, 90, 180, 270):
        p = positions[angle]
        ax.plot([p[0], 0], [p[1], 0], color="#777777", lw=1.4, zorder=1)
    for left, right in local_edges:
        p, q = positions[left], positions[right]
        ax.plot(
            [p[0], q[0]],
            [p[1], q[1]],
            color="#d24a43",
            lw=1.5 if not weak else 1.0,
            ls="--" if weak else "-",
            alpha=0.45 if weak else 0.9,
            zorder=0,
        )
    for angle in (0, 90, 180, 270):
        x, y = positions[angle]
        ax.scatter(x, y, s=135, color="#c7d4e8", edgecolor="#355d8a", linewidth=1.0, zorder=3)
        ax.text(x, y, f"L{angle}", ha="center", va="center", fontsize=7.5, zorder=4)
    ax.scatter(0, 0, s=175, color="#f3cf78", edgecolor="#8a6a21", linewidth=1.0, zorder=3)
    ax.text(0, 0, "C", ha="center", va="center", fontsize=8, fontweight="bold", zorder=4)
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-1.35, 1.35)
    ax.set_aspect("equal")
    ax.axis("off")


def topology_figure() -> list[Path]:
    random_summary = read_json(
        ROOT / "m1/single_use_validation/candidates/RANDOM_10/candidate_summary.json"
    )
    random_edges = [
        (int(edge["left_angle"]), int(edge["right_angle"]))
        for edge in random_summary["topology_audit"]["active_edges"]
    ]
    complete_edges = [(0, 90), (0, 180), (0, 270), (90, 180), (90, 270), (180, 270)]
    ring_edges = [(0, 90), (90, 180), (180, 270), (270, 0)]

    fig = plt.figure(figsize=(13.2, 7.2))
    grid = fig.add_gridspec(2, 4, height_ratios=(1.0, 1.05), hspace=0.34, wspace=0.12)
    ax0 = fig.add_subplot(grid[0, 1:3])
    draw_network(ax0, [])
    ax0.set_title("M0: all families represented by the same star topology", pad=2)
    ax0.text(0, -1.27, "Family-specific edges are averaged into four effective radial branches", ha="center", va="top", fontsize=8.5)

    specs = [
        ("HAND", [], False, "No local–local edge"),
        ("NEAR", complete_edges, True, "Six equal weak edges"),
        ("RANDOM", random_edges, False, "Explicit sparse edges;\nzeros remain absent"),
        ("PHYSICS", ring_edges, False, "Four explicit ordered\nring edges"),
    ]
    for index, (name, edges, weak, subtitle) in enumerate(specs):
        ax = fig.add_subplot(grid[1, index])
        draw_network(ax, edges, weak=weak)
        ax.set_title(f"M1 {name}\n{subtitle}", pad=1, fontsize=9.5)

    fig.suptitle("M0-to-M1 topology representation at a common five-node scale", y=0.985)
    footer(fig)
    fig.subplots_adjust(bottom=0.065, top=0.92)
    return save_pair(fig, "fig01_m0_m1_topology_same_scale")


def add_box(ax: plt.Axes, xy: tuple[float, float], wh: tuple[float, float], text: str, *, color: str) -> None:
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.015",
        linewidth=1.0, edgecolor=color, facecolor=color + "18"
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9)


def add_arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=12, lw=1.1, color="#555555"))


def mapping_figure() -> list[Path]:
    fig, ax = plt.subplots(figsize=(13.2, 6.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.015, 0.78, "M0", fontsize=13, fontweight="bold", va="center")
    ax.text(0.015, 0.30, "M1", fontsize=13, fontweight="bold", va="center")
    xs = (0.07, 0.28, 0.50, 0.72)
    w, h = 0.17, 0.19
    m0 = (
        "Family edge\ncoordinates",
        "Average edges\nby local node",
        "Four effective\nradial branches",
        "Common star matrix\nA₀(ω)",
    )
    m1 = (
        "Family-specific\nexplicit edges e",
        "Per-edge admittance\nYₑ(ω)=1/(Rₑ+jωMₑ)",
        "Graph Laplacian\nBᵀ diag(Yₑ) B",
        "Family matrix\nA_f(ω) and readout y",
    )
    for row_y, labels, color in ((0.68, m0, "#4c78a8"), (0.20, m1, "#e15759")):
        for index, (x, label) in enumerate(zip(xs, labels)):
            add_box(ax, (x, row_y), (w, h), label, color=color)
            if index < len(xs) - 1:
                add_arrow(ax, (x + w + 0.01, row_y + h / 2), (xs[index + 1] - 0.01, row_y + h / 2))
    ax.text(0.405, 0.62, "Topology information compressed", ha="center", va="top", color="#4c78a8", fontsize=9)
    ax.text(0.405, 0.14, "Adjacency and loops retained in the system matrix", ha="center", va="top", color="#b73b35", fontsize=9)
    ax.text(
        0.92, 0.30,
        "Frozen in both:\n• 5 nodes\n• frequency grid\n• nuisance design\n• central readout\n• no path phase\n• no added resonator",
        ha="left", va="center", fontsize=8.7,
        bbox={"boxstyle": "round,pad=0.4", "fc": "#f2f2f2", "ec": "#888888", "lw": 0.8},
    )
    fig.suptitle("M0 averaging versus M1 per-edge matrix assembly", y=0.98)
    footer(fig)
    fig.subplots_adjust(bottom=0.09, top=0.91, left=0.03, right=0.98)
    return save_pair(fig, "fig02_m0_m1_mapping_flow")


def trapezoidal_weights(grid: np.ndarray) -> np.ndarray:
    delta = np.diff(grid)
    weights = np.empty_like(grid)
    weights[0] = delta[0] / 2.0
    weights[-1] = delta[-1] / 2.0
    weights[1:-1] = (delta[:-1] + delta[1:]) / 2.0
    return weights / weights.sum()


def representative_response_figure() -> list[Path]:
    frequency = 200.0 * np.power(2.0, np.arange(208, dtype=float) / 48.0)
    weights = trapezoidal_weights(frequency)
    response = {}
    for family in FAMILIES:
        prefix = {"HAND_DESIGNED": "HAND", "NEAR_INDEPENDENT": "NEAR", "FIXED_SEED_RANDOM_DISORDERED": "RANDOM", "PHYSICS_METAMATERIAL_INSPIRED": "PHYSICS"}[family]
        path = ROOT / f"m1/single_use_validation/candidates/{prefix}_10/compact/mean_response_signature.npy"
        array = np.load(path, allow_pickle=False).reshape((208, 4, 4), order="C")
        unweighted = array / np.sqrt(weights)[:, None, None]
        response[family] = np.linalg.norm(unweighted, axis=1)
    global_max = max(float(np.max(value)) for value in response.values())

    fig, axes = plt.subplots(2, 2, figsize=(11.4, 8.6), sharex=True, sharey=True)
    for ax, family in zip(axes.flat, FAMILIES):
        values = response[family] / global_max
        for state_index, (label, color) in enumerate(zip(STATE_LABELS, STATE_COLORS)):
            ax.plot(frequency, values[:, state_index], color=color, lw=1.25, label=label)
        ax.set_xscale("log", base=2)
        ax.set_xlim(frequency[0], frequency[-1])
        ax.set_ylim(0, 1.03)
        ax.set_title(f"{SHORT[family]} representative (identity 10)")
        ax.grid(True, which="both", color="#dddddd", linewidth=0.55)
        ax.set_xticks([200, 400, 800, 1600, 3200])
        ax.get_xaxis().set_major_formatter(mpl.ticker.ScalarFormatter())
    for ax in axes[-1, :]:
        ax.set_xlabel("Frequency (Hz)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Differential-response amplitude\n(global-normalized, a.u.)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, title="Input state", ncol=4, loc="upper center", bbox_to_anchor=(0.5, 0.925), frameon=False)
    fig.suptitle("Representative M1 central-readout differential responses", y=0.985)
    fig.text(0.5, 0.045, "Curves are nuisance/repeat means; normalization is shared across all four panels.", ha="center", fontsize=8.5, color="#555555")
    footer(fig)
    fig.subplots_adjust(bottom=0.105, top=0.84, hspace=0.28, wspace=0.16)
    return save_pair(fig, "fig03_m1_representative_frequency_response")


def comparison_figure(comparison: dict) -> list[Path]:
    development = comparison["partitions"]["development"]
    validation = comparison["partitions"]["single_use_validation"]
    fig = plt.figure(figsize=(12.0, 8.8))
    grid = fig.add_gridspec(2, 2, hspace=0.40, wspace=0.28)

    ax = fig.add_subplot(grid[0, 0])
    labels = ["D min", "D mean", "V min", "V mean"]
    m0 = [
        development["geometry_separation"]["m0"]["minimum_between_within_ratio"],
        development["geometry_separation"]["m0"]["mean_between_within_ratio"],
        validation["geometry_separation"]["m0"]["minimum_between_within_ratio"],
        validation["geometry_separation"]["m0"]["mean_between_within_ratio"],
    ]
    m1 = [
        development["geometry_separation"]["m1"]["minimum_between_within_ratio"],
        development["geometry_separation"]["m1"]["mean_between_within_ratio"],
        validation["geometry_separation"]["m1"]["minimum_between_within_ratio"],
        validation["geometry_separation"]["m1"]["mean_between_within_ratio"],
    ]
    x = np.arange(len(labels))
    ax.bar(x - 0.18, m0, width=0.36, color="#9aa1a8", label="M0")
    ax.bar(x + 0.18, m1, width=0.36, color="#4c78a8", label="M1")
    ax.axhline(1.0, color="#b73b35", lw=1.0, ls="--", label="between = within")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Between/within separation ratio")
    ax.set_title("(a) Geometry separation improves, but remains < 1")
    ax.legend(frameon=False, ncol=3, loc="upper left")
    ax.grid(axis="y", color="#dddddd", linewidth=0.55)

    ax = fig.add_subplot(grid[0, 1])
    endpoints = validation["family_endpoints"]
    margin_ppm = [endpoints[f]["margin_mean_relative_change"] * 1e6 for f in FAMILIES]
    drift_ppm = [endpoints[f]["drift_mean_relative_change"] * 1e6 for f in FAMILIES]
    x = np.arange(4)
    ax.bar(x - 0.18, margin_ppm, width=0.36, color="#59a14f", label="S_min (higher is favorable)")
    ax.bar(x + 0.18, drift_ppm, width=0.36, color="#e15759", label="U_drift (higher is unfavorable)")
    ax.axhline(0, color="#555555", lw=0.8)
    ax.set_xticks(x, [SHORT[f] for f in FAMILIES], rotation=18, ha="right")
    ax.set_ylabel("M1 relative to M0 (ppm)")
    ax.set_title("(b) Endpoint effects are only tens of ppm")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(axis="y", color="#dddddd", linewidth=0.55)

    ax = fig.add_subplot(grid[1, 0])
    weakest = validation["weakest_pair"]
    p0270 = [weakest["m1"][f]["mean_probability"][2] * 100 for f in FAMILIES]
    p0090 = [weakest["m1"][f]["mean_probability"][0] * 100 for f in FAMILIES]
    x = np.arange(4)
    ax.bar(x, p0270, color="#4c78a8", label="(0°, 270°)")
    ax.bar(x, p0090, bottom=p0270, color="#f28e2b", label="(0°, 90°)")
    ax.axhline(100, color="#555555", lw=0.9, ls="--")
    ax.set_xticks(x, [SHORT[f] for f in FAMILIES], rotation=18, ha="right")
    ax.set_ylim(0, 104)
    ax.set_ylabel("M1 weakest-pair probability (%)")
    ax.set_title("(c) Weakest pair changes only for RANDOM/PHYSICS")
    ax.legend(frameon=False, loc="lower left")
    ax.grid(axis="y", color="#dddddd", linewidth=0.55)

    ax = fig.add_subplot(grid[1, 1])
    p_value = comparison["m1_family_inference"]["validation"]["minimum_adjusted_p"]
    ax.barh([0], [p_value], height=0.38, color="#4c78a8")
    ax.axvline(0.05, color="#b73b35", lw=1.2, ls="--", label="pre-registered α = 0.05")
    ax.set_xlim(0, 0.11)
    ax.set_yticks([])
    ax.set_xlabel("FWER-adjusted p value")
    ax.set_title("(d) No multiplicity-adjusted family contrast passes")
    ax.text(0.002, 0.20, "Validation minimum", va="center", ha="left", fontsize=8.5, color="#333333")
    ax.text(p_value + 0.002, 0, f"{p_value:.3f}", va="center", ha="left")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="x", color="#dddddd", linewidth=0.55)

    fig.suptitle("M0→M1 comparison: repeatable geometric gain without stable family separation", y=0.985)
    footer(fig)
    fig.subplots_adjust(bottom=0.10, top=0.91, left=0.085, right=0.97)
    return save_pair(fig, "fig04_m0_m1_separation_endpoints_weakest_pair")


def write_readme(outputs: list[Path]) -> Path:
    path = OUT / "README.md"
    text = """# GEN-ENC-4 M0/M1 paper figure pack

All figures are derived from the sealed GEN-ENC-4 M0/M1 five-node lumped-parameter reduced-model outputs. They are not COMSOL spatial fields, fabricated-device results, or measurements.

1. `fig01_m0_m1_topology_same_scale`: M0 common star and M1 family-specific explicit adjacency at the same node scale.
2. `fig02_m0_m1_mapping_flow`: M0 node-averaging path versus M1 per-edge admittance/Laplacian assembly.
3. `fig03_m1_representative_frequency_response`: nuisance/repeat-mean M1 differential responses for frozen identity 10 in each family, globally normalized.
4. `fig04_m0_m1_separation_endpoints_weakest_pair`: development/validation separation ratio, validation S_min and U_drift changes, weakest-pair redistribution, and adjusted inference result.

Suggested combined caption: *Topology-faithful five-node reduced-model comparison. M1 preserves family-specific local–local edges in the system matrix while keeping the M0 node count, frequency grid, nuisance design and central single-microphone readout fixed. Explicit topology produces a repeatable increase in between/within geometry ratios and limited weakest-pair redistribution, but endpoint changes remain small and no validation family contrast passes multiplicity adjustment. These results are reduced-model evidence only.*
"""
    path.write_text(text, encoding="utf-8")
    return path


def main() -> int:
    configure()
    OUT.mkdir(parents=True, exist_ok=True)
    comparison = read_json(COMPARISON)
    terminal = read_json(TERMINAL)
    if terminal["status"] != "GEN_ENC_4_M1_NO_MEANINGFUL_GAIN_OVER_M0":
        raise RuntimeError("Unexpected sealed GEN-ENC-4 terminal")
    if terminal["m2_started"] or terminal["m3_started"]:
        raise RuntimeError("Figure pack must not run after M2/M3 start in this stage")

    outputs: list[Path] = []
    outputs += topology_figure()
    outputs += mapping_figure()
    outputs += representative_response_figure()
    outputs += comparison_figure(comparison)
    outputs.append(write_readme(outputs))

    manifest = {
        "schema_version": "gen_enc_4_m0_m1_figure_pack_v1",
        "status": "COMPLETE",
        "scientific_scope": "SEALED_M0_M1_FIVE_NODE_LUMPED_PARAMETER_REDUCED_MODEL_ONLY",
        "comsol_or_physical_claim": False,
        "m0_m1_recomputed": False,
        "m2_started": False,
        "m3_started": False,
        "inputs": {str(path.relative_to(REPO)).replace("\\", "/"): sha256(path) for path in (COMPARISON, CONTRACT, TERMINAL)},
        "outputs": {},
    }
    manifest_path = OUT / "figure_manifest.json"
    for path in outputs:
        manifest["outputs"][str(path.relative_to(REPO)).replace("\\", "/")] = {
            "sha256": sha256(path), "bytes": path.stat().st_size
        }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "COMPLETE", "output_count": len(outputs) + 1, "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
