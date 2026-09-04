"""Read-only mesh-quality audit of the frozen RETRY_05 MPH.

This script loads an existing MPH and calls mesh statistics only. It never
runs a study, builds geometry, runs a mesh sequence, or saves the model.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import mph
import numpy as np


ROOT = Path(r"D:\Bristol course\dissertation\program work")
MPH_PATH = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_05/REPAIRED_ISO_CODED_N_FINE_4PT.mph"
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_N0_NUMERICAL_FEASIBILITY/mesh_quality_distribution.json"
TOTAL_TET = 856_786
THRESHOLDS = (1e-4, 1e-5, 1e-6, 1e-7)
HISTOGRAM_BINS = 10_000_000


def quantile_from_histogram(counts: np.ndarray, probability: float) -> dict[str, float | int]:
    target = probability * int(counts.sum())
    cumulative = np.cumsum(counts, dtype=np.int64)
    index = int(np.searchsorted(cumulative, target, side="left"))
    return {
        "probability": probability,
        "bin_index": index,
        "lower_bound": index / counts.size,
        "upper_bound": (index + 1) / counts.size,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cores", type=int, default=2)
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    client = None
    model = None
    try:
        client = (
            mph.start(cores=args.cores, version="6.4")
            if args.port is None
            else mph.Client(version="6.4", port=args.port)
        )
        if client.models():
            raise RuntimeError(f"Fresh-session gate failed: {client.models()}")
        model = client.load(MPH_PATH)
        mesh = model.java.component("comp1").mesh("mesh1")
        measure = "volcircum (MeshSequence direct-method default per COMSOL 6.4 API)"
        counts = np.asarray(mesh.getQualityDistr("tet", HISTOGRAM_BINS), dtype=np.int64)
        observed_total = int(counts.sum())
        if observed_total != TOTAL_TET:
            raise RuntimeError(f"tet histogram count {observed_total} != authority {TOTAL_TET}")

        threshold_rows = []
        for threshold in THRESHOLDS:
            boundary = int(round(threshold * HISTOGRAM_BINS))
            count = int(counts[:boundary].sum())
            threshold_rows.append({
                "threshold": threshold,
                "count_below": count,
                "proportion": count / observed_total,
                "exact_at_histogram_boundary": True,
            })

        below_1e7 = threshold_rows[-1]["count_below"]
        record = {
            "audit_type": "read_only_saved_mph_mesh_statistics",
            "completed_at": datetime.now().astimezone().isoformat(),
            "source_mph": MPH_PATH.relative_to(ROOT).as_posix(),
            "model_saved": False,
            "study_run_calls": 0,
            "geometry_run_calls": 0,
            "mesh_run_calls": 0,
            "quality_measure": measure,
            "element_type": "tet",
            "elements": int(mesh.getNumElem("tet")),
            "vertices": int(mesh.getNumVertex()),
            "minimum_quality": float(mesh.getMinQuality("tet")),
            "mean_quality": float(mesh.getMeanQuality("tet")),
            "histogram_bins": HISTOGRAM_BINS,
            "histogram_bin_width": 1 / HISTOGRAM_BINS,
            "thresholds": threshold_rows,
            "below_1e8": {
                "exact_count": None,
                "exact_proportion": None,
                "lower_bound_count": 1 if float(mesh.getMinQuality("tet")) < 1e-8 else 0,
                "upper_bound_count": below_1e7,
                "lower_bound_proportion": (1 if float(mesh.getMinQuality("tet")) < 1e-8 else 0) / observed_total,
                "upper_bound_proportion": below_1e7 / observed_total,
                "reason": "Exact 1e-8 boundary requires a 100,000,000-bin Java array; omitted by the bounded resource gate.",
            },
            "quantile_intervals": [
                quantile_from_histogram(counts, probability)
                for probability in (0.000001, 0.00001, 0.0001, 0.001, 0.01, 0.05, 0.5, 0.95, 0.99)
            ],
            "histogram_retained": False,
            "final_test_read": False,
        }
        OUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(record, ensure_ascii=False, indent=2))
    finally:
        if client is not None:
            if model is not None:
                try:
                    client.remove(model)
                except Exception:
                    pass
            client.disconnect()


if __name__ == "__main__":
    main()
