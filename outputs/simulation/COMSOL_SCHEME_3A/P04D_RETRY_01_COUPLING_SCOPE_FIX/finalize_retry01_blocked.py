"""Finalize the immutable P04D RETRY_01 smoke-failure record."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04D_RETRY_01_COUPLING_SCOPE_FIX"
REPORT = ROOT / "docs/progress/COMSOL_3A_P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL_RETRY_01.md"
STATUS = "P04D RETRY_01 BLOCKED_BY_SOLVER"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    smoke = json.loads((OUT / "coupling_smoke_test.json").read_text(encoding="utf-8"))
    activation = json.loads((OUT / "study_activation_audit.json").read_text(encoding="utf-8"))["smoke"]
    coupling = json.loads((OUT / "coupling_configuration_audit.json").read_text(encoding="utf-8"))["smoke"]
    write_json(
        OUT / "formal_solver_result.json",
        {
            "phase_id": "P04D_RETRY_01_COUPLING_SCOPE_FIX",
            "status": "NOT_RUN_SMOKE_FAILED",
            "technical_status": STATUS,
            "formal_study_run_count": 0,
            "formal_frequency_count": 0,
            "formal_mph_created": False,
            "reason": "The single authorized 1650 Hz smoke failed during equation assembly with the same acpr.p_t scope error; the frozen stop rule prohibited the formal band.",
            "final_test_read": False,
        },
    )
    write_json(
        OUT / "scientific_classification.json",
        {
            "phase_id": "P04D_RETRY_01_COUPLING_SCOPE_FIX",
            "technical_status": STATUS,
            "scientific_classification": None,
            "smoke_pass": False,
            "acpr_active": activation["acpr_activate_readback"],
            "ta_active": activation["ta_activate_readback"],
            "single_all_boundaries_coupling": coupling["single_acoustic_thermoviscous_coupling"],
            "crossing_identity_pass": coupling["derived_crossing_groups"] == {"inner": [262, 263, 264, 265, 279], "outer": [257, 259, 260, 261, 284]},
            "acpr_p_t_scope_error_persists": "comp1.acpr.p_t" in smoke["raw_error"],
            "formal_band_run": False,
            "continuous_repair_stopped": True,
            "original_p04d_status_retained": "P04D BLOCKED_BY_SOLVER",
            "no_u4_authorization": True,
            "final_test_read": False,
        },
    )

    fig, axis = plt.subplots(figsize=(11.0, 5.5), dpi=160)
    axis.axis("off")
    stages = [
        ("Original P04D\n24/24 SHA", "PASS", "#2e7d32"),
        ("Single atb_p04d\nAll boundaries", "PASS", "#2e7d32"),
        ("Study activation\nacpr + ta", "PASS", "#2e7d32"),
        ("1650 Hz smoke\nequation assembly", "FAILED", "#b71c1c"),
        ("Formal band", "NOT RUN", "#555555"),
    ]
    for index, (label, state, color) in enumerate(stages):
        x = 0.02 + index * 0.196
        axis.add_patch(plt.Rectangle((x, 0.48), 0.165, 0.24, facecolor=color, alpha=0.11, edgecolor=color, linewidth=2))
        axis.text(x + 0.0825, 0.62, label, ha="center", va="center", fontsize=9.5)
        axis.text(x + 0.0825, 0.515, state, ha="center", va="center", fontsize=10.5, weight="bold", color=color)
        if index < len(stages) - 1:
            axis.annotate("", xy=(x + 0.19, 0.60), xytext=(x + 0.168, 0.60), arrowprops={"arrowstyle": "->", "color": "#555"})
    axis.text(0.5, 0.88, "P04D RETRY_01 — PA–TV Coupling Scope Fix", ha="center", fontsize=16, weight="bold")
    axis.text(0.5, 0.81, STATUS, ha="center", fontsize=14, weight="bold", color="#b71c1c")
    axis.text(0.5, 0.32, "acpr.p_t remained undefined on TV domain 45 across all 10 PA–TV crossing boundaries.", ha="center", fontsize=10.5)
    axis.text(0.5, 0.24, "Reduced/full-TV scientific comparison unavailable: no formal full-TV frequency solution exists.", ha="center", fontsize=10.5)
    axis.text(0.5, 0.15, "No RETRY_02 · no P05/P06/U4 · final_test_read=false", ha="center", fontsize=10, color="#444")
    fig.savefig(OUT / "P04D_RETRY_01_REDUCED_FULL_TV_COMPARISON_UNAVAILABLE.png", bbox_inches="tight")
    plt.close(fig)

    if not REPORT.exists():
        raise RuntimeError("Progress report missing")
    files = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != "SHA256SUMS") + [REPORT]
    lines = [f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}" for path in files]
    (OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
