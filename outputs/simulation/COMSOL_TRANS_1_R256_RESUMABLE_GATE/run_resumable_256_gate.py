"""TRANS-1R256: resumable ISO-CODED/N coarse/fine 256-point gate."""

from __future__ import annotations

import argparse
import ast
import csv
import gc
import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_R256_RESUMABLE_GATE"
SCRIPT = OUT / "run_resumable_256_gate.py"
CONTRACT_PATH = OUT / "frozen_run_contract.json"
AMENDMENT_PATH = OUT / "frozen_run_contract_amendment_03.json"
STATE_PATH = OUT / "resume_state.json"
MANIFEST_PATH = OUT / "checkpoint_manifest.json"
REPORT_PATH = ROOT / "docs/progress/COMSOL_TRANS_1_R256_RESUMABLE_GATE.md"
COARSE_MPH = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_03/SESSION_CONTROL_ISO_CODED_N_COARSE_SMOKE.mph"
FINE_MPH = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_05/REPAIRED_ISO_CODED_N_FINE_4PT.mph"
RESOLVER_PATH = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_03/dataset_node_resolution.py"
AUTHORITY_CONTRACT = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F/simulation_contract.json"
AUTHORITY_EXPRESSION_SOURCE = ROOT / "outputs/simulation/COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_02/run_trans0_retry02.py"
FIELDS = ("frequency", "mic", "e_all", "e_hr03", "e_south", "e_plenum")
TERMINAL_STATES = {
    "TRANS1_R256_NUMERICAL_GATE_PASS", "TRANS1_R256_BLOCKED_DURING_COARSE",
    "TRANS1_R256_BLOCKED_DURING_FINE", "TRANS1_R256_BLOCKED_BY_CHECKPOINT_INTEGRITY",
    "TRANS1_R256_BLOCKED_BY_RESOURCE_STOP", "TRANS1_R256_NUMERICAL_GATE_FAIL",
}
MAX_ELAPSED_S = 18 * 3600
MAX_OUTPUT_BYTES = 25 * 1024**3
MIN_FREE_BYTES = 5 * 1024**3


class CheckpointIntegrityError(RuntimeError):
    pass


class ResourceStop(RuntimeError):
    pass


class ChunkWorkerFailed(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".tmp")
    partial.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(partial, path)


def frozen_frequencies() -> list[float]:
    return [200.0 * 2.0 ** (n / 48.0) for n in range(256)]


def _chunks(mesh: str, size: int) -> list[dict[str, Any]]:
    grid = frozen_frequencies()
    return [{"mesh": mesh, "chunk_index": i // size, "start_index": i,
             "end_index_inclusive": i + size - 1, "frequencies_hz": grid[i:i + size]}
            for i in range(0, 256, size)]


def build_contract_for_tests() -> dict[str, Any]:
    return {"schema": "TRANS-1R256-v1", "frequencies_hz": frozen_frequencies(),
            "chunks": {"coarse": _chunks("coarse", 64), "fine": _chunks("fine", 16)}}


def build_contract() -> dict[str, Any]:
    contract = build_contract_for_tests()
    contract.update({
        "created_utc": utc_now(), "case": "ISO-CODED/N", "frequency_formula": "200 * 2^(n/48), n=0..255",
        "frequency_serialization": "IEEE-754 binary64 JSON round-trip; COMSOL plist uses .17g",
        "base_mph": {"coarse": str(COARSE_MPH.relative_to(ROOT)).replace("\\", "/"),
                     "fine": str(FINE_MPH.relative_to(ROOT)).replace("\\", "/")},
        "base_mph_sha256": {"coarse": sha256(COARSE_MPH), "fine": sha256(FINE_MPH)},
        "script_sha256": sha256(SCRIPT), "authority_contract_sha256": sha256(AUTHORITY_CONTRACT),
        "fields": list(FIELDS), "reload_mic_tolerance_pa": 1e-12,
        "gates": {"resonance_center_relative_change_strict_less_than": 0.01,
                  "fixed_window_key_comparison_change_db_strict_less_than": 0.5},
        "limits": {"planned_study_run_maximum": 20, "elapsed_seconds": MAX_ELAPSED_S,
                   "new_output_bytes": MAX_OUTPUT_BYTES, "minimum_free_bytes_before_chunk": MIN_FREE_BYTES},
        "final_test_read": False,
    })
    return contract


def contract_digest(contract: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(contract, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def initialize_or_verify_contract() -> dict[str, Any]:
    expected = build_contract()
    if not CONTRACT_PATH.exists():
        atomic_json(CONTRACT_PATH, expected)
        return expected
    actual = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    immutable_keys = set(expected) - {"created_utc", "script_sha256"}
    for key in immutable_keys:
        if actual.get(key) != expected.get(key):
            raise CheckpointIntegrityError(f"Frozen contract changed at {key}")
    verify_active_script_authorization(actual)
    return actual


def verify_active_script_authorization(contract: dict[str, Any]) -> None:
    current = sha256(SCRIPT)
    if current == contract.get("script_sha256"):
        return
    if not AMENDMENT_PATH.exists():
        raise CheckpointIntegrityError("Controller changed without frozen extraction-wrapper amendment")
    amendment = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    checks = {
        "base_contract_sha256": amendment.get("base_contract_sha256") == sha256(CONTRACT_PATH),
        "previous_script_sha256": amendment.get("previous_script_sha256") == contract.get("script_sha256"),
        "active_script_sha256": amendment.get("active_script_sha256") == current,
        "authority_source_sha256": amendment.get("authority_source_sha256") == sha256(AUTHORITY_EXPRESSION_SOURCE),
        "scope": amendment.get("scope") == "chunk-lifecycle-and-checkpoint-recovery-wrapper-only",
        "frequency_grid_unchanged": amendment.get("frequency_grid_unchanged") is True,
    }
    if not all(checks.values()):
        raise CheckpointIntegrityError(f"Invalid extraction-wrapper amendment: {checks}")


def initial_state(contract: dict[str, Any]) -> dict[str, Any]:
    return {"schema": "TRANS-1R256-state-v1", "contract_sha256": sha256(CONTRACT_PATH),
            "status": "READY_TO_RUN", "completed": {"coarse": [], "fine": []},
            "study_run_count": 0, "actual_study_run_submissions": 0,
            "successfully_solved_study_runs": 0, "atomically_committed_chunks": 0,
            "accumulated_chunk_elapsed_s": 0.0,
            "next_chunk": {"mesh": "coarse", "chunk_index": 0}, "stop_reason": None,
            "updated_utc": utc_now(), "final_test_read": False}


def next_chunk(contract: dict[str, Any], state: dict[str, Any]) -> tuple[str, int] | None:
    coarse = set(state["completed"]["coarse"]); fine = set(state["completed"]["fine"])
    for item in contract["chunks"]["coarse"]:
        if item["chunk_index"] not in coarse:
            return "coarse", item["chunk_index"]
    for item in contract["chunks"]["fine"]:
        if item["chunk_index"] not in fine:
            return "fine", item["chunk_index"]
    return None


def chunk_dir(mesh: str, index: int) -> Path:
    return OUT / "chunks" / mesh / f"chunk_{index:03d}.completed"


def partial_dir(mesh: str, index: int) -> Path:
    return OUT / "chunks" / mesh / f".chunk_{index:03d}.partial"


def prepare_partial_for_rerun(partial: Path) -> Path | None:
    if not partial.exists():
        return None
    archived = partial.with_name(partial.name + ".abandoned_" + datetime.now().strftime("%Y%m%dT%H%M%S%f"))
    os.replace(partial, archived)
    return archived


def write_checksums(directory: Path) -> None:
    rows = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt"):
        rows.append(f"{sha256(path)}  {path.relative_to(directory).as_posix()}")
    (directory / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def verify_chunk_directory(directory: Path, expected_frequencies: list[float]) -> dict[str, Any]:
    required = {"fields.npz", "fields.csv", "chunk_record.json", "validation.json", "model.mph", "execution.log", "SHA256SUMS.txt"}
    missing = sorted(required - {p.name for p in directory.iterdir()}) if directory.exists() else sorted(required)
    if missing:
        raise CheckpointIntegrityError(f"Completed chunk missing files: {directory}: {missing}")
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1); target = directory / relative
        if not target.exists() or sha256(target) != expected:
            raise CheckpointIntegrityError(f"Completed chunk hash mismatch: {target}")
    with np.load(directory / "fields.npz") as source:
        values = {key: np.asarray(source[key]) for key in FIELDS}
    expected = np.asarray(expected_frequencies)
    if not np.array_equal(values["frequency"], expected):
        raise CheckpointIntegrityError(f"Completed chunk frequency mismatch: {directory}")
    for key in FIELDS:
        if values[key].size != expected.size or not np.all(np.isfinite(values[key])):
            raise CheckpointIntegrityError(f"Completed chunk invalid field {key}: {directory}")
    if np.allclose(values["mic"], 0.0):
        raise CheckpointIntegrityError(f"Completed chunk zero mic: {directory}")
    return {"directory": directory.relative_to(OUT).as_posix(), "sha256sums_sha256": sha256(directory / "SHA256SUMS.txt")}


def verify_checkpoints(contract: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    if state.get("contract_sha256") != sha256(CONTRACT_PATH):
        raise CheckpointIntegrityError("State contract hash mismatch")
    if state["completed"]["fine"] and len(state["completed"]["coarse"]) != 4:
        raise CheckpointIntegrityError("Fine checkpoint exists before all coarse checkpoints")
    records = []
    for mesh in ("coarse", "fine"):
        valid_indices = {c["chunk_index"] for c in contract["chunks"][mesh]}
        if len(state["completed"][mesh]) != len(set(state["completed"][mesh])) or not set(state["completed"][mesh]) <= valid_indices:
            raise CheckpointIntegrityError(f"Invalid completed index list for {mesh}")
        for index in state["completed"][mesh]:
            records.append({"mesh": mesh, "chunk_index": index, **verify_chunk_directory(
                chunk_dir(mesh, index), contract["chunks"][mesh][index]["frequencies_hz"])})
    return records


def commit_partial(partial: Path, completed: Path) -> None:
    if completed.exists():
        raise CheckpointIntegrityError(f"Completed target already exists: {completed}")
    os.replace(partial, completed)


def release_then_commit_validated_partial(partial: Path, completed: Path, release, maximum_rename_attempts: int = 3) -> dict[str, Any]:
    """Release all external resources before a bounded atomic directory rename."""
    release()
    gc.collect()
    errors = []
    for attempt in range(1, maximum_rename_attempts + 1):
        try:
            commit_partial(partial, completed)
            return {"released_before_rename": True, "rename_attempts": attempt, "permission_errors": errors,
                    "source": partial.as_posix(), "target": completed.as_posix(), "committed_utc": utc_now()}
        except PermissionError as exc:
            errors.append({"attempt": attempt, "error": str(exc), "utc": utc_now()})
            if attempt == maximum_rename_attempts:
                raise
            time.sleep(0.5 * attempt)
            gc.collect()
    raise AssertionError("unreachable")


def record_atomic_commit(audit: dict[str, Any]) -> None:
    path = OUT / "atomic_commit_audit.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"events": []}
    existing["events"].append(audit)
    existing["updated_utc"] = utc_now()
    atomic_json(path, existing)


def close_comsol_resources(client, model, loaded):
    """Normally close MPh/COMSOL objects and return cleared references."""
    if client is not None:
        for candidate in (model, loaded):
            if candidate is not None:
                try:
                    client.remove(candidate)
                except Exception:
                    pass
        model = None
        loaded = None
        gc.collect()
        try:
            client.disconnect()
        finally:
            client = None
    gc.collect()
    return client, model, loaded


def dispatch_chunk_worker(cores: int):
    """Run exactly one chunk in a fresh interpreter so MPh session globals cannot leak."""
    command = [sys.executable, str(SCRIPT), "--resume", "--cores", str(cores), "--single-chunk-worker"]
    return subprocess.run(command, check=False)


def persist_checkpoint_integrity_failure(state: dict[str, Any] | None, exc: Exception) -> bool:
    """Record an integrity failure only after state was loaded, or when no checkpoint exists."""
    if state is None and STATE_PATH.exists():
        return False
    if state is None:
        state = {"completed": {"coarse": [], "fine": []}, "study_run_count": 0,
                 "accumulated_chunk_elapsed_s": 0, "actual_study_run_submissions": 0,
                 "successfully_solved_study_runs": 0, "atomically_committed_chunks": 0}
    state.update({"status": "TRANS1_R256_BLOCKED_BY_CHECKPOINT_INTEGRITY", "stop_reason": str(exc),
                  "updated_utc": utc_now(), "final_test_read": False})
    atomic_json(STATE_PATH, state)
    return True


def load_state(contract: dict[str, Any]) -> dict[str, Any]:
    if not STATE_PATH.exists():
        state = initial_state(contract); atomic_json(STATE_PATH, state); return state
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def ensure_provenance_counters(state: dict[str, Any]) -> None:
    partial = partial_dir("coarse", 0)
    log_text = (partial / "execution.log").read_text(encoding="utf-8") if (partial / "execution.log").exists() else ""
    inferred_actual = 1 if "study.run start" in log_text else 0
    inferred_solved = 1 if "study.run complete" in log_text else 0
    state.setdefault("actual_study_run_submissions", inferred_actual)
    state.setdefault("successfully_solved_study_runs", inferred_solved)
    state.setdefault("atomically_committed_chunks", sum(len(state["completed"][m]) for m in ("coarse", "fine")))
    state["study_run_count"] = state["actual_study_run_submissions"]


def output_size() -> int:
    return sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())


def free_bytes() -> int:
    return shutil.disk_usage(OUT).free


def resource_gate(state: dict[str, Any]) -> None:
    if state.get("actual_study_run_submissions", state.get("study_run_count", 0)) >= 20:
        raise ResourceStop("Frozen maximum of 20 actual study.run submissions reached")
    if state["accumulated_chunk_elapsed_s"] >= MAX_ELAPSED_S:
        raise ResourceStop("18-hour accumulated chunk execution limit reached")
    if output_size() >= MAX_OUTPUT_BYTES:
        raise ResourceStop("25-GiB stage output limit reached")
    if free_bytes() < MIN_FREE_BYTES:
        raise ResourceStop("Free space below 5 GiB")


def _load_resolver():
    spec = importlib.util.spec_from_file_location("r256_dataset_resolver", RESOLVER_PATH)
    module = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module)
    return module.dataset_node_by_java_tag


def authoritative_energy_expression() -> str:
    """Parse the frozen authority constant without duplicating its formula."""
    source = AUTHORITY_EXPRESSION_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(AUTHORITY_EXPRESSION_SOURCE))
    matches = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "ENERGY_DENSITY" for target in node.targets):
            matches.append(ast.literal_eval(node.value))
    if len(matches) != 1 or not isinstance(matches[0], str):
        raise CheckpointIntegrityError(f"Expected exactly one literal ENERGY_DENSITY in {AUTHORITY_EXPRESSION_SOURCE}")
    expression = matches[0]
    if "rho0_nom" not in expression or "c0_nom" not in expression or "d(acpr.p_t" not in expression:
        raise CheckpointIntegrityError("Frozen authority energy expression lacks required nominal/gradient terms")
    if "rho0*" in expression or "c0^" in expression:
        raise CheckpointIntegrityError("Bare rho0/c0 leaked into authority energy expression")
    return expression


def evaluate(model, frequencies: list[float]) -> dict[str, np.ndarray]:
    node = _load_resolver()(model, "dset1")
    energy = authoritative_energy_expression()
    expressions = {"frequency": "freq", "mic": "aveop_mic(acpr.p_t)/p_inc", "e_all": f"intop_all({energy})",
                   "e_hr03": f"intop_hr03({energy})", "e_south": f"intop_south({energy})", "e_plenum": f"intop_plenum({energy})"}
    raw = {key: np.asarray(model.evaluate(expr, dataset=node)).reshape(-1) for key, expr in expressions.items()}
    values = {"frequency": raw["frequency"].real, "mic": raw["mic"],
              **{key: raw[key].real for key in ("e_all", "e_hr03", "e_south", "e_plenum")}}
    expected = np.asarray(frequencies)
    if not np.array_equal(values["frequency"], expected):
        raise RuntimeError(f"COMSOL frequency mismatch: {values['frequency']} != {expected}")
    for key in FIELDS:
        if values[key].size != expected.size or not np.all(np.isfinite(values[key])):
            raise RuntimeError(f"Invalid field {key}")
    if np.allclose(values["mic"], 0.0): raise RuntimeError("Microphone is all zero")
    return values


def save_csv(path: Path, values: dict[str, np.ndarray]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream); writer.writerow(["grid_index", "frequency_hz", "mic_real", "mic_imag", "e_all", "e_hr03", "e_south", "e_plenum"])
        for i, f in enumerate(values["frequency"]):
            m = values["mic"][i]; writer.writerow([i, format(float(f), ".17g"), format(float(m.real), ".17g"), format(float(m.imag), ".17g"),
                                                    *[format(float(values[k][i]), ".17g") for k in ("e_all", "e_hr03", "e_south", "e_plenum")]])


def run_chunk(mesh: str, index: int, contract: dict[str, Any], state: dict[str, Any], cores: int) -> dict[str, Any]:
    import mph
    item = contract["chunks"][mesh][index]; frequencies = item["frequencies_hz"]
    partial = partial_dir(mesh, index); completed = chunk_dir(mesh, index)
    if completed.exists(): raise CheckpointIntegrityError(f"Unmanifested completed directory exists: {completed}")
    prepare_partial_for_rerun(partial)
    partial.mkdir(parents=True)
    start_record = {"mesh": mesh, "chunk_index": index, "frequencies_hz": frequencies,
                    "input_mph": contract["base_mph"][mesh], "input_mph_sha256": contract["base_mph_sha256"][mesh],
                    "script_sha256": sha256(SCRIPT), "contract_sha256": sha256(CONTRACT_PATH),
                    "free_bytes_before": free_bytes(), "started_utc": utc_now()}
    atomic_json(partial / "start_record.json", start_record)
    log = partial / "execution.log"; client = model = loaded = None; started = time.time()
    try:
        with log.open("w", encoding="utf-8") as stream:
            stream.write(json.dumps(start_record, ensure_ascii=False, indent=2) + "\n")
            client = mph.start(cores=cores, version="6.4")
            model = client.load(ROOT / contract["base_mph"][mesh])
            model.java.study("std_freq").feature("freq").set("plist", " ".join(format(f, ".17g") for f in frequencies))
            state["actual_study_run_submissions"] += 1; state["study_run_count"] = state["actual_study_run_submissions"]
            state["updated_utc"] = utc_now(); atomic_json(STATE_PATH, state)
            stream.write(f"study.run start {utc_now()}\n"); stream.flush()
            model.java.study("std_freq").run()
            state["successfully_solved_study_runs"] += 1; state["updated_utc"] = utc_now(); atomic_json(STATE_PATH, state)
            stream.write(f"study.run complete {utc_now()}\n"); stream.flush()
            mph_path = partial / "model.mph"; model.save(mph_path)
            live = evaluate(model, frequencies); np.savez_compressed(partial / "fields.npz", **live); save_csv(partial / "fields.csv", live)
            client.remove(model); model = None
            loaded = client.load(mph_path); reloaded = evaluate(loaded, frequencies)
            mic_diff = float(np.max(np.abs(live["mic"] - reloaded["mic"])))
            validation = {"frequency_axis_equal": bool(np.array_equal(live["frequency"], reloaded["frequency"])),
                          "all_fields_finite": all(np.all(np.isfinite(reloaded[k])) for k in FIELDS),
                          "microphone_nonzero": not np.allclose(reloaded["mic"], 0.0),
                          "maximum_complex_microphone_reload_difference_pa": mic_diff, "tolerance_pa": 1e-12,
                          "pass": mic_diff <= 1e-12}
            if not validation["pass"]: raise RuntimeError(f"MPH reload validation failed: {validation}")
            atomic_json(partial / "validation.json", validation)
            record = {**start_record, "completed_utc": utc_now(), "elapsed_s": time.time() - started,
                      "point_count": len(frequencies), "study_run_count": 1, "validation": validation, "final_test_read": False}
            atomic_json(partial / "chunk_record.json", record); write_checksums(partial)
            verify_chunk_directory(partial, frequencies)
        def release_for_commit():
            nonlocal client, model, loaded
            client, model, loaded = close_comsol_resources(client, model, loaded)
        commit_audit = release_then_commit_validated_partial(partial, completed, release_for_commit)
        record_atomic_commit({"mesh": mesh, "chunk_index": index, **commit_audit})
        state["completed"][mesh].append(index); state["completed"][mesh].sort()
        state["atomically_committed_chunks"] += 1; state["accumulated_chunk_elapsed_s"] += record["elapsed_s"]
        nxt = next_chunk(contract, state); state["next_chunk"] = None if nxt is None else {"mesh": nxt[0], "chunk_index": nxt[1]}
        state["status"] = "RUNNING"; state["updated_utc"] = utc_now(); atomic_json(STATE_PATH, state)
        records = verify_checkpoints(contract, state)
        atomic_json(MANIFEST_PATH, {"contract_sha256": sha256(CONTRACT_PATH), "records": records,
                    "provenance_counters": {key: state[key] for key in ("actual_study_run_submissions", "successfully_solved_study_runs", "atomically_committed_chunks")},
                    "updated_utc": utc_now()})
        return record
    finally:
        if client is not None:
            for candidate in (model, loaded):
                if candidate is not None:
                    try: client.remove(candidate)
                    except Exception: pass
            try: client.disconnect()
            except Exception: pass


def recover_solved_partial_chunk_zero(contract: dict[str, Any], state: dict[str, Any], cores: int) -> dict[str, Any] | None:
    """Commit the already-solved chunk 0 without submitting another study."""
    partial = partial_dir("coarse", 0)
    completed = chunk_dir("coarse", 0)
    if 0 in state["completed"]["coarse"] or completed.exists():
        return None
    mph_path = partial / "model.mph"
    log_path = partial / "execution.log"
    if not mph_path.exists() or not log_path.exists() or "study.run complete" not in log_path.read_text(encoding="utf-8"):
        return None
    frequencies = contract["chunks"]["coarse"][0]["frequencies_hz"]
    try:
        verify_chunk_directory(partial, frequencies)
        already_validated = True
    except CheckpointIntegrityError:
        already_validated = False
    if already_validated:
        record = json.loads((partial / "chunk_record.json").read_text(encoding="utf-8"))
        commit_audit = release_then_commit_validated_partial(partial, completed, lambda: None)
        record_atomic_commit({"mesh": "coarse", "chunk_index": 0, "used_prevalidated_partial_without_comsol_reload": True, **commit_audit})
        state["completed"]["coarse"].append(0); state["completed"]["coarse"].sort()
        state["atomically_committed_chunks"] += 1
        state["accumulated_chunk_elapsed_s"] += record.get("pre_recovery_elapsed_s", 0.0) + record.get("recovery_elapsed_s", 0.0)
        state["status"] = "RUNNING"; state["stop_reason"] = None; state.pop("traceback", None)
        nxt = next_chunk(contract, state); state["next_chunk"] = {"mesh": nxt[0], "chunk_index": nxt[1]} if nxt else None
        state["updated_utc"] = utc_now(); atomic_json(STATE_PATH, state)
        records = verify_checkpoints(contract, state)
        atomic_json(MANIFEST_PATH, {"contract_sha256": sha256(CONTRACT_PATH), "records": records,
                    "provenance_counters": {key: state[key] for key in ("actual_study_run_submissions", "successfully_solved_study_runs", "atomically_committed_chunks")},
                    "updated_utc": utc_now()})
        return record
    import mph
    client = model = loaded = None
    started = time.time()
    try:
        client = mph.start(cores=cores, version="6.4")
        model = client.load(mph_path)
        live = evaluate(model, frequencies)
        np.savez_compressed(partial / "fields.npz", **live)
        save_csv(partial / "fields.csv", live)
        client.remove(model); model = None
        loaded = client.load(mph_path)
        reloaded = evaluate(loaded, frequencies)
        differences = {key: float(np.max(np.abs(live[key] - reloaded[key]))) for key in FIELDS if key != "frequency"}
        validation = {
            "recovered_from_existing_solved_partial_without_study_run": True,
            "frequency_axis_equal": bool(np.array_equal(live["frequency"], reloaded["frequency"])),
            "all_six_fields_64_point_finite": all(live[key].size == 64 and np.all(np.isfinite(live[key])) for key in FIELDS),
            "microphone_nonzero": not np.allclose(live["mic"], 0.0),
            "field_maximum_absolute_reload_differences": differences,
            "maximum_complex_microphone_reload_difference_pa": differences["mic"],
            "tolerance_pa": 1e-12,
        }
        validation["pass"] = bool(validation["frequency_axis_equal"] and validation["all_six_fields_64_point_finite"]
                                  and validation["microphone_nonzero"] and differences["mic"] <= 1e-12)
        if not validation["pass"]:
            raise RuntimeError(f"Existing solved partial reload validation failed: {validation}")
        atomic_json(partial / "validation.json", validation)
        start_record = json.loads((partial / "start_record.json").read_text(encoding="utf-8"))
        log_lines = log_path.read_text(encoding="utf-8").splitlines()
        completed_line = next(line for line in log_lines if line.startswith("study.run complete "))
        pre_recovery_elapsed_s = (datetime.fromisoformat(completed_line.removeprefix("study.run complete "))
                                  - datetime.fromisoformat(start_record["started_utc"])).total_seconds()
        recovery_elapsed_s = time.time() - started
        record = {**start_record, "recovery_completed_utc": utc_now(), "pre_recovery_elapsed_s": pre_recovery_elapsed_s,
                  "recovery_elapsed_s": recovery_elapsed_s,
                  "point_count": 64, "study_run_submitted_during_recovery": False,
                  "actual_study_run_submissions_total": state["actual_study_run_submissions"],
                  "successfully_solved_study_runs_total": state["successfully_solved_study_runs"],
                  "atomically_committed_chunks_before": state["atomically_committed_chunks"],
                  "active_script_sha256": sha256(SCRIPT), "authority_expression_source": AUTHORITY_EXPRESSION_SOURCE.relative_to(ROOT).as_posix(),
                  "authority_expression_source_sha256": sha256(AUTHORITY_EXPRESSION_SOURCE), "validation": validation, "final_test_read": False}
        atomic_json(partial / "chunk_record.json", record)
        write_checksums(partial)
        verify_chunk_directory(partial, frequencies)
        def release_for_commit():
            nonlocal client, model, loaded
            client, model, loaded = close_comsol_resources(client, model, loaded)
        commit_audit = release_then_commit_validated_partial(partial, completed, release_for_commit)
        record_atomic_commit({"mesh": "coarse", "chunk_index": 0, **commit_audit})
        state["completed"]["coarse"].append(0); state["completed"]["coarse"].sort()
        state["atomically_committed_chunks"] += 1
        state["accumulated_chunk_elapsed_s"] += pre_recovery_elapsed_s + recovery_elapsed_s
        state["status"] = "RUNNING"; state["stop_reason"] = None; state.pop("traceback", None)
        nxt = next_chunk(contract, state); state["next_chunk"] = {"mesh": nxt[0], "chunk_index": nxt[1]} if nxt else None
        state["updated_utc"] = utc_now(); atomic_json(STATE_PATH, state)
        records = verify_checkpoints(contract, state)
        atomic_json(MANIFEST_PATH, {"contract_sha256": sha256(CONTRACT_PATH), "records": records,
                    "provenance_counters": {key: state[key] for key in ("actual_study_run_submissions", "successfully_solved_study_runs", "atomically_committed_chunks")},
                    "updated_utc": utc_now()})
        return record
    finally:
        if client is not None:
            client, model, loaded = close_comsol_resources(client, model, loaded)


def stitch(mesh: str, contract: dict[str, Any]) -> dict[str, np.ndarray]:
    arrays = {key: [] for key in FIELDS}
    for item in contract["chunks"][mesh]:
        directory = chunk_dir(mesh, item["chunk_index"]); verify_chunk_directory(directory, item["frequencies_hz"])
        with np.load(directory / "fields.npz") as source:
            for key in FIELDS: arrays[key].append(np.asarray(source[key]))
    values = {key: np.concatenate(parts) for key, parts in arrays.items()}
    expected = np.asarray(contract["frequencies_hz"])
    if values["frequency"].size != 256 or not np.array_equal(values["frequency"], expected) or not np.all(np.diff(values["frequency"]) > 0):
        raise CheckpointIntegrityError(f"Invalid stitched {mesh} frequency axis")
    path = OUT / "stitched" / f"{mesh}_256_fields.npz"; np.savez_compressed(path, **values); save_csv(path.with_suffix(".csv"), values)
    atomic_json(OUT / "stitched" / f"{mesh}_256_validation.json", {"point_count": 256, "strictly_increasing": True,
                "exact_frozen_grid_match": True, "all_fields_finite": all(np.all(np.isfinite(values[k])) for k in FIELDS), "pass": True})
    return values


def window_mask(f: np.ndarray, target: float) -> np.ndarray:
    return (f >= target / 2 ** (1 / 6)) & (f <= target * 2 ** (1 / 6))


def peak(f: np.ndarray, q: np.ndarray, target: float) -> float | None:
    indices = np.flatnonzero(window_mask(f, target)); local = int(np.argmax(q[indices]))
    if local == 0 or local == len(indices) - 1: return None
    pick = indices[local-1:local+2]; coef = np.polyfit(np.log(f[pick]), np.log(np.maximum(q[pick], np.finfo(float).tiny)), 2)
    return float(f[indices[local]] if coef[0] >= 0 else np.exp(-coef[1] / (2 * coef[0])))


def numerical_gate(coarse: dict[str, np.ndarray], fine: dict[str, np.ndarray]) -> dict[str, Any]:
    peaks = {}; changes = []
    for label, field, target in (("HR03", "e_hr03", 1850.0), ("HR07", "e_south", 3800.0)):
        cp, fp = peak(coarse["frequency"], coarse[field], target), peak(fine["frequency"], fine[field], target)
        change = None if cp is None or fp is None else abs(fp / cp - 1); peaks[label] = {"coarse_hz": cp, "fine_hz": fp, "relative_change": change}
        if change is not None: changes.append(change)
    windows = {}; db_changes = []
    for label, target in (("HR03", 1850.0), ("HR07", 3800.0)):
        cm, fm = window_mask(coarse["frequency"], target), window_mask(fine["frequency"], target)
        c = 10 * math.log10(float(np.mean(np.abs(coarse["mic"][cm]) ** 2))); f = 10 * math.log10(float(np.mean(np.abs(fine["mic"][fm]) ** 2)))
        change = abs(f-c); windows[label] = {"coarse_db": c, "fine_db": f, "absolute_change_db": change}; db_changes.append(change)
    checks = {"all_peaks_identified": len(changes) == 2, "maximum_peak_center_change_below_1pct": len(changes) == 2 and max(changes) < .01,
              "maximum_fixed_window_change_below_0p5db": max(db_changes) < .5}
    return {"peaks": peaks, "fixed_windows": windows, "thresholds": {"peak": .01, "window_db": .5}, "checks": checks, "pass": all(checks.values())}


def update_recovery_doc(state: dict[str, Any]) -> None:
    nxt = state.get("next_chunk"); next_text = "none" if nxt is None else f"{nxt['mesh']} chunk {nxt['chunk_index']}"
    (OUT / "RESUME_INSTRUCTIONS_zh.md").write_text(f"""# TRANS-1R256 恢复说明\n\n唯一恢复命令：\n\n```powershell\n& 'D:\\Firefly\\Documents\\ChatGPT\\Comsol\\COMSOL_Multiphysics_MCP\\.venv\\Scripts\\python.exe' 'outputs/simulation/COMSOL_TRANS_1_R256_RESUMABLE_GATE/run_resumable_256_gate.py' --resume\n```\n\n- coarse：{len(state['completed']['coarse'])}/4\n- fine：{len(state['completed']['fine'])}/16\n- 下一块：{next_text}\n- 状态：{state['status']}\n- actual study.run / solved / committed：{state.get('actual_study_run_submissions', 0)} / {state.get('successfully_solved_study_runs', 0)} / {state.get('atomically_committed_chunks', 0)}\n- 停止原因：{state.get('stop_reason')}\n\n恢复入口会先核验冻结契约、completed目录、频率和所有SHA；完整性不符会停止，不会静默重算。`.partial`仅表示未提交块，恢复时只重跑该块。\n""", encoding="utf-8")


def write_progress_report(state: dict[str, Any], gate: dict[str, Any] | None = None) -> None:
    nxt = state.get("next_chunk"); next_text = "无" if nxt is None else f"{nxt['mesh']} chunk {nxt['chunk_index']}"
    gate_text = "尚未形成" if gate is None else ("PASS" if gate.get("pass") else "FAIL")
    REPORT_PATH.write_text(f"""# COMSOL TRANS-1R256 — 可恢复256点 coarse/fine 数值门禁

更新时间：{utc_now()}  
状态：`{state.get('status')}`

## 检查点

- coarse：{len(state['completed']['coarse'])}/4
- fine：{len(state['completed']['fine'])}/16
- 下一待运行块：{next_text}
- actual study.run submissions：{state.get('actual_study_run_submissions', state.get('study_run_count', 0))}/20
- successfully solved：{state.get('successfully_solved_study_runs', 0)}
- atomically committed chunks：{state.get('atomically_committed_chunks', 0)}
- 块累计实际时间：{state.get('accumulated_chunk_elapsed_s', 0.0):.3f} s
- 当前阶段产物：{output_size() / 1024**3:.3f} GiB
- 剩余空间：{free_bytes() / 1024**3:.3f} GiB
- 停止原因：{state.get('stop_reason')}
- 检查点完整性：每次入口及每块提交后均校验冻结契约、目录文件、频率轴和 SHA-256。

## 数值门禁

coarse/fine 门禁：{gate_text}。阈值保持共振中心变化 <1%，固定窗口关键对比变化 <0.5 dB。

## 恢复

唯一命令见 `outputs/simulation/COMSOL_TRANS_1_R256_RESUMABLE_GATE/RESUME_INSTRUCTIONS_zh.md`。恢复只继续下一未提交块；不会重跑可信 completed 块。

## 边界

仅 ISO-CODED/N；未启动第二组合、TRANS-2/3、外场、分类器或实体分析。`final_test_read=false`。未 commit、push、tag 或 release。
""", encoding="utf-8")


def write_stage_sha256() -> None:
    excluded = {"SHA256SUMS.txt"}
    rows = []
    for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name not in excluded and ".partial" not in p.parts):
        rows.append(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}")
    if REPORT_PATH.exists(): rows.append(f"{sha256(REPORT_PATH)}  {REPORT_PATH.relative_to(ROOT).as_posix()}")
    (OUT / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--resume", action="store_true"); parser.add_argument("--cores", type=int, default=4); parser.add_argument("--dry-run", action="store_true"); parser.add_argument("--single-chunk-worker", action="store_true"); args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True); contract = None; state = None
    try:
        contract = initialize_or_verify_contract(); state = load_state(contract); ensure_provenance_counters(state); atomic_json(STATE_PATH, state); records = verify_checkpoints(contract, state)
        atomic_json(MANIFEST_PATH, {"contract_sha256": sha256(CONTRACT_PATH), "records": records,
                    "provenance_counters": {key: state[key] for key in ("actual_study_run_submissions", "successfully_solved_study_runs", "atomically_committed_chunks")},
                    "updated_utc": utc_now()})
        if args.dry_run: update_recovery_doc(state); write_progress_report(state); write_stage_sha256(); print(json.dumps(state, indent=2)); return
        recovered = recover_solved_partial_chunk_zero(contract, state, args.cores)
        if recovered is not None:
            update_recovery_doc(state); write_progress_report(state); write_stage_sha256()
            print(json.dumps({"event": "recovered_and_committed_existing_partial", "mesh": "coarse", "index": 0,
                              "provenance_counters": {key: state[key] for key in ("actual_study_run_submissions", "successfully_solved_study_runs", "atomically_committed_chunks")}}), flush=True)
        if args.single_chunk_worker:
            nxt = next_chunk(contract, state)
            if nxt is None:
                return
            if nxt[0] == "fine" and len(state["completed"]["coarse"]) != 4: raise CheckpointIntegrityError("Fine blocked until coarse complete")
            resource_gate(state); print(json.dumps({"event": "starting_chunk_worker", "mesh": nxt[0], "index": nxt[1], "utc": utc_now()}), flush=True)
            run_chunk(nxt[0], nxt[1], contract, state, args.cores); update_recovery_doc(state); write_progress_report(state); write_stage_sha256()
            print(json.dumps({"event": "completed_chunk_worker", "mesh": nxt[0], "index": nxt[1], "state": state}, ensure_ascii=False), flush=True)
            if nxt == ("coarse", 3): stitch("coarse", contract)
            return
        while True:
            nxt = next_chunk(contract, state)
            if nxt is None: break
            if nxt[0] == "fine" and len(state["completed"]["coarse"]) != 4: raise CheckpointIntegrityError("Fine blocked until coarse complete")
            resource_gate(state); print(json.dumps({"event": "starting_chunk", "mesh": nxt[0], "index": nxt[1], "utc": utc_now()}), flush=True)
            worker = dispatch_chunk_worker(args.cores)
            if worker.returncode != 0:
                raise ChunkWorkerFailed(f"Isolated chunk worker exited with code {worker.returncode}")
            state = load_state(contract); verify_checkpoints(contract, state); update_recovery_doc(state); write_progress_report(state); write_stage_sha256()
            print(json.dumps({"event": "completed_chunk", "mesh": nxt[0], "index": nxt[1], "state": state}, ensure_ascii=False), flush=True)
        coarse, fine = stitch("coarse", contract), stitch("fine", contract); gate = numerical_gate(coarse, fine); atomic_json(OUT / "stitched/numerical_gate.json", gate)
        state["status"] = "TRANS1_R256_NUMERICAL_GATE_PASS" if gate["pass"] else "TRANS1_R256_NUMERICAL_GATE_FAIL"; state["next_chunk"] = None; state["updated_utc"] = utc_now(); atomic_json(STATE_PATH, state); update_recovery_doc(state); write_progress_report(state, gate); write_stage_sha256()
    except CheckpointIntegrityError as exc:
        persisted = persist_checkpoint_integrity_failure(state, exc)
        if persisted:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8")); update_recovery_doc(state); write_progress_report(state); write_stage_sha256()
        raise
    except ResourceStop as exc:
        state.update({"status": "TRANS1_R256_BLOCKED_BY_RESOURCE_STOP", "stop_reason": str(exc), "updated_utc": utc_now()}); atomic_json(STATE_PATH, state); update_recovery_doc(state); write_progress_report(state); write_stage_sha256(); raise
    except ChunkWorkerFailed:
        state = load_state(contract); update_recovery_doc(state); write_progress_report(state); write_stage_sha256(); raise
    except Exception as exc:
        mesh = (state or {}).get("next_chunk", {}).get("mesh", "coarse")
        status = "TRANS1_R256_BLOCKED_DURING_FINE" if mesh == "fine" else "TRANS1_R256_BLOCKED_DURING_COARSE"
        if state is None: state = {"completed": {"coarse": [], "fine": []}, "study_run_count": 0, "accumulated_chunk_elapsed_s": 0}
        state.update({"status": status, "stop_reason": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(), "updated_utc": utc_now(), "final_test_read": False}); atomic_json(STATE_PATH, state); update_recovery_doc(state); write_progress_report(state); write_stage_sha256(); raise


if __name__ == "__main__":
    main()
