"""Read-only extraction of the frozen INFO-TOP-2 spatial anchor."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import mph
import numpy as np


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/info_top/INFO_TOP_2_INFORMATION_COST_CURVE"
MPH = ROOT / "outputs/simulation/COMSOL_TRANS_1_R256_RESUMABLE_GATE/chunks/coarse/chunk_000.completed/model.mph"


def main() -> None:
    candidates = json.loads((OUT / "microphone_candidates.json").read_text(encoding="utf-8"))["candidates"]
    client = mph.start(cores=1, version="6.4")
    try:
        model = client.load(MPH)
        java = model.java
        solution_dataset = [node for node in list(model / "datasets") if node.tag() == "dset1"]
        if len(solution_dataset) != 1:
            raise RuntimeError("Expected exactly one dset1 solution dataset")
        base_frequency = np.asarray(model.evaluate("freq", dataset=solution_dataset[0])).real.reshape(-1)
        existing_mic = np.asarray(model.evaluate("aveop_mic(acpr.p_t)/p_inc", dataset=solution_dataset[0])).reshape(-1)
        pressure = np.empty((len(candidates), base_frequency.size), dtype=complex)
        for index, row in enumerate(candidates):
            dtag = f"top2_anchor_pt_{index:02d}"
            etag = f"top2_anchor_pev_{index:02d}"
            for group, tag in ((java.result().numerical(), etag), (java.result().dataset(), dtag)):
                try:
                    group.remove(tag)
                except Exception:
                    pass
            dataset = java.result().dataset().create(dtag, "CutPoint3D")
            dataset.set("data", "dset1")
            dataset.set("pointx", [f"{float(row['x_m']):.17g}"])
            dataset.set("pointy", [f"{float(row['y_m']):.17g}"])
            dataset.set("pointz", [f"{float(row['z_m']):.17g}"])
            evaluator = java.result().numerical().create(etag, "EvalPoint")
            evaluator.set("data", dtag)
            evaluator.set("expr", ["freq", "acpr.p_t/p_inc"])
            real = np.asarray(evaluator.getReal())
            imag = np.asarray(evaluator.getImag()) if evaluator.isComplex() else np.zeros_like(real)
            frequency = real[0].reshape(-1)
            values = (real + 1j * imag)[1].reshape(-1)
            if not np.array_equal(frequency, base_frequency) or not np.all(np.isfinite(values)) or not np.iscomplexobj(values):
                raise RuntimeError(f"Candidate QC failed without coordinate repair: {row['id']}")
            pressure[index] = values
            java.result().numerical().remove(etag)
            java.result().dataset().remove(dtag)
        np.savez_compressed(
            OUT / "path_a_spatial_anchor.npz",
            frequency=base_frequency,
            pressure=pressure,
            candidate_id=np.asarray([row["id"] for row in candidates]),
            existing_mic=existing_mic,
        )
        with (OUT / "path_a_spatial_anchor.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["candidate_id", "frequency_hz", "pressure_real", "pressure_imag"])
            for row, values in zip(candidates, pressure, strict=True):
                for frequency, value in zip(base_frequency, values, strict=True):
                    writer.writerow([row["id"], f"{frequency:.17g}", f"{value.real:.17g}", f"{value.imag:.17g}"])
        audit = {
            "schema_version": "info_top_2_spatial_anchor_audit_v1",
            "mph": str(MPH.relative_to(ROOT)).replace("\\", "/"),
            "mph_sha256": hashlib.sha256(MPH.read_bytes()).hexdigest(),
            "candidate_count": len(candidates),
            "frequency_count": int(base_frequency.size),
            "all_finite_complex": bool(np.all(np.isfinite(pressure)) and np.iscomplexobj(pressure)),
            "frequency_exactly_dset1": True,
            "temporary_nodes_removed": True,
            "model_saved": False,
            "study_run_called": False,
            "final_test_read": False,
        }
        (OUT / "path_a_spatial_anchor_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    finally:
        client.clear()


if __name__ == "__main__":
    main()
