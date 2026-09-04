"""Standalone Repair-09 verifier; imports neither driver nor any old implementation."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.gen_enc_b1_repair_09 import cad_projection_verifier as cad
import jsonschema

from scripts.gen_enc_b1_repair_09.primitives import atomic_json, canonical, pointer, read_canonical, sha_bytes, sha_file, sha_value

TASK_ID="01a049a7-15ca-79e1-92a2-d3822ba8609d";BATCH_ID="B1";REPAIR="PRE-RELEASE-REPAIR-09"
FAMILIES=("HAND_DESIGNED","NEAR_INDEPENDENT","FIXED_SEED_RANDOM_DISORDERED","PHYSICS_METAMATERIAL_INSPIRED");PREFIX=dict(zip(FAMILIES,("HAND","NEAR","RANDOM","PHYSICS")));SECTORS=("0","90","180","270")
CLAIM="BATCH_LOCAL_IDENTITY_COMPLETE_CAD_STATIC_AND_TECHNICAL_VALIDITY_ONLY";PROJECTION_PATH="outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_09/cad_typed_projection_contract.json";DEPENDENCY_PATH="outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_09/cad_leaf_dependency_matrix.json"
SUBJECT_SEAL_PATH="VERIFICATION_SUBJECT_SEAL.json"
RANDOM_AXES=("q0","q90","q180","edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270","loss_0","loss_90","loss_180","loss_270");PHYSICS_AXES=("q0","q90","q180","external_0","external_90","external_180","external_270","ring_0_90","ring_90_180","ring_180_270","ring_270_0","loss_0","loss_90","loss_180","loss_270")
MASK=(1<<64)-1;GAMMA=0x9E3779B97F4A7C15;RUN_DOMAIN=b"GEN-ENC-FAST-B1-PRE-RELEASE-REPAIR-09-RUN-ID-v1"
MODE="FORMAL_B1_EXACT_20_TYPED_CAD";COMMANDS=("preflight","generate-staging","verify","publish","recover","package-results")
PHASE_A_COMMANDS=("preflight","generate-staging","verify")
PHASE_A_HANDOFF_PATH="PHASE_A_VERIFIED_HANDOFF.json"
GUARDIAN_TWO_PHASE_CONTRACT_PATH="outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/contracts/GEN_ENC_FAST_B1_B4_TWO_STAGE_POSTERIOR_ANCHOR_CONTRACT.json";GUARDIAN_TWO_PHASE_CONTRACT_SHA256="526d64e67ddbdb6e15ea2fb0a0f0bb84aae4e90a55f3d9bde44237f34c5027c2"
GUARDIAN_TWO_PHASE_REVIEW_PATH="outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_FAST_B1_B4_TWO_STAGE_POSTERIOR_ANCHOR_CONTRACT_REVIEW.json";GUARDIAN_TWO_PHASE_REVIEW_SHA256="c3d21497f26744219656b80de1e639027fee48b2c96171f593381926d7220edd"
GUARDIAN_SIGNING_CHECK_PATH="outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/signing_checks/GEN_ENC_FAST_B1_REPAIR_07_PHASE_A_CONTROL_SIGNING_FAIL_CLOSED.json";GUARDIAN_SIGNING_CHECK_SHA256="3b98531d8ab333920f0551a88398feab60bb0029819705c69803de9c39b0621d"
ROLLOVER_SIGNING_FAIL_PATH="outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/signing_checks/GEN_ENC_FAST_B1_REPAIR_08_ENTIRELY_NEW_RUN_CONTROL_SIGNING_FAIL_CLOSED.json";ROLLOVER_SIGNING_FAIL_SHA256="9ba0dc07067b5086e3f813650b1791ff4f05e8c24ec92025f341d8fa5dcdbe6f"
ROLLOVER_REGISTRATION_PATH="outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/technical_repair_events/B1_REPAIR_09_CONTROL_PATH_ROLLOVER_REGISTRATION_20260829_001.json";ROLLOVER_REGISTRATION_SHA256="55e38765e4f1805b1422893a9965744c5d23556182a20b9bd6a17709d49b300f"
REVOKED_RUN_ID="dd45162503eabf764ef91fb4cdf198ed454cc89283616d169433c2a83df0e613";REVOKED_DISPATCH_ID="80042c4cdecaaa698b6ecd31745bcbbb16c2ba7b0bb645d6c93cf1bc07780d6f"
ADVISOR_B_FINAL_REVIEW_PATH="outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_FAST_B1_PRE_RELEASE_REPAIR_07_TWO_PHASE_MECHANICAL_SPLIT_FINAL_REREVIEW.json";ADVISOR_B_FINAL_REVIEW_SHA256="98cf8df05267ff4828a906b0e4fc0083c91d4a456aea51e608235519798378f0"
ADVISOR_LEDGER_SNAPSHOT_PROTOCOL_PATH="outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/contracts/REVIEW_SPECIFIC_IMMUTABLE_LEDGER_SNAPSHOT_PROTOCOL.json";ADVISOR_LEDGER_SNAPSHOT_PROTOCOL_SHA256="47ee5e6b7b4175a312add18fb47903a6d656bb0ce467487e766ce86ca6bfc63e"
R07_LEDGER_SNAPSHOT_ABSENCE_PATH="outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/stage_events/R07_FINAL_REVIEW_LEDGER_SNAPSHOT_ABSENCE_DISCLOSURE_20260829_001.json";R07_LEDGER_SNAPSHOT_ABSENCE_SHA256="0165e1716fea948a959ea3951627b9c63c2833c719ed3c9731a96236191e813c"
AUTHORITY_ALLOWLIST_PATH="outputs/gen_enc/GEN_ENC_FAST_START/fast_0_authority_batch_contract_freeze/authority_allowlist.json"


class Verify09Error(RuntimeError):pass


def derive_run_id(release:Mapping[str,Any])->str:
    copy=dict(release);copy["run_id"]="0"*64
    if "roots" in copy:copy["roots"]=_roots("0"*64,copy.get("record_kind")=="TECHNICAL_MIRROR_RELEASE")
    for key in ("phase_a_release_path","phase_a_attestation_path","phase_a_dispatch_path"):
        if key in copy:copy[key]=str(copy[key]).replace(str(release.get("run_id","")),"0"*64)
    return sha_bytes(RUN_DOMAIN+b"\n"+canonical(copy))


def _mix64(value:int)->int:
    value=(value+GAMMA)&MASK;value=((value^(value>>30))*0xBF58476D1CE4E5B9)&MASK;value=((value^(value>>27))*0x94D049BB133111EB)&MASK
    return (value^(value>>31))&MASK


def _u(seed:int,axis:int)->float:
    result=((_mix64((seed+GAMMA*(axis+1))&MASK)>>11)+.5)/(1<<53)
    return math.nextafter(1.0,0.0) if result==1 else result


def _perm(master:int,axis:int)->list[int]:
    order=list(range(20))
    for upper in range(19,0,-1):
        chosen=_mix64((master+GAMMA*(1+32*axis+19-upper))&MASK)%(upper+1);order[upper],order[chosen]=order[chosen],order[upper]
    return order


def _bounds(spec:Mapping[str,Any],axes:Sequence[str],groups:Sequence[str])->dict[str,tuple[float,float]]:
    if tuple(spec.get("parameter_order",()))!=tuple(axes) or spec.get("member_count")!=20 or spec.get("dof")!=len(axes):raise Verify09Error("AXES")
    result={}
    if len(spec.get("parameters",[]))!=len(groups):raise Verify09Error("GROUPS")
    for position,name in enumerate(groups):
        item=spec["parameters"][position]
        if set(item)!={"group","axes","bounds"} or item["group"]!=name or len(item["bounds"])!=2:raise Verify09Error("GROUP")
        lo,hi=float(item["bounds"][0]),float(item["bounds"][1])
        if lo>=hi:raise Verify09Error("BOUND")
        for axis in item["axes"]:
            if axis in result:raise Verify09Error("DUP")
            result[axis]=(lo,hi)
    if list(result)!=list(axes):raise Verify09Error("GROUP_ORDER")
    return result


def expected_parameters(objects:Mapping[str,Any],family:str,ordinal:int)->dict[str,float]:
    if family==FAMILIES[0] or family==FAMILIES[1]:
        row=objects["HAND_ROWS" if family==FAMILIES[0] else "NEAR_ROWS"][ordinal-1]
        out={"q0":float(row["volume_logit_0"]),"q90":float(row["volume_logit_90"]),"q180":float(row["volume_logit_180"]),"q270":float(row["derived_volume_logit_270"])}
        out.update({f"external_{s}":float(row[f"external_aperture_fraction_{s}"]) for s in SECTORS});out.update({f"loss_{s}":float(row[f"loss_fraction_{s}"]) for s in SECTORS});out["central_mix" if family==FAMILIES[0] else "shared_alpha"]=float(row["central_mix_aperture_fraction" if family==FAMILIES[0] else "shared_coupling_alpha"]);return out
    if family==FAMILIES[2]:
        spec=objects["RANDOM_FAMILY_SPEC"];b=_bounds(spec,RANDOM_AXES,("VOLUME_LOGIT","RECIPROCAL_EDGE_POSITIVE","LOSS"))
        if spec.get("uniform_algorithm")!={"interval":"OPEN_0_1_BINARY64","word_to_uniform":"((word>>11)+0.5)/2^53","one_guard":"nextafter(1.0,0.0)"} or spec.get("splitmix64",{}).get("gamma_hex")!="9e3779b97f4a7c15":raise Verify09Error("RANDOM_SPEC")
        out={f"external_{s}":.5 for s in SECTORS};seed=int(objects["RANDOM_FIXED_SEEDS"][ordinal-1])
        for index,name in enumerate(RANDOM_AXES):
            lo,hi=b[name];sample=_u(seed,index);out[name]=lo+(hi-lo)*sample if index<3 or index>=9 else 0.0 if sample<.5 else lo+(hi-lo)*(2*sample-1)
        out["q270"]=-(out["q0"]+out["q90"]+out["q180"])/3;return out
    spec=objects["PHYSICS_FAMILY_SPEC_PARAMETERS_LHS"];b=_bounds(spec,PHYSICS_AXES,("VOLUME_LOGIT","EXTERNAL_APERTURE","RING_COUPLING","LOSS"));master=int(objects["PHYSICS_MASTER_SEED"])
    if spec.get("lhs_algorithm")!=["STRATA=20","SAMPLE=(PERMUTATION[row]+0.5)/20","JITTER=false","FISHER_YATES_SPLITMIX64=i19_TO_1"] or spec.get("lhs_master_seed")!=master:raise Verify09Error("PHYSICS_SPEC")
    out={}
    for index,name in enumerate(PHYSICS_AXES):
        lo,hi=b[name];out[name]=lo+(hi-lo)*(_perm(master,index)[ordinal-1]+.5)/20
    out["q270"]=-(out["q0"]+out["q90"]+out["q180"])/3;return out


def _components(nodes:Sequence[str],edges:Sequence[Mapping[str,Any]])->int:
    remaining=set(nodes);total=0
    while remaining:
        total+=1;queue=[remaining.pop()]
        while queue:
            here=queue.pop()
            adjacent={e["b"] for e in edges if e["weight"]>0 and e["a"]==here}|{e["a"] for e in edges if e["weight"]>0 and e["b"]==here}
            for item in adjacent&remaining:remaining.remove(item);queue.append(item)
    return total


def expected_evidence(family:str,p:Mapping[str,float],projected:Mapping[str,Any])->tuple[dict[str,Any],str]:
    v=projected["values"];r=v["OWNERSHIP_RULE"]
    ownership=[{"cell_id":c["cell_id"],"owner":c["owner"],"rule":r["central"] if c["owner"]=="CENTRAL" else r["sector"],"positive_overlap_volume_m3":float(c["positive_overlap_volume_m3"])} for c in v["OWNERSHIP_CELLS"]]
    z=float(v["GEOMETRY_SLOT_Z"]);slots=[{"slot_id":s["slot_id"],"sector":s["sector"],"owner_cell_id":s["owner_cell_id"],"coordinates_m":[float(s["coordinates_xy_m"][0]),float(s["coordinates_xy_m"][1]),z],"placement_status":"PLACED_OR_EXPLICIT_ZERO","width_m":float(s["width_m"])} for s in v["SLOT_ROWS"]]
    common=v["ROOT_COMMON"];initial=[float(x) for x in v["ROOT_BRACKET"]];weights=[math.exp(float(p[f"q{x}"])) for x in SECTORS];roots=[]
    for sector,weight in zip(SECTORS,weights):
        target=float(v["GEOMETRY_VOLUME"])*float(v["GEOMETRY_TARGET_FRACTION"])*weight/sum(weights);lo,hi=initial;trace=[]
        for count in range(int(common["iterations"])):
            midpoint=(lo+hi)/2;volume=float(common["fixed_volume_m3"])+float(common["linear_coefficient_m2"])*midpoint;trace.append({"iteration":count+1,"low_m":lo,"high_m":hi,"mid_m":midpoint,"measured_volume_m3":volume})
            if volume<target:lo=midpoint
            else:hi=midpoint
        root=(lo+hi)/2;volume=float(common["fixed_volume_m3"])+float(common["linear_coefficient_m2"])*root
        if abs(volume-target)>float(common["tolerance_m3"]):raise Verify09Error("RESIDUAL")
        roots.append({"sector":sector,"domain_m":[float(x) for x in common["domain_m"]],"initial_bracket_m":initial,"final_bracket_m":[lo,hi],"tolerance_m3":float(common["tolerance_m3"]),"iterations":common["iterations"],"trace":trace,"root_length_m":root,"target_volume_m3":target,"measured_volume_m3":volume,"residual_m3":volume-target})
    coordinates=v["U4_COORDINATES"];exceptions=[]
    for sector_group in v["U4_OBJECTS"]:
        for item in sector_group["exceptions"]:
            suffix=item["suffix"];exceptions.append({"exception_id":f"IFX_U4_{int(sector_group['sector']):03d}_{suffix}","sector":sector_group["sector"],"local_coordinates_m":[float(coordinates["x_m"]),float(coordinates["suffix_z_m"][suffix])],"feature_m":float(item["feature_m"]),"load_path_m":float(item["load_path_m"]),"participation":v["U4_PARTICIPATION"],"excluded_only_from":"GENERAL_MINIMA"})
    fields=v["STATIC_FIELDS"];features=[{"witness_id":x["witness_id"],"measured_m":float(x["measured_m"])} for x in fields["general_feature_candidates"]];loads=[{"witness_id":x["witness_id"],"measured_m":float(x["measured_m"])} for x in fields["general_load_candidates"]]
    graph=v["GRAPH_DEFINITION"];reduced=[{"edge_id":e["edge_id"],"a":e["a"],"b":e["b"],"weight":float(p.get(e["parameter_key"],0)),"active":float(p.get(e["parameter_key"],0))>0} for e in graph["reduced_edges"]];actual=[{"edge_id":e["edge_id"],"a":e["a"],"b":e["b"],"weight":float(e["positive_area_m2"]),"positive_area_m2":float(e["positive_area_m2"])} for e in graph["actual_edges"]]
    zero=v["ZERO_EDGE_RULE"];zeros=[{"edge_id":e["edge_id"],"exact_value":zero["exact_zero"],"generator_branch":zero["branch"],"verified_exact_zero":True} for e in reduced if family==zero["family"] and e["weight"]==zero["exact_zero"]]
    semantic={"ownership_transforms":v["OWNERSHIP_ALGORITHMS"],"slot_sector_order":v["SLOT_SECTOR_ORDER"],"slot_mapping":v["SLOT_MAPPING"],"slot_required_fields":v["SLOT_BURDEN"],"root_family_rules":v["ROOT_FAMILIES"],"root_domain_proof":v["ROOT_DOMAIN"],"root_derived_proof":v["ROOT_DERIVED_PROOF"],"root_independent_proof":v["ROOT_INDEPENDENT_PROOF"],"minima_fail_rules":v["STATIC_FAIL_RULES"],"solid_metrics":v["SOLID_METRICS"],"solid_eligible_pair":v["SOLID_ELIGIBLE_PAIR"],"graph_terms":v["GRAPH_TERMS"]};approval={"U1":v["APPROVAL_U1"],"U2":v["APPROVAL_U2"],"U3":v["APPROVAL_U3"],"mandatory_carry_forward":v["APPROVAL_CARRY"]}
    evidence={"schema_version":"gen_enc_fast_b1_repair_09_member_cad_static_v1","ownership_cells":ownership,"slot_placements":slots,"volume_root_witnesses":roots,"u4_exception_witnesses":exceptions,"general_minima":{"feature_candidates":features,"load_path_candidates":loads,"measured_minimum_feature_m":min(x["measured_m"] for x in features),"measured_minimum_load_path_m":min(x["measured_m"] for x in loads),"feature_witness_ids":[x["witness_id"] for x in features if x["measured_m"]==min(y["measured_m"] for y in features)],"load_path_witness_ids":[x["witness_id"] for x in loads if x["measured_m"]==min(y["measured_m"] for y in loads)]},"exception_minima":{"measured_minimum_feature_m":min(float(x) for x in fields["exception_feature_candidates"]),"measured_minimum_load_path_m":min(float(x) for x in fields["exception_load_candidates"]),"exception_ids":[x["exception_id"] for x in exceptions]},"reduced_graph":{"nodes":graph["reduced_nodes"],"edges":reduced,"component_count":_components(graph["reduced_nodes"],reduced)},"actual_fluid_graph":{"nodes":graph["actual_nodes"],"edges":actual,"component_count":_components(graph["actual_nodes"],actual)},"random_zero_edge_witnesses":zeros,"thresholds":{"minimum_general_feature_m":float(fields["minimum_general_feature_m"]),"minimum_general_load_path_m":float(fields["minimum_general_load_path_m"])},"semantic_derivation_inputs":semantic,"typed_projection_approval":approval,"thresholds_copied_as_measurements":False,"complete_witness_semantics":True}
    eligible=evidence["general_minima"]["measured_minimum_feature_m"]>=evidence["thresholds"]["minimum_general_feature_m"] and evidence["general_minima"]["measured_minimum_load_path_m"]>=evidence["thresholds"]["minimum_general_load_path_m"] and evidence["actual_fluid_graph"]["component_count"]==1
    return evidence,"ELIGIBLE" if eligible else "COST_INELIGIBLE"


def verify_members(members:Sequence[Mapping[str,Any]],objects:Mapping[str,Any],entries:Sequence[Mapping[str,Any]],contract:Mapping[str,Any],binding:Mapping[str,Any])->dict[str,Any]:
    projected=cad.project(objects,entries,contract)
    if projected["projection_contract_sha256"]!=binding["projection_contract_sha256"] or projected["dependency_matrix_sha256"]!=binding["dependency_structure_sha256"]:raise Verify09Error("PROJECTION_BINDING")
    expected_ids=[f"{PREFIX[f]}_{i:02d}" for f in FAMILIES for i in range(1,6)]
    if [m.get("member_id") for m in members]!=expected_ids:raise Verify09Error("MEMBER_SET_ORDER")
    for member in members:
        family=member["family_id"];ordinal=int(member["slot_ordinal"]);params=expected_parameters(objects,family,ordinal);evidence,status=expected_evidence(family,params,projected)
        provenance={"projection_contract_path":PROJECTION_PATH,"projection_contract_sha256":binding["projection_contract_sha256"],"dependency_matrix_path":DEPENDENCY_PATH,"dependency_matrix_sha256":binding["dependency_matrix_sha256"],"dependency_structure_sha256":binding["dependency_structure_sha256"],"semantic_leaf_count":projected["semantic_leaf_count"]}
        if member["parameters"]!=params or member["cad_static_evidence"]!=evidence or member["typed_projection_provenance"]!=provenance or member["static_status"]!=status:raise Verify09Error("DEEP_MEMBER:"+member["member_id"])
    return {"status":"PASS_TYPED_CAD_INDEPENDENT_RECOMPUTE","verified_member_count":20,"semantic_leaf_count":projected["semantic_leaf_count"],"dependency_matrix_sha256":projected["dependency_matrix_sha256"],"authority_read_count":binding.get("authority_read_count",0)}


def pre_read_binding(record:Mapping[str,Any],expected:Mapping[str,Any])->None:
    for name in ("task_id","batch_id","run_id","projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256"):
        if record.get(name)!=expected.get(name):raise Verify09Error("PRE_READ_BINDING:"+name)


def _safe(repo:Path,value:str)->Path:
    result=(repo/value).resolve()
    if result==repo or not result.is_relative_to(repo):raise Verify09Error("PATH_CONTAINMENT")
    return result


def _schemas(root:Path)->dict[str,Any]:
    result={p.name.removesuffix(".schema.json"):json.loads(p.read_text()) for p in root.glob("*.schema.json")}
    for schema in result.values():jsonschema.Draft202012Validator.check_schema(schema)
    return result


def _validate(value:Any,schemas:Mapping[str,Any],name:str)->None:
    try:jsonschema.Draft202012Validator(schemas[name]).validate(value)
    except jsonschema.ValidationError as exc:raise Verify09Error("SCHEMA_"+name+":"+exc.message) from exc


def _roots(run_id:str,technical:bool)->dict[str,str]:
    base=(".technical_b1_repair_09/" if technical else "outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_09_runs/")+run_id;result={x:f"{base}/{x}" for x in ("staging","run","journal","success","failure","side_records")};result["pointer"]=f".technical_b1_repair_09_commit/{run_id}" if technical else f"outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_09_commit/{run_id}";return result


def _artifacts()->list[str]:return [f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in range(1,6)]+[f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES]+["batch_index.json","static_audit.json","independent_verification.json","SHA256SUMS.txt","generation_terminal.json","verifier_terminal.json","publication_terminal.json"]


def _file_binding(release:Mapping[str,Any])->dict[str,Any]:
    keys=("task_id","batch_id","run_id","mode","commands_exact","guardian_two_phase_contract_path","guardian_two_phase_contract_sha256","guardian_two_phase_review_path","guardian_two_phase_review_sha256","advisor_b_final_review_path","advisor_b_final_review_sha256","advisor_b_ledger_snapshot_path","advisor_b_ledger_snapshot_sha256","phase_a_commands_exact","phase_a_permissions","phase_a_release_path","phase_a_attestation_path","phase_a_dispatch_id","phase_a_dispatch_path","guardian_phase_b_authorization_path","guardian_phase_b_attestation_path","phase_b_dispatch_path","authority_allowlist_path","authority_allowlist_sha256","verification_subject_seal_path","projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256","source_manifest_path","source_manifest_sha256","schema_manifest_path","schema_manifest_sha256","command_manifest_path","command_manifest_sha256","roots")
    return {k:release[k] for k in keys}


def _validate_rollover_paths(release:Mapping[str,Any],release_path:Path,attestation_path:Path,dispatch_path:Path|None,repo:Path,technical:bool)->None:
    rid=release.get("run_id");paths={"release":release.get("phase_a_release_path"),"attestation":release.get("phase_a_attestation_path"),"dispatch":release.get("phase_a_dispatch_path")}
    if not isinstance(rid,str) or not re.fullmatch(r"[0-9a-f]{64}",rid) or rid==REVOKED_RUN_ID:raise Verify09Error("ROLLOVER_RUN_ID")
    if technical:patterns={"release":rf"t/c/{rid}/R\.{rid}\.json","attestation":rf"t/c/{rid}/A\.{rid}\.json","dispatch":rf"t/d/{rid}/D\.{rid}\.json"}
    else:patterns={"release":rf"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_09/control_rollover/{rid}/PHASE_A_RELEASE\.{rid}\.json","attestation":rf"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_09/control_rollover/{rid}/PHASE_A_GUARDIAN_ATTESTATION\.{rid}\.json","dispatch":rf"control/gen_enc_fast_b1_repair_09/{rid}/PHASE_A_DISPATCH_AUTHORIZATION\.{rid}\.json"}
    for key,value in paths.items():
        if not isinstance(value,str) or "\\" in value or value.startswith("/") or ".." in value.split("/") or not re.fullmatch(patterns[key],value):raise Verify09Error("ROLLOVER_PATH:"+key)
    if len({v.casefold() for v in paths.values()})!=3:raise Verify09Error("ROLLOVER_CASEFOLD_COLLISION")
    try:actual_release=release_path.resolve().relative_to(repo).as_posix();actual_att=attestation_path.resolve().relative_to(repo).as_posix();actual_dispatch=None if dispatch_path is None else dispatch_path.resolve().relative_to(repo).as_posix()
    except ValueError as exc:raise Verify09Error("ROLLOVER_PATH_CONTAINMENT") from exc
    if actual_release!=paths["release"] or actual_att!=paths["attestation"]:raise Verify09Error("ROLLOVER_ACTUAL_PATH_BINDING")
    if actual_dispatch is not None and actual_dispatch!=paths["dispatch"]:raise Verify09Error("ROLLOVER_DISPATCH_CLI_BINDING")
    if release.get("phase_a_dispatch_id")==REVOKED_DISPATCH_ID:raise Verify09Error("ROLLOVER_DISPATCH_ID")


def _validate_signing_authority_bytes(repo:Path,release:Mapping[str,Any],technical:bool)->None:
    fixed=((ROLLOVER_SIGNING_FAIL_PATH,ROLLOVER_SIGNING_FAIL_SHA256,"ROLLOVER_SIGNING_FAIL_RECORD_BYTES"),(ROLLOVER_REGISTRATION_PATH,ROLLOVER_REGISTRATION_SHA256,"ROLLOVER_REGISTRATION_BYTES"),(GUARDIAN_SIGNING_CHECK_PATH,GUARDIAN_SIGNING_CHECK_SHA256,"GUARDIAN_SIGNING_FAIL_RECORD_BYTES"),(ADVISOR_B_FINAL_REVIEW_PATH,ADVISOR_B_FINAL_REVIEW_SHA256,"R07_FINAL_REVIEW_PROVENANCE_BYTES"),(ADVISOR_LEDGER_SNAPSHOT_PROTOCOL_PATH,ADVISOR_LEDGER_SNAPSHOT_PROTOCOL_SHA256,"LEDGER_SNAPSHOT_PROTOCOL_BYTES"),(R07_LEDGER_SNAPSHOT_ABSENCE_PATH,R07_LEDGER_SNAPSHOT_ABSENCE_SHA256,"R07_SNAPSHOT_ABSENCE_BYTES"))
    for path,want,error in fixed:
        if sha_file(_safe(repo,path))!=want:raise Verify09Error(error)
    for label,path_key,sha_key in (("FINAL_REVIEW","advisor_b_final_review_path","advisor_b_final_review_sha256"),("LEDGER_SNAPSHOT","advisor_b_ledger_snapshot_path","advisor_b_ledger_snapshot_sha256")):
        path_value=release.get(path_key);expected_sha=release.get(sha_key)
        if not isinstance(path_value,str) or not path_value.endswith(".json") or not isinstance(expected_sha,str) or len(expected_sha)!=64 or any(c not in "0123456789abcdef" for c in expected_sha):raise Verify09Error("ADVISOR_DYNAMIC_BINDING:"+label)
        required_root="technical/" if technical else ("outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/" if label=="FINAL_REVIEW" else "outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/ledger_snapshots/")
        if not path_value.startswith(required_root):raise Verify09Error("ADVISOR_DYNAMIC_ROOT:"+label)
        value,raw=read_canonical(_safe(repo,path_value))
        if sha_bytes(raw)!=expected_sha:raise Verify09Error("ADVISOR_DYNAMIC_HASH:"+label)
        if technical and (value.get("identity_class")!="TASK_OWNED_SYNTHETIC_IMMUTABLE_NEVER_FORMAL" or value.get("subject")!=label or value.get("task_id")!=TASK_ID or value.get("final_test_read") is not False):raise Verify09Error("ADVISOR_TECHNICAL_SYNTHETIC_CLASS:"+label)


def gate(repo:Path,release_path:Path,attestation_path:Path,schema_root:Path,cli:argparse.Namespace|None=None,raw_argv:Sequence[str]=())->dict[str,Any]:
    release,raw=read_canonical(release_path);technical=release.get("record_kind")=="TECHNICAL_MIRROR_RELEASE";schemas=_schemas(schema_root)
    if technical:
        if release.get("identity_class")!="TECHNICAL_MIRROR_RELEASE_NEVER_FORMAL" or not (repo/".technical_b1_repair_09_root").is_file():raise Verify09Error("TECH_ROOT")
    else:_validate(release,schemas,"release")
    if release.get("record_kind") not in ("PHASE_A_RELEASE","TECHNICAL_MIRROR_RELEASE") or release.get("repair_id")!=REPAIR or release.get("task_id")!=TASK_ID or release.get("batch_id")!=BATCH_ID or release.get("mode")!=MODE or release.get("commands_exact")!=list(PHASE_A_COMMANDS) or release["run_id"]!=derive_run_id(release):raise Verify09Error("PHASE_A_RELEASE")
    if release.get("phase_a_commands_exact")!=list(PHASE_A_COMMANDS) or release.get("phase_a_permissions")!={"preflight":True,"generate_staging":True,"independent_verify":True,"publish":False,"recover":False,"package_results":False}:raise Verify09Error("PHASE_A_PERMISSIONS")
    _validate_rollover_paths(release,release_path,attestation_path,None if cli is None else cli.phase_a_dispatch,repo,technical)
    if release.get("guardian_two_phase_contract_path")!=GUARDIAN_TWO_PHASE_CONTRACT_PATH or release.get("guardian_two_phase_contract_sha256")!=GUARDIAN_TWO_PHASE_CONTRACT_SHA256 or release.get("guardian_two_phase_review_path")!=GUARDIAN_TWO_PHASE_REVIEW_PATH or release.get("guardian_two_phase_review_sha256")!=GUARDIAN_TWO_PHASE_REVIEW_SHA256:raise Verify09Error("GUARDIAN_TWO_PHASE_AUTHORITY_BINDING")
    if release.get("authority_allowlist_path")!=AUTHORITY_ALLOWLIST_PATH:raise Verify09Error("AUTHORITY_ALLOWLIST_PATH")
    if sha_file(_safe(repo,GUARDIAN_TWO_PHASE_CONTRACT_PATH))!=GUARDIAN_TWO_PHASE_CONTRACT_SHA256 or sha_file(_safe(repo,GUARDIAN_TWO_PHASE_REVIEW_PATH))!=GUARDIAN_TWO_PHASE_REVIEW_SHA256:raise Verify09Error("GUARDIAN_TWO_PHASE_AUTHORITY_BYTES")
    _validate_signing_authority_bytes(repo,release,technical)
    if datetime.fromisoformat(release["expires_at"]).astimezone(timezone.utc)<=datetime.now(timezone.utc) or release["roots"]!=_roots(release["run_id"],technical):raise Verify09Error("EXPIRY_ROOT")
    roots={k:_safe(repo,v) for k,v in release["roots"].items()};projection_path=_safe(repo,release["projection_contract_path"]);matrix_path=_safe(repo,release["dependency_matrix_path"])
    if release["projection_contract_path"]!=PROJECTION_PATH or release["dependency_matrix_path"]!=DEPENDENCY_PATH or sha_file(projection_path)!=release["projection_contract_sha256"] or sha_file(matrix_path)!=release["dependency_matrix_sha256"]:raise Verify09Error("PROJECTION_FILE")
    matrix,_=read_canonical(matrix_path)
    if matrix.get("dependency_structure_sha256")!=release["dependency_structure_sha256"] or matrix.get("projection_contract_sha256")!=release["projection_contract_sha256"]:raise Verify09Error("STRUCTURE")
    for name in ("source","schema","command"):
        if sha_file(_safe(repo,release[f"{name}_manifest_path"]))!=release[f"{name}_manifest_sha256"]:raise Verify09Error("MANIFEST:"+name)
    command_manifest,_=read_canonical(_safe(repo,release["command_manifest_path"]))
    rows=command_manifest.get("entries",[])
    if command_manifest.get("mode")!=MODE or command_manifest.get("commands_exact")!=list(COMMANDS) or len(rows)!=6 or [row.get("command") for row in rows]!=list(COMMANDS):raise Verify09Error("COMMAND_MANIFEST")
    att,araw=read_canonical(attestation_path);_validate(att,schemas,"technical_guardian_attestation" if technical else "guardian_attestation");expected=_file_binding(release)
    if att.get("record_kind") not in ("GUARDIAN_ONE_WAY_ATTESTATION","TECHNICAL_MIRROR_ONE_WAY_ATTESTATION") or att.get("release_sha256")!=sha_bytes(raw) or att.get("one_way") is not True:raise Verify09Error("ATTESTATION")
    for key,value in expected.items():
        if att.get(key)!=value:raise Verify09Error("ATTESTATION_BINDING:"+key)
    side=roots["side_records"]
    failure=roots["failure"]/"FAIL_CLOSED.json"
    if failure.exists():
        failed,_=read_canonical(failure);_validate(failed,schemas,"package_terminal")
        for key,want in {"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":release["run_id"],"mode":MODE,"release_sha256":sha_bytes(raw),"attestation_sha256":sha_bytes(araw),"projection_contract_sha256":release["projection_contract_sha256"],"dependency_matrix_sha256":release["dependency_matrix_sha256"],"dependency_structure_sha256":release["dependency_structure_sha256"]}.items():
            if failed.get(key)!=want:raise Verify09Error("PHASE_A_FAILURE_BINDING:"+key)
        if failed.get("terminal_phase")=="PHASE_A":raise Verify09Error("PHASE_A_FAILURE_PERMANENT_NEW_RUN_REQUIRED")
    issued,_=read_canonical(_safe(repo,release["phase_a_dispatch_path"]));_validate(issued,schemas,"technical_phase_dispatch" if technical else "phase_dispatch")
    expected_kind="TECHNICAL_PHASE_DISPATCH" if technical else "PHASE_A_DISPATCH_AUTHORIZATION"
    if issued.get("record_kind")!=expected_kind or issued.get("state")!="PHASE_A_ISSUED" or issued.get("phase")!="A" or issued.get("one_use") is not True or issued.get("revoked") is not False or issued.get("final_test_read") is not False or issued.get("dispatch_id")!=release["phase_a_dispatch_id"] or issued.get("release_sha256")!=sha_bytes(raw) or issued.get("attestation_sha256")!=sha_bytes(araw):raise Verify09Error("PHASE_A_ISSUED_CONSTANTS")
    for key,want in expected.items():
        if issued.get(key)!=want:raise Verify09Error("ISSUED_BINDING:"+key)
    if (side/"REVOKED.json").exists():
        revoked,_=read_canonical(side/"REVOKED.json");_validate(revoked,schemas,"side_record")
        if (side/"CONSUMED.json").exists() or revoked.get("state")!="REVOKED" or revoked.get("revoked") is not True:raise Verify09Error("REVOKED_INVALID_STATE")
        for key,want in {**expected,"release_sha256":sha_bytes(raw),"attestation_sha256":sha_bytes(araw)}.items():
            if revoked.get(key)!=want:raise Verify09Error("REVOKED_BINDING:"+key)
        raise Verify09Error("REVOKED_VALID_BOUND")
    for state in ("PHASE_A_CONSUMED",):
        value,_=read_canonical(side/f"{state}.json")
        _validate(value,schemas,"technical_phase_a_dispatch_consumed" if technical else "phase_a_dispatch_consumed")
        if value.get("state")!=state or value.get("phase")!="A" or value.get("dispatch_id")!=release["phase_a_dispatch_id"] or value.get("release_sha256")!=sha_bytes(raw) or value.get("attestation_sha256")!=sha_bytes(araw):raise Verify09Error(state)
        for key,want in expected.items():
            if value.get(key)!=want:raise Verify09Error(state+"_BINDING:"+key)
    # Exact CLI and projection/dependency path checks precede opening either
    # the technical mirror bundle or any future formal authority object.
    if cli is not None:_check_cli_paths(cli,repo,{**expected,"technical":technical,"command_manifest":command_manifest},raw_argv)
    context={**expected,"technical":technical,"repo_root":str(repo),"phase_a_release_path":release_path.relative_to(repo).as_posix(),"phase_a_attestation_path":attestation_path.relative_to(repo).as_posix(),"release":release,"release_sha256":sha_bytes(raw),"attestation_sha256":sha_bytes(araw),"roots_resolved":roots,"schemas":schemas,"projection":json.loads(projection_path.read_text()),"matrix":matrix,"command_manifest":command_manifest}
    return {**context,"authority_read_count":authority_read_count(context)}


def _receipt_binding(context:Mapping[str,Any])->dict[str,Any]:return {**_file_binding(context["release"]),"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"]}


def authority_read_count(context:Mapping[str,Any])->int:
    directory=context["roots_resolved"]["side_records"]/"AUTHORITY_READS"
    if not directory.exists():return 0
    paths=sorted(directory.glob("*.json"));expected=_receipt_binding(context)
    if [p.name for p in paths]!=[f"{i:04d}.json" for i in range(1,len(paths)+1)]:raise Verify09Error("READ_RECEIPT_SEQUENCE")
    for ordinal,path in enumerate(paths,1):
        value,_=read_canonical(path);_validate(value,context["schemas"],"authority_read_receipt")
        if value.get("ordinal")!=ordinal:raise Verify09Error("READ_RECEIPT_ORDINAL")
        for key,want in expected.items():
            if value.get(key)!=want:raise Verify09Error("READ_RECEIPT_BINDING:"+key)
    return len(paths)


def record_authority_read(context:Mapping[str,Any],purpose:str,path_label:str,expected_sha256:str)->int:
    ordinal=authority_read_count(context)+1;directory=context["roots_resolved"]["side_records"]/"AUTHORITY_READS";directory.mkdir(parents=True,exist_ok=True)
    value={"schema_version":"gen_enc_fast_b1_repair_09_authority_read_receipt_v1","record_kind":"CUMULATIVE_AUTHORITY_READ_RECEIPT","repair_id":REPAIR,**_receipt_binding(context),"ordinal":ordinal,"phase":"INDEPENDENT_VERIFICATION","purpose":purpose,"path_label":path_label,"expected_sha256":expected_sha256,"final_test_read":False};_validate(value,context["schemas"],"authority_read_receipt")
    path=directory/f"{ordinal:04d}.json"
    with path.open("xb") as stream:stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    return ordinal


def load_objects(repo:Path,context:Mapping[str,Any])->tuple[dict[str,Any],list[dict[str,Any]],int]:
    release=context["release"]
    if context["technical"]:
        bundle_path=_safe(repo,release["technical_bundle_path"])
        if sha_file(bundle_path)!=release["technical_bundle_sha256"]:raise Verify09Error("BUNDLE_HASH")
        bundle,_=read_canonical(bundle_path)
        if bundle.get("identity_class")!="TECHNICAL_MIRROR_ONLY_NEVER_FORMAL_AUTHORITY":raise Verify09Error("BUNDLE_CLASS")
        if not release.get("simulate_formal_read_accounting",False):return bundle["objects"],bundle["authority_entries"],authority_read_count(context)
        fail_after=release.get("technical_fail_after_reads_verifier");objects={}
        for entry in bundle["authority_entries"]:
            data=canonical(bundle["objects"][entry["purpose"]]);count=record_authority_read(context,entry["purpose"],"TECHNICAL_MIRROR:"+entry["purpose"],sha_bytes(data))
            if fail_after==count:raise Verify09Error("INJECT_AUTHORITY_READ_FAILURE")
            objects[entry["purpose"]]=bundle["objects"][entry["purpose"]]
        return objects,bundle["authority_entries"],authority_read_count(context)
    else:
        allow_path=_safe(repo,release["authority_allowlist_path"])
        if sha_file(allow_path)!=release["authority_allowlist_sha256"]:raise Verify09Error("ALLOWLIST")
        allow=json.loads(allow_path.read_text());objects={}
        for entry in allow["entries"]:
            path=_safe(repo,entry["path"])
            with path.open("rb") as stream:
                record_authority_read(context,entry["purpose"],entry["path"],entry["sha256"]);data=stream.read()
            if sha_bytes(data)!=entry["sha256"]:raise Verify09Error("AUTHORITY_HASH")
            objects[entry["purpose"]]=pointer(json.loads(data.decode("utf-8")),entry["pointer"])
        return objects,allow["entries"],authority_read_count(context)


def subject_paths()->list[str]:
    return [f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in range(1,6)]+[f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES]+["static_audit.json","generation_terminal.json","batch_index.json"]


def create_subject_seal(stage:Path,context:Mapping[str,Any])->tuple[dict[str,Any],str]:
    paths=subject_paths();entries=[{"path":rel,"sha256":sha_file(stage/rel)} for rel in paths];digest=sha_value({"domain":"GEN-ENC-FAST-B1-REPAIR-09-VERIFICATION-SUBJECT-v1","entries":entries})
    value={"schema_version":"gen_enc_fast_b1_repair_09_verification_subject_seal_v1","record_kind":"IMMUTABLE_INDEPENDENT_VERIFICATION_SUBJECT_SEAL","repair_id":REPAIR,**_file_binding(context["release"]),"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"],"subject_count":27,"subject_entries":entries,"subject_digest":digest,"verification_nonce":sha_value({"run_id":context["run_id"],"subject_digest":digest,"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"]}),"final_test_read":False};_validate(value,context["schemas"],"verification_subject_seal")
    path=context["roots_resolved"]["side_records"]/SUBJECT_SEAL_PATH;path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open("xb") as stream:stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    except FileExistsError as exc:raise Verify09Error("SUBJECT_SEAL_ALREADY_EXISTS") from exc
    return value,sha_file(path)


def verify_stage(stage:Path,objects:Mapping[str,Any],entries:Sequence[Mapping[str,Any]],context:Mapping[str,Any])->dict[str,Any]:
    pending=set(_artifacts())-{"verifier_terminal.json","publication_terminal.json"}
    if {p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()}!=pending:raise Verify09Error("PENDING_GRAPH")
    members=[json.loads((stage/f"members/{PREFIX[f]}_{i:02d}.json").read_text()) for f in FAMILIES for i in range(1,6)]
    for member in members:_validate(member,context["schemas"],"member_identity")
    binding={k:context[k] for k in ("projection_contract_sha256","dependency_matrix_sha256","dependency_structure_sha256")};result=verify_members(members,objects,entries,context["projection"],binding)
    for family in FAMILIES:
        manifest=json.loads((stage/f"partial_manifests/{PREFIX[family]}.json").read_text());_validate(manifest,context["schemas"],"partial_family_manifest");selected=[m for m in members if m["family_id"]==family];expected=[{"member_id":m["member_id"],"path":f"members/{m['member_id']}.json","sha256":sha_file(stage/f"members/{m['member_id']}.json"),"static_status":m["static_status"],"failure_slot_retained":True} for m in selected]
        if manifest["member_entries"]!=expected or manifest["slot_ordinals"]!=[1,2,3,4,5]:raise Verify09Error("MANIFEST_GRAPH")
    index=json.loads((stage/"batch_index.json").read_text());audit=json.loads((stage/"static_audit.json").read_text())
    _validate(index,context["schemas"],"batch_index");_validate(audit,context["schemas"],"static_audit");_validate(json.loads((stage/"generation_terminal.json").read_text()),context["schemas"],"generation_terminal")
    expected_sums="".join(f"{sha_file(p)}  {p.relative_to(stage).as_posix()}\n" for p in sorted(stage.rglob("*")) if p.is_file() and p.name!="SHA256SUMS.txt")
    if (stage/"SHA256SUMS.txt").read_text(encoding="ascii")!=expected_sums:raise Verify09Error("PENDING_SHA256SUMS")
    for key,want in (("mode",MODE),("projection_contract_path",PROJECTION_PATH),("projection_contract_sha256",context["projection_contract_sha256"]),("dependency_matrix_path",DEPENDENCY_PATH),("dependency_matrix_sha256",context["dependency_matrix_sha256"]),("dependency_structure_sha256",context["dependency_structure_sha256"]),("member_paths",[f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in range(1,6)])):
        if index.get(key)!=want:raise Verify09Error("INDEX:"+key)
    if audit.get("member_count")!=20 or len(audit.get("member_paths",[]))!=20:raise Verify09Error("AUDIT")
    index["verification_complete"]=True;atomic_json(stage/"batch_index.json",index);seal,seal_sha=create_subject_seal(stage,context)
    subject_binding={"verification_subject_seal_path":SUBJECT_SEAL_PATH,"verification_subject_seal_sha256":seal_sha,"verification_subject_digest":seal["subject_digest"],"verification_subject_count":27}
    report={"schema_version":"gen_enc_fast_b1_repair_09_independent_verification_v1","record_kind":"INDEPENDENT_VERIFICATION","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"status":"PASS","verified_member_count":20,"verified_manifest_count":4,"authority_read_count":context["authority_read_count"],"artifact_count":31,"checks":["TYPED_CAD_349_LEAVES","20_MEMBER_DEEP_RECOMPUTE","31_GRAPH_ZERO_UNLISTED"],"resealed":True,**subject_binding,"projection_contract_path":PROJECTION_PATH,"projection_contract_sha256":context["projection_contract_sha256"],"dependency_matrix_path":DEPENDENCY_PATH,"dependency_matrix_sha256":context["dependency_matrix_sha256"],"dependency_structure_sha256":context["dependency_structure_sha256"],"mode":MODE,"claim_ceiling":CLAIM,"final_test_read":False};_validate(report,context["schemas"],"independent_verification");atomic_json(stage/"independent_verification.json",report)
    verifier_terminal={"schema_version":"gen_enc_fast_b1_repair_09_verifier_terminal_v1","record_kind":"VERIFIED_STAGING_NON_PUBLICATION","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"status":"VERIFIED_RESEALED_AWAITING_PUBLICATION","authority_read_count":context["authority_read_count"],"verified_member_count":20,"artifact_count":31,"publication_started":False,"success_terminal_written":False,**subject_binding,"claim_ceiling":CLAIM,"final_test_read":False};_validate(verifier_terminal,context["schemas"],"verifier_terminal");atomic_json(stage/"verifier_terminal.json",verifier_terminal)
    publication={"schema_version":"gen_enc_fast_b1_repair_09_publication_terminal_v1","record_kind":"PUBLICATION_INTENT_NON_SUCCESS","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"status":"AWAITING_MULTI_TARGET_ATOMIC_PUBLICATION","target_count":31,"published_count":0,"commit_pointer_written":False,"success_terminal_written":False,"claim_ceiling":CLAIM,"final_test_read":False};atomic_json(stage/"publication_terminal.json",publication)
    (stage/"SHA256SUMS.txt").write_text("".join(f"{sha_file(p)}  {p.relative_to(stage).as_posix()}\n" for p in sorted(stage.rglob("*")) if p.is_file() and p.name!="SHA256SUMS.txt"),encoding="ascii",newline="\n")
    if len([p for p in stage.rglob("*") if p.is_file()])!=31:raise Verify09Error("VERIFIED_CARDINALITY")
    return {**result,"artifact_count":31,"status":"VERIFIED_RESEALED_NOT_PUBLISHED"}


def write_phase_a_handoff(stage:Path,context:Mapping[str,Any])->dict[str,Any]:
    roots=context["roots_resolved"]
    for name in ("run","pointer","success","failure","journal"):
        if roots[name].exists():raise Verify09Error("PHASE_A_ZERO_PUBLICATION:"+name)
    logical=_artifacts();graph_entries=[{"path":rel,"sha256":sha_file(stage/rel)} for rel in logical]
    seal_path=roots["side_records"]/SUBJECT_SEAL_PATH;seal,_=read_canonical(seal_path);_validate(seal,context["schemas"],"verification_subject_seal")
    manifest=context["command_manifest"];argv=[next(x for x in manifest["entries"] if x["command"]==command)["argv_after_python"] for command in PHASE_A_COMMANDS]
    value={"schema_version":"gen_enc_fast_two_phase_guardian_phase_a_handoff_v1","record_kind":"CANONICAL_PHASE_A_VERIFIED_HANDOFF","state":"PHASE_A_VERIFIED_HANDOFF_STOP","terminal_state":"VERIFIED_STAGING_AWAITING_GUARDIAN_POSTERIOR_ANCHOR","repair_id":REPAIR,"task_id":TASK_ID,"phase_a_task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"mode":MODE,"claim_ceiling":CLAIM,"phase_a_release_path":context["phase_a_release_path"],"phase_a_release_sha256":context["release_sha256"],"phase_a_attestation_path":context["phase_a_attestation_path"],"phase_a_attestation_sha256":context["attestation_sha256"],"phase_a_dispatch_id":context["release"]["phase_a_dispatch_id"],"phase_a_commands_exact":list(PHASE_A_COMMANDS),"phase_a_permissions":{"preflight":True,"generate_staging":True,"independent_verify":True,"publish":False,"recover":False,"package_results":False},"phase_a_exact_argv":argv,"roots":context["roots"],"verification_subject_seal_path":context["roots"]["side_records"]+"/"+SUBJECT_SEAL_PATH,"verification_subject_seal_sha256":sha_file(seal_path),"verification_subject_digest":seal["subject_digest"],"verification_subject_count":27,"independent_report_path":context["roots"]["staging"]+"/independent_verification.json","independent_report_sha256":sha_file(stage/"independent_verification.json"),"verifier_terminal_path":context["roots"]["staging"]+"/verifier_terminal.json","verifier_terminal_sha256":sha_file(stage/"verifier_terminal.json"),"artifact_graph_count":31,"artifact_graph_entries":graph_entries,"artifact_graph_digest":sha_value({"domain":"GEN-ENC-FAST-PHASE-A-31-GRAPH-v1","entries":graph_entries}),"sha256sums_sha256":sha_file(stage/"SHA256SUMS.txt"),"authority_read_count":authority_read_count(context),"source_manifest_sha256":context["source_manifest_sha256"],"schema_manifest_sha256":context["schema_manifest_sha256"],"command_manifest_sha256":context["command_manifest_sha256"],"projection_contract_path":PROJECTION_PATH,"projection_contract_sha256":context["projection_contract_sha256"],"dependency_matrix_path":DEPENDENCY_PATH,"dependency_matrix_sha256":context["dependency_matrix_sha256"],"dependency_structure_sha256":context["dependency_structure_sha256"],"formal_publication_count":0,"commit_pointer_count":0,"success_package_count":0,"final_test_read":False}
    value.update(authority_allowlist_path=context["authority_allowlist_path"],authority_allowlist_sha256=context["authority_allowlist_sha256"],source_manifest_path=context["source_manifest_path"],schema_manifest_path=context["schema_manifest_path"],command_manifest_path=context["command_manifest_path"],guardian_two_phase_contract_path=GUARDIAN_TWO_PHASE_CONTRACT_PATH,guardian_two_phase_contract_sha256=GUARDIAN_TWO_PHASE_CONTRACT_SHA256,guardian_two_phase_review_path=GUARDIAN_TWO_PHASE_REVIEW_PATH,guardian_two_phase_review_sha256=GUARDIAN_TWO_PHASE_REVIEW_SHA256,advisor_b_final_review_path=context["advisor_b_final_review_path"],advisor_b_final_review_sha256=context["advisor_b_final_review_sha256"],advisor_b_ledger_snapshot_path=context["advisor_b_ledger_snapshot_path"],advisor_b_ledger_snapshot_sha256=context["advisor_b_ledger_snapshot_sha256"])
    value["handoff_digest"]=sha_value({"domain":"GEN-ENC-FAST-TWO-PHASE-HANDOFF-v1","payload":value});_validate(value,context["schemas"],"phase_a_handoff")
    path=roots["side_records"]/PHASE_A_HANDOFF_PATH
    try:
        with path.open("xb") as stream:stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    except FileExistsError as exc:raise Verify09Error("PHASE_A_HANDOFF_ALREADY_EXISTS") from exc
    return value


def write_failure(context:Mapping[str,Any],reason:str)->Path:
    roots=context["roots_resolved"];success=roots["success"]/"VERIFIED_SUCCESS.json";failure=roots["failure"]/"FAIL_CLOSED.json"
    if success.exists():raise Verify09Error("SUCCESS_FORBIDS_FAILURE")
    if failure.exists():return failure
    stage=roots["staging"];members=len(list((stage/"members").glob("*.json"))) if (stage/"members").exists() else 0;artifacts=len([p for p in stage.rglob("*") if p.is_file()]) if stage.exists() else 0
    value={"schema_version":"gen_enc_fast_b1_repair_09_package_terminal_v1","record_kind":"FAIL_CLOSED","terminal_phase":"PHASE_A","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"mode":MODE,"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"],"projection_contract_path":PROJECTION_PATH,"projection_contract_sha256":context["projection_contract_sha256"],"dependency_matrix_path":DEPENDENCY_PATH,"dependency_matrix_sha256":context["dependency_matrix_sha256"],"dependency_structure_sha256":context["dependency_structure_sha256"],"status":"TECHNICAL_FAIL_CLOSED","reason":reason,"honest_counts":{"authority_reads":context["authority_read_count"],"members":members,"artifacts":artifacts,"published":0},"commit_pointer_sha256":None,"package_terminal_count":1,"claim_ceiling":CLAIM,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False};_validate(value,context["schemas"],"package_terminal");failure.parent.mkdir(parents=True,exist_ok=True)
    with failure.open("xb") as stream:stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    return failure


def parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser();p.add_argument("verify",choices=["verify"])
    for name in ("repo-root","release","guardian-attestation","phase-a-dispatch","schema-root","projection-contract","dependency-matrix"):p.add_argument("--"+name,required=True,type=Path)
    return p


def _check_cli_paths(ns:argparse.Namespace,repo:Path,context:Mapping[str,Any],raw_argv:Sequence[str])->None:
    if ns.projection_contract.as_posix()!=PROJECTION_PATH or ns.dependency_matrix.as_posix()!=DEPENDENCY_PATH:raise Verify09Error("ARGV_PROJECTION_PATH")
    if ns.projection_contract.resolve()!=_safe(repo,context["projection_contract_path"]) or ns.dependency_matrix.resolve()!=_safe(repo,context["dependency_matrix_path"]):raise Verify09Error("ARGV_PROJECTION_RESOLUTION")
    expected={"repo_root":Path("."),"release":Path(context["phase_a_release_path"]),"guardian_attestation":Path(context["phase_a_attestation_path"]),"phase_a_dispatch":Path(context["phase_a_dispatch_path"])}
    if any(getattr(ns,key)!=value for key,value in expected.items()) or (not context["technical"] and ns.schema_root!=Path("schemas/gen_enc/b1_repair_09")):raise Verify09Error("ARGV_CONTROL_PATH_EXACT")
    row=next((x for x in context["command_manifest"]["entries"] if x["command"]=="verify"),None);expected_argv=[] if row is None else list(row["argv_after_python"][2:]);replacements={"<GUARDIAN_PHASE_A_RELEASE_EXACT_PATH>":context["phase_a_release_path"],"<GUARDIAN_PHASE_A_ATTESTATION_EXACT_PATH>":context["phase_a_attestation_path"],"<CONTROLLER_PHASE_A_DISPATCH_EXACT_PATH>":context["phase_a_dispatch_path"]};expected_argv=[replacements.get(x,x) for x in expected_argv]
    if context["technical"]:expected_argv=[str(ns.schema_root) if x=="schemas/gen_enc/b1_repair_09" else x for x in expected_argv]
    if row is None or list(raw_argv)!=expected_argv:raise Verify09Error("ARGV_BYTE_EXACT")


def main(argv:Sequence[str]|None=None)->int:
    raw_argv=list(sys.argv[1:] if argv is None else argv);ns=parser().parse_args(raw_argv);context=None
    try:
        repo=ns.repo_root.resolve();context=gate(repo,ns.release.resolve(),ns.guardian_attestation.resolve(),ns.schema_root.resolve(),ns,raw_argv);objects,entries,reads=load_objects(repo,context);context={**context,"authority_read_count":reads};result=verify_stage(context["roots_resolved"]["staging"],objects,entries,context);handoff=write_phase_a_handoff(context["roots_resolved"]["staging"],context);print(json.dumps({**result,"status":"VERIFIED_STAGING_AWAITING_GUARDIAN_POSTERIOR_ANCHOR","handoff_digest":handoff["handoff_digest"],"formal_publication_count":0,"commit_pointer_count":0,"success_package_count":0},sort_keys=True));return 0
    except BaseException as exc:
        if context is not None:
            context={**context,"authority_read_count":authority_read_count(context)};write_failure(context,type(exc).__name__+":"+str(exc))
        print(json.dumps({"status":"FAIL_CLOSED","error":type(exc).__name__+":"+str(exc),"authority_read_count":0 if context is None else context["authority_read_count"]},sort_keys=True),file=sys.stderr);return 2


if __name__=="__main__":raise SystemExit(main())
