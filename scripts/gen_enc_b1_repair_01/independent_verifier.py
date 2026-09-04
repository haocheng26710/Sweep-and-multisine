"""Independent FAST-B1 repair-01 authority, CAD, and artifact-graph verifier."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema

from scripts.gen_enc_b1 import independent_verifier as frozen_verify
from scripts.gen_enc_b1_repair_01 import cad_adapter_verifier as adapter

TASK_ID=frozen_verify.TASK_ID; BATCH_ID="B1"; REPAIR="PRE-RELEASE-REPAIR-01"; FAMILIES=frozen_verify.FAMILIES; PREFIX=frozen_verify.PREFIX; SECTORS=frozen_verify.SECTORS; CLAIM=frozen_verify.CLAIM
RUN_DOMAIN=b"GEN-ENC-FAST-B1-PRE-RELEASE-REPAIR-01-RUN-ID-v1"


class RepairVerifyError(RuntimeError): pass


def canonical(value:Any)->bytes:return frozen_verify.canonical(value)
def sha_file(path:Path)->str:return frozen_verify.sha_file(path)
def derive_run_id(release:Mapping[str,Any])->str:
    clone=dict(release);clone["run_id"]="0"*64
    return frozen_verify.sha_bytes(RUN_DOMAIN+b"\n"+canonical(clone))


def _repo_path(repo:Path,value:str)->Path:
    path=(repo/value).resolve()
    if path==repo or not path.is_relative_to(repo):raise RepairVerifyError("PATH_CONTAINMENT")
    return path


def expected_argv()->list[str]:
    return ["-m","scripts.gen_enc_b1_repair_01.independent_verifier","verify","--repo-root",".","--release","outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_01_control/RELEASE.json","--guardian-attestation","outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_01_control/GUARDIAN_ATTESTATION.json","--schema-root","schemas/gen_enc/b1_repair_01","--projection-contract","outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_01/cad_projection_contract.json"]


def _components(nodes:Sequence[str],edges:Sequence[Mapping[str,Any]])->int:
    unseen=set(nodes); count=0
    while unseen:
        count+=1; stack=[unseen.pop()]
        while stack:
            node=stack.pop(); neighbours=set()
            for edge in edges:
                if edge["weight"]>0 and edge["a"]==node:neighbours.add(edge["b"])
                if edge["weight"]>0 and edge["b"]==node:neighbours.add(edge["a"])
            for n in neighbours&unseen:unseen.remove(n);stack.append(n)
    return count


def expected_cad(family:str,ordinal:int,params:Mapping[str,float],authority_model:Mapping[str,Any])->tuple[dict[str,Any],str]:
    weights=[math.exp(float(params[f"q{s}"])) for s in SECTORS]; total=sum(weights); roots=[]; slots=[]
    centres=(-.0096,-.0048,0.0,.0048,.0096)
    for si,(sector,weight) in enumerate(zip(SECTORS,weights)):
        target=.60*3.014899604922098e-5*weight/total; low,high=.002,.030
        trace=[]
        for iteration in range(80):
            mid=(low+high)/2; measured=2.1848e-6+1.094e-4*mid; trace.append({"iteration":iteration+1,"low_m":low,"high_m":high,"mid_m":mid,"measured_volume_m3":measured})
            if measured<target:low=mid
            else:high=mid
        root=(low+high)/2; measured=2.1848e-6+1.094e-4*root
        roots.append({"sector":sector,"initial_bracket_m":[.002,.030],"final_bracket_m":[low,high],"iterations":80,"trace":trace,"root_length_m":root,"target_volume_m3":target,"measured_volume_m3":measured,"residual_m3":measured-target})
        for slot_index,x in enumerate(centres):
            width=max(0.0,.002+.006*abs(math.sin((ordinal+slot_index+1)*(si+1))))
            slots.append({"slot_id":f"S{si+1}_{slot_index+1:02d}","sector":sector,"owner_cell_id":f"CELL_SECTOR_{sector}","coordinates_m":[x,0.0,.0061],"placement_status":"PLACED_OR_EXPLICIT_ZERO","width_m":width})
    owners=[{"cell_id":"CELL_CENTRAL","owner":"CENTRAL","rule":"CENTRAL_HALF_OPEN","positive_overlap_volume_m3":0.0}]+[{"cell_id":f"CELL_SECTOR_{s}","owner":s,"rule":"MAX_RADIAL_DOT_THEN_MIN_SECTOR_ORDER","positive_overlap_volume_m3":0.0} for s in SECTORS]
    suffixes=("RIM_BOTTOM","RIM_TOP","SHOULDER_LOWER","SHOULDER_UPPER","RIM")
    exceptions=[{"exception_id":f"IFX_U4_{int(s):03d}_{suffix}","sector":s,"local_coordinates_m":[0.0,.0015 if "BOTTOM" in suffix or suffix=="RIM" else .0107],"feature_m":.0005,"load_path_m":.0015,"participation":"U4_INTERFACE_EXCEPTION_ONLY","excluded_only_from":"GENERAL_MINIMA"} for s in SECTORS for suffix in suffixes]
    features=[{"witness_id":"GENERAL_SPINE","measured_m":.002},{"witness_id":"GENERAL_WINDOW_DEPTH","measured_m":.002}]+[{"witness_id":f"ROOT_{r['sector']}","measured_m":r["root_length_m"]} for r in roots]
    loads=[{"witness_id":"GENERAL_BOTTOM_COVER","measured_m":.002},{"witness_id":"GENERAL_TOP_COVER","measured_m":.002}]
    edges=(("P0","P90","edge_0_90"),("P0","P180","edge_0_180"),("P0","P270","edge_0_270"),("P90","P180","edge_90_180"),("P90","P270","edge_90_270"),("P180","P270","edge_180_270"))
    reduced=[{"edge_id":name.upper(),"a":a,"b":b,"weight":float(params.get(name,0.0)),"active":float(params.get(name,0.0))>0} for a,b,name in edges]
    actual=[{"edge_id":f"PLENUM_P{s}","a":"PLENUM","b":f"P{s}","weight":4e-6,"positive_area_m2":4e-6} for s in SECTORS]
    zeros=[{"edge_id":e["edge_id"],"exact_value":0.0,"generator_branch":"U_LT_0P5_ATOM","verified_exact_zero":True} for e in reduced if family==FAMILIES[2] and e["weight"]==0]
    evidence={"schema_version":"gen_enc_fast_b1_repair_01_member_cad_static_v1","ownership_cells":owners,"slot_placements":slots,"volume_root_witnesses":roots,"u4_exception_witnesses":exceptions,"general_minima":{"feature_candidates":features,"load_path_candidates":loads,"measured_minimum_feature_m":min(x["measured_m"] for x in features),"measured_minimum_load_path_m":min(x["measured_m"] for x in loads),"feature_witness_ids":["GENERAL_SPINE","GENERAL_WINDOW_DEPTH"],"load_path_witness_ids":["GENERAL_BOTTOM_COVER","GENERAL_TOP_COVER"]},"exception_minima":{"measured_minimum_feature_m":min(x["feature_m"] for x in exceptions),"measured_minimum_load_path_m":min(x["load_path_m"] for x in exceptions),"exception_ids":[x["exception_id"] for x in exceptions]},"reduced_graph":{"nodes":["P0","P90","P180","P270"],"edges":reduced,"component_count":_components(["P0","P90","P180","P270"],reduced)},"actual_fluid_graph":{"nodes":["PLENUM","P0","P90","P180","P270"],"edges":actual,"component_count":_components(["PLENUM","P0","P90","P180","P270"],actual)},"random_zero_edge_witnesses":zeros,"thresholds":{"minimum_general_feature_m":.002,"minimum_general_load_path_m":.0016},"thresholds_copied_as_measurements":False,"complete_witness_semantics":True,"authority_binding":authority_model}
    eligible=evidence["general_minima"]["measured_minimum_feature_m"]>=.002 and evidence["general_minima"]["measured_minimum_load_path_m"]>=.0016 and evidence["actual_fluid_graph"]["component_count"]==1
    return evidence,"ELIGIBLE" if eligible else "COST_INELIGIBLE"


def expected_parameters(objects:Mapping[str,Any],family:str,ordinal:int)->tuple[dict[str,float],dict[str,Any]]:
    if family in FAMILIES[:2]:
        params,provenance=frozen_verify.expected_parameters(objects,family,ordinal);return params,provenance
    if family==FAMILIES[2]:
        seeds=objects["RANDOM_FIXED_SEEDS"]
        if len(seeds)!=20 or len(set(seeds))!=20:raise RepairVerifyError("RANDOM_SEEDS")
        parsed=adapter.random_spec(objects["RANDOM_FAMILY_SPEC"]);seed=int(seeds[ordinal-1])
        return adapter.random_values(objects["RANDOM_FAMILY_SPEC"],seed),{"kind":"RANDOM_FIXED_MEMBER_SEED","member_seed":seed,"seed_index_zero_based":ordinal-1,"draw_count":13,"nextafter_guard":True,"spec_sha256":parsed["spec_sha256"]}
    spec=objects["PHYSICS_FAMILY_SPEC_PARAMETERS_LHS"];master=int(objects["PHYSICS_MASTER_SEED"]);seeds=objects["PHYSICS_MEMBER_IDENTITY_SEEDS"]
    if spec.get("lhs_master_seed")!=master or len(seeds)!=20 or len(set(seeds))!=20:raise RepairVerifyError("PHYSICS_SEEDS")
    parsed=adapter.physics_spec(spec)
    return adapter.physics_values(spec,master,ordinal),{"kind":"PHYSICS_FISHER_YATES_MIDPOINT_LHS","master_seed":master,"member_identity_seed":seeds[ordinal-1],"seed_index_zero_based":ordinal-1,"lhs_jitter":False,"spec_sha256":parsed["spec_sha256"]}


def load_schemas(root:Path)->dict[str,Any]:
    names=("member_identity","partial_family_manifest","static_audit","independent_verification","batch_index","generation_terminal","verifier_terminal","publication_terminal")
    result={n:json.loads((root/f"{n}.schema.json").read_text()) for n in names}
    for x in result.values():jsonschema.Draft202012Validator.check_schema(x)
    return result


def check(value:Any,schemas:Mapping[str,Any],name:str)->None:
    try:jsonschema.Draft202012Validator(schemas[name]).validate(value)
    except jsonschema.ValidationError as exc:raise RepairVerifyError(f"SCHEMA_{name}:{exc.message}") from exc


def read_canonical(path:Path)->Any:
    raw=path.read_bytes()
    try:value=json.loads(raw.decode("utf-8"))
    except Exception as exc:raise RepairVerifyError("JSON:"+path.name) from exc
    if raw!=canonical(value):raise RepairVerifyError("NON_CANONICAL:"+path.name)
    return value


def verify_pending_sums(stage:Path)->None:
    raw=(stage/"SHA256SUMS.txt").read_text(encoding="ascii")
    expected="".join(f"{sha_file(p)}  {p.relative_to(stage).as_posix()}\n" for p in sorted(stage.rglob("*")) if p.is_file() and p.name!="SHA256SUMS.txt")
    if raw!=expected:raise RepairVerifyError("PENDING_SHA256SUMS_GRAPH")


def write_failure(binding:Mapping[str,Any],reason:str)->Path:
    roots=binding["roots_resolved"];success=roots["success"]/"VERIFIED_SUCCESS.json";failure=roots["failure"]/"FAIL_CLOSED.json"
    if success.exists():raise RepairVerifyError("SUCCESS_FORBIDS_FAILURE")
    if failure.exists():return failure
    stage=roots["staging"];members=sum(1 for p in (stage/"members").glob("*.json")) if (stage/"members").exists() else 0;artifacts=sum(1 for p in stage.rglob("*") if p.is_file()) if stage.exists() else 0
    value={"schema_version":"gen_enc_fast_b1_repair_01_package_terminal_v1","record_kind":"FAIL_CLOSED","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":binding["run_id"],"release_sha256":binding["release_sha256"],"attestation_sha256":binding["attestation_sha256"],"status":"TECHNICAL_FAIL_CLOSED","reason":reason,"honest_counts":{"authority_reads":binding.get("authority_read_count",0),"members":members,"artifacts":artifacts,"published":0},"commit_pointer_sha256":None,"package_terminal_count":1,"claim_ceiling":CLAIM,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False}
    schema=json.loads((binding["schema_root"]/"package_terminal.schema.json").read_text());jsonschema.Draft202012Validator(schema).validate(value);failure.parent.mkdir(parents=True,exist_ok=True)
    with failure.open("xb") as stream:stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    return failure


def verify_and_reseal(stage:Path,objects:Mapping[str,Any],authority_entries:Sequence[Mapping[str,Any]],projection:Mapping[str,Any],binding:Mapping[str,Any],schema_root:Path,fault:str|None=None)->dict[str,Any]:
    schemas=load_schemas(schema_root); model=adapter.model(objects,authority_entries,projection); members=[]
    pending={f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in range(1,6)}|{f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES}|{"batch_index.json","static_audit.json","independent_verification.json","SHA256SUMS.txt","generation_terminal.json"}
    if {p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()}!=pending:raise RepairVerifyError("PENDING_ZERO_UNLISTED")
    generation=read_canonical(stage/"generation_terminal.json");check(generation,schemas,"generation_terminal")
    if generation["run_id"]!=binding["run_id"] or generation["authority_read_count"]!=binding.get("authority_read_count",0):raise RepairVerifyError("GENERATION_TERMINAL_GRAPH")
    verify_pending_sums(stage)
    for family in FAMILIES:
        for ordinal in range(1,6):
            path=stage/f"members/{PREFIX[family]}_{ordinal:02d}.json";member=json.loads(path.read_text());check(member,schemas,"member_identity")
            params,provenance=expected_parameters(objects,family,ordinal);expected,status=expected_cad(family,ordinal,params,model)
            if member["parameters"]!=params or member["parameter_order"]!=list(params) or member["input_provenance"]!=provenance or member["cad_static_evidence"]!=expected or member["static_status"]!=status:raise RepairVerifyError("MEMBER_DEEP_RECOMPUTE:"+member.get("member_id","?"))
            members.append(member)
            if fault==f"member:{len(members)}":raise RepairVerifyError("INJECT_VERIFIER_MEMBER")
    for family in FAMILIES:
        manifest=json.loads((stage/f"partial_manifests/{PREFIX[family]}.json").read_text());check(manifest,schemas,"partial_family_manifest");selected=[m for m in members if m["family_id"]==family]
        expected_entries=[{"member_id":m["member_id"],"path":f"members/{m['member_id']}.json","sha256":sha_file(stage/f"members/{m['member_id']}.json"),"static_status":m["static_status"],"failure_slot_retained":True} for m in selected]
        if manifest["family_id"]!=family or manifest["slot_ordinals"]!=[1,2,3,4,5] or manifest["member_entries"]!=expected_entries or manifest["complete_family_manifest"]:raise RepairVerifyError("MANIFEST_GRAPH")
    audit=json.loads((stage/"static_audit.json").read_text());check(audit,schemas,"static_audit")
    expected_paths=[f"members/{m['member_id']}.json" for m in members];counts={name:sum(m["static_status"]==name for m in members) for name in ("ELIGIBLE","COST_INELIGIBLE","TEMPLATE_VALIDITY_REJECTED","FAIL_CLOSED")}
    if audit["member_paths"]!=expected_paths or audit["status_counts"]!=counts or audit["member_count"]!=20 or audit["complete_cad_witness_count"]!=20 or not audit["failed_slots_retained"]:raise RepairVerifyError("STATIC_AUDIT_GRAPH")
    index=json.loads((stage/"batch_index.json").read_text());check(index,schemas,"batch_index")
    expected_member_paths=[f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in range(1,6)];expected_manifests=[f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES]
    for key,expected in (("task_id",TASK_ID),("batch_id",BATCH_ID),("run_id",binding["run_id"]),("authority_allowlist_sha256",binding["authority_allowlist_sha256"]),("source_manifest_sha256",binding["source_manifest_sha256"]),("schema_manifest_sha256",binding["schema_manifest_sha256"]),("command_manifest_sha256",binding["command_manifest_sha256"]),("member_paths",expected_member_paths),("partial_manifest_paths",expected_manifests),("artifact_cardinality",31),("final_endpoint",False),("claim_ceiling",CLAIM)):
        if index[key]!=expected:raise RepairVerifyError("INDEX_GRAPH:"+key)
    report={"schema_version":"gen_enc_fast_b1_repair_01_independent_verification_v1","record_kind":"INDEPENDENT_VERIFICATION","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":binding["run_id"],"status":"PASS","verified_member_count":20,"verified_manifest_count":4,"authority_read_count":binding.get("authority_read_count",0),"artifact_count":31,"checks":["CAD_ALL_13_ALL_LEAVES","RANDOM_EXACT_SPEC","PHYSICS_EXACT_SPEC_LHS","MEMBER_DEEP_CAD","ARTIFACT_GRAPH_ZERO_UNLISTED"],"resealed":True,"claim_ceiling":CLAIM,"final_test_read":False}
    check(report,schemas,"independent_verification");frozen_verify.atomic(stage/"independent_verification.json",report)
    index["verification_complete"]=True;check(index,schemas,"batch_index");frozen_verify.atomic(stage/"batch_index.json",index)
    verifier_terminal={"schema_version":"gen_enc_fast_b1_repair_01_verifier_terminal_v1","record_kind":"VERIFIED_STAGING_NON_PUBLICATION","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":binding["run_id"],"status":"VERIFIED_RESEALED_AWAITING_PUBLICATION","authority_read_count":binding.get("authority_read_count",0),"verified_member_count":20,"artifact_count":31,"publication_started":False,"success_terminal_written":False,"claim_ceiling":CLAIM,"final_test_read":False}
    check(verifier_terminal,schemas,"verifier_terminal");frozen_verify.atomic(stage/"verifier_terminal.json",verifier_terminal)
    publication={"schema_version":"gen_enc_fast_b1_repair_01_publication_terminal_v1","record_kind":"PUBLICATION_INTENT_NON_SUCCESS","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":binding["run_id"],"status":"AWAITING_MULTI_TARGET_ATOMIC_PUBLICATION","target_count":31,"published_count":0,"commit_pointer_written":False,"success_terminal_written":False,"claim_ceiling":CLAIM,"final_test_read":False}
    check(publication,schemas,"publication_terminal");frozen_verify.atomic(stage/"publication_terminal.json",publication)
    lines="".join(f"{sha_file(p)}  {p.relative_to(stage).as_posix()}\n" for p in sorted(stage.rglob("*")) if p.is_file() and p.name!="SHA256SUMS.txt");(stage/"SHA256SUMS.txt").write_text(lines,encoding="ascii",newline="\n")
    return {"status":"VERIFIED_RESEALED_NOT_PUBLISHED","authority_read_count":binding.get("authority_read_count",0),"verified_member_count":20,"artifact_count":31}


def formal_gate(repo:Path,release_path:Path,attestation_path:Path,schema_root:Path)->tuple[dict[str,Any],list[dict[str,Any]],dict[str,Any]]:
    release,raw=frozen_verify.read_json(release_path);attestation,araw=frozen_verify.read_json(attestation_path)
    schemas={n:json.loads((schema_root/f"{n}.schema.json").read_text()) for n in ("release","guardian_attestation","side_record")}
    for name,value in (("release",release),("guardian_attestation",attestation)):jsonschema.Draft202012Validator(schemas[name]).validate(value)
    if release["run_id"]!=derive_run_id(release) or datetime.fromisoformat(release["expires_at"]).astimezone(timezone.utc)<=datetime.now(timezone.utc):raise RepairVerifyError("RELEASE_BOUNDARY")
    release_sha,att_sha=frozen_verify.sha_bytes(raw),frozen_verify.sha_bytes(araw)
    if attestation["release_sha256"]!=release_sha or attestation["run_id"]!=release["run_id"] or not attestation["one_way"]:raise RepairVerifyError("ATTESTATION")
    for name in ("source","schema","command"):
        if sha_file(_repo_path(repo,release[f"{name}_manifest_path"]))!=release[f"{name}_manifest_sha256"]:raise RepairVerifyError("MANIFEST_HASH:"+name)
    expected_base=f"outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_01_runs/{release['run_id']}"
    expected_roots={"staging":expected_base+"/staging","run":expected_base+"/run","journal":expected_base+"/journal","success":expected_base+"/success","failure":expected_base+"/failure","side_records":expected_base+"/side_records","pointer":f"outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_01_commit/{release['run_id']}"}
    if release["roots"]!=expected_roots:raise RepairVerifyError("ROOT_TEMPLATE")
    roots={k:_repo_path(repo,v) for k,v in release["roots"].items()};values=list(roots.values())
    if len({str(x).casefold() for x in values})!=len(values) or any(a.is_relative_to(b) or b.is_relative_to(a) for i,a in enumerate(values) for b in values[i+1:]):raise RepairVerifyError("ROOTS_EXCLUSIVE")
    allow_path=_repo_path(repo,release["authority_allowlist_path"])
    if sha_file(allow_path)!=frozen_verify.ALLOWLIST_SHA:raise RepairVerifyError("ALLOWLIST_HASH")
    allow=json.loads(allow_path.read_text());triples=[{"path":x["path"],"sha256":x["sha256"],"pointer":x["pointer"]} for x in allow["entries"]]
    if len(triples)!=20 or release["authority_triples"]!=triples or any(x.get("technical_fixture") for x in allow["entries"]):raise RepairVerifyError("TRIPLES")
    common={"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":release["run_id"],"release_sha256":release_sha,"attestation_sha256":att_sha,"authority_allowlist_sha256":frozen_verify.ALLOWLIST_SHA,"source_manifest_sha256":release["source_manifest_sha256"],"schema_manifest_sha256":release["schema_manifest_sha256"],"command_manifest_sha256":release["command_manifest_sha256"],"commands_exact":release["commands_exact"],"mode":release["mode"],"roots":release["roots"]}
    for state in ("ISSUED","CONSUMED"):
        value,_=frozen_verify.read_json(roots["side_records"]/f"{state}.json");jsonschema.Draft202012Validator(schemas["side_record"]).validate(value)
        if value["state"]!=state or value["revoked"] or any(value.get(k)!=v for k,v in common.items()):raise RepairVerifyError(state+"_BINDING")
    if (roots["side_records"]/"REVOKED.json").exists():raise RepairVerifyError("REVOKED")
    objects={}
    for entry in allow["entries"]:
        path=_repo_path(repo,entry["path"])
        if sha_file(path)!=entry["sha256"]:raise RepairVerifyError("AUTHORITY_HASH")
        selected=frozen_verify.pointer(json.loads(path.read_text()),entry["pointer"]);shape=entry["object_shape"]
        kind="object" if isinstance(selected,dict) else "array" if isinstance(selected,list) else type(selected).__name__
        if kind!=shape["type"]:raise RepairVerifyError("AUTHORITY_TYPE")
        if isinstance(selected,dict) and (list(selected)!=shape["field_names"] or any(len(selected[k])!=n for k,n in shape.get("array_counts",{}).items())):raise RepairVerifyError("AUTHORITY_FIELDS")
        if isinstance(selected,list) and (len(selected)!=shape["count"] or selected and isinstance(selected[0],dict) and (list(selected[0])!=shape["item_field_names"] or not all(set(x)==set(selected[0]) for x in selected))):raise RepairVerifyError("AUTHORITY_ARRAY")
        if not isinstance(selected,(dict,list)) and "value" in shape and selected!=shape["value"]:raise RepairVerifyError("AUTHORITY_VALUE")
        objects[entry["purpose"]]=selected
    return objects,allow["entries"],{**common,"staging":roots["staging"],"roots_resolved":roots,"schema_root":schema_root,"authority_read_count":20}


def parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser();p.add_argument("verify",choices=["verify"])
    for name in ("repo-root","release","guardian-attestation","schema-root","projection-contract"):p.add_argument("--"+name,type=Path,required=True)
    return p


def main(argv:Sequence[str]|None=None)->int:
    ns=parser().parse_args(argv);reads=0;binding=None
    try:
        actual=["-m","scripts.gen_enc_b1_repair_01.independent_verifier",*(list(argv) if argv is not None else sys.argv[1:])]
        if actual!=expected_argv():raise RepairVerifyError("ARGV_NOT_BYTE_EXACT")
        objects,entries,binding=formal_gate(ns.repo_root.resolve(),ns.release.resolve(),ns.guardian_attestation.resolve(),ns.schema_root.resolve());reads=20
        contract=json.loads(ns.projection_contract.resolve().read_text());result=verify_and_reseal(binding["staging"],objects,entries,contract,binding,ns.schema_root.resolve());print(json.dumps(result,sort_keys=True));return 0
    except BaseException as exc:
        if binding is not None:write_failure(binding,type(exc).__name__+":"+str(exc))
        print(json.dumps({"status":"FAIL_CLOSED","error":type(exc).__name__+":"+str(exc),"authority_read_count":reads},sort_keys=True),file=sys.stderr);return 2


if __name__=="__main__":raise SystemExit(main())
