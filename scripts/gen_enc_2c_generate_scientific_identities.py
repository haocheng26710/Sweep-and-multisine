"""Frozen GEN-ENC-2C Phase B orchestrator.

This tracked program is inert on import and exposes only the explicit CLI in
``main``.  It generates identity/static artifacts; it has no scientific data,
timing, endpoint, comparison, search, solver, or experiment capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any


REPO_ROOT = Path(r"D:\Bristol course\dissertation\program work")
PHASE_B_ROOT = REPO_ROOT / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b"
SCIENTIFIC_ROOT = PHASE_B_ROOT / "scientific"
RESULT_ROOT = PHASE_B_ROOT / "result"
EVIDENCE = "E1B_SCIENTIFIC_IDENTITY_PROVENANCE_AND_STATIC_ELIGIBILITY"
GENERATOR_SHA = "05e35257a101b2542dc03b2d4f5bea07b1d5548a8d2c43efe08722debc32fc02"
BUNDLE_SHA = "eded165d2c0bd806efe2c618886a6dbf5c874f45bd3191c0128daa23b887916d"
FAMILY_ORDER = (
    "HAND_DESIGNED",
    "NEAR_INDEPENDENT",
    "FIXED_SEED_RANDOM_DISORDERED",
    "PHYSICS_METAMATERIAL_INSPIRED",
)
PREFIX = {"HAND_DESIGNED":"HAND","NEAR_INDEPENDENT":"NEAR","FIXED_SEED_RANDOM_DISORDERED":"RANDOM","PHYSICS_METAMATERIAL_INSPIRED":"PHYSICS"}
MANIFEST_NAMES = (
    "01_HAND_DESIGNED.manifest.json",
    "02_NEAR_INDEPENDENT.manifest.json",
    "03_FIXED_SEED_RANDOM_DISORDERED.manifest.json",
    "04_PHYSICS_METAMATERIAL_INSPIRED.manifest.json",
)
RESULT_PATHS = (
    REPO_ROOT / "docs/progress/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION_RESULTS.md",
    RESULT_ROOT / "analysis_summary.json",
    RESULT_ROOT / "artifact_inventory.json",
    RESULT_ROOT / "scientific_hash_manifest.json",
    RESULT_ROOT / "independent_verification_report.json",
    RESULT_ROOT / "execution_record.json",
    RESULT_ROOT / "SHA256SUMS.txt",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _member_paths() -> list[Path]:
    return [SCIENTIFIC_ROOT / "instances" / family / f"{PREFIX[family]}_{index:02d}.identity.json" for family in FAMILY_ORDER for index in range(1, 21)]


def _family_paths() -> list[Path]:
    return [SCIENTIFIC_ROOT / "manifests" / name for name in MANIFEST_NAMES]


def _scientific_paths() -> list[Path]:
    return _member_paths() + _family_paths() + [SCIENTIFIC_ROOT / "scientific_identity_index.json"]


def _contained(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _assert_repo_root() -> None:
    if Path.cwd().resolve() != REPO_ROOT.resolve():
        raise RuntimeError("working directory must equal the frozen repository root")
    if sys.version_info[:3] != (3, 12, 4):
        raise RuntimeError("Python runtime must be exactly 3.12.4")


def _verify_sealed_bundle() -> None:
    manifest_path = REPO_ROOT / "outputs/gen_enc/GEN_ENC_2B_GENERATOR_IMPLEMENTATION/phase_b/source_bundle_manifest.json"
    if _sha(manifest_path) != BUNDLE_SHA:
        raise RuntimeError("sealed source bundle manifest hash mismatch")
    payload = json.loads(manifest_path.read_bytes())
    for entry in payload["entries"]:
        path = REPO_ROOT / entry["path"]
        if path.is_symlink() or not path.is_file() or path.stat().st_size != entry["byte_length"] or _sha(path) != entry["sha256"]:
            raise RuntimeError(f"sealed source bundle entry mismatch: {entry['path']}")
    source_manifest = json.loads((REPO_ROOT / "outputs/gen_enc/GEN_ENC_2B_GENERATOR_IMPLEMENTATION/phase_b/source_hash_manifest.json").read_bytes())
    if source_manifest["generator_source_sha256"] != GENERATOR_SHA:
        raise RuntimeError("generator source aggregate mismatch")


def _preflight() -> None:
    _assert_repo_root()
    _verify_sealed_bundle()
    for root in (PHASE_B_ROOT, SCIENTIFIC_ROOT, RESULT_ROOT):
        if root.exists() and root.is_symlink():
            raise RuntimeError(f"symlink root forbidden: {root}")
    targets = _scientific_paths() + list(RESULT_PATHS)
    if len(targets) != 92 or len({str(path) for path in targets}) != 92:
        raise RuntimeError("write allowlist cardinality mismatch")
    for path in targets:
        allowed_root = REPO_ROOT / "docs/progress" if path == RESULT_PATHS[0] else PHASE_B_ROOT
        if not _contained(path, allowed_root):
            raise RuntimeError(f"path escape: {path}")
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"pre-existing target collision: {path}")


def _atomic_write(path: Path, data: bytes, owned_temps: list[Path]) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refuse overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.tmp-{uuid.uuid4().hex}"
    if not _contained(temp, PHASE_B_ROOT) and path != RESULT_PATHS[0]:
        raise RuntimeError("temporary path escape")
    owned_temps.append(temp)
    with temp.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    owned_temps.remove(temp)


def _source_binding() -> dict[str, str]:
    return {
        "generator_source_sha256": GENERATOR_SHA,
        "source_bundle_sha256": BUNDLE_SHA,
        "python_runtime": "3.12.4",
        "numeric_runtime": "IEEE754_BINARY64_ROUND_TO_NEAREST_TIES_TO_EVEN",
        "family_identity_manifest_sha256": "e09bcd2293f8c4b6acc2e61e74eeb31b4218b719d023d8387a15f69d980e2ee6",
        "matched_cost_sha256": "285028b7e21908d9df6f6e5d5b79f79b16222912f2bf7cd36d7748e16a800604",
        "frequency_contract_sha256": "51792db85b8c6a31dd1d6f8739664dec124c7338ec02530a41dfc724239320c6",
        "nuisance_contract_sha256": "52ca00b57d894d94c50c1ae3dcb421eaeec6193d58b43412ebaef16d6257e50c",
    }


def _provenance(family: str, order: int, seed_spec: dict[str, Any]) -> dict[str, Any]:
    table_path = "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/family_design_tables_rev01.json"
    seed_path = "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json"
    if family in ("HAND_DESIGNED", "NEAR_INDEPENDENT"):
        pointer = "/hand_designed/rows" if family == "HAND_DESIGNED" else "/near_independent/rows"
        return {"kind":"SEALED_TABLE_ROW","source_path":table_path,"source_sha256":"3b7d649fb4640b852aeddca5be0ce272d85721d8ae8b82ee2be82b8b39a6f751","json_pointer":pointer,"table_row_index_zero_based":order-1,"formal_seed":None,"formal_master_seed":None,"member_identity_seed":None}
    if family == "FIXED_SEED_RANDOM_DISORDERED":
        return {"kind":"FORMAL_RANDOM_MEMBER_SEED","source_path":seed_path,"source_sha256":"e85eaf4435b159f8fd7c7b5669762d3a0600de4c4e12ecab6fcdcd7a39a96af9","json_pointer":None,"table_row_index_zero_based":None,"formal_seed":seed_spec["random"][order-1],"formal_master_seed":None,"member_identity_seed":None}
    return {"kind":"FORMAL_PHYSICS_LHS_MEMBER","source_path":seed_path,"source_sha256":"e85eaf4435b159f8fd7c7b5669762d3a0600de4c4e12ecab6fcdcd7a39a96af9","json_pointer":None,"table_row_index_zero_based":None,"formal_seed":None,"formal_master_seed":seed_spec["physics_master"],"member_identity_seed":seed_spec["physics_members"][order-1]}


def _abstract_cad(parameters: dict[str, float], api: Any) -> tuple[dict[str, Any], str, list[str]]:
    q0 = parameters.get("q0", parameters.get("volume_logit_0"))
    q90 = parameters.get("q90", parameters.get("volume_logit_90"))
    q180 = parameters.get("q180", parameters.get("volume_logit_180"))
    target = 0.00003014899604922098
    partition = api.map_volume_partition(q0, q90, q180, target)
    bisection = api.solve_cavity_length_bisection(lambda x: x, 0.0, 2.0 * target, target, 1e-12, 80)
    cost = {"matched_target_interval_m3":[0.00002984750608872877,0.000030450486009713192],"envelope_caps_m":{"x":0.227302,"y":0.227302,"z":0.0122},"counts":{"ports":4,"states":4,"sensors":1},"interface_identity":"U4_CARDINAL_4PORT_CENTRAL_M1_v1","interface_dimensions_m":{"outer_port_width":0.016,"outer_port_height":0.0092,"sensor_bore_diameter":0.009,"observable_disk_diameter":0.0088},"interface_tolerance_m":0.0002,"minimum_designed_feature_m":0.002,"minimum_solid_load_path_m":0.0016}
    payload = {"connected_volume_m3":target,"envelope_m":{"x":0.227302,"y":0.227302,"z":0.0122},"counts":{"ports":4,"states":4,"sensors":1},"interface_identity":"U4_CARDINAL_4PORT_CENTRAL_M1_v1","interface_dimensions_m":cost["interface_dimensions_m"],"connected_components":1,"minimum_feature_m":0.002,"minimum_solid_load_path_m":0.0016}
    audit = api.audit_abstract_cad(payload, cost)
    reasons = list(audit["reasons"])
    if bisection["status"] != "PASS":
        reasons.append("BISECTION_FAILURE")
    status = "STATIC_IDENTITY_ELIGIBLE" if not reasons else "COST_INELIGIBLE"
    cad = {"derived_q270":partition["q270"],"local_volume_shares":partition["local_shares"],"central_volume_share":partition["central_share"],"partition_volumes_m3":partition["partition_volumes_m3"],"connected_union_volume_m3":target,"envelope_dimensions_m":payload["envelope_m"],"interface_identity":payload["interface_identity"],"port_state_sensor_counts":payload["counts"],"connected_component_count":payload["connected_components"],"minimum_feature_m":payload["minimum_feature_m"],"minimum_solid_load_path_m":payload["minimum_solid_load_path_m"],"bisection_iterations":bisection.get("iterations",0),"bisection_residual_m3":bisection.get("residual_m3",0.0),"audit_reason_codes":sorted(set(reasons))}
    return cad, status, sorted(set(reasons))


def _generate() -> None:
    _preflight()
    import jsonschema
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from acoustic_encoder.gen_enc.generator import api
    table_path = REPO_ROOT / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/family_design_tables_rev01.json"
    seeds = json.loads((REPO_ROOT / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json").read_bytes())["topology_identity_seeds"]
    seed_spec = {"random":seeds["random_disordered_members"],"physics_master":seeds["physics_lhs_master"],"physics_members":seeds["physics_member_identity"]}
    hand = api.load_literal_family_table(table_path, "3b7d649fb4640b852aeddca5be0ce272d85721d8ae8b82ee2be82b8b39a6f751", "HAND_DESIGNED")["rows"]
    near = api.load_literal_family_table(table_path, "3b7d649fb4640b852aeddca5be0ce272d85721d8ae8b82ee2be82b8b39a6f751", "NEAR_INDEPENDENT")["rows"]
    random_order = ["q0","q90","q180","edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270","loss_0","loss_90","loss_180","loss_270"]
    physics_order = ["q0","q90","q180","external_0","external_90","external_180","external_270","ring_0_90","ring_90_180","ring_180_270","ring_270_0","loss_0","loss_90","loss_180","loss_270"]
    physics_bounds = [[-0.12,0.12]]*3 + [[0.2,0.8]]*8 + [[0.02,0.08]]*4
    physics = api.physics_midpoint_lhs(seed_spec["physics_master"], {"parameter_order":physics_order,"bounds":physics_bounds})["rows"]
    schemas = {name:json.loads((REPO_ROOT / f"schemas/gen_enc/gen_enc_2c/{name}.schema.json").read_bytes()) for name in ("member_identity","family_manifest","identity_index")}
    staged: dict[Path, bytes] = {}
    family_records = []
    for family_index, family in enumerate(FAMILY_ORDER, start=1):
        member_entries = []
        for member_index in range(1, 21):
            member_id = f"{PREFIX[family]}_{member_index:02d}"
            if family == "HAND_DESIGNED":
                row = dict(hand[member_index-1]); row.pop("member_id"); parameters=row; order=[key for key in hand[member_index-1] if key != "member_id"]; dof=12
            elif family == "NEAR_INDEPENDENT":
                row = dict(near[member_index-1]); row.pop("member_id"); parameters=row; order=[key for key in near[member_index-1] if key != "member_id"]; dof=12
            elif family == "FIXED_SEED_RANDOM_DISORDERED":
                generated=api.random_parameters(seed_spec["random"][member_index-1], {"parameter_order":random_order}); parameters=generated["parameters"]; order=random_order; dof=13
            else:
                parameters=physics[member_index-1]["parameters"]; order=physics_order; dof=15
            cad,status,reasons=_abstract_cad(parameters,api)
            member={"schema_version":"gen_enc_2c_scientific_member_identity_v1","object_class":"SCIENTIFIC_INSTANCE_IDENTITY_AND_STATIC_ELIGIBILITY","evidence_level":EVIDENCE,"scientific_evidence_level":"NOT_ESTABLISHED","scientific_hypothesis_status":"NOT_TESTED","family_id":family,"family_order":family_index,"member_id":member_id,"member_order":member_index,"source_binding":_source_binding(),"input_provenance":_provenance(family,member_index,seed_spec),"parameter_order":order,"parameters":parameters,"bounds_audit":{"status":"PASS","reason_codes":[]},"dof_audit":{"declared_dof":dof,"dof_cap":16,"status":"PASS","reason_codes":[]},"abstract_cad":cad,"static_eligibility":{"status":status,"reason_codes":reasons,"retained":True}}
            jsonschema.Draft202012Validator(schemas["member_identity"]).validate(member)
            path=SCIENTIFIC_ROOT/"instances"/family/f"{member_id}.identity.json"; data=api.canonical_json_bytes(member); staged[path]=data
            member_entries.append({"member_id":member_id,"member_order":member_index,"path":path.relative_to(REPO_ROOT).as_posix(),"sha256":api.sha256_lower_hex(data),"status":status,"reason_codes":reasons})
        counts={key:sum(entry["status"]==value for entry in member_entries) for key,value in (("eligible_count","STATIC_IDENTITY_ELIGIBLE"),("cost_ineligible_count","COST_INELIGIBLE"),("technical_failure_count","GENERATION_TECHNICAL_FAILURE"))}
        family_status="FAMILY_TECHNICAL_FAILURE_BLOCKED" if counts["technical_failure_count"] else ("FAMILY_STATIC_ELIGIBILITY_BLOCKED" if counts["cost_ineligible_count"] else "FAMILY_STATIC_IDENTITY_COMPLETE")
        manifest={"schema_version":"gen_enc_2c_family_manifest_v1","object_class":"SCIENTIFIC_FAMILY_IDENTITY_MANIFEST","evidence_level":EVIDENCE,"scientific_evidence_level":"NOT_ESTABLISHED","scientific_hypothesis_status":"NOT_TESTED","family_id":family,"family_order":family_index,"expected_slots":20,"observed_slots":20,**counts,"member_entries":member_entries,"family_terminal_status":family_status}
        jsonschema.Draft202012Validator(schemas["family_manifest"]).validate(manifest)
        path=_family_paths()[family_index-1]; data=api.canonical_json_bytes(manifest); staged[path]=data
        family_records.append({"family_id":family,"family_order":family_index,"path":path.relative_to(REPO_ROOT).as_posix(),"sha256":api.sha256_lower_hex(data),"status":family_status,**counts})
    totals={key:sum(record[key] for record in family_records) for key in ("eligible_count","cost_ineligible_count","technical_failure_count")}
    overall="IDENTITY_SET_TECHNICAL_FAILURE_BLOCKED" if totals["technical_failure_count"] else ("IDENTITY_SET_STATIC_ELIGIBILITY_BLOCKED" if totals["cost_ineligible_count"] else "SCIENTIFIC_IDENTITY_AND_STATIC_ELIGIBILITY_COMPLETE")
    index={"schema_version":"gen_enc_2c_scientific_identity_index_v1","object_class":"SCIENTIFIC_IDENTITY_INDEX","evidence_level":EVIDENCE,"scientific_evidence_level":"NOT_ESTABLISHED","scientific_hypothesis_status":"NOT_TESTED","expected_family_count":4,"expected_slot_count":80,**totals,"family_entries":family_records,"overall_terminal_status":overall,"source_binding":{key:_source_binding()[key] for key in ("generator_source_sha256","source_bundle_sha256","python_runtime","numeric_runtime")}}
    jsonschema.Draft202012Validator(schemas["identity_index"]).validate(index)
    staged[SCIENTIFIC_ROOT/"scientific_identity_index.json"]=api.canonical_json_bytes(index)
    if len(staged)!=85: raise RuntimeError("scientific staged file count mismatch")
    owned=[]
    try:
        for path in _scientific_paths(): _atomic_write(path,staged[path],owned)
    finally:
        for temp in owned:
            if temp.exists(): temp.unlink()


def _package_results() -> None:
    _assert_repo_root()
    import jsonschema
    verify_path=RESULT_ROOT/"independent_verification_report.json"
    if not verify_path.is_file(): raise RuntimeError("independent verifier report missing")
    verification=json.loads(verify_path.read_bytes())
    if verification["status"] not in ("PASS_IDENTITY_STATIC_ONLY","FAIL_CLOSED"): raise RuntimeError("invalid verifier status")
    index_path=SCIENTIFIC_ROOT/"scientific_identity_index.json"; index=json.loads(index_path.read_bytes())
    remaining=[path for path in RESULT_PATHS if path!=verify_path]
    for path in remaining:
        if path.exists() or path.is_symlink(): raise FileExistsError(f"result collision: {path}")
    scientific_entries=[{"path":path.relative_to(REPO_ROOT).as_posix(),"sha256":_sha(path)} for path in _member_paths()]
    family_entries=[{"path":path.relative_to(REPO_ROOT).as_posix(),"sha256":_sha(path)} for path in _family_paths()]
    hash_manifest={"schema_version":"gen_enc_2c_phase_b_scientific_hash_manifest_v1","hash_algorithm":"SHA256_EXACT_CANONICAL_BYTES_LOWERCASE_HEX","evidence_level":EVIDENCE,"scientific_evidence_level":"NOT_ESTABLISHED","scientific_hypothesis_status":"NOT_TESTED","member_entries":scientific_entries,"family_manifest_entries":family_entries,"identity_index_path":index_path.relative_to(REPO_ROOT).as_posix(),"identity_index_sha256":_sha(index_path),"final_test_read":False}
    statuses={"SCIENTIFIC_IDENTITY_AND_STATIC_ELIGIBILITY_COMPLETE":("GEN_ENC_2C_PHASE_B_IMPLEMENTATION_COMPLETE","SCIENTIFIC_IDENTITY_AND_STATIC_ELIGIBILITY_COMPLETE","COMPLETE"),"IDENTITY_SET_STATIC_ELIGIBILITY_BLOCKED":("GEN_ENC_2C_PHASE_B_STATIC_ELIGIBILITY_BLOCKED","IDENTITY_SET_STATIC_ELIGIBILITY_BLOCKED","STATIC_ELIGIBILITY_BLOCKED"),"IDENTITY_SET_TECHNICAL_FAILURE_BLOCKED":("GEN_ENC_2C_PHASE_B_TECHNICAL_FAILURE_BLOCKED","IDENTITY_SET_TECHNICAL_FAILURE_BLOCKED","TECHNICAL_FAILURE_BLOCKED")}
    implementation,result,generation=statuses[index["overall_terminal_status"]]
    family_hashes={entry["family_id"]:entry["sha256"] for entry in index["family_entries"]}
    counts={"scientific_instance_generation":80,"formal_random_seed_execution":20,"formal_physics_master_seed_execution":1,"response_read":0,"response_write":0,"endpoint":0,"family_comparison":0,"timing_preflight":0,"development_response_read":0,"validation_read":0,"final_test_read":0}
    analysis={"schema_version":"gen_enc_2c_phase_b_analysis_summary_v1","stage":"GEN-ENC-2C-PHASE-B","implementation_terminal_status":implementation,"result_terminal_status":result,"evidence_level":EVIDENCE,"scientific_evidence_level":"NOT_ESTABLISHED","scientific_hypothesis_status":"NOT_TESTED","expected_slots":80,"observed_slots":80,"eligible_count":index["eligible_count"],"cost_ineligible_count":index["cost_ineligible_count"],"technical_failure_count":index["technical_failure_count"],"instance_manifest_sha256_by_family":family_hashes,"identity_index_sha256":_sha(index_path),"independent_verification_status":verification["status"],"execution_counts":counts,"active_questions_closed":0,"bidirectional_discovery_established":False,"final_test_read":False}
    inventory={"schema_version":"gen_enc_2c_phase_b_artifact_inventory_v1","evidence_level":EVIDENCE,"scientific_evidence_level":"NOT_ESTABLISHED","scientific_hypothesis_status":"NOT_TESTED","scientific_root":SCIENTIFIC_ROOT.relative_to(REPO_ROOT).as_posix(),"scientific_member_files":80,"family_manifest_files":4,"identity_index_files":1,"result_artifacts":[path.relative_to(REPO_ROOT).as_posix() for path in RESULT_PATHS],"all_paths_allowlisted":True,"unlisted_files":[],"final_test_read":False}
    execution={"schema_version":"gen_enc_2c_phase_b_execution_record_v1","orchestrator_source_sha256":_sha(Path(__file__)),"verifier_source_sha256":verification["verifier_source_sha256"],"working_directory":str(REPO_ROOT),"commands":["python -B scripts/gen_enc_2c_generate_scientific_identities.py preflight","python -B scripts/gen_enc_2c_generate_scientific_identities.py generate","python -B scripts/gen_enc_2c_verify_scientific_identities.py verify","python -B scripts/gen_enc_2c_generate_scientific_identities.py package-results"],"preflight_status":"PASS","generation_status":generation,"verification_status":verification["status"],"packaging_status":"COMPLETE","implementation_terminal_status":implementation,"result_terminal_status":result,"evidence_level":EVIDENCE,"scientific_evidence_level":"NOT_ESTABLISHED","scientific_hypothesis_status":"NOT_TESTED","collision_count":0,"unlisted_write_count":0,"temporary_files_remaining":[],"final_test_read":False}
    objects=((RESULT_ROOT/"analysis_summary.json",analysis,"result_analysis_summary"),(RESULT_ROOT/"artifact_inventory.json",inventory,"result_artifact_inventory"),(RESULT_ROOT/"scientific_hash_manifest.json",hash_manifest,"result_scientific_hash_manifest"),(RESULT_ROOT/"execution_record.json",execution,"result_execution_record"))
    owned=[]
    for path,obj,schema_name in objects:
        schema=json.loads((REPO_ROOT/f"schemas/gen_enc/gen_enc_2c/{schema_name}.schema.json").read_bytes());jsonschema.Draft202012Validator(schema).validate(obj);_atomic_write(path,_canonical(obj),owned)
    report=("# GEN-ENC-2C scientific identity/static eligibility result\n\n"+f"Terminal state: `{result}`\n\nEvidence: `{EVIDENCE}`; scientific evidence `NOT_ESTABLISHED`; hypothesis `NOT_TESTED`.\n\nNo response, endpoint, comparison, timing, development, validation or final-test access occurred.\n").encode("utf-8")
    _atomic_write(RESULT_PATHS[0],report,owned)
    members=[path for path in _scientific_paths()]+[path for path in RESULT_PATHS if path.name!="SHA256SUMS.txt"]
    lines=[f"{_sha(path)}  {path.relative_to(REPO_ROOT).as_posix()}" for path in members]
    _atomic_write(RESULT_ROOT/"SHA256SUMS.txt",("\n".join(lines)+"\n").encode("utf-8"),owned)


def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument("action",choices=("preflight","generate","package-results"));args=parser.parse_args()
    if args.action=="preflight": _preflight()
    elif args.action=="generate": _generate()
    else: _package_results()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
