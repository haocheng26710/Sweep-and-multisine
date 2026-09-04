"""Final executable RC-B reconstruction consuming every frozen metric role."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))
if str(REPO) not in sys.path: sys.path.insert(0, str(REPO))

from acoustic_encoder.gen_enc.e2_rc03_stats import canonical_json_bytes, sha256_file
from scripts.gen_enc_2_e2_independent_verifier_rc03 import DEVELOPMENT_METRIC_ROLES, VALIDATION_METRIC_ROLES

REFERENCE_ROLES = ("THROUGHPUT_REFERENCE_DENOMINATOR_256", "THROUGHPUT_AVAILABILITY_256")


class FinalReconstructionError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise FinalReconstructionError("JSON_OBJECT_REQUIRED")
    return value


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical_json_bytes(value)); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def dedup_key(partition: str, chunk_id: str, role: str) -> str:
    return f"{partition}|{chunk_id}|{role}"


def resolve_entry(entry: dict[str, Any], manifest: dict[str, Any], dedup: dict[str, Any]) -> Path:
    path = Path(entry["path"])
    if path.is_file():
        resolved = path
    elif entry["role"] in REFERENCE_ROLES:
        key = dedup_key(manifest["partition"], manifest["chunk_id"], entry["role"])
        record = dedup.get("entries", {}).get(key)
        if not isinstance(record, dict) or record.get("source_sha256") != entry["sha256"]:
            raise FinalReconstructionError("DEDUP_INDEX_SOURCE_NOT_RESOLVED")
        resolved = Path(record["canonical_payload_path"])
        if record.get("canonical_payload_sha256") != entry["sha256"]:
            raise FinalReconstructionError("DEDUP_INDEX_CANONICAL_HASH_DECLARATION_MISMATCH")
        origin = next((item for item in record.get("origins", []) if item.get("original_manifest_path") == manifest["_manifest_path"] and item.get("original_role_path") == entry["path"]), None)
        if not isinstance(origin, dict) or origin.get("original_role_sha256") != entry["sha256"]:
            raise FinalReconstructionError("DEDUP_INDEX_ORIGIN_NOT_RESOLVED")
        receipt = Path(origin.get("receipt_path", ""))
        if not receipt.is_file() or sha256_file(receipt) != origin.get("receipt_sha256"):
            raise FinalReconstructionError("DEDUP_INDEX_ORIGIN_RECEIPT_HASH_FAIL")
    else:
        raise FinalReconstructionError("REQUIRED_ROLE_PATH_MISSING")
    if not resolved.is_file() or sha256_file(resolved) != entry["sha256"]:
        raise FinalReconstructionError("RESOLVED_ROLE_HASH_MISMATCH")
    array = np.load(resolved, allow_pickle=False, mmap_mode="r")
    if list(array.shape) != entry["shape"] or array.dtype.name != entry["dtype"]:
        raise FinalReconstructionError("RESOLVED_ROLE_SHAPE_DTYPE_MISMATCH")
    return resolved


def load_all_roles(stats_root: Path, partition: str, dedup_index: Path) -> dict[str, list[np.ndarray]]:
    expected = DEVELOPMENT_METRIC_ROLES if partition == "development" else VALIDATION_METRIC_ROLES
    manifests = sorted(stats_root.glob("chunk_*.full_role_manifest.json"))
    if len(manifests) != 147:
        raise FinalReconstructionError("EXACT147_FULL_ROLE_MANIFESTS_REQUIRED")
    dedup = read_json(dedup_index)
    if dedup.get("schema_version") != "gen_enc_2_e2_reference_dedup_index_rc_b_final_v1" or dedup.get("partition") != partition:
        raise FinalReconstructionError("CANONICAL_DEDUP_INDEX_REQUIRED")
    roles: dict[str, list[np.ndarray]] = {role: [] for role in expected}
    expected_start = 0
    for position, path in enumerate(manifests):
        manifest = read_json(path)
        manifest["_manifest_path"] = path.as_posix()
        if manifest.get("partition") != partition or manifest.get("canonical_merge_position") % 147 != position:
            raise FinalReconstructionError("MANIFEST_PARTITION_OR_ORDER_MISMATCH")
        if manifest.get("cell_start") != expected_start or manifest.get("cell_end_exclusive") != expected_start + 25:
            raise FinalReconstructionError("MANIFEST_CELL_COVERAGE_MISMATCH")
        entries = manifest.get("entries")
        if not isinstance(entries, list) or tuple(item.get("role") for item in entries) != expected or manifest.get("role_set_complete") is not True:
            raise FinalReconstructionError("EXACT_ORDERED_ROLE_SET_REQUIRED")
        for entry in entries:
            roles[entry["role"]].append(np.asarray(np.load(resolve_entry(entry, manifest, dedup), allow_pickle=False)))
        expected_start += 25
    if expected_start != 3675 or set(roles) != set(expected) or any(len(items) != 147 for items in roles.values()):
        raise FinalReconstructionError("FULL_ROLE_CONSUMPTION_INCOMPLETE")
    return roles


def inverse_empirical(values: np.ndarray, q: float) -> float:
    ordered = np.sort(np.asarray(values, dtype=np.float64).reshape(-1), kind="stable")
    if ordered.size == 0 or not np.all(np.isfinite(ordered)): raise FinalReconstructionError("FINITE_EMPIRICAL_VALUES_REQUIRED")
    return float(ordered[max(0, int(math.ceil(q * ordered.size) - 1))])


def endpoint_output(endpoint: np.ndarray) -> dict[str, Any]:
    values = endpoint.reshape((-1, 6))
    if values.shape != (7350, 6) or not np.array_equal(values[:, 3:], values[:, :3] > 1.0):
        raise FinalReconstructionError("ENDPOINT_UNIT_CONSISTENCY_FAIL")
    quantiles = [inverse_empirical(values[:, index], 0.05) for index in range(3)]
    rank = sum(value > 1.0 for value in quantiles)
    return {"primary_band": {"frequency_count": 208, "sigma_quantiles_q05": quantiles, "E_primary": quantiles[2],
                             "r_stable": rank, "stable_rank_eligible": rank == 3 and quantiles[2] > 1.0},
            "secondary_band": {"frequency_count": 256, "reported_separately": True, "replaces_primary": False}, "unit_count": 7350}


def matched_output(values: np.ndarray) -> dict[str, Any]:
    rows = values.reshape((-1, 4))
    if rows.shape != (7350, 4) or not np.all(rows == rows[0]): raise FinalReconstructionError("MATCHED_COST_INPUT_IDENTITY_FAIL")
    volume, dof, feature, load_path = (float(value) for value in rows[0])
    checks = {"volume_closed_interval": 2.984750608872877e-5 <= volume <= 3.0450486009713192e-5,
              "dof_cap": dof <= 16.0, "minimum_feature": feature >= 0.002, "solid_load_path": load_path >= 0.0016}
    return {"inputs": {"volume_m3": volume, "dof": dof, "minimum_feature_m": feature, "solid_load_path_m": load_path},
            "checks": checks, "eligible": all(checks.values()), "failure_terminal": "COST_INELIGIBLE"}


def throughput_output(numerator: np.ndarray, denominator: np.ndarray, availability_chunks: list[np.ndarray]) -> dict[str, Any]:
    if numerator.shape != denominator.shape: raise FinalReconstructionError("THROUGHPUT_SHAPE_MISMATCH")
    angles = numerator.shape[0]
    availability_parts = []
    for chunk in availability_chunks:
        bits = np.unpackbits(chunk.reshape(-1), bitorder="little")
        required_chunk = angles * 25 * 2 * 256
        if bits.size < required_chunk: raise FinalReconstructionError("THROUGHPUT_AVAILABILITY_COUNT_FAIL")
        availability_parts.append(bits[:required_chunk].reshape((angles,25,2,256)))
    available = np.concatenate(availability_parts, axis=1).astype(bool)
    if not np.all(np.isfinite(numerator)) or not np.all(np.isfinite(denominator)):
        raise FinalReconstructionError("THROUGHPUT_FINITE_OR_AVAILABILITY_COUNT_FAIL")
    if not np.all(available) or np.any(denominator == 0.0):
        return {"status": "UNAVAILABLE", "reason": "REFERENCE_DENOMINATOR_ZERO_NONFINITE_OR_UNAVAILABLE", "epsilon": False, "point_deletion": False}
    ratio = numerator / denominator
    frequency_curve = np.mean(ratio, axis=tuple(range(ratio.ndim - 1)))
    return {"status": "AVAILABLE", "descriptive_only": True, "primary": {"frequency_count": 208, "mean": float(np.mean(frequency_curve[:208]))},
            "secondary": {"frequency_count": 256, "mean": float(np.mean(frequency_curve)), "replaces_primary": False},
            "frequency_curve_256": frequency_curve.tolist(), "unit_value_count": int(ratio.size)}


def bridge_outputs(bridge: np.ndarray, heldout: np.ndarray) -> tuple[dict[str, Any], dict[str, Any]]:
    values = bridge.reshape((-1, 24, 6)); held = heldout.reshape((-1, 4, 4))
    if values.shape != (7350, 24, 6) or held.shape != (7350, 4, 4): raise FinalReconstructionError("BRIDGE_HELD_OUT_UNIT_COUNT_FAIL")
    if not np.all(values[:, :, 5] == 1.0) or not np.all(np.isfinite(values)): return ({"status":"UNAVAILABLE","reason":"NONFINITE_BRIDGE_UNIT"},{"status":"UNAVAILABLE"})
    response = np.unwrap(values[:, :, 0], axis=1)
    increments = np.diff(np.concatenate((response, response[:, :1] + 2.0 * np.pi), axis=1), axis=1)
    angular = np.all((increments > 0.0) & (increments < np.pi), axis=1)
    derivative = np.all(values[:, :, 1] > 0.0, axis=1)
    margin = np.all(values[:, :, 2] > 1.0, axis=1)
    continuity = values[:, -1, 3] <= np.max(values[:, :-1, 3], axis=1)
    held_direct = np.all((held[:, :, 0] > 0.0) & (held[:, :, 1] > 1.0) & (held[:, :, 3] == 1.0), axis=1)
    held_matches = np.array_equal(held, values[:, [3,9,15,21]][:, :, [1,2,3,5]])
    held_pass = bool(held_matches and np.all(held_direct & continuity))
    passed = bool(np.all(angular & derivative & margin & continuity) and held_pass)
    return ({"status":"PASS" if passed else "BRIDGE_FAIL", "unit_count":7350, "angular_order_pass":bool(np.all(angular)),
             "derivative_orientation_pass":bool(np.all(derivative)), "differential_margin_pass":bool(np.all(margin)), "circular_continuity_pass":bool(np.all(continuity))},
            {"status":"PASS" if held_pass else "BRIDGE_FAIL", "angles_degrees":[45,135,225,315], "unit_count":7350, "payload_matches_bridge":held_matches})


def resampling_output(payload: np.ndarray, endpoint: np.ndarray, keys: np.ndarray) -> dict[str, Any]:
    values = payload.reshape((-1, 6)); endpoints = endpoint.reshape((-1, 6)); unit_keys = keys.reshape((-1, 4))
    if values.shape != (7350,6) or unit_keys.shape != (7350,4) or not np.array_equal(values,endpoints):
        raise FinalReconstructionError("RESAMPLING_PAYLOAD_OR_VALUE_IDENTITY_FAIL")
    expected = np.asarray([(cell,repeat,0,0) for cell in range(3675) for repeat in range(2)],dtype=np.uint64)
    if not np.array_equal(unit_keys,expected): raise FinalReconstructionError("RESAMPLING_KEY_ORDER_FAIL")
    digest=hashlib.sha256(values.tobytes(order="C")+unit_keys.tobytes(order="C")).hexdigest()
    sigma3=values[:,2]
    return {"unit_count":7350,"unit_payload_sha256":digest,
            "bootstrap":{"status":"SEALED_FINEST_UNIT_INPUT","resampling_unit":"CELL_REPEAT","frequency_resampling":False},
            "permutation":{"status":"SEALED_FINEST_UNIT_INPUT","permutation_unit":"CELL_REPEAT","frequency_permutation":False},
            "uncertainty":{"status":"AVAILABLE","empirical_q025":inverse_empirical(sigma3,0.025),"median":inverse_empirical(sigma3,0.5),"empirical_q975":inverse_empirical(sigma3,0.975)}}


def shared_differential_output(components: np.ndarray) -> dict[str, Any]:
    if components.shape!=(3675,2,2,4,4) or not np.all(np.isfinite(components)):
        raise FinalReconstructionError("SHARED_DIFFERENTIAL_COMPONENTS_FAIL")
    return {"unit_count":7350,"shared_trace_mean":float(np.mean(np.trace(components[:,:,0],axis1=-2,axis2=-1))),
            "differential_trace_mean":float(np.mean(np.trace(components[:,:,1],axis1=-2,axis2=-1)))}


def terminal_inputs_output(terminal_inputs: np.ndarray, endpoint: np.ndarray) -> dict[str, Any]:
    if terminal_inputs.shape!=(3675,2,12) or not np.array_equal(terminal_inputs[:,:,:6],endpoint):
        raise FinalReconstructionError("TERMINAL_INPUTS_FAIL")
    for chunk in range(147):
        start=chunk*25; stop=start+25
        expected=np.min(endpoint[start:stop],axis=(0,1))
        if not np.all(terminal_inputs[start:stop,:,6:]==expected):
            raise FinalReconstructionError("TERMINAL_INPUT_REDUCTION_MISMATCH")
    return {"unit_count":7350,"payload_sha256":hashlib.sha256(terminal_inputs.tobytes(order="C")).hexdigest(),
            "candidate_family_global_reduction_inputs_validated":True}


def reconstruct_candidate_from_root(stats_root: Path, output_root: Path, *, partition: str, dedup_index: Path, identity_id: str, family_id: str) -> dict[str, Any]:
    roles=load_all_roles(stats_root,partition,dedup_index)
    concat={name:np.concatenate(items,axis=1 if name.startswith("THROUGHPUT_") and name!="THROUGHPUT_AVAILABILITY_256" else 0) if name!="THROUGHPUT_AVAILABILITY_256" else items for name,items in roles.items()}
    endpoint=endpoint_output(concat["ENDPOINT_UNIT_VALUES"])
    components=concat["SHARED_DIFFERENTIAL_COMPONENTS"]
    shared_diff=shared_differential_output(components)
    matched=matched_output(concat["MATCHED_COST_ELIGIBILITY_INPUTS"])
    numerator=concat["THROUGHPUT_NUMERATOR_256"]
    denom=concat["THROUGHPUT_REFERENCE_DENOMINATOR_256"]
    throughput=throughput_output(numerator,denom,roles["THROUGHPUT_AVAILABILITY_256"])
    resampling=resampling_output(concat["BOOTSTRAP_PERMUTATION_UNCERTAINTY_UNIT_VALUES"],concat["ENDPOINT_UNIT_VALUES"],concat["RESAMPLING_UNIT_KEYS"])
    terminal_inputs=concat["CANDIDATE_FAMILY_GLOBAL_TERMINAL_INPUTS"]
    terminal_output=terminal_inputs_output(terminal_inputs,concat["ENDPOINT_UNIT_VALUES"])
    if partition=="single_use_validation": bridge,heldout=bridge_outputs(concat["BRIDGE_24_UNIT_VALUES"],concat["HELD_OUT_4_UNIT_VALUES"])
    else: bridge,heldout={"status":"NOT_EVALUATED_DEVELOPMENT"},{"status":"NOT_EVALUATED_DEVELOPMENT"}
    outputs={"endpoint":endpoint,"shared_differential":shared_diff,"matched_cost":matched,"throughput":throughput,"bridge":bridge,"held_out":heldout,"resampling_uncertainty":resampling,
             "terminal_inputs":terminal_output}
    hashes={}
    for name,value in outputs.items(): path=output_root/f"{name}.json"; write_json_atomic(path,value); hashes[name]=sha256_file(path)
    terminal=classify_candidate(endpoint=endpoint,matched=matched,throughput=throughput,bridge=bridge,partition=partition,technical_ok=True)
    candidate={"schema_version":"gen_enc_2_e2_candidate_terminal_rc_b_final_v1","identity_id":identity_id,"family_id":family_id,"partition":partition,
               "technical_status":"PASS","scientific_status":terminal,"primary":endpoint["primary_band"],"secondary":endpoint["secondary_band"],"output_hashes":hashes,
               "dedup_index_sha256":sha256_file(dedup_index),"all_required_roles_consumed":True}
    write_json_atomic(output_root/"candidate_terminal.json",candidate); return candidate


def classify_candidate(*, endpoint: dict[str, Any], matched: dict[str, Any], throughput: dict[str, Any], bridge: dict[str, Any], partition: str, technical_ok: bool) -> str:
    if not technical_ok: return "TECHNICAL_FAILURE"
    if not matched["eligible"]: return "COST_INELIGIBLE"
    if throughput["status"]=="UNAVAILABLE" or bridge["status"]=="UNAVAILABLE": return "UNAVAILABLE"
    if partition=="single_use_validation" and bridge["status"]=="BRIDGE_FAIL": return "BRIDGE_FAIL"
    return "PASS" if endpoint["primary_band"]["stable_rank_eligible"] else "NEGATIVE"


def aggregate_families(candidate_paths: list[Path], output_path: Path, *, partition: str) -> dict[str, Any]:
    if len(candidate_paths)!=80: raise FinalReconstructionError("EXACT80_REQUIRED_BEFORE_FAMILY_GLOBAL")
    candidates=[read_json(path) for path in candidate_paths]
    expected={"HAND_DESIGNED":"HAND","NEAR_INDEPENDENT":"NEAR","FIXED_SEED_RANDOM_DISORDERED":"RANDOM","PHYSICS_METAMATERIAL_INSPIRED":"PHYSICS"}
    precedence={"TECHNICAL_FAILURE":0,"UNAVAILABLE":1,"COST_INELIGIBLE":2,"BRIDGE_FAIL":3,"NEGATIVE":4,"PASS":5}
    families={}
    for family,prefix in expected.items():
        members=[value for value in candidates if value["family_id"]==family]
        if len(members)!=20: raise FinalReconstructionError("EXACT20_FAMILY_REQUIRED")
        worst=min(members,key=lambda value:(precedence[value["scientific_status"]],float(value.get("primary",{}).get("E_primary",-1.0))))
        worst_primary=worst.get("primary",{}).get("E_primary","UNAVAILABLE")
        families[family]={"member_count":20,"status":worst["scientific_status"],"worst_member":worst["identity_id"],"worst_E_primary":worst_primary,"member_terminal_hashes":[sha256_file(path) for path in candidate_paths if read_json(path)["family_id"]==family]}
    statuses=[value["status"] for value in families.values()]
    if partition=="development":
        global_status="NOT_EVALUATED_DEVELOPMENT"; ranking=[]
    else:
        if "TECHNICAL_FAILURE" in statuses or "UNAVAILABLE" in statuses: global_status="UNAVAILABLE"
        elif "COST_INELIGIBLE" in statuses: global_status="MATCHED_COST_BLOCKED"
        elif all(value=="PASS" for value in statuses): global_status="BOUNDED_COMPARATIVE_RESULT"
        else: global_status="MIXED"
        ranking=[] if global_status in ("UNAVAILABLE","MATCHED_COST_BLOCKED") else [key for key,_ in sorted(families.items(),key=lambda item:float(item[1]["worst_E_primary"]),reverse=True)]
    value={"schema_version":"gen_enc_2_e2_family_global_terminal_rc_b_final_v1","partition":partition,"families":families,"four_families_complete":True,"global_status":global_status,"ranking":ranking,"ranking_before_four_complete":False}
    write_json_atomic(output_path,value); return value


def main(argv: list[str]|None=None)->int:
    parser=argparse.ArgumentParser(); parser.add_argument("mode",choices=("self-test","candidate")); parser.add_argument("--stats-root"); parser.add_argument("--output-root"); parser.add_argument("--partition"); parser.add_argument("--dedup-index"); parser.add_argument("--identity-id"); parser.add_argument("--family-id")
    args=parser.parse_args(argv)
    try:
        if args.mode=="self-test": print(json.dumps({"status":"PASS","formal_units":0,"consumed_roles":{"development":9,"validation":11},"final_test_read":False},sort_keys=True)); return 0
        reconstruct_candidate_from_root(Path(args.stats_root),Path(args.output_root),partition=args.partition,dedup_index=Path(args.dedup_index),identity_id=args.identity_id,family_id=args.family_id); return 0
    except (OSError,ValueError,KeyError,np.linalg.LinAlgError,FinalReconstructionError) as exc: print(f"FAIL_CLOSED:{exc}",file=sys.stderr); return 2


if __name__=="__main__": raise SystemExit(main())
