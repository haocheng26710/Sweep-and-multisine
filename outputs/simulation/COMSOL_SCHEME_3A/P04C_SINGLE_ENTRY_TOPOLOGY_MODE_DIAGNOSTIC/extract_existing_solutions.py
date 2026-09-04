"""P04C read-only extraction from already-solved COMSOL models.

The script never calls a study, mesh build, geometry build, save, or solve.
Temporary coupling operators exist only in the unsaved in-memory model.
"""
from __future__ import annotations

import csv
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04C_SINGLE_ENTRY_TOPOLOGY_MODE_DIAGNOSTIC"
P04B = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION"
P03 = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P03_HR03_RETRY_01"
P04A = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04A_GLOBAL_CALIBRATION"
sys.path.insert(0, r"C:\Users\Firefly\AppData\Local\Temp\p04bn_pydeps_20260825")

import mph
import numpy as np

REGIONS = [
    ("hr_neck_inner", "sel_hr_neck_inner"),
    ("hr_cavity", "sel_hr_cavity"),
    ("hr_neck_outer", "sel_hr_neck_outer"),
    ("whole_hr_module", "sel_hr_module_all"),
    ("fixed_inner_passage", "sel_fixed_inner_000"),
    ("shared_chamber", "sel_chamber"),
    ("fixed_outer_passage", "sel_fixed_outer_000"),
    ("whole_fluid", "sel_fluid_all"),
]
LEAF = ["hr_neck_inner", "hr_cavity", "hr_neck_outer", "fixed_inner_passage", "shared_chamber", "fixed_outer_passage"]
EP = "abs(acpr.p_t)^2/(4*rho0_nom*c0_nom^2)"
EK = "(abs(d(acpr.p_t,x))^2+abs(d(acpr.p_t,y))^2+abs(d(acpr.p_t,z))^2)/(4*rho0_nom*(2*pi*freq)^2)"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def manifest_inputs() -> dict:
    model_rows = []
    with (P04B / "model_manifest.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            path = ROOT / row["model_path"]
            actual = sha256(path)
            model_rows.append({
                "module_id": row["module_id"], "role": row["role"],
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "expected_sha256": row["model_sha256"], "actual_sha256": actual,
                "hash_match": actual == row["model_sha256"],
            })
    extra = []
    for path in [
        P03 / "COMSOL_3A_P03_HR03_RETRY_01_REDUCED_COARSE.mph",
        P03 / "COMSOL_3A_P03_HR03_RETRY_01_REDUCED_FINE.mph",
        P03 / "COMSOL_3A_P03_HR03_RETRY_01_THERMOVISCOUS_COARSE.mph",
        P03 / "COMSOL_3A_P03_HR03_RETRY_01_THERMOVISCOUS_FINE.mph",
        P04A / "P04A_HR03_NOMINAL.mph",
    ]:
        extra.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "actual_sha256": sha256(path)})
    if not all(row["hash_match"] for row in model_rows):
        raise RuntimeError("P04B model hash mismatch")
    return {
        "phase_id": "P04C_SINGLE_ENTRY_TOPOLOGY_MODE_DIAGNOSTIC",
        "contract_sha256": sha256(OUT / "diagnostic_contract.json"),
        "authority_manifest_reverification": {"P03": "37/37", "P04A": "124/124", "P04B-N": "94/94"},
        "p04b_models": model_rows,
        "supporting_models": extra,
        "read_only": True,
        "study_run_calls": 0,
        "model_save_calls": 0,
        "final_test_read": False,
    }


def as_series(value, count: int) -> np.ndarray:
    array = np.asarray(value).reshape(-1)
    if array.size != count:
        raise RuntimeError(f"Expected {count} values, got {array.size}")
    return array


def extract_one(client, path: Path, module: str, role: str):
    model = client.load(path)
    selection_rows = []
    try:
        java = model.java
        component = java.component("comp1")
        datasets = list(java.result().dataset().tags())
        solutions = list(java.sol().tags())
        if "dset1" not in datasets or "sol1" not in solutions:
            raise RuntimeError(f"{path.name}: required dset1/sol1 unavailable")
        entity_sets = {}
        for _, tag in REGIONS:
            entities = sorted(int(x) for x in component.selection(tag).entities())
            entity_sets[tag] = set(entities)
            selection_rows.append({
                "module_id": module, "role": role, "model_file": path.name,
                "region": next(name for name, source in REGIONS if source == tag),
                "selection_tag": tag, "entity_dimension": 3,
                "entity_count": len(entities), "entities": ";".join(map(str, entities)),
                "available": bool(entities), "dataset": "dset1", "solution": "sol1",
            })
        mic = sorted(int(x) for x in component.selection("sel_mic_nominal").entities())
        selection_rows.append({
            "module_id": module, "role": role, "model_file": path.name,
            "region": "nominal_microphone", "selection_tag": "sel_mic_nominal",
            "entity_dimension": 2, "entity_count": len(mic), "entities": ";".join(map(str, mic)),
            "available": bool(mic), "dataset": "dset1", "solution": "sol1",
        })
        selection_rows.append({
            "module_id": module, "role": role, "model_file": path.name,
            "region": "microphone_volume_neighborhood", "selection_tag": "",
            "entity_dimension": 3, "entity_count": 0, "entities": "",
            "available": False, "dataset": "dset1", "solution": "sol1",
        })
        if not all(entity_sets[tag] for _, tag in REGIONS) or not mic:
            raise RuntimeError(f"{path.name}: empty required existing selection")

        frequency = as_series(model.evaluate("freq"), 256).real
        labels = []
        requests = []
        for region, _ in REGIONS:
            labels += [f"{region}:pressure", f"{region}:kinetic"]
            tag = next(tag for name, tag in REGIONS if name == region)
            requests += [("IntVolume", tag, EP), ("IntVolume", tag, EK)]
        labels += ["hr_cavity:complex", "shared_chamber:complex", "nominal_microphone:complex"]
        requests += [
            ("AvVolume", "sel_hr_cavity", "acpr.p_t/p_inc"),
            ("AvVolume", "sel_chamber", "acpr.p_t/p_inc"),
            ("AvSurface", "sel_mic_nominal", "acpr.p_t/p_inc"),
        ]
        evaluated = []
        numerical = java.result().numerical()
        for index, ((feature_type, selection_tag, expression), label) in enumerate(zip(requests, labels)):
            print(f"  EVAL {index + 1}/{len(requests)} {label}", flush=True)
            node_tag = "p04cnum"
            try:
                numerical.remove(node_tag)
            except Exception:
                pass
            numerical.create(node_tag, feature_type)
            node = java.result().numerical(node_tag)
            node.selection().named(selection_tag)
            node.set("data", "dset1")
            node.set("expr", expression)
            result = np.asarray(node.computeResult())
            if result.shape != (2, 256, 1):
                raise RuntimeError(f"Unexpected {feature_type} result shape {result.shape}")
            evaluated.append(result[0, :, 0] + 1j * result[1, :, 0])
            numerical.remove(node_tag)
        if not (np.all(np.diff(frequency) > 0) and np.all(np.isfinite(frequency))):
            raise RuntimeError("Invalid existing frequency axis")
        values = {label: as_series(evaluated[i], 256) for i, label in enumerate(labels)}

        energy_rows = []
        for i, f in enumerate(frequency):
            for region, _ in REGIONS:
                ep = float(values[f"{region}:pressure"][i].real)
                ek = float(values[f"{region}:kinetic"][i].real)
                total = ep + ek
                energy_rows.append({
                    "module_id": module, "role": role, "grid_index": i,
                    "frequency_hz": f"{f:.15g}", "region": region,
                    "pressure_energy_J": f"{ep:.17g}", "kinetic_energy_J": f"{ek:.17g}",
                    "total_energy_J": f"{total:.17g}", "kinetic_fraction": f"{ek/total:.17g}",
                })
        participation_rows = []
        complex_rows = []
        for i, f in enumerate(frequency):
            totals = {region: float(values[f"{region}:pressure"][i].real + values[f"{region}:kinetic"][i].real) for region, _ in REGIONS}
            raw = np.array([totals[name] / totals["whole_fluid"] for name in LEAF], dtype=float)
            norm = float(np.linalg.norm(raw))
            vector = raw / norm if norm > 0 else raw
            prow = {"module_id": module, "role": role, "grid_index": i, "frequency_hz": f"{f:.15g}"}
            for name, value in zip(LEAF, vector):
                prow[f"p_{name}"] = f"{value:.17g}"
            for name in LEAF:
                prow[f"whole_fraction_{name}"] = f"{totals[name]/totals['whole_fluid']:.17g}"
                prow[f"module_fraction_{name}"] = f"{totals[name]/totals['whole_hr_module']:.17g}"
            participation_rows.append(prow)
            cav = complex(values["hr_cavity:complex"][i])
            chamber = complex(values["shared_chamber:complex"][i])
            mic_value = complex(values["nominal_microphone:complex"][i])
            def phase(z): return float(np.degrees(np.angle(z)))
            def phase_ratio(a, b): return phase(a / b) if abs(b) else float("nan")
            complex_rows.append({
                "module_id": module, "role": role, "grid_index": i, "frequency_hz": f"{f:.15g}",
                "cavity_real": f"{cav.real:.17g}", "cavity_imag": f"{cav.imag:.17g}", "cavity_magnitude": f"{abs(cav):.17g}", "cavity_phase_deg": f"{phase(cav):.17g}",
                "chamber_real": f"{chamber.real:.17g}", "chamber_imag": f"{chamber.imag:.17g}", "chamber_magnitude": f"{abs(chamber):.17g}", "chamber_phase_deg": f"{phase(chamber):.17g}",
                "mic_real": f"{mic_value.real:.17g}", "mic_imag": f"{mic_value.imag:.17g}", "mic_magnitude": f"{abs(mic_value):.17g}", "mic_phase_deg": f"{phase(mic_value):.17g}",
                "phase_cavity_minus_chamber_deg": f"{phase_ratio(cav,chamber):.17g}",
                "phase_cavity_minus_mic_deg": f"{phase_ratio(cav,mic_value):.17g}",
                "phase_chamber_minus_mic_deg": f"{phase_ratio(chamber,mic_value):.17g}",
            })
        return selection_rows, energy_rows, participation_rows, complex_rows
    finally:
        client.remove(model)


def worker(index: int) -> None:
    manifest = manifest_inputs()
    item = manifest["p04b_models"][index]
    mph.option("session", "stand-alone")
    client = mph.start(cores=2)
    try:
        path = ROOT / item["path"]
        print(f"READ_ONLY_EXTRACT {item['module_id']} {item['role']} {path.name}", flush=True)
        selections, energies, participation, complex_values = extract_one(client, path, item["module_id"], item["role"])
    finally:
        client.clear()
    prefix = OUT / f"_part_{index:02d}"
    write_csv(Path(str(prefix) + "_selection.csv"), selections, list(selections[0]))
    write_csv(Path(str(prefix) + "_energy.csv"), energies, list(energies[0]))
    write_csv(Path(str(prefix) + "_participation.csv"), participation, list(participation[0]))
    write_csv(Path(str(prefix) + "_complex.csv"), complex_values, list(complex_values[0]))


def merge_parts(count: int, suffix: str, output: str) -> int:
    rows = []
    for index in range(count):
        path = OUT / f"_part_{index:02d}_{suffix}.csv"
        with path.open(newline="", encoding="utf-8") as stream:
            rows.extend(csv.DictReader(stream))
    write_csv(OUT / output, rows, list(rows[0]))
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-index", type=int)
    args = parser.parse_args()
    if args.worker_index is not None:
        worker(args.worker_index)
        return
    manifest = manifest_inputs()
    write_json(OUT / "authority_manifest.json", manifest)
    for index in range(len(manifest["p04b_models"])):
        subprocess.run([sys.executable, str(Path(__file__)), "--worker-index", str(index)], check=True)
    counts = {
        "models": len(manifest["p04b_models"]),
        "selection_rows": merge_parts(len(manifest["p04b_models"]), "selection", "selection_audit.csv"),
        "energy_rows": merge_parts(len(manifest["p04b_models"]), "energy", "energy_long.csv"),
        "participation_rows": merge_parts(len(manifest["p04b_models"]), "participation", "participation_vectors.csv"),
        "complex_rows": merge_parts(len(manifest["p04b_models"]), "complex", "complex_averages.csv"),
    }
    for path in OUT.glob("_part_*.csv"):
        path.unlink()
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
