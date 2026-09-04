from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_02"
CONTROL = OUT / "run_SESSION_CONTROL_ISO_CODED_N_COARSE_SMOKE.json"
RAW = OUT / "raw_SESSION_CONTROL_ISO_CODED_N_COARSE_SMOKE.npz"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows, fields) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(path: Path) -> dict:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, rel = line.split(maxsplit=1)
        target = ROOT / rel.strip()
        actual = sha256(target) if target.is_file() else None
        rows.append({"path": rel.strip(), "expected": expected, "actual": actual,
                     "match": actual == expected})
    return {"manifest": path.relative_to(ROOT).as_posix(), "entries": len(rows),
            "all_match": all(row["match"] for row in rows), "rows": rows}


def main() -> None:
    control = read_json(CONTROL)
    failure = read_json(OUT / "solver_failure.json")
    with np.load(RAW) as data:
        values = {key: np.asarray(data[key]) for key in data.files}

    smoke_rows = []
    energy_rows = []
    for index, frequency in enumerate(values["frequency"]):
        pressure = values["mic"][index]
        smoke_rows.append({"grid_index": index, "frequency_hz": f"{frequency:.15g}",
                           "mic_real_pa": f"{pressure.real:.17g}",
                           "mic_imag_pa": f"{pressure.imag:.17g}",
                           "mic_magnitude_pa": f"{abs(pressure):.17g}"})
        energy_rows.append({"grid_index": index, "frequency_hz": f"{frequency:.15g}",
                            "e_all_j": f"{values['e_all'][index]:.17g}",
                            "e_hr03_j": f"{values['e_hr03'][index]:.17g}",
                            "e_south_j": f"{values['e_south'][index]:.17g}",
                            "e_plenum_j": f"{values['e_plenum'][index]:.17g}"})
    write_csv(OUT / "sparse_smoke_results.csv", smoke_rows,
              ["grid_index", "frequency_hz", "mic_real_pa", "mic_imag_pa", "mic_magnitude_pa"])
    write_csv(OUT / "cavity_energy_smoke.csv", energy_rows,
              ["grid_index", "frequency_hz", "e_all_j", "e_hr03_j", "e_south_j", "e_plenum_j"])

    write_json(OUT / "study_solution_dataset_audit.json", {
        "coarse_control": control["solution_dataset"],
        "fine_smoke": {
            "study_created_after_complete_fine_mesh": True,
            "study_tag": "std_freq", "feature_tag": "freq",
            "study_run_returned": True,
            "valid_solution_gate_passed_before_dataset_retry": True,
            "solution_dataset_tag_selected_by_java_audit": "dset1",
            "default_extraction_complete": False,
            "default_field_lengths": "not persisted before the bounded exception",
            "explicit_dataset_retry_used": True,
            "explicit_dataset_retry_error": failure["error"],
            "interpretation": "MPh string lookup treated Java dataset tag dset1 as a display name; the one authorized explicit extraction retry failed.",
        },
        "terminal_status": "TRANS1_RETRY_02_BLOCKED_BY_SOLVER_DATASET",
        "no_further_compatibility_retry": True,
        "final_test_read": False,
    })
    write_json(OUT / "geometry_and_selection_audit.json", {
        "coarse_control": control["geometry_and_selection"],
        "fine_geometry_changed": False,
        "fine_model_reused_frozen_authority": "outputs/simulation/COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_02/run_trans0_retry02.py",
        "fine_result_not_scientifically_usable": True,
    })
    write_json(OUT / "mesh_statistics.json", {
        "warning": "LOW_MESH_QUALITY_WARNING",
        "coarse_control": control["mesh"],
        "fine_configuration": {"control_frequency_hz": 12000.0,
                               "critical_hmax_m": 0.0028 / 6.0,
                               "study_created_after_mesh": True},
        "fine_actual_statistics": "not persisted before dataset extraction failure",
        "formal_256_mesh_gate": "not_started",
    })
    write_json(OUT / "reload_validation.json", control["reload"])
    write_json(OUT / "numerical_convergence.json", {
        "status": "not_started", "reason": "fine four-point field extraction failed",
        "peak_center_change_lt_1pct": "not_evaluated",
        "fixed_window_change_lt_0p5_db": "not_evaluated",
    })
    write_json(OUT / "simulation_contract.json", {
        "phase": "TRANS-1 RETRY_02", "repair_scope": "study_solution_dataset_only",
        "frequency_grid": "200*2^(n/48), n=0..255", "formal_frequency_count": 256,
        "smoke_frequency_hz": [1000, 1850, 3800, 5000],
        "fixed_windows": "HR03/HR07 frozen target +/-1/6 octave",
        "geometry_modified": False, "thresholds_modified": False,
        "external_field_run": False, "classifier_run": False,
        "final_test_read": False,
    })
    write_json(OUT / "scientific_classification.json", {
        "terminal_classification": "TRANS1_RETRY_02_BLOCKED_BY_SOLVER_DATASET",
        "solver_dataset_technical_status": "blocked_after_one_authorized_explicit_dataset_retry",
        "mesh_numerical_status": "formal coarse/fine 256-point gate not started",
        "acoustic_scientific_status": "no new selectivity conclusion",
        "six_combinations_completed": 0,
        "print_recommendation": "DO_NOT_AUTHORIZE_PRINT_FROM_THIS_STAGE",
        "future_mechanical_option_only": "可在 TRANS-2 将完整八边形底盘/盖板缩减为南北两个通道承载臂加中央麦克风固定区；前提是内部空气域、入口端面位置、局部入口边缘、通道高度和密封边界保持不变。",
        "final_test_read": False,
    })

    provenance = {
        "retry02_preflight": verify_manifest(ROOT / "outputs/simulation/COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_02/SHA256SUMS.txt"),
        "retry01": verify_manifest(ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_01/SHA256SUMS.txt"),
    }
    write_json(OUT / "provenance_hash_verification.json", provenance)

    session = read_json(OUT / "solver_session_license_log.json")
    session["runs"] = [{"stage": "coarse_session_control", "success": True,
                        "study": control["study"], "solution_dataset": control["solution_dataset"],
                        "solve_elapsed_s": control["solve_elapsed_s"], "reload": control["reload"]}]
    session["fine_smoke"] = {"study_run_returned": True, "valid_solution_observed": True,
                             "default_fields_complete": False,
                             "explicit_dataset_retry_error": failure["error"]}
    session["terminal_classification"] = "TRANS1_RETRY_02_BLOCKED_BY_SOLVER_DATASET"
    session["completed_at"] = datetime.now().astimezone().isoformat()
    write_json(OUT / "solver_session_license_log.json", session)

    state = read_json(OUT / "execution_state.json")
    state.update({"coarse_control_pass": True, "fine_smoke_pass": False,
                  "fine_valid_solution_observed": True,
                  "formal_256_gate_started": False, "six_combinations_completed": 0,
                  "completed_runs": [control["mph"]],
                  "final_test_read": False})
    write_json(OUT / "execution_state.json", state)

    files = sorted(path for path in OUT.iterdir() if path.is_file() and path.name not in {"artifact_inventory.json", "SHA256SUMS.txt"})
    inventory = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                  "sha256": sha256(path)} for path in files]
    write_json(OUT / "artifact_inventory.json", {
        "terminal_classification": "TRANS1_RETRY_02_BLOCKED_BY_SOLVER_DATASET",
        "artifact_count_excluding_manifest": len(inventory), "artifacts": inventory,
        "final_test_read": False,
    })
    manifest_files = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt")
    lines = [f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}" for path in manifest_files]
    (OUT / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
