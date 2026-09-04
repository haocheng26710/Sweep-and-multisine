"""Redraw one publication figure from sealed existing CSV exports.

This script changes labels and typography only.  It does not run a model,
search parameters, or alter any source evidence.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
ISOLATED = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P03_HR03_RETRY_01"
CONNECTED = ROOT / (
    "outputs/simulation/COMSOL_SCHEME_3A/"
    "P04C_SINGLE_ENTRY_TOPOLOGY_MODE_DIAGNOSTIC"
)


def normalised(series: pd.Series) -> pd.Series:
    return series / series.max()


reduced = pd.read_csv(ISOLATED / "reduced_fine_transfer_phase.csv")
thermoviscous = pd.read_csv(ISOLATED / "thermoviscous_fine_transfer_phase.csv")
energy = pd.read_csv(CONNECTED / "energy_long.csv")

r3 = energy.loc[
    (energy["module_id"] == "HR03")
    & energy["region"].isin(["whole_hr_module", "hr_cavity"])
]
pivot = r3.pivot(
    index="frequency_hz", columns="region", values="total_energy_J"
).sort_index()

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 8,
        "axes.labelsize": 8,
        "legend.fontsize": 6.6,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "axes.linewidth": 0.6,
    }
)

fig, ax = plt.subplots(figsize=(3.45, 2.35), constrained_layout=True)
ax.plot(
    reduced["frequency_hz"],
    normalised(reduced["magnitude"]),
    linewidth=1.1,
    label="Isolated reduced transfer",
)
ax.plot(
    thermoviscous["frequency_hz"],
    normalised(thermoviscous["magnitude"]),
    linewidth=1.1,
    label="Isolated thermoviscous transfer",
)
ax.plot(
    pivot.index,
    normalised(pivot["hr_cavity"]),
    linewidth=1.1,
    label="Connected cavity energy",
)
ax.plot(
    pivot.index,
    normalised(pivot["whole_hr_module"]),
    linewidth=1.1,
    linestyle="--",
    label="Connected resonator energy",
)
ax.axvspan(1900, 2000, color="0.75", alpha=0.25, linewidth=0)
ax.set_xlim(1000, 4250)
ax.set_ylim(0, 1.04)
ax.set_xlabel("Frequency (Hz)")
ax.set_ylabel("Normalised response")
ax.grid(True, linewidth=0.35, alpha=0.35)
ax.legend(loc="upper right", frameon=True, framealpha=0.92)

for language in ("english", "chinese"):
    destination = PACKAGE / language / "figures" / "r3_isolated_connected.png"
    fig.savefig(destination, dpi=600, bbox_inches="tight")

plt.close(fig)
