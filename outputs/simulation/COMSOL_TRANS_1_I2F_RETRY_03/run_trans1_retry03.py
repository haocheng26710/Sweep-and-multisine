"""TRANS-1 RETRY_03: resolve MPh datasets by Java tag via Node objects."""

from __future__ import annotations

import argparse
import importlib.util
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import mph
import numpy as np

from dataset_node_resolution import dataset_node_by_java_tag


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_03"
RETRY02_DIR = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_02"
RETRY02_RUNNER = RETRY02_DIR / "run_trans1_retry02.py"
CONTROL_MPH = RETRY02_DIR / "SESSION_CONTROL_ISO_CODED_N_COARSE_SMOKE.mph"
CONTROL_RAW = RETRY02_DIR / "raw_SESSION_CONTROL_ISO_CODED_N_COARSE_SMOKE.npz"


def load_retry02():
    spec = importlib.util.spec_from_file_location("trans1_retry02_authority", RETRY02_RUNNER)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Cannot load TRANS-1 RETRY_02 authority")
    spec.loader.exec_module(module)
    return module


R2 = load_retry02()
R2.OUT = OUT


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def evaluate_fields(model, expected: int, dataset_tag: str | None = None) -> dict[str, np.ndarray]:
    dataset_node = None if dataset_tag is None else dataset_node_by_java_tag(model, dataset_tag)
    keyword = {} if dataset_node is None else {"dataset": dataset_node}
    values = {
        "frequency": np.asarray(model.evaluate("freq", **keyword)).real.reshape(-1),
        "mic": np.asarray(model.evaluate("aveop_mic(acpr.p_t)/p_inc", **keyword)).reshape(-1),
        "e_all": np.asarray(model.evaluate(f"intop_all({R2.R0.ENERGY_DENSITY})", **keyword)).real.reshape(-1),
        "e_hr03": np.asarray(model.evaluate(f"intop_hr03({R2.R0.ENERGY_DENSITY})", **keyword)).real.reshape(-1),
        "e_south": np.asarray(model.evaluate(f"intop_south({R2.R0.ENERGY_DENSITY})", **keyword)).real.reshape(-1),
        "e_plenum": np.asarray(model.evaluate(f"intop_plenum({R2.R0.ENERGY_DENSITY})", **keyword)).real.reshape(-1),
    }
    sizes = {key: int(value.size) for key, value in values.items()}
    return {**values, "_sizes": sizes, "_expected": expected}


# The RETRY_02 extraction algorithm remains authoritative; only its dataset
# argument adapter changes from a display-name string to a real MPh Node.
R2.evaluate_fields = evaluate_fields


def verify_existing_mph_node_resolution(client) -> dict[str, Any]:
    model = None
    try:
        model = client.load(CONTROL_MPH)
        audit = R2.solution_dataset_audit(model)
        tags = audit["solution_dataset_tags"]
        if tags != ["dset1"]:
            raise RuntimeError(f"Expected one dset1 solution dataset, found {tags}")
        node = dataset_node_by_java_tag(model, "dset1")
        values = evaluate_fields(model, 4, dataset_tag="dset1")
        sizes = values.pop("_sizes")
        values.pop("_expected")
        expected_frequency = R2.SMOKE_FREQ
        R2.validate_values(values, expected_frequency)
        with np.load(CONTROL_RAW) as source:
            reference = {key: np.asarray(source[key]) for key in R2.FIELDS}
        differences = {
            key: float(np.max(np.abs(values[key] - reference[key])))
            for key in R2.FIELDS
            if key != "frequency"
        }
        result = {
            "status": "PASS",
            "source_mph": CONTROL_MPH.relative_to(ROOT).as_posix(),
            "source_mph_sha256": R2.sha256(CONTROL_MPH),
            "java_dataset_tag": "dset1",
            "mph_dataset_node_name": node.name(),
            "mph_dataset_node_tag": node.tag(),
            "node_object_passed_to_evaluate": True,
            "field_lengths": sizes,
            "frequency_axis_equal": bool(np.array_equal(values["frequency"], reference["frequency"])),
            "field_maximum_absolute_differences": differences,
            "maximum_complex_microphone_difference_pa": differences["mic"],
            "tolerance_pa": 1e-12,
            "pass": bool(differences["mic"] <= 1e-12),
            "solution_dataset_audit": audit,
        }
        if not result["pass"]:
            raise RuntimeError(f"Existing MPH Node feedback mismatch: {result}")
        atomic_json(OUT / "existing_mph_node_feedback.json", result)
        return result
    finally:
        if model is not None:
            try:
                client.remove(model)
            except Exception:
                pass


def run(client, server_port: int | None) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    if client.models():
        raise RuntimeError(f"Fresh-session gate failed; initial models={client.models()}")
    feedback = verify_existing_mph_node_resolution(client)
    if client.models():
        raise RuntimeError(f"Feedback cleanup failed; remaining models={client.models()}")
    try:
        result = R2.run_all(client, -1 if server_port is None else server_port)
    except Exception as exc:
        state = {
            "technical_status": "TRANS1_RETRY_03_BLOCKED_AFTER_NODE_FIX",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "existing_mph_node_feedback_pass": True,
            "final_test_read": False,
        }
        atomic_json(OUT / "retry03_failure.json", state)
        atomic_json(OUT / "execution_state.json", state)
        raise
    result["existing_mph_node_feedback"] = feedback
    result["completed_at"] = datetime.now().astimezone().isoformat()
    atomic_json(OUT / "retry03_execution_result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int)
    parser.add_argument("--cores", type=int, default=4)
    args = parser.parse_args()
    client = None
    try:
        if args.port is None:
            client = mph.start(cores=args.cores, version="6.4")
        else:
            client = mph.Client(version="6.4", port=args.port)
        result = run(client, args.port)
        print(json.dumps({
            "success": True,
            "gate_pass": result["gate_pass"],
            "record_count": len(result["records"]),
        }, indent=2))
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
