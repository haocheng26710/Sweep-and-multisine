"""One-shot bounded fine-result extraction diagnostic for TRANS-1 RETRY_04."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import mph
import numpy as np

from fine_field_diagnostics import summarize_array


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_04"
RETRY02 = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_02"
RETRY03 = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_03"
RUNNER02 = RETRY02 / "run_trans1_retry02.py"
MPH_PATH = OUT / "DIAGNOSTIC_ISO_CODED_N_FINE_4PT.mph"
EXPECTED = np.asarray([1000.0, 1850.0, 3800.0, 5000.0])


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    spec.loader.exec_module(module)
    return module


R2 = load_module("trans1_retry02_authority_retry04", RUNNER02)
resolver_module = load_module(
    "trans1_retry03_dataset_resolver",
    RETRY03 / "dataset_node_resolution.py",
)
dataset_node_by_java_tag = resolver_module.dataset_node_by_java_tag
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
        expected_hash, relative = line.split("  ", 1)
        target = ROOT / Path(relative)
        actual = sha256(target) if target.exists() else None
        rows.append({
            "path": relative,
            "expected": expected_hash,
            "actual": actual,
            "match": actual == expected_hash,
        })
    result = {
        "manifest": path.relative_to(ROOT).as_posix(),
        "entries": len(rows),
        "all_match": all(row["match"] for row in rows),
        "rows": rows,
    }
    if not result["all_match"]:
        raise RuntimeError("RETRY_03 provenance hash verification failed")
    return result


def result_probe(model, dataset_node, expressions: dict[str, str]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    summaries: dict[str, Any] = {}
    arrays: dict[str, np.ndarray] = {}
    for key, expression in expressions.items():
        try:
            raw = np.asarray(model.evaluate(expression, dataset=dataset_node))
            arrays[key] = raw
            summaries[key] = {
                "expression": expression,
                "status": "returned",
                **summarize_array(raw, expected_size=4),
            }
        except Exception as exc:
            summaries[key] = {
                "expression": expression,
                "status": "exception",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
    return summaries, arrays


def direct_java_global_probe(model, dataset_tag: str, expressions: dict[str, str]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    result: dict[str, Any] = {}
    arrays: dict[str, np.ndarray] = {}
    numerical = model.java.result().numerical()
    for key, expression in expressions.items():
        tag = f"gev_r4_{key}"
        try:
            if tag in [str(value) for value in numerical.tags()]:
                numerical.remove(tag)
            evaluation = numerical.create(tag, "EvalGlobal")
            evaluation.set("expr", expression)
            evaluation.set("data", dataset_tag)
            raw = np.asarray(evaluation.computeResult())
            arrays[key] = raw
            result[key] = {
                "expression": expression,
                "status": "returned",
                "java_is_complex": bool(evaluation.isComplex()),
                **summarize_array(raw),
            }
        except Exception as exc:
            result[key] = {
                "expression": expression,
                "status": "exception",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        finally:
            try:
                if tag in [str(value) for value in numerical.tags()]:
                    numerical.remove(tag)
            except Exception:
                pass
    return result, arrays


def dataset_solution_axes(model, dataset_node) -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        indices, values = model.inner(dataset_node)
        result["inner"] = {
            "indices": np.asarray(indices).astype(int).reshape(-1).tolist(),
            "values": np.asarray(values).reshape(-1).tolist(),
            "indices_summary": summarize_array(indices),
            "values_summary": summarize_array(values),
        }
    except Exception as exc:
        result["inner"] = {"error_type": type(exc).__name__, "error": str(exc)}
    try:
        indices, values = model.outer(dataset_node)
        result["outer"] = {
            "indices": np.asarray(indices).astype(int).reshape(-1).tolist(),
            "values": np.asarray(values).reshape(-1).tolist(),
            "indices_summary": summarize_array(indices),
            "values_summary": summarize_array(values),
        }
    except Exception as exc:
        result["outer"] = {"error_type": type(exc).__name__, "error": str(exc)}
    return result


def selection_and_operator_audit(model) -> dict[str, Any]:
    comp = model.java.component("comp1")
    result: dict[str, Any] = {}
    for tag in ("aveop_mic", "intop_all", "intop_hr03", "intop_south", "intop_plenum"):
        try:
            operator = comp.cpl(tag)
            entities = [int(value) for value in operator.selection().entities()]
            result[tag] = {"entities": entities, "entity_count": len(entities)}
        except Exception as exc:
            result[tag] = {"error_type": type(exc).__name__, "error": str(exc)}
    return result


def save_arrays(path: Path, arrays: dict[str, np.ndarray]) -> None:
    np.savez_compressed(path, **arrays)


def run(client) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    provenance = verify_manifest(RETRY03 / "SHA256SUMS.txt")
    atomic_json(OUT / "retry03_provenance_verification.json", provenance)
    if client.models():
        raise RuntimeError(f"Fresh-session gate failed: {client.models()}")

    model = None
    loaded = None
    started = time.time()
    try:
        model, audit = R2.build_case(client, "ISO_CODED", "N", EXPECTED, "fine", "RETRY04_FINE_DIAGNOSTIC")
        study_audit = R2.validate_study(model)
        mesh = audit["mesh"]
        mesh_record = {
            **mesh,
            "persisted_before_study_run": True,
            "solver_warnings_before_run": [],
            "low_mesh_quality_warning": bool(mesh["minimum_quality"] <= 1e-5),
        }
        atomic_json(OUT / "fine_mesh_statistics_before_extraction.json", mesh_record)
        atomic_json(OUT / "geometry_selection_audit.json", R2.compact_audit(audit))

        solve_started = time.time()
        model.java.study("std_freq").run()
        solve_elapsed = time.time() - solve_started
        solution_audit = R2.solution_dataset_audit(model)
        solution_audit["study"] = study_audit
        solution_audit["solve_elapsed_s"] = solve_elapsed
        atomic_json(OUT / "study_solution_dataset_audit.json", solution_audit)
        if not solution_audit["solution_has_valid_result"] or not solution_audit["dataset_bound_to_valid_solution"]:
            raise RuntimeError("Fine solve did not produce a non-empty solution and bound dataset")

        # Freeze the only newly solved model before any field extraction.
        model.save(MPH_PATH)
        atomic_json(OUT / "mph_pre_extraction_persistence.json", {
            "mph": MPH_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256(MPH_PATH),
            "saved_before_field_extraction": True,
            "solve_count": 1,
        })

        dataset_tags = solution_audit["solution_dataset_tags"]
        if len(dataset_tags) != 1:
            raise RuntimeError(f"Expected one bound dataset, found {dataset_tags}")
        dataset_tag = dataset_tags[0]
        dataset_node = dataset_node_by_java_tag(model, dataset_tag)

        energy = R2.R0.ENERGY_DENSITY
        expressions = {
            "frequency": "freq",
            "mic": "aveop_mic(acpr.p_t)/p_inc",
            "mic_numerator": "aveop_mic(acpr.p_t)",
            "incident_pressure": "p_inc",
            "mic_operator_unity": "aveop_mic(1)",
            "e_all": f"intop_all({energy})",
            "e_hr03": f"intop_hr03({energy})",
            "e_south": f"intop_south({energy})",
            "e_plenum": f"intop_plenum({energy})",
        }
        summaries, arrays = result_probe(model, dataset_node, expressions)
        java_summaries, java_arrays = direct_java_global_probe(model, dataset_tag, expressions)
        live_probe = {
            "dataset_java_tag": dataset_tag,
            "dataset_node_name": dataset_node.name(),
            "dataset_node_tag": dataset_node.tag(),
            "solution_axes": dataset_solution_axes(model, dataset_node),
            "operators": selection_and_operator_audit(model),
            "mph_evaluate": summaries,
            "java_eval_global": java_summaries,
        }
        atomic_json(OUT / "fine_live_raw_extraction_diagnostic.json", live_probe)
        save_arrays(OUT / "fine_live_raw_arrays.npz", {**arrays, **{f"java_{k}": v for k, v in java_arrays.items()}})

        client.remove(model)
        model = None
        loaded = client.load(MPH_PATH)
        reload_audit = R2.solution_dataset_audit(loaded)
        reload_node = dataset_node_by_java_tag(loaded, dataset_tag)
        reload_summaries, reload_arrays = result_probe(loaded, reload_node, expressions)
        reload_probe = {
            "solution_dataset_audit": reload_audit,
            "dataset_java_tag": dataset_tag,
            "dataset_node_name": reload_node.name(),
            "dataset_node_tag": reload_node.tag(),
            "solution_axes": dataset_solution_axes(loaded, reload_node),
            "operators": selection_and_operator_audit(loaded),
            "mph_evaluate": reload_summaries,
        }
        atomic_json(OUT / "fine_reload_raw_extraction_diagnostic.json", reload_probe)
        save_arrays(OUT / "fine_reload_raw_arrays.npz", reload_arrays)

        mic = reload_summaries.get("mic", {})
        all_core_valid = all(
            reload_summaries.get(key, {}).get("size_matches_expected") is True
            and reload_summaries.get(key, {}).get("all_finite") is True
            for key in ("frequency", "mic", "e_all", "e_hr03", "e_south", "e_plenum")
        )
        mic_nonzero = mic.get("all_zero") is False
        extraction_pass = bool(all_core_valid and mic_nonzero)
        status = (
            "TRANS1_RETRY_04_FINE_EXTRACTION_PASS"
            if extraction_pass
            else "TRANS1_RETRY_04_DIAGNOSTIC_COMPLETE_FIELD_INVALID"
        )
        result = {
            "technical_status": status,
            "fine_solution_generation_pass": True,
            "dataset_node_resolution_pass": True,
            "field_extraction_pass": extraction_pass,
            "mic_summary": mic,
            "fresh_comsol_solve_count": 1,
            "formal_256_gate_started": False,
            "six_combinations_completed": 0,
            "trans2_started": False,
            "print_authorized": False,
            "final_test_read": False,
            "elapsed_s": time.time() - started,
            "completed_at": datetime.now().astimezone().isoformat(),
        }
        atomic_json(OUT / "retry04_execution_result.json", result)
        return result
    except Exception as exc:
        failure = {
            "technical_status": "TRANS1_RETRY_04_DIAGNOSTIC_EXECUTION_FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "fresh_comsol_solve_count_maximum": 1,
            "formal_256_gate_started": False,
            "six_combinations_completed": 0,
            "trans2_started": False,
            "print_authorized": False,
            "final_test_read": False,
        }
        atomic_json(OUT / "retry04_failure.json", failure)
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
