"""Read actual mesh statistics from the ten saved P04B-N MPH files."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION"
sys.path.insert(0, str(OUT/"_pydeps"))

import mph


def main() -> None:
    paths = [(f"HR{i:02d}", "production", OUT/f"P04BN_HR{i:02d}_PRODUCTION.mph") for i in range(1, 9)]
    paths += [(module, "second_mesh_verification", OUT/f"P04BN_{module}_MESH2.mph") for module in ("HR04", "HR07")]
    rows = []
    client = mph.Client(version="6.4", cores=2)
    try:
        for module, role, path in paths:
            model = client.load(path)
            mesh = model.java.component("comp1").mesh("mesh1")
            rows.append({
                "module_id": module,
                "role": role,
                "automatic_size": 6 if role == "production" else 5,
                "frequency_control_hz": 25000.0,
                "elements": int(mesh.getNumElem()),
                "vertices": int(mesh.getNumVertex()),
                "minimum_quality": float(mesh.getMinQuality()),
                "mean_quality": float(mesh.getMeanQuality()),
                "maximum_growth_rate": float(mesh.getMaxGrowthRate()),
                "minimum_element_volume_m3": float(mesh.getMinVolume()),
                "maximum_element_volume_m3": float(mesh.getMaxVolume()),
                "second_order_elements": bool(mesh.hasSecondOrderElements()),
                "model_path": str(path.relative_to(ROOT)),
            })
            print(module, role, rows[-1]["elements"], flush=True)
            client.remove(model)
    finally:
        client.clear()
    with (OUT/"mesh_statistics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    p03 = json.loads((ROOT/"outputs/simulation/COMSOL_SCHEME_3A/P03_HR03_RETRY_01/mesh_statistics.json").read_text(encoding="utf-8"))
    (OUT/"mesh_statistics.json").write_text(json.dumps({
        "phase_id": "P04B-NOMINAL_AS_DESIGNED_CROSS_MODULE_VALIDATION",
        "mesh_rule": "Pressure Acoustics physics-controlled mesh with 25 kHz frequency control; production automatic size 6; verification automatic size 5",
        "p04bn_models": rows,
        "p03_existing_hr03_dual_mesh_statistics": p03,
        "final_test_read": False,
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
