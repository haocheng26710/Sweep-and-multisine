"""Bounded explicit-volume-mesh repair and one fine four-point smoke test."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import mph
import numpy as np

from fine_mesh_repair import require_positive_volume_mesh


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_05"
R2_DIR = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_02"
R3_DIR = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_03"
R4_DIR = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_04"
EXPECTED = np.asarray([1000.0, 1850.0, 3800.0, 5000.0])
MPH_PATH = OUT / "REPAIRED_ISO_CODED_N_FINE_4PT.mph"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    spec.loader.exec_module(module)
    return module


R2 = load_module("trans1_retry02_authority_retry05", R2_DIR / "run_trans1_retry02.py")
resolver = load_module("trans1_retry03_dataset_resolver_retry05", R3_DIR / "dataset_node_resolution.py")
dataset_node_by_java_tag = resolver.dataset_node_by_java_tag
R2.OUT = OUT


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(path: Path) -> dict[str, Any]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        target = ROOT / Path(relative)
        actual = sha256(target) if target.exists() else None
        rows.append({"path": relative, "expected": expected, "actual": actual, "match": actual == expected})
    result = {
        "manifest": path.relative_to(ROOT).as_posix(),
        "entries": len(rows),
        "all_match": all(row["match"] for row in rows),
        "rows": rows,
    }
    if not result["all_match"]:
        raise RuntimeError("RETRY_04 provenance verification failed")
    return result


def feature_record(mesh, tag: str) -> dict[str, Any]:
    feature = mesh.feature(tag)
    try:
        feature_type = str(feature.getType())
    except Exception:
        feature_type = None
    return {"tag": tag, "type": feature_type, "label": str(feature.label())}


def configure_explicit_fine_volume_mesh(model, audit: dict[str, Any], kind: str) -> dict[str, Any]:
    comp = model.java.component("comp1")
    actual, outputs = R2.R0.resolve_feature_domain_selections(comp, R2.critical_feature_tags(kind))
    R2.R0.add_union_selection(comp, "dom_critical_mesh", outputs)
    critical_domains = R2.R0.selection_entities(comp, "dom_critical_mesh")
    if not critical_domains:
        raise RuntimeError("Fine critical-domain selection is empty")

    physics = comp.physics("acpr")
    physics.prop("MeshControl").set(
        "PhysicsControlledMeshMaximumFrequency",
        f"{R2.FINE_CONTROL_FREQUENCY_HZ:.15g}[Hz]",
    )
    mesh = comp.mesh("mesh1")
    mesh.clearMesh()
    mesh.automatic(False)
    before_tags = [str(tag) for tag in mesh.feature().tags()]

    removed = []
    retained = []
    for tag in before_tags:
        if tag == "size":
            retained.append(tag)
            continue
        try:
            mesh.feature().remove(tag)
            removed.append(tag)
        except Exception:
            retained.append(tag)

    existing = [str(tag) for tag in mesh.feature().tags()]
    for tag in ("size_global_r5", "ftet_full_r5"):
        if tag in existing:
            mesh.feature().remove(tag)

    global_size = mesh.feature().create("size_global_r5", "Size")
    global_size.set("custom", "on")
    global_size.set("hmaxactive", True)
    global_size.set("hmax", f"{R2.FINE_GLOBAL_HMAX_M:.15g}[m]")

    free_tet = mesh.feature().create("ftet_full_r5", "FreeTet")
    free_tet.selection().geom("geom1", 3)
    free_tet.selection().all()
    local_size = free_tet.feature().create("size_critical_r5", "Size")
    local_size.selection().geom("geom1", 3)
    local_size.selection().named("dom_critical_mesh")
    local_size.set("custom", "on")
    local_size.set("hmaxactive", True)
    local_size.set("hmax", f"{R2.FINE_CRITICAL_HMAX_M:.15g}[m]")

    mesh.run()
    after_tags = [str(tag) for tag in mesh.feature().tags()]
    stats = require_positive_volume_mesh({
        "variant": "fine_explicit_free_tet",
        "automatic": bool(mesh.isAutomatic()),
        "control_frequency_hz": R2.FINE_CONTROL_FREQUENCY_HZ,
        "global_hmax_m": R2.FINE_GLOBAL_HMAX_M,
        "critical_hmax_m": R2.FINE_CRITICAL_HMAX_M,
        "fine_to_coarse_global_hmax_ratio": R2.FINE_TO_COARSE_HMAX_RATIO,
        "fine_to_coarse_ratio_gate": bool(R2.FINE_TO_COARSE_HMAX_RATIO <= 0.75),
        "critical_neck_elements_across_minimum_by_hmax": 0.0028 / R2.FINE_CRITICAL_HMAX_M,
        "critical_domains": critical_domains,
        "critical_domain_count": len(critical_domains),
        "actual_component_selection_tags": actual,
        "critical_feature_output_tags": outputs,
        "features_before_reset": before_tags,
        "features_removed": removed,
        "features_retained": retained,
        "features_after_repair": [feature_record(mesh, tag) for tag in after_tags],
        "local_size_parent": "ftet_full_r5",
        "volume_operation": "FreeTet",
        "elements": int(mesh.getNumElem()),
        "vertices": int(mesh.getNumVertex()),
        "minimum_quality": float(mesh.getMinQuality()),
        "mean_quality": float(mesh.getMeanQuality()),
    })
    stats["low_mesh_quality_warning"] = bool(stats["minimum_quality"] <= 1e-5)
    audit["mesh"] = stats
    return stats


def evaluate_fields(model, dataset_node) -> dict[str, np.ndarray]:
    energy = R2.R0.ENERGY_DENSITY
    expressions = {
        "frequency": "freq",
        "mic": "aveop_mic(acpr.p_t)/p_inc",
        "e_all": f"intop_all({energy})",
        "e_hr03": f"intop_hr03({energy})",
        "e_south": f"intop_south({energy})",
        "e_plenum": f"intop_plenum({energy})",
    }
    values = {
        key: np.asarray(model.evaluate(expression, dataset=dataset_node))
        for key, expression in expressions.items()
    }
    normalized = {
        "frequency": values["frequency"].real.reshape(-1),
        "mic": values["mic"].reshape(-1),
        "e_all": values["e_all"].real.reshape(-1),
        "e_hr03": values["e_hr03"].real.reshape(-1),
        "e_south": values["e_south"].real.reshape(-1),
        "e_plenum": values["e_plenum"].real.reshape(-1),
    }
    if not np.array_equal(normalized["frequency"], EXPECTED):
        raise RuntimeError(f"Frequency axis mismatch: {normalized['frequency']}")
    for key, value in normalized.items():
        if value.size != 4 or not np.all(np.isfinite(value)):
            raise RuntimeError(f"Invalid repaired fine field {key}: shape={values[key].shape}, size={value.size}")
    if np.allclose(normalized["mic"], 0.0):
        raise RuntimeError("Repaired fine microphone field is all zero")
    return normalized


def save_npz(path: Path, values: dict[str, np.ndarray]) -> None:
    np.savez_compressed(path, **values)


def run(client) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    provenance = verify_manifest(R4_DIR / "SHA256SUMS.txt")
    atomic_json(OUT / "retry04_provenance_verification.json", provenance)
    if client.models():
        raise RuntimeError(f"Fresh-session gate failed: {client.models()}")

    model = None
    loaded = None
    solve_count = 0
    started = time.time()
    try:
        model, audit = R2.R0.build_model(client, "ISO_CODED", "N", 7, EXPECTED, "RETRY05_FINE_MESH_REPAIR")
        java = model.java
        java.study().remove("std_freq")
        for tag in [str(value) for value in java.sol().tags()]:
            java.sol().remove(tag)

        mesh_stats = configure_explicit_fine_volume_mesh(model, audit, "ISO_CODED")
        atomic_json(OUT / "fine_mesh_repair_audit.json", mesh_stats)
        atomic_json(OUT / "geometry_selection_audit.json", R2.compact_audit(audit))

        # The positive-volume hard gate has passed before any acoustic solve.
        R2.create_frequency_study(model, EXPECTED)
        study_audit = R2.validate_study(model)
        solve_count += 1
        solve_started = time.time()
        model.java.study("std_freq").run()
        solve_elapsed = time.time() - solve_started
        solution_audit = R2.solution_dataset_audit(model)
        solution_audit.update({"study": study_audit, "solve_elapsed_s": solve_elapsed})
        atomic_json(OUT / "study_solution_dataset_audit.json", solution_audit)
        if not solution_audit["solution_has_valid_result"] or not solution_audit["dataset_bound_to_valid_solution"]:
            raise RuntimeError("Repaired fine solve lacks a non-empty solution and bound dataset")

        model.save(MPH_PATH)
        atomic_json(OUT / "mph_pre_extraction_persistence.json", {
            "path": MPH_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256(MPH_PATH),
            "saved_before_extraction": True,
            "solve_count": solve_count,
        })
        dataset_tags = solution_audit["solution_dataset_tags"]
        if len(dataset_tags) != 1:
            raise RuntimeError(f"Expected exactly one bound solution dataset, found {dataset_tags}")
        dataset_tag = dataset_tags[0]
        node = dataset_node_by_java_tag(model, dataset_tag)
        values = evaluate_fields(model, node)
        save_npz(OUT / "repaired_fine_fields_live.npz", values)

        client.remove(model)
        model = None
        loaded = client.load(MPH_PATH)
        reload_node = dataset_node_by_java_tag(loaded, dataset_tag)
        reloaded = evaluate_fields(loaded, reload_node)
        save_npz(OUT / "repaired_fine_fields_reload.npz", reloaded)
        differences = {
            key: float(np.max(np.abs(values[key] - reloaded[key])))
            for key in values if key != "frequency"
        }
        reload_record = {
            "frequency_axis_equal": bool(np.array_equal(values["frequency"], reloaded["frequency"])),
            "field_maximum_absolute_differences": differences,
            "maximum_complex_microphone_difference_pa": differences["mic"],
            "tolerance_pa": 1e-12,
            "pass": bool(differences["mic"] <= 1e-12),
        }
        atomic_json(OUT / "mph_reload_validation.json", reload_record)
        if not reload_record["pass"]:
            raise RuntimeError(f"Repaired fine MPH reload mismatch: {reload_record}")

        result = {
            "technical_status": "TRANS1_RETRY_05_FINE_SMOKE_PASS",
            "root_cause_repaired": True,
            "mesh_hard_gate_pass": True,
            "fine_solution_generation_pass": True,
            "dataset_node_resolution_pass": True,
            "all_six_fields_four_point_finite": True,
            "microphone_nonzero": True,
            "mph_reload_pass": True,
            "fresh_comsol_solve_count": solve_count,
            "formal_256_gate_started": False,
            "six_combinations_completed": 0,
            "trans2_started": False,
            "print_authorized": False,
            "scientific_conclusion": "none; technical fine-smoke repair only",
            "final_test_read": False,
            "elapsed_s": time.time() - started,
            "completed_at": datetime.now().astimezone().isoformat(),
        }
        atomic_json(OUT / "retry05_execution_result.json", result)
        return result
    except Exception as exc:
        failure = {
            "technical_status": "TRANS1_RETRY_05_MESH_REPAIR_BLOCKED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "fresh_comsol_solve_count": solve_count,
            "formal_256_gate_started": False,
            "six_combinations_completed": 0,
            "trans2_started": False,
            "print_authorized": False,
            "final_test_read": False,
        }
        atomic_json(OUT / "retry05_failure.json", failure)
        raise
    finally:
        for candidate in (model, loaded):
            if candidate is not None:
                try:
                    client.remove(candidate)
                except Exception:
                    pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    client = None
    try:
        client = mph.start(cores=args.cores, version="6.4") if args.port is None else mph.Client(version="6.4", port=args.port)
        print(json.dumps(run(client), ensure_ascii=False, indent=2))
    finally:
        if client is not None:
            for model in list(client.models()):
                try:
                    client.remove(model)
                except Exception:
                    pass
            client.disconnect()


if __name__ == "__main__":
    main()
