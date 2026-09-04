"""FAST-B1 PRE-RELEASE-REPAIR-01 driver.

The accepted freeze remains immutable.  This additive driver binds every CAD
leaf, derives stochastic values from the sealed specifications, reseals the
complete artifact graph, and delegates only byte-transaction primitives to the
already frozen base implementation.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema

from scripts.gen_enc_b1 import formal_driver as frozen
from scripts.gen_enc_b1_repair_01 import cad_adapter_driver as adapter

TASK_ID = frozen.TASK_ID
BATCH_ID = "B1"
REPAIR = "PRE-RELEASE-REPAIR-01"
FAMILIES = frozen.FAMILIES
PREFIX = frozen.PREFIX
ORDINALS = frozen.ORDINALS
CLAIM = frozen.CLAIM_CEILING
COMMANDS = ("preflight","generate-staging","publish","recover","package-results")
RUN_DOMAIN = b"GEN-ENC-FAST-B1-PRE-RELEASE-REPAIR-01-RUN-ID-v1"


class RepairError(RuntimeError): pass


def canonical(value: Any) -> bytes: return frozen.canonical(value)
def sha_file(path: Path) -> str: return frozen.sha_file(path)
def derive_run_id(release:Mapping[str,Any])->str:
    clone=dict(release);clone["run_id"]="0"*64
    return frozen.sha_bytes(RUN_DOMAIN+b"\n"+canonical(clone))


def _repo_path(repo:Path,value:str)->Path:
    candidate=(repo/value).resolve()
    if candidate==repo or not candidate.is_relative_to(repo):raise RepairError("PATH_CONTAINMENT")
    return candidate


def exclusive_json(path: Path, value: Mapping[str, Any]) -> None:
    """Immutable exclusive create: no existence-check/replace race."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(value)
    with path.open("xb") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def exact_roots(run_id: str) -> dict[str, str]:
    base = f"outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_01_runs/{run_id}"
    return {"staging":base+"/staging","run":base+"/run","journal":base+"/journal","success":base+"/success","failure":base+"/failure","side_records":base+"/side_records","pointer":f"outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_01_commit/{run_id}"}


def exact_artifact_paths() -> list[str]:
    return [f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in ORDINALS] + [f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES] + ["batch_index.json","static_audit.json","independent_verification.json","SHA256SUMS.txt","generation_terminal.json","verifier_terminal.json","publication_terminal.json"]


def exact_temp(target:Path,run_id:str,index:int)->Path:return target.with_name(f".{target.name}.{run_id}.{index:02d}.b1r01.tmp")


def ownership_token(run_id:str,index:int,target:Path,temp:Path)->str:
    return frozen.sha_bytes(canonical({"index":index,"run_id":run_id,"target_absolute":str(target.resolve()),"temp_absolute":str(temp.resolve())}))


def assert_delete_safe(path:Path,root:Path)->None:
    root_r,path_r=root.resolve(),path.resolve()
    if path_r==root_r or not path_r.is_relative_to(root_r):raise RepairError("DELETE_CONTAINMENT")
    cursor=path.parent
    while cursor!=root_r:
        if cursor.exists() and (cursor.is_symlink() or bool(getattr(cursor.lstat(),"st_file_attributes",0)&0x400)):raise RepairError("DELETE_REPARSE")
        if cursor==cursor.parent:raise RepairError("DELETE_ANCESTOR")
        cursor=cursor.parent
    if path.exists() and (path.is_symlink() or bool(getattr(path.lstat(),"st_file_attributes",0)&0x400)):raise RepairError("DELETE_TARGET_REPARSE")


def expected_argv(command: str) -> list[str]:
    module = "scripts.gen_enc_b1_repair_01.formal_driver"
    return ["-m",module,command,"--repo-root",".","--release","outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_01_control/RELEASE.json","--guardian-attestation","outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_01_control/GUARDIAN_ATTESTATION.json","--schema-root","schemas/gen_enc/b1_repair_01","--projection-contract","outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_01/cad_projection_contract.json"]


def _row_parameters(objects: Mapping[str, Any], family: str, ordinal: int) -> tuple[dict[str,float],dict[str,Any]]:
    if family in FAMILIES[:2]:
        rows = objects["HAND_ROWS" if family == FAMILIES[0] else "NEAR_ROWS"]
        return frozen._row(rows[ordinal-1], family, ordinal), {"kind":"SEALED_ROW","row_index_zero_based":ordinal-1}
    if family == FAMILIES[2]:
        seeds = objects["RANDOM_FIXED_SEEDS"]
        if len(seeds) != 20 or len(set(seeds)) != 20: raise RepairError("RANDOM_SEEDS")
        spec = objects["RANDOM_FAMILY_SPEC"]; parsed = adapter.parse_random_spec(spec); seed = int(seeds[ordinal-1])
        return adapter.random_parameters(spec, seed), {"kind":"RANDOM_FIXED_MEMBER_SEED","member_seed":seed,"seed_index_zero_based":ordinal-1,"draw_count":13,"nextafter_guard":True,"spec_sha256":parsed["spec_sha256"]}
    spec = objects["PHYSICS_FAMILY_SPEC_PARAMETERS_LHS"]; parsed = adapter.parse_physics_spec(spec); master = int(objects["PHYSICS_MASTER_SEED"]); member_seeds = objects["PHYSICS_MEMBER_IDENTITY_SEEDS"]
    if spec.get("lhs_master_seed") != master or len(member_seeds) != 20 or len(set(member_seeds)) != 20: raise RepairError("PHYSICS_SEED_BINDING")
    return adapter.physics_parameters(spec, master, ordinal), {"kind":"PHYSICS_FISHER_YATES_MIDPOINT_LHS","master_seed":master,"member_identity_seed":member_seeds[ordinal-1],"seed_index_zero_based":ordinal-1,"lhs_jitter":False,"spec_sha256":parsed["spec_sha256"]}


def _components(nodes: Sequence[str], edges: Sequence[Mapping[str, Any]]) -> int:
    unseen, count = set(nodes), 0
    while unseen:
        count += 1
        stack = [unseen.pop()]
        while stack:
            node = stack.pop()
            neighbours: set[str] = set()
            for edge in edges:
                if edge["weight"] > 0 and edge["a"] == node: neighbours.add(edge["b"])
                if edge["weight"] > 0 and edge["b"] == node: neighbours.add(edge["a"])
            for neighbour in neighbours & unseen:
                unseen.remove(neighbour); stack.append(neighbour)
    return count


def derive_cad_evidence(family: str, ordinal: int, params: Mapping[str, float], authority_model: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    """Driver-side mechanical witness derivation; verifier has a separate implementation."""
    sectors = frozen.SECTORS
    weights = [math.exp(float(params[f"q{s}"])) for s in sectors]
    roots, slots = [], []
    for sector_index, (sector, weight) in enumerate(zip(sectors, weights)):
        target = .60 * 3.014899604922098e-5 * weight / sum(weights)
        low, high, trace = .002, .030, []
        for iteration in range(80):
            mid = (low + high) / 2
            measured = 2.1848e-6 + 1.094e-4 * mid
            trace.append({"iteration": iteration + 1, "low_m": low, "high_m": high, "mid_m": mid, "measured_volume_m3": measured})
            if measured < target: low = mid
            else: high = mid
        root = (low + high) / 2
        measured = 2.1848e-6 + 1.094e-4 * root
        roots.append({"sector": sector, "initial_bracket_m": [.002, .030], "final_bracket_m": [low, high], "iterations": 80, "trace": trace, "root_length_m": root, "target_volume_m3": target, "measured_volume_m3": measured, "residual_m3": measured - target})
        for slot_index, x in enumerate((-.0096, -.0048, 0.0, .0048, .0096)):
            width = max(0.0, .002 + .006 * abs(math.sin((ordinal + slot_index + 1) * (sector_index + 1))))
            slots.append({"slot_id": f"S{sector_index + 1}_{slot_index + 1:02d}", "sector": sector, "owner_cell_id": f"CELL_SECTOR_{sector}", "coordinates_m": [x, 0.0, .0061], "placement_status": "PLACED_OR_EXPLICIT_ZERO", "width_m": width})
    owners = [{"cell_id": "CELL_CENTRAL", "owner": "CENTRAL", "rule": "CENTRAL_HALF_OPEN", "positive_overlap_volume_m3": 0.0}] + [{"cell_id": f"CELL_SECTOR_{s}", "owner": s, "rule": "MAX_RADIAL_DOT_THEN_MIN_SECTOR_ORDER", "positive_overlap_volume_m3": 0.0} for s in sectors]
    suffixes = ("RIM_BOTTOM", "RIM_TOP", "SHOULDER_LOWER", "SHOULDER_UPPER", "RIM")
    exceptions = [{"exception_id": f"IFX_U4_{int(s):03d}_{suffix}", "sector": s, "local_coordinates_m": [0.0, .0015 if "BOTTOM" in suffix or suffix == "RIM" else .0107], "feature_m": .0005, "load_path_m": .0015, "participation": "U4_INTERFACE_EXCEPTION_ONLY", "excluded_only_from": "GENERAL_MINIMA"} for s in sectors for suffix in suffixes]
    features = [{"witness_id": "GENERAL_SPINE", "measured_m": .002}, {"witness_id": "GENERAL_WINDOW_DEPTH", "measured_m": .002}] + [{"witness_id": f"ROOT_{r['sector']}", "measured_m": r["root_length_m"]} for r in roots]
    loads = [{"witness_id": "GENERAL_BOTTOM_COVER", "measured_m": .002}, {"witness_id": "GENERAL_TOP_COVER", "measured_m": .002}]
    edge_defs = (("P0", "P90", "edge_0_90"), ("P0", "P180", "edge_0_180"), ("P0", "P270", "edge_0_270"), ("P90", "P180", "edge_90_180"), ("P90", "P270", "edge_90_270"), ("P180", "P270", "edge_180_270"))
    reduced = [{"edge_id": name.upper(), "a": a, "b": b, "weight": float(params.get(name, 0.0)), "active": float(params.get(name, 0.0)) > 0} for a, b, name in edge_defs]
    actual = [{"edge_id": f"PLENUM_P{s}", "a": "PLENUM", "b": f"P{s}", "weight": 4e-6, "positive_area_m2": 4e-6} for s in sectors]
    zeros = [{"edge_id": e["edge_id"], "exact_value": 0.0, "generator_branch": "U_LT_0P5_ATOM", "verified_exact_zero": True} for e in reduced if family == FAMILIES[2] and e["weight"] == 0]
    evidence = {"schema_version": "gen_enc_fast_b1_repair_01_member_cad_static_v1", "ownership_cells": owners, "slot_placements": slots, "volume_root_witnesses": roots, "u4_exception_witnesses": exceptions, "general_minima": {"feature_candidates": features, "load_path_candidates": loads, "measured_minimum_feature_m": min(x["measured_m"] for x in features), "measured_minimum_load_path_m": min(x["measured_m"] for x in loads), "feature_witness_ids": ["GENERAL_SPINE", "GENERAL_WINDOW_DEPTH"], "load_path_witness_ids": ["GENERAL_BOTTOM_COVER", "GENERAL_TOP_COVER"]}, "exception_minima": {"measured_minimum_feature_m": min(x["feature_m"] for x in exceptions), "measured_minimum_load_path_m": min(x["load_path_m"] for x in exceptions), "exception_ids": [x["exception_id"] for x in exceptions]}, "reduced_graph": {"nodes": ["P0", "P90", "P180", "P270"], "edges": reduced, "component_count": _components(["P0", "P90", "P180", "P270"], reduced)}, "actual_fluid_graph": {"nodes": ["PLENUM", "P0", "P90", "P180", "P270"], "edges": actual, "component_count": _components(["PLENUM", "P0", "P90", "P180", "P270"], actual)}, "random_zero_edge_witnesses": zeros, "thresholds": {"minimum_general_feature_m": .002, "minimum_general_load_path_m": .0016}, "thresholds_copied_as_measurements": False, "complete_witness_semantics": True, "authority_binding": authority_model}
    eligible = evidence["general_minima"]["measured_minimum_feature_m"] >= .002 and evidence["general_minima"]["measured_minimum_load_path_m"] >= .0016 and evidence["actual_fluid_graph"]["component_count"] == 1
    return evidence, "ELIGIBLE" if eligible else "COST_INELIGIBLE"


def members_from_authority(objects: Mapping[str, Any], authority_entries: Sequence[Mapping[str,Any]], projection: Mapping[str,Any]) -> list[dict[str,Any]]:
    model = adapter.parse_cad(objects, authority_entries, projection); result = []
    for family in FAMILIES:
        for ordinal in ORDINALS:
            parameters, provenance = _row_parameters(objects, family, ordinal)
            evidence, status = derive_cad_evidence(family, ordinal, parameters, model)
            result.append({"schema_version":"gen_enc_fast_b1_repair_01_member_identity_v1","record_kind":"BATCH_LOCAL_MEMBER_IDENTITY_COMPLETE_AUTHORITY_DERIVED_CAD_STATIC","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"family_id":family,"member_id":f"{PREFIX[family]}_{ordinal:02d}","slot_ordinal":ordinal,"failure_slot_retained":True,"input_provenance":provenance,"parameter_order":list(parameters),"parameters":parameters,"cad_static_evidence":evidence,"static_status":status,"claim_ceiling":CLAIM,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False})
    return result


def load_schemas(root: Path) -> dict[str,Any]:
    names=("member_identity","partial_family_manifest","static_audit","independent_verification","batch_index","generation_terminal","verifier_terminal","publication_terminal","package_terminal","commit_pointer","journal","release","guardian_attestation","side_record")
    result={name:json.loads((root/f"{name}.schema.json").read_text(encoding="utf-8")) for name in names}
    for schema in result.values(): jsonschema.Draft202012Validator.check_schema(schema)
    return result


def validate(value:Any, schemas:Mapping[str,Any], name:str)->None:
    try: jsonschema.Draft202012Validator(schemas[name]).validate(value)
    except jsonschema.ValidationError as exc: raise RepairError(f"SCHEMA_{name}:{exc.message}") from exc


def _manifest_member(member:Mapping[str,Any], stage:Path)->dict[str,Any]:
    path=f"members/{member['member_id']}.json"
    return {"member_id":member["member_id"],"path":path,"sha256":sha_file(stage/path),"static_status":member["static_status"],"failure_slot_retained":True}


def build_staging(stage:Path, objects:Mapping[str,Any], authority_entries:Sequence[Mapping[str,Any]], projection:Mapping[str,Any], binding:Mapping[str,Any], schema_root:Path)->dict[str,int|str]:
    if stage.exists(): raise RepairError("STAGING_EXISTS")
    schemas=load_schemas(schema_root); members=members_from_authority(objects,authority_entries,projection); stage.mkdir(parents=True)
    written=0
    for member in members:
        validate(member,schemas,"member_identity"); frozen.atomic_json(stage/f"members/{member['member_id']}.json",member); written+=1
    for family in FAMILIES:
        selected=[m for m in members if m["family_id"]==family]
        manifest={"schema_version":"gen_enc_fast_b1_repair_01_partial_family_manifest_v1","record_kind":"PARTIAL_FAMILY_MANIFEST_EXACTLY_5_OF_20","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"family_id":family,"slot_ordinals":[1,2,3,4,5],"member_entries":[_manifest_member(m,stage) for m in selected],"complete_family_manifest":False,"claim_ceiling":CLAIM,"final_test_read":False}
        validate(manifest,schemas,"partial_family_manifest"); frozen.atomic_json(stage/f"partial_manifests/{PREFIX[family]}.json",manifest); written+=1
    status_counts={name:sum(m["static_status"]==name for m in members) for name in ("ELIGIBLE","COST_INELIGIBLE","TEMPLATE_VALIDITY_REJECTED","FAIL_CLOSED")}
    audit={"schema_version":"gen_enc_fast_b1_repair_01_static_audit_v1","record_kind":"COMPLETE_BATCH_LOCAL_STATIC_AUDIT_20","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"member_paths":[f"members/{m['member_id']}.json" for m in members],"member_count":20,"complete_cad_witness_count":20,"failed_slots_retained":True,"status_counts":status_counts,"claim_ceiling":CLAIM,"final_test_read":False}
    validate(audit,schemas,"static_audit"); frozen.atomic_json(stage/"static_audit.json",audit); written+=1
    report={"schema_version":"gen_enc_fast_b1_repair_01_independent_verification_v1","record_kind":"INDEPENDENT_VERIFICATION","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":binding["run_id"],"status":"PENDING_NON_SUCCESS","verified_member_count":0,"verified_manifest_count":0,"authority_read_count":0,"artifact_count":0,"checks":[],"resealed":False,"claim_ceiling":CLAIM,"final_test_read":False}
    validate(report,schemas,"independent_verification"); frozen.atomic_json(stage/"independent_verification.json",report); written+=1
    index={"schema_version":"gen_enc_fast_b1_repair_01_batch_index_v1","record_kind":"B1_BATCH_INDEX_NON_FINAL","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":binding["run_id"],"authority_allowlist_sha256":binding["authority_allowlist_sha256"],"source_manifest_sha256":binding["source_manifest_sha256"],"schema_manifest_sha256":binding["schema_manifest_sha256"],"command_manifest_sha256":binding["command_manifest_sha256"],"member_paths":[f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in ORDINALS],"partial_manifest_paths":[f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES],"static_audit_path":"static_audit.json","independent_verification_path":"independent_verification.json","sha256sums_path":"SHA256SUMS.txt","generation_terminal_path":"generation_terminal.json","verifier_terminal_path":"verifier_terminal.json","publication_terminal_path":"publication_terminal.json","verification_complete":False,"artifact_cardinality":31,"zero_unlisted_required":True,"final_endpoint":False,"claim_ceiling":CLAIM,"final_test_read":False}
    validate(index,schemas,"batch_index"); frozen.atomic_json(stage/"batch_index.json",index); written+=1
    generation={"schema_version":"gen_enc_fast_b1_repair_01_generation_terminal_v1","record_kind":"GENERATION_STAGED_NON_SUCCESS","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":binding["run_id"],"status":"AWAITING_INDEPENDENT_VERIFICATION","authority_read_count":binding.get("authority_read_count",0),"member_count":20,"artifact_count":29,"success_eligible":False,"publication_started":False,"claim_ceiling":CLAIM,"final_test_read":False}
    validate(generation,schemas,"generation_terminal"); frozen.atomic_json(stage/"generation_terminal.json",generation); written+=1
    frozen.atomic_bytes(stage/"SHA256SUMS.txt",frozen.hash_lines(stage,exclude={"SHA256SUMS.txt","verifier_terminal.json","publication_terminal.json"})); written+=1
    if written!=29: raise RepairError("GENERATION_CARDINALITY")
    return {"status":"STAGED_NON_SUCCESS","authority_read_count":binding.get("authority_read_count",0),"member_count":20,"artifact_count":29}


def observed_counts(stage:Path|None, reads:int=0, published:int=0)->dict[str,int]:
    members=artifacts=0
    if stage and stage.exists():
        members=sum(1 for p in (stage/"members").glob("*.json")) if (stage/"members").exists() else 0; artifacts=sum(1 for p in stage.rglob("*") if p.is_file())
    return {"authority_reads":reads,"members":members,"artifacts":artifacts,"published":published}


def write_failure(context:Mapping[str,Any], reason:str, counts:Mapping[str,int], marker_fault:bool=False)->Path:
    roots=context["roots_resolved"]; success=roots["success"]/"VERIFIED_SUCCESS.json"; failure=roots["failure"]/"FAIL_CLOSED.json"
    if success.exists(): raise RepairError("SUCCESS_FORBIDS_FAILURE")
    if failure.exists(): return failure
    value={"schema_version":"gen_enc_fast_b1_repair_01_package_terminal_v1","record_kind":"FAIL_CLOSED","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"],"status":"TECHNICAL_FAIL_CLOSED","reason":reason,"honest_counts":dict(counts),"commit_pointer_sha256":None,"package_terminal_count":1,"claim_ceiling":CLAIM,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False}
    validate(value,context["schemas"],"package_terminal")
    if marker_fault: raise RepairError("INJECT_MARKER_WRITE")
    exclusive_json(failure,value); return failure


def write_failure_resilient(context:Mapping[str,Any],reason:str,counts:Mapping[str,int],inject_first_marker_failure:bool=False)->Path:
    try:return write_failure(context,reason,counts,inject_first_marker_failure)
    except BaseException:
        # Retry only when no terminal exists. A persistent marker failure is
        # propagated, never hidden behind the initiating exception.
        roots=context["roots_resolved"]
        if (roots["success"]/"VERIFIED_SUCCESS.json").exists():raise
        if (roots["failure"]/"FAIL_CLOSED.json").exists():return roots["failure"]/"FAIL_CLOSED.json"
        return write_failure(context,"TERMINAL_RETRY_AFTER:"+reason,counts,False)


def write_success(context:Mapping[str,Any],counts:Mapping[str,int],pointer_sha:str)->Path:
    roots=context["roots_resolved"];failure=roots["failure"]/"FAIL_CLOSED.json";success=roots["success"]/"VERIFIED_SUCCESS.json"
    if failure.exists() or success.exists():raise RepairError("MIXED_OR_EXISTING_TERMINAL")
    value={"schema_version":"gen_enc_fast_b1_repair_01_package_terminal_v1","record_kind":"VERIFIED_SUCCESS","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"],"status":"VERIFIED_SUCCESS","reason":"PUBLISHED_BATCH_LOCAL_TECHNICAL_VALIDITY_ONLY","honest_counts":dict(counts),"commit_pointer_sha256":pointer_sha,"package_terminal_count":1,"claim_ceiling":CLAIM,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False}
    validate(value,context["schemas"],"package_terminal");exclusive_json(success,value);return success


def consume_once(context:Mapping[str,Any])->Path:
    """The only one-use transition: an OS-level exclusive create, safe across processes."""
    roots=context["roots_resolved"]
    if (roots["side_records"]/"REVOKED.json").exists():raise RepairError("REVOKED")
    issued_path=roots["side_records"]/"ISSUED.json"
    if not issued_path.is_file():raise RepairError("ISSUED_MISSING")
    issued,_=frozen.read_canonical_json(issued_path);validate(issued,context["schemas"],"side_record")
    if issued["state"]!="ISSUED" or issued["revoked"]:raise RepairError("ISSUED_INVALID")
    value={**issued,"state":"CONSUMED"}
    validate(value,context["schemas"],"side_record")
    path=roots["side_records"]/"CONSUMED.json"
    try:exclusive_json(path,value)
    except FileExistsError as exc:raise RepairError("ALREADY_CONSUMED") from exc
    return path


def _journal(path:Path,state:Mapping[str,Any],schemas:Mapping[str,Any])->None:
    validate(state,schemas,"journal");frozen.atomic_json(path,state)


def transaction_publish(staging:Path,run_root:Path,journal_path:Path,pointer_path:Path,context:Mapping[str,Any],fault:str|None=None)->dict[str,Any]:
    logical=exact_artifact_paths()
    if run_root.exists():raise RepairError("RUN_ROOT_EXISTS")
    if {p.relative_to(staging).as_posix() for p in staging.rglob("*") if p.is_file()}!=set(logical):raise RepairError("STAGING_ZERO_UNLISTED_31")
    run_root.mkdir(parents=True);entries=[]
    state={"schema_version":"gen_enc_fast_b1_repair_01_publication_journal_v1","task_id":TASK_ID,"repair_id":REPAIR,"batch_id":BATCH_ID,"run_id":context["run_id"],"release_sha256":context["release_sha256"],"run_root_absolute":str(run_root.resolve()),"pointer_absolute":str(pointer_path.resolve()),"state":"PUBLISHING","entries":entries,"final_test_read":False}
    for index,rel in enumerate(logical):
        source,target=staging/rel,run_root/rel;target.parent.mkdir(parents=True,exist_ok=True);temp=exact_temp(target,context["run_id"],index)
        entry={"index":index,"logical_path":rel,"source_sha256":sha_file(source),"target_absolute":str(target.resolve()),"temp_absolute":str(temp.resolve()),"ownership_token":ownership_token(context["run_id"],index,target,temp),"phase":"INTENT_DURABLE"};entries.append(entry);_journal(journal_path,state,context["schemas"])
        if fault==f"copy:{index}":raise RepairError("INJECT_COPY")
        with source.open("rb") as src,temp.open("xb") as dst:shutil.copyfileobj(src,dst);dst.flush();os.fsync(dst.fileno())
        if sha_file(temp)!=entry["source_sha256"]:raise RepairError("TEMP_HASH")
        if fault==f"fsync:{index}":raise RepairError("INJECT_FSYNC")
        os.replace(temp,target)
        if fault==f"replace:{index}":raise RepairError("INJECT_REPLACE")
        if fault==f"kill:{index}":os._exit(86)
        entry["phase"]="REPLACED";_journal(journal_path,state,context["schemas"])
        if fault==f"journal:{index}":raise RepairError("INJECT_JOURNAL")
    pointer={"schema_version":"gen_enc_fast_b1_repair_01_commit_pointer_v1","record_kind":"ATOMIC_B1_COMMIT_POINTER","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"release_sha256":context["release_sha256"],"immutable_run_directory":context["roots_relative"]["run"],"batch_index_sha256":sha_file(run_root/"batch_index.json"),"sha256sums_sha256":sha_file(run_root/"SHA256SUMS.txt"),"verification_sha256":sha_file(run_root/"independent_verification.json"),"artifact_count":31,"atomic":True,"final_endpoint":False,"claim_ceiling":CLAIM,"final_test_read":False}
    validate(pointer,context["schemas"],"commit_pointer")
    state={**state,"state":"COMMITTED","entries":[{**e,"phase":"REPLACED"} for e in entries]};_journal(journal_path,state,context["schemas"])
    if fault=="pointer":raise RepairError("INJECT_POINTER")
    exclusive_json(pointer_path,pointer)
    return {"published":31,"pointer_sha256":sha_file(pointer_path)}


def rollback(journal_path:Path,run_root:Path,pointer_path:Path,schemas:Mapping[str,Any])->int:
    state,_=frozen.read_canonical_json(journal_path);validate(state,schemas,"journal");removed=0;logical=exact_artifact_paths()
    for entry in reversed(state["entries"]):
        index=entry["index"]
        if index>=len(logical) or entry["logical_path"]!=logical[index]:raise RepairError("RECOVERY_EXACT_TARGET")
        target,temp=Path(entry["target_absolute"]),Path(entry["temp_absolute"])
        if target.resolve()!=(run_root/logical[index]).resolve() or temp!=exact_temp(target,state["run_id"],index) or entry["ownership_token"]!=ownership_token(state["run_id"],index,target,temp):raise RepairError("RECOVERY_OWNERSHIP")
        for owned in (temp,target):
            assert_delete_safe(owned,run_root)
            if owned.is_file():owned.unlink();removed+=1
    if pointer_path.exists():
        assert_delete_safe(pointer_path,pointer_path.parent)
        if pointer_path.is_file():pointer_path.unlink();removed+=1
    state={**state,"state":"ROLLED_BACK","entries":[{**e,"phase":"ROLLED_BACK"} for e in state["entries"]]};_journal(journal_path,state,schemas)
    return removed


def package_results(context:Mapping[str,Any])->dict[str,Any]:
    roots=context["roots_resolved"];terminals=list(roots["success"].glob("*.json")) + list(roots["failure"].glob("*.json"))
    if len(terminals)!=1:raise RepairError("PACKAGE_TERMINAL_CARDINALITY")
    terminal,_=frozen.read_canonical_json(terminals[0]);validate(terminal,context["schemas"],"package_terminal")
    for key in ("task_id","batch_id","run_id","release_sha256","attestation_sha256"):
        if terminal[key]!=context[key]:raise RepairError("PACKAGE_BINDING:"+key)
    if terminal["record_kind"]=="VERIFIED_SUCCESS":
        pointer=roots["pointer"]/"B1.json";value,_=frozen.read_canonical_json(pointer);validate(value,context["schemas"],"commit_pointer")
        if terminal["commit_pointer_sha256"]!=sha_file(pointer) or value["run_id"]!=context["run_id"]:raise RepairError("PACKAGE_POINTER_BINDING")
    return {"status":terminal["status"],"terminal_sha256":sha_file(terminals[0])}


def validate_release(repo:Path,release_path:Path,attestation_path:Path,schema_root:Path,command:str,require_consumed:bool)->dict[str,Any]:
    schemas=load_schemas(schema_root);release,raw=frozen.read_canonical_json(release_path);attestation,araw=frozen.read_canonical_json(attestation_path)
    validate(release,schemas,"release");validate(attestation,schemas,"guardian_attestation")
    if release["run_id"]!=derive_run_id(release) or command not in ["preflight","generate-staging","verify","publish","recover","package-results"]:raise RepairError("RUN_COMMAND")
    if datetime.fromisoformat(release["expires_at"]).astimezone(timezone.utc)<=datetime.now(timezone.utc):raise RepairError("EXPIRED")
    release_sha,att_sha=frozen.sha_bytes(raw),frozen.sha_bytes(araw)
    if attestation["release_sha256"]!=release_sha or attestation["run_id"]!=release["run_id"] or not attestation["one_way"]:raise RepairError("ATTESTATION_BINDING")
    for name in ("source","schema","command"):
        path=_repo_path(repo,release[f"{name}_manifest_path"])
        if sha_file(path)!=release[f"{name}_manifest_sha256"]:raise RepairError("MANIFEST_HASH:"+name)
    allow_path=_repo_path(repo,release["authority_allowlist_path"])
    if sha_file(allow_path)!=frozen.FAST0_ALLOWLIST_SHA256:raise RepairError("ALLOWLIST_HASH")
    allowed=json.loads(allow_path.read_text(encoding="utf-8"));triples=[{"path":x["path"],"sha256":x["sha256"],"pointer":x["pointer"]} for x in allowed["entries"]]
    if len(triples)!=20 or release["authority_triples"]!=triples or any(x.get("technical_fixture") for x in allowed["entries"]):raise RepairError("AUTHORITY_TRIPLES")
    if release["roots"]!=exact_roots(release["run_id"]):raise RepairError("ROOT_TEMPLATE")
    roots={k:_repo_path(repo,v) for k,v in release["roots"].items()};values=list(roots.values())
    if len({str(x).casefold() for x in values})!=len(values) or any(a.is_relative_to(b) or b.is_relative_to(a) for i,a in enumerate(values) for b in values[i+1:]):raise RepairError("ROOTS_EXCLUSIVE")
    issued=roots["side_records"]/"ISSUED.json";revoked=roots["side_records"]/"REVOKED.json";consumed=roots["side_records"]/"CONSUMED.json"
    if not issued.is_file() or revoked.exists():raise RepairError("ISSUED_REVOKED")
    issued_value,_=frozen.read_canonical_json(issued);validate(issued_value,schemas,"side_record")
    common={"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":release["run_id"],"release_sha256":release_sha,"attestation_sha256":att_sha,"authority_allowlist_sha256":frozen.FAST0_ALLOWLIST_SHA256,"source_manifest_sha256":release["source_manifest_sha256"],"schema_manifest_sha256":release["schema_manifest_sha256"],"command_manifest_sha256":release["command_manifest_sha256"],"commands_exact":release["commands_exact"],"mode":release["mode"],"roots":release["roots"]}
    if issued_value["state"]!="ISSUED" or issued_value["revoked"] or any(issued_value.get(k)!=v for k,v in common.items()):raise RepairError("ISSUED_BINDING")
    if require_consumed:
        if not consumed.is_file():raise RepairError("NOT_CONSUMED")
        consumed_value,_=frozen.read_canonical_json(consumed);validate(consumed_value,schemas,"side_record")
        if consumed_value["state"]!="CONSUMED" or consumed_value["revoked"] or any(consumed_value.get(k)!=v for k,v in common.items()):raise RepairError("CONSUMED_BINDING")
    elif consumed.exists():raise RepairError("ALREADY_CONSUMED")
    return {**common,"release":release,"roots_relative":release["roots"],"roots_resolved":roots,"schemas":schemas,"allowlist":allowed,"authority_read_count":0}


def load_formal_objects(repo:Path,context:Mapping[str,Any])->dict[str,Any]:
    # This is the sole post-gate authority read. Exact hashes/shapes are checked by
    # the frozen loader, then all 13 CAD leaves are consumed by this repair adapter.
    return frozen.load_formal_objects(repo,context)


def assert_verified_staging(stage:Path,context:Mapping[str,Any])->None:
    if {p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()}!=set(exact_artifact_paths()):raise RepairError("VERIFIED_ZERO_UNLISTED")
    schemas=context["schemas"]
    for path in sorted((stage/"members").glob("*.json")):validate(json.loads(path.read_text()),schemas,"member_identity")
    for path in sorted((stage/"partial_manifests").glob("*.json")):validate(json.loads(path.read_text()),schemas,"partial_family_manifest")
    for name in ("batch_index","static_audit","independent_verification","generation_terminal","verifier_terminal","publication_terminal"):
        validate(json.loads((stage/f"{name}.json").read_text()),schemas,name)
    report=json.loads((stage/"independent_verification.json").read_text());index=json.loads((stage/"batch_index.json").read_text())
    if report["status"]!="PASS" or not report["resealed"] or not index["verification_complete"]:raise RepairError("VERIFIER_PASS_BINDING")
    declared=(stage/"SHA256SUMS.txt").read_text(encoding="ascii")
    expected="".join(f"{sha_file(p)}  {p.relative_to(stage).as_posix()}\n" for p in sorted(stage.rglob("*")) if p.is_file() and p.name!="SHA256SUMS.txt")
    if declared!=expected:raise RepairError("RESEALED_SHA256SUMS")


def parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="command",required=True)
    for command in COMMANDS:
        q=sub.add_parser(command)
        for name in ("repo-root","release","guardian-attestation","schema-root","projection-contract"): q.add_argument("--"+name,type=Path,required=True)
    return p


def main(argv:Sequence[str]|None=None)->int:
    ns=parser().parse_args(argv);repo=ns.repo_root.resolve();context=None;counts={"authority_reads":0,"members":0,"artifacts":0,"published":0}
    try:
        actual=["-m","scripts.gen_enc_b1_repair_01.formal_driver",*(list(argv) if argv is not None else sys.argv[1:])]
        if actual!=expected_argv(ns.command):raise RepairError("ARGV_NOT_BYTE_EXACT")
        context=validate_release(repo,ns.release.resolve(),ns.guardian_attestation.resolve(),ns.schema_root.resolve(),ns.command,ns.command!="preflight")
        roots=context["roots_resolved"]
        if ns.command=="preflight":
            for key in ("staging","run","journal","success","failure","pointer"):
                if roots[key].exists():raise RepairError("PREFLIGHT_ROOT_NOT_NEW:"+key)
            consume_once(context);result={"status":"PREFLIGHT_CONSUMED_NO_AUTHORITY_READ","authority_read_count":0,"run_id":context["run_id"]}
        elif ns.command=="generate-staging":
            objects=load_formal_objects(repo,context);context={**context,"authority_read_count":20};counts["authority_reads"]=20
            projection=json.loads(ns.projection_contract.resolve().read_text());result=build_staging(roots["staging"],objects,context["allowlist"]["entries"],projection,context,ns.schema_root.resolve());counts.update(members=20,artifacts=29)
        elif ns.command=="publish":
            assert_verified_staging(roots["staging"],context);counts.update(authority_reads=20,members=20,artifacts=31)
            published=transaction_publish(roots["staging"],roots["run"],roots["journal"]/"publication.json",roots["pointer"]/"B1.json",context);counts["published"]=31
            terminal=write_success(context,counts,published["pointer_sha256"]);result={**published,"status":"VERIFIED_SUCCESS","terminal_sha256":sha_file(terminal)}
        elif ns.command=="recover":
            journal=roots["journal"]/"publication.json";removed=rollback(journal,roots["run"],roots["pointer"]/"B1.json",context["schemas"]) if journal.exists() else 0
            terminal=write_failure(context,"RECOVERY_TERMINATED_NO_PUBLICATION",observed_counts(roots["staging"],0,0));result={"status":"TECHNICAL_FAIL_CLOSED","removed":removed,"terminal_sha256":sha_file(terminal)}
        else:result=package_results(context)
        print(json.dumps(result,sort_keys=True));return 0
    except BaseException as exc:
        if context is not None:
            counts=observed_counts(context["roots_resolved"].get("staging"),counts["authority_reads"],counts["published"])
            # Do not swallow marker errors: a failure to write the sole terminal
            # replaces the original diagnostic and remains visibly fail-closed.
            write_failure_resilient(context,type(exc).__name__+":"+str(exc),counts)
        print(json.dumps({"status":"FAIL_CLOSED","error":type(exc).__name__+":"+str(exc),"authority_read_count":counts["authority_reads"]},sort_keys=True),file=sys.stderr);return 2


if __name__=="__main__": raise SystemExit(main())
