"""Standalone Repair-10 driver with short, run-bound Phase-A controls."""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.gen_enc_b1_repair_10 import cad_projection_driver as cad
import jsonschema

from scripts.gen_enc_b1_repair_10.primitives import atomic_json, canonical, pointer, read_canonical, sha_bytes, sha_file, sha_value

TASK_ID="01a049a7-15ca-79e1-92a2-d3822ba8609d";BATCH_ID="B1";REPAIR="PRE-RELEASE-REPAIR-10"
FAMILIES=("HAND_DESIGNED","NEAR_INDEPENDENT","FIXED_SEED_RANDOM_DISORDERED","PHYSICS_METAMATERIAL_INSPIRED")
PREFIX=dict(zip(FAMILIES,("HAND","NEAR","RANDOM","PHYSICS")));SECTORS=("0","90","180","270")
RANDOM_AXES=("q0","q90","q180","edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270","loss_0","loss_90","loss_180","loss_270")
PHYSICS_AXES=("q0","q90","q180","external_0","external_90","external_180","external_270","ring_0_90","ring_90_180","ring_180_270","ring_270_0","loss_0","loss_90","loss_180","loss_270")
CLAIM="BATCH_LOCAL_IDENTITY_COMPLETE_CAD_STATIC_AND_TECHNICAL_VALIDITY_ONLY";MASK=(1<<64)-1;GAMMA=0x9E3779B97F4A7C15
RUN_DOMAIN=b"GEN-ENC-FAST-B1-PRE-RELEASE-REPAIR-10-RUN-ID-v1"
PROJECTION_PATH="outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_10/cad_typed_projection_contract.json"
DEPENDENCY_PATH="outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_10/cad_leaf_dependency_matrix.json"
SUBJECT_SEAL_PATH="VERIFICATION_SUBJECT_SEAL.json"
MODE="FORMAL_B1_EXACT_20_TYPED_CAD";COMMANDS=("preflight","generate-staging","verify","publish","recover","package-results")
PHASE_A_COMMANDS=("preflight","generate-staging","verify");PHASE_B_COMMANDS=("publish","recover","package-results")
PHASE_A_PERMISSIONS={"preflight":True,"generate_staging":True,"independent_verify":True,"publish":False,"recover":False,"package_results":False}
PHASE_B_PERMISSIONS={"preflight":False,"generate_staging":False,"independent_verify":False,"publish":True,"recover":True,"package_results":True}
PHASE_A_HANDOFF_PATH="PHASE_A_VERIFIED_HANDOFF.json"
PHASE_B_AUTH_PATH="outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/GEN_ENC_FAST_PHASE_B/GEN_ENC_FAST_B1_PHASE_B_AUTHORIZATION.json"
PHASE_B_ATTESTATION_PATH="outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/GEN_ENC_FAST_PHASE_B/GEN_ENC_FAST_B1_PHASE_B_ONE_WAY_ATTESTATION.json"
PHASE_B_DISPATCH_PATH="control/PHASE_B_DISPATCH_AUTHORIZATION.json"
GUARDIAN_TWO_PHASE_CONTRACT_PATH="outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/contracts/GEN_ENC_FAST_B1_B4_TWO_STAGE_POSTERIOR_ANCHOR_CONTRACT.json";GUARDIAN_TWO_PHASE_CONTRACT_SHA256="526d64e67ddbdb6e15ea2fb0a0f0bb84aae4e90a55f3d9bde44237f34c5027c2"
GUARDIAN_TWO_PHASE_REVIEW_PATH="outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_FAST_B1_B4_TWO_STAGE_POSTERIOR_ANCHOR_CONTRACT_REVIEW.json";GUARDIAN_TWO_PHASE_REVIEW_SHA256="c3d21497f26744219656b80de1e639027fee48b2c96171f593381926d7220edd"
GUARDIAN_SIGNING_CHECK_PATH="outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/signing_checks/GEN_ENC_FAST_B1_REPAIR_07_PHASE_A_CONTROL_SIGNING_FAIL_CLOSED.json";GUARDIAN_SIGNING_CHECK_SHA256="3b98531d8ab333920f0551a88398feab60bb0029819705c69803de9c39b0621d"
ROLLOVER_SIGNING_FAIL_PATH="outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/signing_checks/GEN_ENC_FAST_B1_REPAIR_08_ENTIRELY_NEW_RUN_CONTROL_SIGNING_FAIL_CLOSED.json";ROLLOVER_SIGNING_FAIL_SHA256="9ba0dc07067b5086e3f813650b1791ff4f05e8c24ec92025f341d8fa5dcdbe6f"
ROLLOVER_REGISTRATION_PATH="outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/technical_repair_events/B1_REPAIR_09_CONTROL_PATH_ROLLOVER_REGISTRATION_20260829_001.json";ROLLOVER_REGISTRATION_SHA256="55e38765e4f1805b1422893a9965744c5d23556182a20b9bd6a17709d49b300f"
REVOKED_RUN_ID="dd45162503eabf764ef91fb4cdf198ed454cc89283616d169433c2a83df0e613";REVOKED_DISPATCH_ID="80042c4cdecaaa698b6ecd31745bcbbb16c2ba7b0bb645d6c93cf1bc07780d6f"
PATH_ADDRESSABILITY_FAIL_PATH="outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/signing_checks/GEN_ENC_FAST_B1_REPAIR_09_ENTIRELY_NEW_RUN_CONTROL_SIGNING_FAIL_CLOSED_AND_REVOCATION.json";PATH_ADDRESSABILITY_FAIL_SHA256="308a7875a07384958e12dda2557b69bab7765819afb43fcb5d42d20c46e932e7"
R10_REGISTRATION_PATH="outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/technical_repair_events/B1_REPAIR_10_SHORT_CONTROL_PATH_ADDRESSABILITY_REGISTRATION_20260829_001.json";R10_REGISTRATION_SHA256="0d8493b16f6ee19734b0a655deb8f72ce9ea7900356fd4d478d8a30f201a8011"
R09_REVOKED_RUN_ID="0135cb06febe7bf5aa7beca053d3b45c42dbeddb1c1ef9bffe2b882cdd8f606d";R09_REVOKED_DISPATCH_ID="c0a54eba939263521c928904599fa67ce8c930f303d50467dc4b1eaf4960179f"
REVOKED_RUN_IDS=frozenset((REVOKED_RUN_ID,R09_REVOKED_RUN_ID));REVOKED_DISPATCH_IDS=frozenset((REVOKED_DISPATCH_ID,R09_REVOKED_DISPATCH_ID))
CONTROL_ROOT="control/gen_enc_b1/phase_a";MAX_WORKSPACE_PREFIX_CHARS=120;CONTROL_RELATIVE_CHARS=98;MAX_CONTROL_ABSOLUTE_CHARS=219;WINDOWS_PATH_SAFETY_LIMIT=259
ADVISOR_B_FINAL_REVIEW_PATH="outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_FAST_B1_PRE_RELEASE_REPAIR_07_TWO_PHASE_MECHANICAL_SPLIT_FINAL_REREVIEW.json";ADVISOR_B_FINAL_REVIEW_SHA256="98cf8df05267ff4828a906b0e4fc0083c91d4a456aea51e608235519798378f0"
ADVISOR_LEDGER_SNAPSHOT_PROTOCOL_PATH="outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/contracts/REVIEW_SPECIFIC_IMMUTABLE_LEDGER_SNAPSHOT_PROTOCOL.json";ADVISOR_LEDGER_SNAPSHOT_PROTOCOL_SHA256="47ee5e6b7b4175a312add18fb47903a6d656bb0ce467487e766ce86ca6bfc63e"
R07_LEDGER_SNAPSHOT_ABSENCE_PATH="outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/stage_events/R07_FINAL_REVIEW_LEDGER_SNAPSHOT_ABSENCE_DISCLOSURE_20260829_001.json";R07_LEDGER_SNAPSHOT_ABSENCE_SHA256="0165e1716fea948a959ea3951627b9c63c2833c719ed3c9731a96236191e813c"
AUTHORITY_ALLOWLIST_PATH="outputs/gen_enc/GEN_ENC_FAST_START/fast_0_authority_batch_contract_freeze/authority_allowlist.json"


class Repair10Error(RuntimeError):pass


def derive_run_id(release:Mapping[str,Any])->str:
    clone=dict(release);clone["run_id"]="0"*64
    if "roots" in clone:clone["roots"]=exact_roots("0"*64,clone.get("record_kind")=="TECHNICAL_MIRROR_RELEASE")
    for key in ("phase_a_release_path","phase_a_attestation_path","phase_a_dispatch_path"):
        if key in clone:clone[key]=str(clone[key]).replace(str(release.get("run_id","")),"0"*64)
    return sha_bytes(RUN_DOMAIN+b"\n"+canonical(clone))


def _mix(x:int)->int:
    z=(x+GAMMA)&MASK;z=((z^(z>>30))*0xBF58476D1CE4E5B9)&MASK;z=((z^(z>>27))*0x94D049BB133111EB)&MASK
    return (z^(z>>31))&MASK


def _uniform(seed:int,index:int)->float:
    value=((_mix((seed+GAMMA*(index+1))&MASK)>>11)+.5)/(1<<53)
    return math.nextafter(1.0,0.0) if value==1 else value


def _permutation(seed:int,index:int)->list[int]:
    result=list(range(20))
    for i in range(19,0,-1):
        j=_mix((seed+GAMMA*(1+32*index+19-i))&MASK)%(i+1);result[i],result[j]=result[j],result[i]
    return result


def _groups(spec:Mapping[str,Any],axes:Sequence[str],names:Sequence[str])->dict[str,tuple[float,float]]:
    if tuple(spec.get("parameter_order",()))!=tuple(axes) or spec.get("member_count")!=20 or spec.get("dof")!=len(axes):raise Repair10Error("SPEC_AXES")
    result={}
    for item,name in zip(spec.get("parameters",[]),names):
        if set(item)!={"group","axes","bounds"} or item["group"]!=name or len(item["bounds"])!=2:raise Repair10Error("SPEC_GROUP")
        lo,hi=map(float,item["bounds"])
        if not lo<hi:raise Repair10Error("SPEC_BOUND")
        for axis in item["axes"]:
            if axis in result:raise Repair10Error("DUP_AXIS")
            result[axis]=(lo,hi)
    if tuple(result)!=tuple(axes):raise Repair10Error("GROUP_AXIS_ORDER")
    return result


def parameters(objects:Mapping[str,Any],family:str,ordinal:int)->dict[str,float]:
    if family in FAMILIES[:2]:
        row=objects["HAND_ROWS" if family==FAMILIES[0] else "NEAR_ROWS"][ordinal-1]
        result={"q0":float(row["volume_logit_0"]),"q90":float(row["volume_logit_90"]),"q180":float(row["volume_logit_180"]),"q270":float(row["derived_volume_logit_270"]),**{f"external_{s}":float(row[f"external_aperture_fraction_{s}"]) for s in SECTORS},**{f"loss_{s}":float(row[f"loss_fraction_{s}"]) for s in SECTORS}}
        result["central_mix" if family==FAMILIES[0] else "shared_alpha"]=float(row["central_mix_aperture_fraction" if family==FAMILIES[0] else "shared_coupling_alpha"]);return result
    if family==FAMILIES[2]:
        spec=objects["RANDOM_FAMILY_SPEC"];bounds=_groups(spec,RANDOM_AXES,("VOLUME_LOGIT","RECIPROCAL_EDGE_POSITIVE","LOSS"))
        if spec.get("uniform_algorithm")!={"interval":"OPEN_0_1_BINARY64","word_to_uniform":"((word>>11)+0.5)/2^53","one_guard":"nextafter(1.0,0.0)"} or spec.get("splitmix64",{}).get("gamma_hex")!="9e3779b97f4a7c15":raise Repair10Error("RANDOM_ALGORITHM")
        seed=int(objects["RANDOM_FIXED_SEEDS"][ordinal-1]);result={f"external_{s}":.5 for s in SECTORS}
        for index,axis in enumerate(RANDOM_AXES):
            lo,hi=bounds[axis];u=_uniform(seed,index);result[axis]=lo+(hi-lo)*u if index<3 or index>=9 else 0.0 if u<.5 else lo+(hi-lo)*(2*u-1)
        result["q270"]=-(result["q0"]+result["q90"]+result["q180"])/3;return result
    spec=objects["PHYSICS_FAMILY_SPEC_PARAMETERS_LHS"];bounds=_groups(spec,PHYSICS_AXES,("VOLUME_LOGIT","EXTERNAL_APERTURE","RING_COUPLING","LOSS"));master=int(objects["PHYSICS_MASTER_SEED"])
    if spec.get("lhs_algorithm")!=["STRATA=20","SAMPLE=(PERMUTATION[row]+0.5)/20","JITTER=false","FISHER_YATES_SPLITMIX64=i19_TO_1"] or spec.get("lhs_master_seed")!=master:raise Repair10Error("PHYSICS_ALGORITHM")
    result={}
    for index,axis in enumerate(PHYSICS_AXES):
        lo,hi=bounds[axis];result[axis]=lo+(hi-lo)*(_permutation(master,index)[ordinal-1]+.5)/20
    result["q270"]=-(result["q0"]+result["q90"]+result["q180"])/3;return result


def _components(nodes:Sequence[str],edges:Sequence[Mapping[str,Any]])->int:
    unseen=set(nodes);count=0
    while unseen:
        count+=1;stack=[unseen.pop()]
        while stack:
            node=stack.pop();neighbours=set()
            for edge in edges:
                if edge["weight"]>0 and edge["a"]==node:neighbours.add(edge["b"])
                if edge["weight"]>0 and edge["b"]==node:neighbours.add(edge["a"])
            for nxt in neighbours&unseen:unseen.remove(nxt);stack.append(nxt)
    return count


def derive_cad_evidence(family:str,params:Mapping[str,float],projection:Mapping[str,Any])->tuple[dict[str,Any],str]:
    v=projection["values"];rules=v["OWNERSHIP_RULE"]
    owners=[{"cell_id":x["cell_id"],"owner":x["owner"],"rule":rules["central"] if x["owner"]=="CENTRAL" else rules["sector"],"positive_overlap_volume_m3":float(x["positive_overlap_volume_m3"])} for x in v["OWNERSHIP_CELLS"]]
    z=float(v["GEOMETRY_SLOT_Z"]);slots=[{"slot_id":x["slot_id"],"sector":x["sector"],"owner_cell_id":x["owner_cell_id"],"coordinates_m":[float(x["coordinates_xy_m"][0]),float(x["coordinates_xy_m"][1]),z],"placement_status":"PLACED_OR_EXPLICIT_ZERO","width_m":float(x["width_m"])} for x in v["SLOT_ROWS"]]
    common=v["ROOT_COMMON"];bracket=list(map(float,v["ROOT_BRACKET"]));weights=[math.exp(float(params[f"q{s}"])) for s in SECTORS];roots=[]
    for sector,weight in zip(SECTORS,weights):
        target=float(v["GEOMETRY_VOLUME"])*float(v["GEOMETRY_TARGET_FRACTION"])*weight/sum(weights);low,high=bracket;trace=[]
        for iteration in range(common["iterations"]):
            mid=(low+high)/2;measured=float(common["fixed_volume_m3"])+float(common["linear_coefficient_m2"])*mid;trace.append({"iteration":iteration+1,"low_m":low,"high_m":high,"mid_m":mid,"measured_volume_m3":measured})
            if measured<target:low=mid
            else:high=mid
        root=(low+high)/2;measured=float(common["fixed_volume_m3"])+float(common["linear_coefficient_m2"])*root
        if abs(measured-target)>float(common["tolerance_m3"]):raise Repair10Error("ROOT_TOLERANCE")
        roots.append({"sector":sector,"domain_m":list(map(float,common["domain_m"])),"initial_bracket_m":bracket,"final_bracket_m":[low,high],"tolerance_m3":float(common["tolerance_m3"]),"iterations":common["iterations"],"trace":trace,"root_length_m":root,"target_volume_m3":target,"measured_volume_m3":measured,"residual_m3":measured-target})
    coord=v["U4_COORDINATES"];exceptions=[]
    for group in v["U4_OBJECTS"]:
        for item in group["exceptions"]:
            suffix=item["suffix"];exceptions.append({"exception_id":f"IFX_U4_{int(group['sector']):03d}_{suffix}","sector":group["sector"],"local_coordinates_m":[float(coord["x_m"]),float(coord["suffix_z_m"][suffix])],"feature_m":float(item["feature_m"]),"load_path_m":float(item["load_path_m"]),"participation":v["U4_PARTICIPATION"],"excluded_only_from":"GENERAL_MINIMA"})
    fields=v["STATIC_FIELDS"];features=[{"witness_id":x["witness_id"],"measured_m":float(x["measured_m"])} for x in fields["general_feature_candidates"]];loads=[{"witness_id":x["witness_id"],"measured_m":float(x["measured_m"])} for x in fields["general_load_candidates"]]
    graph=v["GRAPH_DEFINITION"];reduced=[{"edge_id":x["edge_id"],"a":x["a"],"b":x["b"],"weight":float(params.get(x["parameter_key"],0.0)),"active":float(params.get(x["parameter_key"],0.0))>0} for x in graph["reduced_edges"]];actual=[{"edge_id":x["edge_id"],"a":x["a"],"b":x["b"],"weight":float(x["positive_area_m2"]),"positive_area_m2":float(x["positive_area_m2"])} for x in graph["actual_edges"]]
    zero=v["ZERO_EDGE_RULE"];zeros=[{"edge_id":x["edge_id"],"exact_value":zero["exact_zero"],"generator_branch":zero["branch"],"verified_exact_zero":True} for x in reduced if family==zero["family"] and x["weight"]==zero["exact_zero"]]
    semantic_inputs={"ownership_transforms":v["OWNERSHIP_ALGORITHMS"],"slot_sector_order":v["SLOT_SECTOR_ORDER"],"slot_mapping":v["SLOT_MAPPING"],"slot_required_fields":v["SLOT_BURDEN"],"root_family_rules":v["ROOT_FAMILIES"],"root_domain_proof":v["ROOT_DOMAIN"],"root_derived_proof":v["ROOT_DERIVED_PROOF"],"root_independent_proof":v["ROOT_INDEPENDENT_PROOF"],"minima_fail_rules":v["STATIC_FAIL_RULES"],"solid_metrics":v["SOLID_METRICS"],"solid_eligible_pair":v["SOLID_ELIGIBLE_PAIR"],"graph_terms":v["GRAPH_TERMS"]}
    approval={"U1":v["APPROVAL_U1"],"U2":v["APPROVAL_U2"],"U3":v["APPROVAL_U3"],"mandatory_carry_forward":v["APPROVAL_CARRY"]}
    evidence={"schema_version":"gen_enc_fast_b1_repair_10_member_cad_static_v1","ownership_cells":owners,"slot_placements":slots,"volume_root_witnesses":roots,"u4_exception_witnesses":exceptions,"general_minima":{"feature_candidates":features,"load_path_candidates":loads,"measured_minimum_feature_m":min(x["measured_m"] for x in features),"measured_minimum_load_path_m":min(x["measured_m"] for x in loads),"feature_witness_ids":[x["witness_id"] for x in features if x["measured_m"]==min(y["measured_m"] for y in features)],"load_path_witness_ids":[x["witness_id"] for x in loads if x["measured_m"]==min(y["measured_m"] for y in loads)]},"exception_minima":{"measured_minimum_feature_m":min(float(x) for x in fields["exception_feature_candidates"]),"measured_minimum_load_path_m":min(float(x) for x in fields["exception_load_candidates"]),"exception_ids":[x["exception_id"] for x in exceptions]},"reduced_graph":{"nodes":graph["reduced_nodes"],"edges":reduced,"component_count":_components(graph["reduced_nodes"],reduced)},"actual_fluid_graph":{"nodes":graph["actual_nodes"],"edges":actual,"component_count":_components(graph["actual_nodes"],actual)},"random_zero_edge_witnesses":zeros,"thresholds":{"minimum_general_feature_m":float(fields["minimum_general_feature_m"]),"minimum_general_load_path_m":float(fields["minimum_general_load_path_m"])},"semantic_derivation_inputs":semantic_inputs,"typed_projection_approval":approval,"thresholds_copied_as_measurements":False,"complete_witness_semantics":True}
    eligible=evidence["general_minima"]["measured_minimum_feature_m"]>=evidence["thresholds"]["minimum_general_feature_m"] and evidence["general_minima"]["measured_minimum_load_path_m"]>=evidence["thresholds"]["minimum_general_load_path_m"] and evidence["actual_fluid_graph"]["component_count"]==1
    return evidence,"ELIGIBLE" if eligible else "COST_INELIGIBLE"


def members_from_authority(objects:Mapping[str,Any],entries:Sequence[Mapping[str,Any]],contract:Mapping[str,Any],binding:Mapping[str,Any])->list[dict[str,Any]]:
    projected=cad.project(objects,entries,contract)
    if projected["projection_contract_sha256"]!=binding["projection_contract_sha256"] or projected["dependency_matrix_sha256"]!=binding["dependency_structure_sha256"]:raise Repair10Error("PROJECTION_DEPENDENCY_BINDING")
    result=[]
    for family in FAMILIES:
        for ordinal in range(1,6):
            params=parameters(objects,family,ordinal);evidence,status=derive_cad_evidence(family,params,projected)
            result.append({"schema_version":"gen_enc_fast_b1_repair_10_member_identity_v1","record_kind":"BATCH_LOCAL_MEMBER_IDENTITY_TYPED_CAD_DERIVED","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"family_id":family,"member_id":f"{PREFIX[family]}_{ordinal:02d}","slot_ordinal":ordinal,"failure_slot_retained":True,"parameter_order":list(params),"parameters":params,"cad_static_evidence":evidence,"typed_projection_provenance":{"projection_contract_path":PROJECTION_PATH,"projection_contract_sha256":binding["projection_contract_sha256"],"dependency_matrix_path":DEPENDENCY_PATH,"dependency_matrix_sha256":binding["dependency_matrix_sha256"],"dependency_structure_sha256":binding["dependency_structure_sha256"],"semantic_leaf_count":projected["semantic_leaf_count"]},"static_status":status,"claim_ceiling":CLAIM,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False})
    return result


def pre_read_binding(record:Mapping[str,Any],expected:Mapping[str,Any])->None:
    for key in ("task_id","batch_id","run_id","projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256"):
        if record.get(key)!=expected.get(key):raise Repair10Error("PRE_READ_BINDING:"+key)


def _safe(repo:Path,value:str)->Path:
    path=(repo/value).resolve()
    if path==repo or not path.is_relative_to(repo):raise Repair10Error("PATH_CONTAINMENT")
    return path


def load_schemas(root:Path)->dict[str,Any]:
    result={p.name.removesuffix(".schema.json"):json.loads(p.read_text()) for p in root.glob("*.schema.json")}
    for schema in result.values():jsonschema.Draft202012Validator.check_schema(schema)
    return result


def validate(value:Any,schemas:Mapping[str,Any],name:str)->None:
    try:jsonschema.Draft202012Validator(schemas[name]).validate(value)
    except jsonschema.ValidationError as exc:raise Repair10Error("SCHEMA_"+name+":"+exc.message) from exc


def exact_roots(run_id:str,technical:bool=False)->dict[str,str]:
    base=(".technical_b1_repair_10/" if technical else "outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_10_runs/")+run_id
    roots={x:f"{base}/{x}" for x in ("staging","run","journal","success","failure","side_records")};roots["pointer"]=(f".technical_b1_repair_10_commit/{run_id}" if technical else f"outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_10_commit/{run_id}");return roots


def exact_artifacts()->list[str]:
    return [f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in range(1,6)]+[f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES]+["batch_index.json","static_audit.json","independent_verification.json","SHA256SUMS.txt","generation_terminal.json","verifier_terminal.json","publication_terminal.json"]


def _hash_lines(root:Path)->bytes:
    return "".join(f"{sha_file(p)}  {p.relative_to(root).as_posix()}\n" for p in sorted(root.rglob("*")) if p.is_file() and p.name!="SHA256SUMS.txt").encode("ascii")


def _binding(record:Mapping[str,Any])->dict[str,Any]:
    keys=("task_id","batch_id","run_id","mode","commands_exact","guardian_two_phase_contract_path","guardian_two_phase_contract_sha256","guardian_two_phase_review_path","guardian_two_phase_review_sha256","advisor_b_final_review_path","advisor_b_final_review_sha256","advisor_b_ledger_snapshot_path","advisor_b_ledger_snapshot_sha256","phase_a_commands_exact","phase_a_permissions","phase_a_release_path","phase_a_attestation_path","phase_a_dispatch_id","phase_a_dispatch_path","guardian_phase_b_authorization_path","guardian_phase_b_attestation_path","phase_b_dispatch_path","authority_allowlist_path","authority_allowlist_sha256","verification_subject_seal_path","projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256","source_manifest_path","source_manifest_sha256","schema_manifest_path","schema_manifest_sha256","command_manifest_path","command_manifest_sha256","roots")
    return {k:record[k] for k in keys}


def _validate_cli_control_addressability(repo:Path,release_path:Path,attestation_path:Path,dispatch_path:Path|None)->None:
    repo=repo.resolve()
    if len(str(repo))>MAX_WORKSPACE_PREFIX_CHARS:raise Repair10Error("CONTROL_WORKSPACE_PREFIX_BUDGET")
    supplied={"release":release_path,"attestation":attestation_path}
    if dispatch_path is not None:supplied["dispatch"]=dispatch_path
    roles={"release":"R.json","attestation":"A.json","dispatch":"D.json"};seen=[];run_ids=set()
    for key,path in supplied.items():
        absolute=path.resolve()
        if len(str(absolute))>MAX_CONTROL_ABSOLUTE_CHARS or len(str(absolute))>=WINDOWS_PATH_SAFETY_LIMIT:raise Repair10Error("CONTROL_MAX_PATH:"+key)
        try:relative=absolute.relative_to(repo).as_posix()
        except ValueError as exc:raise Repair10Error("CONTROL_PATH_CONTAINMENT") from exc
        match=re.fullmatch(rf"{CONTROL_ROOT}/([0-9a-f]{{64}})/{roles[key]}",relative)
        if match is None or len(relative)!=CONTROL_RELATIVE_CHARS:raise Repair10Error("CONTROL_SHORT_PATH:"+key)
        run_ids.add(match.group(1));seen.append(relative.casefold())
    if len(run_ids)!=1 or len(seen)!=len(set(seen)):raise Repair10Error("CONTROL_PATH_ROLE_OR_RUN_COLLISION")


def _validate_rollover_paths(release:Mapping[str,Any],release_path:Path,attestation_path:Path,dispatch_path:Path|None,repo:Path,technical:bool)->None:
    rid=release.get("run_id");paths={"release":release.get("phase_a_release_path"),"attestation":release.get("phase_a_attestation_path"),"dispatch":release.get("phase_a_dispatch_path")}
    if not isinstance(rid,str) or not re.fullmatch(r"[0-9a-f]{64}",rid) or rid in REVOKED_RUN_IDS:raise Repair10Error("ROLLOVER_RUN_ID")
    patterns={"release":rf"{CONTROL_ROOT}/{rid}/R\.json","attestation":rf"{CONTROL_ROOT}/{rid}/A\.json","dispatch":rf"{CONTROL_ROOT}/{rid}/D\.json"}
    for key,value in paths.items():
        if not isinstance(value,str) or "\\" in value or value.startswith("/") or ".." in value.split("/") or not re.fullmatch(patterns[key],value):raise Repair10Error("ROLLOVER_PATH:"+key)
    if len({v.casefold() for v in paths.values()})!=3:raise Repair10Error("ROLLOVER_CASEFOLD_COLLISION")
    try:actual_release=release_path.resolve().relative_to(repo).as_posix();actual_att=attestation_path.resolve().relative_to(repo).as_posix();actual_dispatch=None if dispatch_path is None else dispatch_path.resolve().relative_to(repo).as_posix()
    except ValueError as exc:raise Repair10Error("ROLLOVER_PATH_CONTAINMENT") from exc
    if actual_release!=paths["release"] or actual_att!=paths["attestation"]:raise Repair10Error("ROLLOVER_ACTUAL_PATH_BINDING")
    if actual_dispatch is not None and actual_dispatch!=paths["dispatch"]:raise Repair10Error("ROLLOVER_DISPATCH_CLI_BINDING")
    if release.get("phase_a_dispatch_id") in REVOKED_DISPATCH_IDS:raise Repair10Error("ROLLOVER_DISPATCH_ID")


def _validate_signing_authority_bytes(repo:Path,release:Mapping[str,Any],technical:bool)->None:
    fixed=((PATH_ADDRESSABILITY_FAIL_PATH,PATH_ADDRESSABILITY_FAIL_SHA256,"PATH_ADDRESSABILITY_FAIL_RECORD_BYTES"),(R10_REGISTRATION_PATH,R10_REGISTRATION_SHA256,"R10_REGISTRATION_BYTES"),(ROLLOVER_SIGNING_FAIL_PATH,ROLLOVER_SIGNING_FAIL_SHA256,"ROLLOVER_SIGNING_FAIL_RECORD_BYTES"),(ROLLOVER_REGISTRATION_PATH,ROLLOVER_REGISTRATION_SHA256,"ROLLOVER_REGISTRATION_BYTES"),(GUARDIAN_SIGNING_CHECK_PATH,GUARDIAN_SIGNING_CHECK_SHA256,"GUARDIAN_SIGNING_FAIL_RECORD_BYTES"),(ADVISOR_B_FINAL_REVIEW_PATH,ADVISOR_B_FINAL_REVIEW_SHA256,"R07_FINAL_REVIEW_PROVENANCE_BYTES"),(ADVISOR_LEDGER_SNAPSHOT_PROTOCOL_PATH,ADVISOR_LEDGER_SNAPSHOT_PROTOCOL_SHA256,"LEDGER_SNAPSHOT_PROTOCOL_BYTES"),(R07_LEDGER_SNAPSHOT_ABSENCE_PATH,R07_LEDGER_SNAPSHOT_ABSENCE_SHA256,"R07_SNAPSHOT_ABSENCE_BYTES"))
    for path,want,error in fixed:
        if sha_file(_safe(repo,path))!=want:raise Repair10Error(error)
    for label,path_key,sha_key in (("FINAL_REVIEW","advisor_b_final_review_path","advisor_b_final_review_sha256"),("LEDGER_SNAPSHOT","advisor_b_ledger_snapshot_path","advisor_b_ledger_snapshot_sha256")):
        path_value=release.get(path_key);expected_sha=release.get(sha_key)
        if not isinstance(path_value,str) or not path_value.endswith(".json") or not isinstance(expected_sha,str) or len(expected_sha)!=64 or any(c not in "0123456789abcdef" for c in expected_sha):raise Repair10Error("ADVISOR_DYNAMIC_BINDING:"+label)
        required_root="technical/" if technical else ("outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/" if label=="FINAL_REVIEW" else "outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/ledger_snapshots/")
        if not path_value.startswith(required_root):raise Repair10Error("ADVISOR_DYNAMIC_ROOT:"+label)
        value,raw=read_canonical(_safe(repo,path_value))
        if sha_bytes(raw)!=expected_sha:raise Repair10Error("ADVISOR_DYNAMIC_HASH:"+label)
        if technical and (value.get("identity_class")!="TASK_OWNED_SYNTHETIC_IMMUTABLE_NEVER_FORMAL" or value.get("subject")!=label or value.get("task_id")!=TASK_ID or value.get("final_test_read") is not False):raise Repair10Error("ADVISOR_TECHNICAL_SYNTHETIC_CLASS:"+label)


def validate_control(repo:Path,release_path:Path,attestation_path:Path,schema_root:Path,command:str,dispatch_path:Path|None=None)->dict[str,Any]:
    _validate_cli_control_addressability(repo,release_path,attestation_path,dispatch_path)
    release,raw=read_canonical(release_path);technical=release.get("record_kind")=="TECHNICAL_MIRROR_RELEASE"
    if technical:
        if release.get("identity_class")!="TECHNICAL_MIRROR_RELEASE_NEVER_FORMAL" or not (repo/".technical_b1_repair_10_root").is_file():raise Repair10Error("TECHNICAL_ROOT_MARKER")
    else:validate(release,load_schemas(schema_root),"release")
    if release.get("record_kind") not in ("PHASE_A_RELEASE","TECHNICAL_MIRROR_RELEASE") or release.get("repair_id")!=REPAIR or release.get("task_id")!=TASK_ID or release.get("batch_id")!=BATCH_ID or release.get("mode")!=MODE or release.get("commands_exact")!=list(PHASE_A_COMMANDS) or command not in COMMANDS:raise Repair10Error("PHASE_A_RELEASE_CONTRACT")
    if release.get("phase_a_commands_exact")!=list(PHASE_A_COMMANDS) or release.get("phase_a_permissions")!=PHASE_A_PERMISSIONS or release.get("guardian_phase_b_authorization_path")!=PHASE_B_AUTH_PATH or release.get("guardian_phase_b_attestation_path")!=PHASE_B_ATTESTATION_PATH or release.get("phase_b_dispatch_path")!=PHASE_B_DISPATCH_PATH:raise Repair10Error("PHASE_SPLIT_CONTRACT")
    _validate_rollover_paths(release,release_path,attestation_path,dispatch_path,repo,technical)
    if release.get("guardian_two_phase_contract_path")!=GUARDIAN_TWO_PHASE_CONTRACT_PATH or release.get("guardian_two_phase_contract_sha256")!=GUARDIAN_TWO_PHASE_CONTRACT_SHA256 or release.get("guardian_two_phase_review_path")!=GUARDIAN_TWO_PHASE_REVIEW_PATH or release.get("guardian_two_phase_review_sha256")!=GUARDIAN_TWO_PHASE_REVIEW_SHA256:raise Repair10Error("GUARDIAN_TWO_PHASE_AUTHORITY_BINDING")
    if release.get("authority_allowlist_path")!=AUTHORITY_ALLOWLIST_PATH:raise Repair10Error("AUTHORITY_ALLOWLIST_PATH")
    if sha_file(_safe(repo,GUARDIAN_TWO_PHASE_CONTRACT_PATH))!=GUARDIAN_TWO_PHASE_CONTRACT_SHA256 or sha_file(_safe(repo,GUARDIAN_TWO_PHASE_REVIEW_PATH))!=GUARDIAN_TWO_PHASE_REVIEW_SHA256:raise Repair10Error("GUARDIAN_TWO_PHASE_AUTHORITY_BYTES")
    _validate_signing_authority_bytes(repo,release,technical)
    if release["run_id"]!=derive_run_id(release):raise Repair10Error("RUN_ID")
    if datetime.fromisoformat(release["expires_at"]).astimezone(timezone.utc)<=datetime.now(timezone.utc):raise Repair10Error("EXPIRED")
    if release["roots"]!=exact_roots(release["run_id"],technical):raise Repair10Error("ROOT_TEMPLATE")
    roots={k:_safe(repo,v) for k,v in release["roots"].items()};vals=list(roots.values())
    if len({str(x).casefold() for x in vals})!=len(vals) or any(a.is_relative_to(b) or b.is_relative_to(a) for i,a in enumerate(vals) for b in vals[i+1:]):raise Repair10Error("ROOT_EXCLUSIVITY")
    # Five-field projection/dependency binding is computed from immutable bytes
    # before any authority or technical-mirror object is opened.
    if release["projection_contract_path"]!=PROJECTION_PATH or release["dependency_matrix_path"]!=DEPENDENCY_PATH:raise Repair10Error("PROJECTION_PATH")
    projection_path=_safe(repo,release["projection_contract_path"]);matrix_path=_safe(repo,release["dependency_matrix_path"])
    if sha_file(projection_path)!=release["projection_contract_sha256"] or sha_file(matrix_path)!=release["dependency_matrix_sha256"]:raise Repair10Error("PROJECTION_FILE_HASH")
    matrix,_=read_canonical(matrix_path)
    if matrix.get("dependency_structure_sha256")!=release["dependency_structure_sha256"] or matrix.get("projection_contract_sha256")!=release["projection_contract_sha256"]:raise Repair10Error("DEPENDENCY_STRUCTURE")
    for name in ("source","schema","command"):
        if sha_file(_safe(repo,release[f"{name}_manifest_path"]))!=release[f"{name}_manifest_sha256"]:raise Repair10Error("MANIFEST_HASH:"+name)
    command_manifest,_=read_canonical(_safe(repo,release["command_manifest_path"]))
    rows=command_manifest.get("entries",[])
    if command_manifest.get("mode")!=MODE or command_manifest.get("commands_exact")!=list(COMMANDS) or len(rows)!=6 or [row.get("command") for row in rows]!=list(COMMANDS):raise Repair10Error("COMMAND_MANIFEST")
    attestation,araw=read_canonical(attestation_path)
    validate(attestation,load_schemas(schema_root),"technical_guardian_attestation" if technical else "guardian_attestation")
    if attestation.get("record_kind") not in ("GUARDIAN_ONE_WAY_ATTESTATION","TECHNICAL_MIRROR_ONE_WAY_ATTESTATION") or attestation.get("release_sha256")!=sha_bytes(raw) or attestation.get("one_way") is not True:raise Repair10Error("ATTESTATION")
    expected=_binding(release)
    for key,value in expected.items():
        if attestation.get(key)!=value:raise Repair10Error("ATTESTATION_BINDING:"+key)
    side=roots["side_records"];issued_path=_safe(repo,release["phase_a_dispatch_path"]);revoked=side/"REVOKED.json";consumed=side/"PHASE_A_CONSUMED.json"
    failure=roots["failure"]/"FAIL_CLOSED.json"
    if failure.exists():
        failed,_=read_canonical(failure);validate(failed,load_schemas(schema_root),"package_terminal")
        for key,want in {"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":release["run_id"],"mode":MODE,"release_sha256":sha_bytes(raw),"attestation_sha256":sha_bytes(araw),"projection_contract_sha256":release["projection_contract_sha256"],"dependency_matrix_sha256":release["dependency_matrix_sha256"],"dependency_structure_sha256":release["dependency_structure_sha256"]}.items():
            if failed.get(key)!=want:raise Repair10Error("PHASE_A_FAILURE_BINDING:"+key)
        if failed.get("terminal_phase")=="PHASE_A":raise Repair10Error("PHASE_A_FAILURE_PERMANENT_NEW_RUN_REQUIRED")
    if not issued_path.is_file():raise Repair10Error("ISSUED_MISSING")
    issued,_=read_canonical(issued_path)
    validate(issued,load_schemas(schema_root),"technical_phase_dispatch" if technical else "phase_dispatch")
    expected_kind="TECHNICAL_PHASE_DISPATCH" if technical else "PHASE_A_DISPATCH_AUTHORIZATION"
    if issued.get("record_kind")!=expected_kind or issued.get("state")!="PHASE_A_ISSUED" or issued.get("phase")!="A" or issued.get("one_use") is not True or issued.get("revoked") is not False or issued.get("final_test_read") is not False or issued.get("dispatch_id")!=release["phase_a_dispatch_id"] or issued.get("release_sha256")!=sha_bytes(raw) or issued.get("attestation_sha256")!=sha_bytes(araw):raise Repair10Error("PHASE_A_ISSUED_CONSTANTS")
    for key,value in expected.items():
        if issued.get(key)!=value:raise Repair10Error("ISSUED_BINDING:"+key)
    if revoked.exists():
        revoked_value,_=read_canonical(revoked);validate(revoked_value,load_schemas(schema_root),"side_record")
        if consumed.exists() or revoked_value.get("state")!="REVOKED" or revoked_value.get("revoked") is not True:raise Repair10Error("REVOKED_INVALID_STATE")
        for key,value in {**expected,"release_sha256":sha_bytes(raw),"attestation_sha256":sha_bytes(araw)}.items():
            if revoked_value.get(key)!=value:raise Repair10Error("REVOKED_BINDING:"+key)
        raise Repair10Error("REVOKED_VALID_BOUND")
    if command=="preflight":
        if consumed.exists():raise Repair10Error("ALREADY_CONSUMED")
    else:
        if not consumed.is_file():raise Repair10Error("NOT_CONSUMED")
        consumed_value,_=read_canonical(consumed)
        validate(consumed_value,load_schemas(schema_root),"technical_phase_a_dispatch_consumed" if technical else "phase_a_dispatch_consumed")
        if consumed_value.get("state")!="PHASE_A_CONSUMED" or consumed_value.get("phase")!="A" or consumed_value.get("dispatch_id")!=release["phase_a_dispatch_id"]:raise Repair10Error("PHASE_A_CONSUMED")
        for key,value in {**expected,"release_sha256":sha_bytes(raw),"attestation_sha256":sha_bytes(araw)}.items():
            if consumed_value.get(key)!=value:raise Repair10Error("CONSUMED_BINDING:"+key)
    context={**expected,"technical":technical,"repo_root":str(repo),"phase_a_release_path":release_path.relative_to(repo).as_posix(),"phase_a_attestation_path":attestation_path.relative_to(repo).as_posix(),"release":release,"release_sha256":sha_bytes(raw),"attestation_sha256":sha_bytes(araw),"roots_resolved":roots,"schemas":load_schemas(schema_root),"projection":json.loads(projection_path.read_text()),"matrix":matrix,"command_manifest":command_manifest}
    return {**context,"authority_read_count":authority_read_count(context)}


def consume_once(context:Mapping[str,Any])->Path:
    roots=context["roots_resolved"];issued,_=read_canonical(_safe(Path(context["repo_root"]),context["release"]["phase_a_dispatch_path"]));value={**issued,"schema_version":"gen_enc_fast_b1_repair_10_technical_phase_a_dispatch_consumed_v1" if context["technical"] else "gen_enc_fast_b1_repair_10_phase_a_dispatch_consumed_v1","state":"PHASE_A_CONSUMED"};path=roots["side_records"]/"PHASE_A_CONSUMED.json";path.parent.mkdir(parents=True,exist_ok=True)
    validate(value,context["schemas"],"technical_phase_a_dispatch_consumed" if context["technical"] else "phase_a_dispatch_consumed")
    try:
        with path.open("xb") as stream:stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    except FileExistsError as exc:raise Repair10Error("ALREADY_CONSUMED") from exc
    return path


def _external_record(repo:Path,path_arg:Path|None,expected_sha:str|None,exact_path:str,error:str)->tuple[dict[str,Any],str]:
    if path_arg is None or expected_sha is None or path_arg.as_posix()!=exact_path or len(expected_sha)!=64 or any(c not in "0123456789abcdef" for c in expected_sha):raise Repair10Error(error+":EXTERNAL_EXPECTED_REQUIRED")
    path=_safe(repo,exact_path);raw=path.read_bytes()
    if sha_bytes(raw)!=expected_sha:raise Repair10Error(error+":EXPECTED_SHA256")
    value,canonical_raw=read_canonical(path)
    if canonical_raw!=raw:raise Repair10Error(error+":CANONICAL")
    return value,expected_sha


def _phase_a_handoff_path(context:Mapping[str,Any])->Path:return context["roots_resolved"]["side_records"]/PHASE_A_HANDOFF_PATH


def validate_phase_b(repo:Path,ns:argparse.Namespace,context:Mapping[str,Any],consume:bool)->dict[str,Any]:
    handoff_path=_phase_a_handoff_path(context);handoff,hraw=read_canonical(handoff_path);validate(handoff,context["schemas"],"phase_a_handoff")
    failure=context["roots_resolved"]["failure"]/"FAIL_CLOSED.json"
    if failure.exists():
        failed,_=read_canonical(failure);validate(failed,context["schemas"],"package_terminal")
        if failed.get("terminal_phase")=="PHASE_A":raise Repair10Error("PHASE_A_FAILURE_FORBIDS_PHASE_B")
    auth,auth_sha=_external_record(repo,ns.guardian_phase_b_authorization,ns.guardian_phase_b_expected_sha256,PHASE_B_AUTH_PATH,"PHASE_B_AUTH")
    att,phase_b_att_sha=_external_record(repo,ns.guardian_phase_b_attestation,ns.guardian_phase_b_attestation_expected_sha256,PHASE_B_ATTESTATION_PATH,"PHASE_B_ATTESTATION")
    dispatch,dispatch_sha=_external_record(repo,ns.phase_b_dispatch,ns.phase_b_dispatch_expected_sha256,PHASE_B_DISPATCH_PATH,"PHASE_B_DISPATCH")
    validate(auth,context["schemas"],"guardian_phase_b_authorization");validate(att,context["schemas"],"guardian_phase_b_attestation");validate(dispatch,context["schemas"],"phase_b_dispatch")
    if context["technical"]:
        if auth.get("record_kind")!="TECHNICAL_MIRROR_GUARDIAN_PHASE_B_AUTHORIZATION" or att.get("record_kind")!="TECHNICAL_MIRROR_GUARDIAN_PHASE_B_ONE_WAY_ATTESTATION" or dispatch.get("record_kind")!="TECHNICAL_PHASE_DISPATCH" or auth.get("authoritative") is not False or att.get("authoritative") is not False:raise Repair10Error("PHASE_B_TECHNICAL_CLASS")
    elif auth.get("record_kind")!="GUARDIAN_PHASE_B_PUBLISH_AUTHORIZATION" or att.get("record_kind")!="GUARDIAN_PHASE_B_ONE_WAY_ATTESTATION" or dispatch.get("record_kind")!="PHASE_B_TASK_BOUND_DISPATCH" or auth.get("authoritative") is not True or att.get("authoritative") is not True:raise Repair10Error("PHASE_B_FORMAL_CLASS")
    for name,record in (("AUTH",auth),("ATTESTATION",att),("DISPATCH",dispatch)):
        if record.get("one_use") is not True or record.get("revoked") is not False or datetime.fromisoformat(record["expires_at"]).astimezone(timezone.utc)<=datetime.now(timezone.utc):raise Repair10Error("PHASE_B_"+name+"_LIFETIME")
    handoff_payload=dict(handoff);handoff_digest=handoff_payload.pop("handoff_digest")
    if handoff_digest!=sha_value({"domain":"GEN-ENC-FAST-TWO-PHASE-HANDOFF-v1","payload":handoff_payload}):raise Repair10Error("PHASE_A_HANDOFF_DIGEST")
    phase_a_argv=[next(row for row in context["command_manifest"]["entries"] if row["command"]==command)["argv_after_python"] for command in PHASE_A_COMMANDS]
    expected_handoff={"state":"PHASE_A_VERIFIED_HANDOFF_STOP","terminal_state":"VERIFIED_STAGING_AWAITING_GUARDIAN_POSTERIOR_ANCHOR","task_id":TASK_ID,"phase_a_task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"mode":MODE,"phase_a_release_path":context["phase_a_release_path"],"phase_a_release_sha256":context["release_sha256"],"phase_a_attestation_path":context["phase_a_attestation_path"],"phase_a_attestation_sha256":context["attestation_sha256"],"phase_a_commands_exact":list(PHASE_A_COMMANDS),"phase_a_permissions":PHASE_A_PERMISSIONS,"phase_a_exact_argv":phase_a_argv,"roots":context["roots"],"verification_subject_seal_path":context["roots"]["side_records"]+"/"+SUBJECT_SEAL_PATH,"independent_report_path":context["roots"]["staging"]+"/independent_verification.json","verifier_terminal_path":context["roots"]["staging"]+"/verifier_terminal.json","verification_subject_count":27,"artifact_graph_count":31,"claim_ceiling":CLAIM,"guardian_two_phase_contract_path":GUARDIAN_TWO_PHASE_CONTRACT_PATH,"guardian_two_phase_contract_sha256":GUARDIAN_TWO_PHASE_CONTRACT_SHA256,"guardian_two_phase_review_path":GUARDIAN_TWO_PHASE_REVIEW_PATH,"guardian_two_phase_review_sha256":GUARDIAN_TWO_PHASE_REVIEW_SHA256}
    for key,want in expected_handoff.items():
        if handoff.get(key)!=want:raise Repair10Error("PHASE_A_HANDOFF_BINDING:"+key)
    common={"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"mode":MODE,"claim_ceiling":CLAIM,"verification_subject_count":27,"phase_a_commands_exact":list(PHASE_A_COMMANDS),"phase_a_permissions":PHASE_A_PERMISSIONS,"phase_a_release_path":context["phase_a_release_path"],"phase_a_release_sha256":context["release_sha256"],"phase_a_attestation_path":context["phase_a_attestation_path"],"phase_a_attestation_sha256":context["attestation_sha256"],"phase_a_handoff_path":context["roots"]["side_records"]+"/"+PHASE_A_HANDOFF_PATH,"phase_a_handoff_sha256":sha_bytes(hraw),"phase_a_handoff_digest":handoff["handoff_digest"],"verification_subject_seal_path":handoff["verification_subject_seal_path"],"verification_subject_seal_sha256":handoff["verification_subject_seal_sha256"],"verification_subject_digest":handoff["verification_subject_digest"],"independent_report_sha256":handoff["independent_report_sha256"],"verifier_terminal_sha256":handoff["verifier_terminal_sha256"],"artifact_graph_digest":handoff["artifact_graph_digest"],"source_manifest_sha256":context["source_manifest_sha256"],"schema_manifest_sha256":context["schema_manifest_sha256"],"command_manifest_sha256":context["command_manifest_sha256"],"projection_contract_sha256":context["projection_contract_sha256"],"dependency_matrix_sha256":context["dependency_matrix_sha256"],"dependency_structure_sha256":context["dependency_structure_sha256"],"roots":context["roots"],"phase_b_commands_exact":list(PHASE_B_COMMANDS),"phase_b_permissions":PHASE_B_PERMISSIONS,"final_test_read":False}
    common.update({"authority_allowlist_path":context["authority_allowlist_path"],"authority_allowlist_sha256":context["authority_allowlist_sha256"],"source_manifest_path":context["source_manifest_path"],"schema_manifest_path":context["schema_manifest_path"],"command_manifest_path":context["command_manifest_path"],"projection_contract_path":context["projection_contract_path"],"dependency_matrix_path":context["dependency_matrix_path"],"phase_a_task_id":TASK_ID,"phase_b_task_id":TASK_ID,"guardian_two_phase_contract_path":GUARDIAN_TWO_PHASE_CONTRACT_PATH,"guardian_two_phase_contract_sha256":GUARDIAN_TWO_PHASE_CONTRACT_SHA256,"guardian_two_phase_review_path":GUARDIAN_TWO_PHASE_REVIEW_PATH,"guardian_two_phase_review_sha256":GUARDIAN_TWO_PHASE_REVIEW_SHA256,"phase_b_authorization_path":PHASE_B_AUTH_PATH,"phase_b_attestation_path":PHASE_B_ATTESTATION_PATH,"phase_b_dispatch_path":PHASE_B_DISPATCH_PATH})
    for name,record in (("AUTH",auth),("ATTESTATION",att),("DISPATCH",dispatch)):
        for key,want in common.items():
            if record.get(key)!=want:raise Repair10Error("PHASE_B_"+name+"_BINDING:"+key)
    if att.get("authorization_sha256")!=auth_sha or att.get("authorization_id")!=auth.get("authorization_id") or att.get("one_way") is not True:raise Repair10Error("PHASE_B_ATTESTATION_LINK")
    if dispatch.get("authorization_sha256")!=auth_sha or dispatch.get("phase_b_attestation_sha256")!=phase_b_att_sha or dispatch.get("authorization_id")!=auth.get("authorization_id") or dispatch.get("phase_a_dispatch_id")!=context["release"]["phase_a_dispatch_id"] or dispatch.get("dispatch_id")==context["release"]["phase_a_dispatch_id"]:raise Repair10Error("PHASE_B_DISPATCH_LINK")
    if handoff.get("formal_publication_count")!=0 or handoff.get("commit_pointer_count")!=0 or handoff.get("success_package_count")!=0 or handoff.get("final_test_read") is not False:raise Repair10Error("PHASE_A_HANDOFF_ZERO_STATE")
    consumed_path=context["roots_resolved"]["side_records"]/"PHASE_B_CONSUMED.json"
    if consume and consumed_path.exists():raise Repair10Error("PHASE_B_ALREADY_CONSUMED")
    if consume:
        for name in ("run","journal","pointer","success","failure"):
            if context["roots_resolved"][name].exists():raise Repair10Error("PHASE_B_PUBLISH_DIRTY_PRECOPY:"+name)
    stage=context["roots_resolved"]["staging"];verified_stage_gate(stage,context)
    graph_entries=[{"path":rel,"sha256":sha_file(stage/rel)} for rel in exact_artifacts()]
    if handoff.get("artifact_graph_entries")!=graph_entries or handoff.get("artifact_graph_digest")!=sha_value({"domain":"GEN-ENC-FAST-PHASE-A-31-GRAPH-v1","entries":graph_entries}):raise Repair10Error("PHASE_A_HANDOFF_GRAPH_CHANGED")
    if consume:
        if dispatch.get("state")!="PHASE_B_ISSUED" or consumed_path.exists():raise Repair10Error("PHASE_B_ALREADY_CONSUMED")
        consumed={**dispatch,"state":"PHASE_B_CONSUMED","dispatch_expected_sha256":dispatch_sha};validate(consumed,context["schemas"],"phase_b_dispatch_consumed");consumed_path.parent.mkdir(parents=True,exist_ok=True)
        try:
            with consumed_path.open("xb") as stream:stream.write(canonical(consumed));stream.flush();os.fsync(stream.fileno())
        except FileExistsError as exc:raise Repair10Error("PHASE_B_ALREADY_CONSUMED") from exc
    else:
        consumed,_=read_canonical(consumed_path);validate(consumed,context["schemas"],"phase_b_dispatch_consumed")
        if consumed.get("state")!="PHASE_B_CONSUMED" or consumed.get("phase")!="B" or consumed.get("dispatch_expected_sha256")!=dispatch_sha or consumed.get("dispatch_id")!=dispatch.get("dispatch_id"):raise Repair10Error("PHASE_B_CONSUMED_BINDING")
        for key,want in common.items():
            if consumed.get(key)!=want:raise Repair10Error("PHASE_B_CONSUMED_BINDING:"+key)
    return {**context,"phase_b_authorization_sha256":auth_sha,"phase_b_attestation_sha256":phase_b_att_sha,"phase_b_dispatch_sha256":dispatch_sha,"phase_b_dispatch_id":dispatch["dispatch_id"]}


def _receipt_binding(context:Mapping[str,Any])->dict[str,Any]:
    return {**_binding(context["release"]),"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"]}


def authority_read_count(context:Mapping[str,Any])->int:
    directory=context["roots_resolved"]["side_records"]/"AUTHORITY_READS"
    if not directory.exists():return 0
    paths=sorted(directory.glob("*.json"));expected=_receipt_binding(context)
    if [p.name for p in paths]!=[f"{i:04d}.json" for i in range(1,len(paths)+1)]:raise Repair10Error("READ_RECEIPT_SEQUENCE")
    for ordinal,path in enumerate(paths,1):
        value,_=read_canonical(path);validate(value,context["schemas"],"authority_read_receipt")
        if value.get("ordinal")!=ordinal:raise Repair10Error("READ_RECEIPT_ORDINAL")
        for key,want in expected.items():
            if value.get(key)!=want:raise Repair10Error("READ_RECEIPT_BINDING:"+key)
    return len(paths)


def record_authority_read(context:Mapping[str,Any],phase:str,purpose:str,path_label:str,expected_sha256:str)->int:
    ordinal=authority_read_count(context)+1;directory=context["roots_resolved"]["side_records"]/"AUTHORITY_READS";directory.mkdir(parents=True,exist_ok=True)
    value={"schema_version":"gen_enc_fast_b1_repair_10_authority_read_receipt_v1","record_kind":"CUMULATIVE_AUTHORITY_READ_RECEIPT","repair_id":REPAIR,**_receipt_binding(context),"ordinal":ordinal,"phase":phase,"purpose":purpose,"path_label":path_label,"expected_sha256":expected_sha256,"final_test_read":False};validate(value,context["schemas"],"authority_read_receipt")
    path=directory/f"{ordinal:04d}.json"
    with path.open("xb") as stream:stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    return ordinal


def load_objects(repo:Path,context:Mapping[str,Any])->tuple[dict[str,Any],list[dict[str,Any]],int]:
    release=context["release"]
    if context["technical"]:
        bundle_path=_safe(repo,release["technical_bundle_path"])
        if sha_file(bundle_path)!=release["technical_bundle_sha256"]:raise Repair10Error("TECHNICAL_BUNDLE_HASH")
        bundle,_=read_canonical(bundle_path)
        if bundle.get("identity_class")!="TECHNICAL_MIRROR_ONLY_NEVER_FORMAL_AUTHORITY":raise Repair10Error("TECHNICAL_BUNDLE_CLASS")
        if not release.get("simulate_formal_read_accounting",False):return bundle["objects"],bundle["authority_entries"],authority_read_count(context)
        fail_after=release.get("technical_fail_after_reads");result={}
        for entry in bundle["authority_entries"]:
            data=canonical(bundle["objects"][entry["purpose"]]);count=record_authority_read(context,"DRIVER_GENERATION",entry["purpose"],"TECHNICAL_MIRROR:"+entry["purpose"],sha_bytes(data))
            if fail_after==count:raise Repair10Error("INJECT_AUTHORITY_READ_FAILURE")
            result[entry["purpose"]]=bundle["objects"][entry["purpose"]]
        return result,bundle["authority_entries"],authority_read_count(context)
    allow_path=_safe(repo,release["authority_allowlist_path"])
    if sha_file(allow_path)!=release["authority_allowlist_sha256"]:raise Repair10Error("ALLOWLIST_HASH")
    allow=json.loads(allow_path.read_text());objects={}
    for entry in allow["entries"]:
        path=_safe(repo,entry["path"])
        with path.open("rb") as stream:
            record_authority_read(context,"DRIVER_GENERATION",entry["purpose"],entry["path"],entry["sha256"]);data=stream.read()
        if sha_bytes(data)!=entry["sha256"]:raise Repair10Error("AUTHORITY_HASH")
        objects[entry["purpose"]]=pointer(json.loads(data.decode("utf-8")),entry["pointer"])
    return objects,allow["entries"],authority_read_count(context)


def build_staging(stage:Path,objects:Mapping[str,Any],entries:Sequence[Mapping[str,Any]],context:Mapping[str,Any])->dict[str,Any]:
    if stage.exists():raise Repair10Error("STAGE_EXISTS")
    binding={k:context[k] for k in ("projection_contract_sha256","dependency_matrix_sha256","dependency_structure_sha256")};members=members_from_authority(objects,entries,context["projection"],binding);stage.mkdir(parents=True)
    for member in members:validate(member,context["schemas"],"member_identity");atomic_json(stage/f"members/{member['member_id']}.json",member)
    for family in FAMILIES:
        selected=[m for m in members if m["family_id"]==family];manifest={"schema_version":"gen_enc_fast_b1_repair_10_partial_family_manifest_v1","record_kind":"PARTIAL_FAMILY_MANIFEST_EXACTLY_5_OF_20","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"family_id":family,"slot_ordinals":[1,2,3,4,5],"member_entries":[{"member_id":m["member_id"],"path":f"members/{m['member_id']}.json","sha256":sha_file(stage/f"members/{m['member_id']}.json"),"static_status":m["static_status"],"failure_slot_retained":True} for m in selected],"complete_family_manifest":False,"claim_ceiling":CLAIM,"final_test_read":False};validate(manifest,context["schemas"],"partial_family_manifest");atomic_json(stage/f"partial_manifests/{PREFIX[family]}.json",manifest)
    counts={s:sum(m["static_status"]==s for m in members) for s in ("ELIGIBLE","COST_INELIGIBLE","TEMPLATE_VALIDITY_REJECTED","FAIL_CLOSED")};audit={"schema_version":"gen_enc_fast_b1_repair_10_static_audit_v1","record_kind":"COMPLETE_BATCH_LOCAL_STATIC_AUDIT_20","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"member_paths":[f"members/{m['member_id']}.json" for m in members],"member_count":20,"complete_cad_witness_count":20,"failed_slots_retained":True,"status_counts":counts,"authority_read_count_at_generation":context["authority_read_count"],"claim_ceiling":CLAIM,"final_test_read":False};validate(audit,context["schemas"],"static_audit");atomic_json(stage/"static_audit.json",audit)
    report={"schema_version":"gen_enc_fast_b1_repair_10_independent_verification_v1","record_kind":"INDEPENDENT_VERIFICATION","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"status":"PENDING_NON_SUCCESS","verified_member_count":0,"verified_manifest_count":0,"authority_read_count":0,"artifact_count":0,"checks":[],"resealed":False,"verification_subject_seal_path":SUBJECT_SEAL_PATH,"verification_subject_seal_sha256":None,"verification_subject_digest":None,"verification_subject_count":0,"projection_contract_path":PROJECTION_PATH,"projection_contract_sha256":context["projection_contract_sha256"],"dependency_matrix_path":DEPENDENCY_PATH,"dependency_matrix_sha256":context["dependency_matrix_sha256"],"dependency_structure_sha256":context["dependency_structure_sha256"],"mode":MODE,"claim_ceiling":CLAIM,"final_test_read":False};atomic_json(stage/"independent_verification.json",report)
    index={"schema_version":"gen_enc_fast_b1_repair_10_batch_index_v1","record_kind":"B1_BATCH_INDEX_NON_FINAL","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"mode":MODE,"projection_contract_path":PROJECTION_PATH,"projection_contract_sha256":context["projection_contract_sha256"],"dependency_matrix_path":DEPENDENCY_PATH,"dependency_matrix_sha256":context["dependency_matrix_sha256"],"dependency_structure_sha256":context["dependency_structure_sha256"],"authority_allowlist_sha256":context["release"].get("authority_allowlist_sha256","0"*64),"source_manifest_sha256":context["source_manifest_sha256"],"schema_manifest_sha256":context["schema_manifest_sha256"],"command_manifest_sha256":context["command_manifest_sha256"],"member_paths":[f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in range(1,6)],"partial_manifest_paths":[f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES],"static_audit_path":"static_audit.json","independent_verification_path":"independent_verification.json","sha256sums_path":"SHA256SUMS.txt","generation_terminal_path":"generation_terminal.json","verifier_terminal_path":"verifier_terminal.json","publication_terminal_path":"publication_terminal.json","verification_complete":False,"artifact_cardinality":31,"zero_unlisted_required":True,"final_endpoint":False,"claim_ceiling":CLAIM,"final_test_read":False};validate(index,context["schemas"],"batch_index");atomic_json(stage/"batch_index.json",index)
    terminal={"schema_version":"gen_enc_fast_b1_repair_10_generation_terminal_v1","record_kind":"GENERATION_STAGED_NON_SUCCESS","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"status":"AWAITING_INDEPENDENT_VERIFICATION","authority_read_count":context["authority_read_count"],"member_count":20,"artifact_count":29,"success_eligible":False,"publication_started":False,"claim_ceiling":CLAIM,"final_test_read":False};validate(terminal,context["schemas"],"generation_terminal");atomic_json(stage/"generation_terminal.json",terminal);(stage/"SHA256SUMS.txt").write_bytes(_hash_lines(stage))
    if len([p for p in stage.rglob("*") if p.is_file()])!=29:raise Repair10Error("GENERATION_CARDINALITY")
    return {"status":"STAGED_NON_SUCCESS","authority_read_count":context["authority_read_count"],"member_count":20,"artifact_count":29}


def terminal_value(context:Mapping[str,Any],success:bool,counts:Mapping[str,int],reason:str,pointer_sha:str|None,phase:str="PHASE_B")->dict[str,Any]:
    return {"schema_version":"gen_enc_fast_b1_repair_10_package_terminal_v1","record_kind":"VERIFIED_SUCCESS" if success else "FAIL_CLOSED","terminal_phase":phase,"repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"mode":MODE,"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"],"projection_contract_path":PROJECTION_PATH,"projection_contract_sha256":context["projection_contract_sha256"],"dependency_matrix_path":DEPENDENCY_PATH,"dependency_matrix_sha256":context["dependency_matrix_sha256"],"dependency_structure_sha256":context["dependency_structure_sha256"],"status":"VERIFIED_SUCCESS" if success else "TECHNICAL_FAIL_CLOSED","reason":reason,"honest_counts":dict(counts),"commit_pointer_sha256":pointer_sha,"package_terminal_count":1,"claim_ceiling":CLAIM,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False}


def write_terminal(context:Mapping[str,Any],success:bool,counts:Mapping[str,int],reason:str,pointer_sha:str|None=None,phase:str="PHASE_B")->Path:
    roots=context["roots_resolved"];sp=roots["success"]/"VERIFIED_SUCCESS.json";fp=roots["failure"]/"FAIL_CLOSED.json"
    if sp.exists() or fp.exists():raise Repair10Error("SINGLE_TERMINAL")
    value=terminal_value(context,success,counts,reason,pointer_sha,phase);validate(value,context["schemas"],"package_terminal");path=sp if success else fp;path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("xb") as stream:stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    return path


def _temp(target:Path,run_id:str,index:int)->Path:
    # Target-derived but bounded for Windows MAX_PATH: the digest binds the
    # complete run id, index, and resolved target bytes.
    suffix=sha_value({"run_id":run_id,"index":index,"target":str(target.resolve())})[:16]
    return target.with_name(f".r08.{index:02d}.{suffix}.tmp")
def _token(run_id:str,index:int,target:Path,temp:Path)->str:return sha_value({"run_id":run_id,"index":index,"target":str(target.resolve()),"temp":str(temp.resolve())})


def verification_subject_paths()->list[str]:
    return [f"members/{PREFIX[f]}_{i:02d}.json" for f in FAMILIES for i in range(1,6)]+[f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES]+["static_audit.json","generation_terminal.json","batch_index.json"]


def verify_subject_seal(root:Path,context:Mapping[str,Any],report:Mapping[str,Any],verifier:Mapping[str,Any])->dict[str,Any]:
    if context["verification_subject_seal_path"]!=SUBJECT_SEAL_PATH:raise Repair10Error("SUBJECT_SEAL_CONTROL_PATH")
    path=context["roots_resolved"]["side_records"]/SUBJECT_SEAL_PATH;seal,_=read_canonical(path);validate(seal,context["schemas"],"verification_subject_seal")
    expected_binding={**_binding(context["release"]),"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"]}
    for key,want in expected_binding.items():
        if seal.get(key)!=want:raise Repair10Error("SUBJECT_SEAL_BINDING:"+key)
    paths=verification_subject_paths();entries=[{"path":rel,"sha256":sha_file(root/rel)} for rel in paths];digest=sha_value({"domain":"GEN-ENC-FAST-B1-REPAIR-09-VERIFICATION-SUBJECT-v1","entries":entries})
    if seal["subject_count"]!=27 or seal["subject_entries"]!=entries or seal["subject_digest"]!=digest:raise Repair10Error("SUBJECT_SEAL_SUBJECT_MISMATCH")
    seal_sha=sha_file(path);expected={"verification_subject_seal_path":SUBJECT_SEAL_PATH,"verification_subject_seal_sha256":seal_sha,"verification_subject_digest":digest,"verification_subject_count":27}
    for name,record in (("REPORT",report),("VERIFIER_TERMINAL",verifier)):
        for key,want in expected.items():
            if record.get(key)!=want:raise Repair10Error("SUBJECT_SEAL_"+name+":"+key)
    return {**expected,"subject_entries":entries}


def verified_stage_gate(root:Path,context:Mapping[str,Any])->dict[str,Any]:
    logical=exact_artifacts();actual={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual!=set(logical):raise Repair10Error("VERIFIED_GATE_GRAPH")
    if (root/"SHA256SUMS.txt").read_bytes()!=_hash_lines(root):raise Repair10Error("VERIFIED_GATE_SHA256SUMS")
    members=[]
    for family in FAMILIES:
        for ordinal in range(1,6):
            member,_=read_canonical(root/f"members/{PREFIX[family]}_{ordinal:02d}.json");validate(member,context["schemas"],"member_identity")
            if member["family_id"]!=family or member["slot_ordinal"]!=ordinal:raise Repair10Error("VERIFIED_GATE_MEMBER_ORDER")
            members.append(member)
    for family in FAMILIES:
        manifest,_=read_canonical(root/f"partial_manifests/{PREFIX[family]}.json");validate(manifest,context["schemas"],"partial_family_manifest");selected=[m for m in members if m["family_id"]==family]
        expected=[{"member_id":m["member_id"],"path":f"members/{m['member_id']}.json","sha256":sha_file(root/f"members/{m['member_id']}.json"),"static_status":m["static_status"],"failure_slot_retained":True} for m in selected]
        if manifest["member_entries"]!=expected or manifest["slot_ordinals"]!=[1,2,3,4,5]:raise Repair10Error("VERIFIED_GATE_MANIFEST")
    audit,_=read_canonical(root/"static_audit.json");validate(audit,context["schemas"],"static_audit")
    if audit["member_paths"]!=[f"members/{m['member_id']}.json" for m in members] or audit["status_counts"]!={s:sum(m["static_status"]==s for m in members) for s in ("ELIGIBLE","COST_INELIGIBLE","TEMPLATE_VALIDITY_REJECTED","FAIL_CLOSED")}:raise Repair10Error("VERIFIED_GATE_AUDIT")
    generation,_=read_canonical(root/"generation_terminal.json");report,_=read_canonical(root/"independent_verification.json");index,_=read_canonical(root/"batch_index.json");verifier,_=read_canonical(root/"verifier_terminal.json");publication,_=read_canonical(root/"publication_terminal.json")
    for name,value in (("generation_terminal",generation),("independent_verification",report),("batch_index",index),("verifier_terminal",verifier),("publication_terminal",publication)):validate(value,context["schemas"],name)
    if generation["status"]!="AWAITING_INDEPENDENT_VERIFICATION" or generation["member_count"]!=20 or generation["artifact_count"]!=29:raise Repair10Error("VERIFIED_GATE_GENERATION")
    checks=["TYPED_CAD_349_LEAVES","20_MEMBER_DEEP_RECOMPUTE","31_GRAPH_ZERO_UNLISTED"]
    if report["status"]!="PASS" or report["resealed"] is not True or report["verified_member_count"]!=20 or report["verified_manifest_count"]!=4 or report["artifact_count"]!=31 or report["checks"]!=checks:raise Repair10Error("VERIFIED_GATE_REPORT")
    if index["verification_complete"] is not True or index["artifact_cardinality"]!=31 or index["member_paths"]!=[f"members/{m['member_id']}.json" for m in members] or index["partial_manifest_paths"]!=[f"partial_manifests/{PREFIX[f]}.json" for f in FAMILIES]:raise Repair10Error("VERIFIED_GATE_INDEX")
    if verifier["status"]!="VERIFIED_RESEALED_AWAITING_PUBLICATION" or verifier["verified_member_count"]!=20 or verifier["artifact_count"]!=31 or publication!={"schema_version":"gen_enc_fast_b1_repair_10_publication_terminal_v1","record_kind":"PUBLICATION_INTENT_NON_SUCCESS","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"status":"AWAITING_MULTI_TARGET_ATOMIC_PUBLICATION","target_count":31,"published_count":0,"commit_pointer_written":False,"success_terminal_written":False,"claim_ceiling":CLAIM,"final_test_read":False}:raise Repair10Error("VERIFIED_GATE_TERMINALS")
    verify_subject_seal(root,context,report,verifier)
    for record_name,record in (("INDEX",index),("REPORT",report)):
        for key,want in (("task_id",TASK_ID),("batch_id",BATCH_ID),("run_id",context["run_id"]),("mode",MODE),("projection_contract_path",PROJECTION_PATH),("projection_contract_sha256",context["projection_contract_sha256"]),("dependency_matrix_path",DEPENDENCY_PATH),("dependency_matrix_sha256",context["dependency_matrix_sha256"]),("dependency_structure_sha256",context["dependency_structure_sha256"])):
            if record.get(key)!=want:raise Repair10Error("VERIFIED_GATE_"+record_name+"_BINDING:"+key)
    cumulative=authority_read_count(context)
    if not (audit["authority_read_count_at_generation"]==generation["authority_read_count"]<=report["authority_read_count"]==verifier["authority_read_count"]==cumulative):raise Repair10Error("VERIFIED_GATE_READ_COUNT")
    return {"members":20,"artifacts":31,"authority_reads":cumulative}


def publish(stage:Path,run:Path,journal:Path,pointer_path:Path,context:Mapping[str,Any])->dict[str,Any]:
    logical=exact_artifacts();verified_stage_gate(stage,context)
    if run.exists():raise Repair10Error("PUBLISH_INPUT")
    run.mkdir(parents=True);entries=[];fault=os.environ.get("GEN_ENC_B1_REPAIR10_FAULT") if context["technical"] else None
    state={"schema_version":"gen_enc_fast_b1_repair_10_publication_journal_v1","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"release_sha256":context["release_sha256"],"run_root_absolute":str(run.resolve()),"pointer_absolute":str(pointer_path.resolve()),"state":"PUBLISHING","entries":entries,"final_test_read":False}
    for index,rel in enumerate(logical):
        source,target=stage/rel,run/rel;target.parent.mkdir(parents=True,exist_ok=True);temp=_temp(target,context["run_id"],index);entry={"index":index,"logical_path":rel,"source_sha256":sha_file(source),"target_absolute":str(target.resolve()),"temp_absolute":str(temp.resolve()),"ownership_token":_token(context["run_id"],index,target,temp),"phase":"INTENT_DURABLE"};entries.append(entry);atomic_json(journal,state)
        if fault==f"copy:{index}":raise Repair10Error("INJECT_COPY")
        with source.open("rb") as src,temp.open("xb") as dst:shutil.copyfileobj(src,dst);dst.flush();os.fsync(dst.fileno())
        if fault==f"fsync:{index}":raise Repair10Error("INJECT_FSYNC")
        os.replace(temp,target)
        if fault==f"kill:{index}":os._exit(86)
        if fault==f"replace:{index}":raise Repair10Error("INJECT_REPLACE")
        entry["phase"]="REPLACED";atomic_json(journal,state)
        if fault==f"journal:{index}":raise Repair10Error("INJECT_JOURNAL")
    if fault=="after-targets":os._exit(87)
    pointer=_pointer_value(run,context)
    state={**state,"state":"COMMITTED","entries":[{**e,"phase":"REPLACED"} for e in entries]};atomic_json(journal,state)
    if fault in ("pointer","after-commit"):os._exit(88)
    pointer_path.parent.mkdir(parents=True,exist_ok=True);atomic_json(pointer_path,pointer)
    if fault=="after-pointer":os._exit(89)
    return {"published":31,"pointer_sha256":sha_file(pointer_path)}


def _pointer_value(run:Path,context:Mapping[str,Any])->dict[str,Any]:
    value={"schema_version":"gen_enc_fast_b1_repair_10_commit_pointer_v1","record_kind":"ATOMIC_B1_COMMIT_POINTER","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"mode":MODE,"release_sha256":context["release_sha256"],"projection_contract_path":PROJECTION_PATH,"projection_contract_sha256":context["projection_contract_sha256"],"dependency_matrix_path":DEPENDENCY_PATH,"dependency_matrix_sha256":context["dependency_matrix_sha256"],"dependency_structure_sha256":context["dependency_structure_sha256"],"immutable_run_directory":context["roots"]["run"],"batch_index_sha256":sha_file(run/"batch_index.json"),"sha256sums_sha256":sha_file(run/"SHA256SUMS.txt"),"verification_sha256":sha_file(run/"independent_verification.json"),"artifact_count":31,"atomic":True,"final_endpoint":False,"claim_ceiling":CLAIM,"final_test_read":False};validate(value,context["schemas"],"commit_pointer");return value


def rollback(journal:Path,run:Path,pointer:Path,context:Mapping[str,Any])->int:
    state,_=read_canonical(journal);validate(state,context["schemas"],"journal")
    if state["state"]!="PUBLISHING" or pointer.exists() or (context["roots_resolved"]["success"]/"VERIFIED_SUCCESS.json").exists():raise Repair10Error("ROLLBACK_STATE_FORBIDDEN")
    removed=0;logical=exact_artifacts()
    for entry in reversed(state["entries"]):
        i=entry["index"];target=Path(entry["target_absolute"]);temp=Path(entry["temp_absolute"])
        if i>=31 or entry["logical_path"]!=logical[i] or target.resolve()!=(run/logical[i]).resolve() or temp!=_temp(target,state["run_id"],i) or entry["ownership_token"]!=_token(state["run_id"],i,target,temp):raise Repair10Error("RECOVERY_OWNERSHIP")
        for path in (temp,target):
            if not path.resolve().is_relative_to(run.resolve()):raise Repair10Error("RECOVERY_CONTAINMENT")
            if path.is_file():path.unlink();removed+=1
    atomic_json(journal,{**state,"state":"ROLLED_BACK","entries":[{**e,"phase":"ROLLED_BACK"} for e in state["entries"]]});return removed


def rollback_postcopy(journal:Path,run:Path,pointer_path:Path,context:Mapping[str,Any])->int:
    """Fail-closed settlement for a caught Phase-B error after durable copy began."""
    state,_=read_canonical(journal);validate(state,context["schemas"],"journal")
    if state["state"] not in ("PUBLISHING","COMMITTED") or (context["roots_resolved"]["success"]/"VERIFIED_SUCCESS.json").exists():raise Repair10Error("POSTCOPY_ROLLBACK_STATE")
    logical=exact_artifacts();removed=0
    if pointer_path.exists():
        pointer_value,_=read_canonical(pointer_path);validate(pointer_value,context["schemas"],"commit_pointer")
        if pointer_value!=_pointer_value(run,context):raise Repair10Error("POSTCOPY_POINTER_OWNERSHIP")
        pointer_path.unlink();removed+=1
    for entry in reversed(state["entries"]):
        i=entry["index"];target=Path(entry["target_absolute"]);temp=Path(entry["temp_absolute"])
        if i>=31 or entry["logical_path"]!=logical[i] or target.resolve()!=(run/logical[i]).resolve() or temp!=_temp(target,state["run_id"],i) or entry["ownership_token"]!=_token(state["run_id"],i,target,temp):raise Repair10Error("POSTCOPY_RECOVERY_OWNERSHIP")
        for path in (temp,target):
            if not path.resolve().is_relative_to(run.resolve()):raise Repair10Error("POSTCOPY_RECOVERY_CONTAINMENT")
            if path.is_file():path.unlink();removed+=1
    atomic_json(journal,{**state,"state":"ROLLED_BACK","entries":[{**e,"phase":"ROLLED_BACK"} for e in state["entries"]]})
    return removed


def recover_transaction(context:Mapping[str,Any])->dict[str,Any]:
    roots=context["roots_resolved"];journal_path=roots["journal"]/"publication.json";pointer_path=roots["pointer"]/"B1.json";success=roots["success"]/"VERIFIED_SUCCESS.json";failure=roots["failure"]/"FAIL_CLOSED.json"
    if success.exists():
        if failure.exists() or not journal_path.is_file() or not pointer_path.is_file():raise Repair10Error("RECOVER_SUCCESS_INCOMPLETE")
        state,_=read_canonical(journal_path);validate(state,context["schemas"],"journal")
        if state["state"]!="COMMITTED":raise Repair10Error("RECOVER_SUCCESS_JOURNAL")
        packaged=package_results(context);return {"status":"ALREADY_VERIFIED_SUCCESS_IDEMPOTENT","terminal_sha256":packaged["terminal_sha256"],"pointer_sha256":sha_file(pointer_path),"mutated":False}
    if failure.exists():return {"status":"ALREADY_FAIL_CLOSED_IDEMPOTENT","terminal_sha256":sha_file(failure),"mutated":False}
    counts={"authority_reads":authority_read_count(context),"members":0,"artifacts":0,"published":0}
    _observe_counts(roots,counts);counts["published"]=0
    if not journal_path.is_file():
        terminal=write_terminal(context,False,counts,"RECOVERY_NO_JOURNAL_FAIL_CLOSED");return {"status":"TECHNICAL_FAIL_CLOSED","terminal_sha256":sha_file(terminal),"mutated":True}
    state,_=read_canonical(journal_path);validate(state,context["schemas"],"journal")
    if state["state"]=="PUBLISHING":
        _observe_counts(roots,counts);counts["published"]=0
        removed=rollback(journal_path,roots["run"],pointer_path,context);terminal=write_terminal(context,False,counts,"RECOVERY_ROLLED_BACK_INCOMPLETE_PUBLISHING");return {"status":"TECHNICAL_FAIL_CLOSED","removed":removed,"terminal_sha256":sha_file(terminal),"mutated":True}
    if state["state"]=="COMMITTED":
        verified_stage_gate(roots["run"],context)
        logical=exact_artifacts()
        if len(state["entries"])!=31:raise Repair10Error("RECOVER_COMMITTED_CARDINALITY")
        for i,e in enumerate(state["entries"]):
            target=Path(e["target_absolute"]);temp=Path(e["temp_absolute"])
            if e["index"]!=i or e["logical_path"]!=logical[i] or target.resolve()!=(roots["run"]/logical[i]).resolve() or temp!=_temp(target,state["run_id"],i) or e["ownership_token"]!=_token(state["run_id"],i,target,temp) or e["phase"]!="REPLACED" or sha_file(target)!=e["source_sha256"]:raise Repair10Error("RECOVER_COMMITTED_GRAPH")
        pointer_value=_pointer_value(roots["run"],context)
        if pointer_path.exists():
            existing,_=read_canonical(pointer_path)
            if existing!=pointer_value:raise Repair10Error("RECOVER_POINTER_MISMATCH")
        else:pointer_path.parent.mkdir(parents=True,exist_ok=True);atomic_json(pointer_path,pointer_value)
        counts.update(members=20,artifacts=31,published=31);terminal=write_terminal(context,True,counts,"RECOVERED_COMMITTED_POINTER_LAST",sha_file(pointer_path));return {"status":"VERIFIED_SUCCESS","terminal_sha256":sha_file(terminal),"pointer_sha256":sha_file(pointer_path),"mutated":True}
    if state["state"]=="ROLLED_BACK":
        if pointer_path.exists() or any(p.is_file() for p in roots["run"].rglob("*")):raise Repair10Error("RECOVER_ROLLED_BACK_DIRTY")
        terminal=write_terminal(context,False,counts,"RECOVERY_ALREADY_ROLLED_BACK");return {"status":"TECHNICAL_FAIL_CLOSED","terminal_sha256":sha_file(terminal),"mutated":True}
    raise Repair10Error("RECOVER_STATE")


def package_results(context:Mapping[str,Any])->dict[str,Any]:
    roots=context["roots_resolved"];terminals=list(roots["success"].glob("*.json"))+list(roots["failure"].glob("*.json"))
    if len(terminals)!=1:raise Repair10Error("TERMINAL_CARDINALITY")
    terminal,_=read_canonical(terminals[0]);validate(terminal,context["schemas"],"package_terminal")
    for key,value in {**_binding(context["release"]),"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"]}.items():
        if key in terminal and terminal[key]!=value:raise Repair10Error("PACKAGE_BINDING:"+key)
    cumulative=authority_read_count(context)
    if terminal["honest_counts"]["authority_reads"]!=cumulative:raise Repair10Error("PACKAGE_READ_COUNT")
    if terminal["record_kind"]=="VERIFIED_SUCCESS":
        pointer_path=roots["pointer"]/"B1.json";pointer,_=read_canonical(pointer_path);validate(pointer,context["schemas"],"commit_pointer")
        if terminal["commit_pointer_sha256"]!=sha_file(pointer_path):raise Repair10Error("PACKAGE_POINTER")
        expected={"task_id":TASK_ID,"batch_id":BATCH_ID,"run_id":context["run_id"],"mode":MODE,"release_sha256":context["release_sha256"],"projection_contract_path":PROJECTION_PATH,"projection_contract_sha256":context["projection_contract_sha256"],"dependency_matrix_path":DEPENDENCY_PATH,"dependency_matrix_sha256":context["dependency_matrix_sha256"],"dependency_structure_sha256":context["dependency_structure_sha256"]}
        for key,value in expected.items():
            if pointer.get(key)!=value:raise Repair10Error("PACKAGE_POINTER_BINDING:"+key)
        run=roots["run"]
        verified_stage_gate(run,context)
        if {p.relative_to(run).as_posix() for p in run.rglob("*") if p.is_file()}!=set(exact_artifacts()):raise Repair10Error("PACKAGE_GRAPH")
        index,_=read_canonical(run/"batch_index.json");report,_=read_canonical(run/"independent_verification.json");validate(index,context["schemas"],"batch_index");validate(report,context["schemas"],"independent_verification")
        for record_name,record in (("INDEX",index),("REPORT",report)):
            for key,value in {k:v for k,v in expected.items() if k!="release_sha256"}.items():
                if record.get(key)!=value:raise Repair10Error("PACKAGE_"+record_name+"_BINDING:"+key)
        if (run/"SHA256SUMS.txt").read_bytes()!=_hash_lines(run):raise Repair10Error("PACKAGE_SHA256SUMS")
        if pointer["batch_index_sha256"]!=sha_file(run/"batch_index.json") or pointer["verification_sha256"]!=sha_file(run/"independent_verification.json") or pointer["sha256sums_sha256"]!=sha_file(run/"SHA256SUMS.txt"):raise Repair10Error("PACKAGE_RESEAL")
    else:
        observed={"authority_reads":cumulative,"members":0,"artifacts":0,"published":0};_observe_counts(roots,observed);observed["published"]=0
        if terminal["honest_counts"]!=observed:raise Repair10Error("PACKAGE_FAILURE_HISTORICAL_COUNTS")
        if (roots["pointer"]/"B1.json").exists() or any(p.is_file() for p in roots["run"].rglob("*")):raise Repair10Error("PACKAGE_FAILURE_COMMITTED_RESIDUE")
    return {"status":terminal["status"],"terminal_sha256":sha_file(terminals[0])}


def parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser();p.add_argument("command",choices=["preflight","generate-staging","publish","recover","package-results"])
    for name in ("repo-root","release","guardian-attestation","phase-a-dispatch","schema-root","projection-contract","dependency-matrix"):p.add_argument("--"+name,required=True,type=Path)
    for name in ("guardian-phase-b-authorization","guardian-phase-b-attestation","phase-b-dispatch"):p.add_argument("--"+name,type=Path)
    for name in ("guardian-phase-b-expected-sha256","guardian-phase-b-attestation-expected-sha256","phase-b-dispatch-expected-sha256"):p.add_argument("--"+name)
    return p


def _check_cli_paths(ns:argparse.Namespace,repo:Path,context:Mapping[str,Any],raw_argv:Sequence[str])->None:
    if ns.projection_contract.as_posix()!=PROJECTION_PATH or ns.dependency_matrix.as_posix()!=DEPENDENCY_PATH:raise Repair10Error("ARGV_PROJECTION_PATH")
    if ns.projection_contract.resolve()!=_safe(repo,context["projection_contract_path"]) or ns.dependency_matrix.resolve()!=_safe(repo,context["dependency_matrix_path"]):raise Repair10Error("ARGV_PROJECTION_RESOLUTION")
    expected={"repo_root":Path("."),"release":Path(context["phase_a_release_path"]),"guardian_attestation":Path(context["phase_a_attestation_path"]),"phase_a_dispatch":Path(context["phase_a_dispatch_path"])}
    if any(getattr(ns,key)!=value for key,value in expected.items()) or (not context["technical"] and ns.schema_root!=Path("schemas/gen_enc/b1_repair_10")):raise Repair10Error("ARGV_CONTROL_PATH_EXACT")
    row=next((x for x in context["command_manifest"]["entries"] if x["command"]==ns.command),None);expected_argv=[] if row is None else list(row["argv_after_python"][2:])
    replacements={"<GUARDIAN_PHASE_A_RELEASE_EXACT_PATH>":context["phase_a_release_path"],"<GUARDIAN_PHASE_A_ATTESTATION_EXACT_PATH>":context["phase_a_attestation_path"],"<CONTROLLER_PHASE_A_DISPATCH_EXACT_PATH>":context["phase_a_dispatch_path"],"<EXTERNAL_GUARDIAN_AUTHORIZATION_SHA256>":ns.guardian_phase_b_expected_sha256,"<EXTERNAL_GUARDIAN_ATTESTATION_SHA256>":ns.guardian_phase_b_attestation_expected_sha256,"<EXTERNAL_CONTROLLER_DISPATCH_SHA256>":ns.phase_b_dispatch_expected_sha256};expected_argv=[replacements.get(x,x) for x in expected_argv]
    if context["technical"]:expected_argv=[str(ns.schema_root) if x=="schemas/gen_enc/b1_repair_10" else x for x in expected_argv]
    if row is None or list(raw_argv)!=expected_argv:raise Repair10Error("ARGV_BYTE_EXACT")


def _observe_counts(roots:Mapping[str,Path],counts:dict[str,int])->None:
    stage=roots["staging"]
    if stage.exists():
        counts["members"]=len(list((stage/"members").glob("*.json"))) if (stage/"members").exists() else 0
        counts["artifacts"]=len([p for p in stage.rglob("*") if p.is_file()])
    run=roots["run"]
    counts["published"]=len([p for p in run.rglob("*") if p.is_file()]) if run.exists() else 0


def main(argv:Sequence[str]|None=None)->int:
    raw_argv=list(sys.argv[1:] if argv is None else argv);ns=parser().parse_args(raw_argv);context=None;phase_b_validated=ns.command not in PHASE_B_COMMANDS;counts={"authority_reads":0,"members":0,"artifacts":0,"published":0}
    try:
        repo=ns.repo_root.resolve();context=validate_control(repo,ns.release.resolve(),ns.guardian_attestation.resolve(),ns.schema_root.resolve(),ns.command,ns.phase_a_dispatch.resolve());roots=context["roots_resolved"]
        counts["authority_reads"]=context["authority_read_count"]
        _check_cli_paths(ns,repo,context,raw_argv)
        if ns.command in PHASE_B_COMMANDS:context=validate_phase_b(repo,ns,context,ns.command=="publish");roots=context["roots_resolved"];phase_b_validated=True
        if ns.command=="preflight":
            for name in ("staging","run","journal","success","failure","pointer"):
                if roots[name].exists():raise Repair10Error("PREFLIGHT_ROOT_EXISTS:"+name)
            consume_once(context);result={"status":"PREFLIGHT_CONSUMED_NO_AUTHORITY_READ","authority_read_count":context["authority_read_count"],"run_id":context["run_id"]}
        elif ns.command=="generate-staging":
            objects,entries,reads=load_objects(ns.repo_root.resolve(),context);context={**context,"authority_read_count":reads};counts["authority_reads"]=reads;result=build_staging(roots["staging"],objects,entries,context);counts.update(members=20,artifacts=29)
        elif ns.command=="publish":
            counts["authority_reads"]=authority_read_count(context);publication=publish(roots["staging"],roots["run"],roots["journal"]/"publication.json",roots["pointer"]/"B1.json",context);counts.update(members=20,artifacts=31,published=31)
            if context["technical"] and os.environ.get("GEN_ENC_B1_REPAIR10_FAULT")=="post-copy-exception":raise Repair10Error("INJECT_POST_COPY_EXCEPTION")
            terminal=write_terminal(context,True,counts,"POINTER_LAST_PUBLISHED",publication["pointer_sha256"])
            if context["technical"] and os.environ.get("GEN_ENC_B1_REPAIR10_FAULT")=="after-success":os._exit(90)
            result={**publication,"terminal_sha256":sha_file(terminal),"status":"VERIFIED_SUCCESS"}
        elif ns.command=="recover":
            result=recover_transaction(context)
        else:result=package_results(context)
        print(json.dumps(result,sort_keys=True));return 0
    except BaseException as exc:
        if context is not None and phase_b_validated and ns.command!="package-results":
            counts["authority_reads"]=authority_read_count(context)
            roots=context["roots_resolved"];sp=roots["success"]/"VERIFIED_SUCCESS.json";fp=roots["failure"]/"FAIL_CLOSED.json"
            if not sp.exists():
                journal=roots["journal"]/"publication.json"
                if ns.command in PHASE_B_COMMANDS and journal.is_file():
                    try:
                        state,_=read_canonical(journal)
                        if state.get("state") in ("PUBLISHING","COMMITTED"):rollback_postcopy(journal,roots["run"],roots["pointer"]/"B1.json",context)
                    except BaseException as rollback_exc:raise Repair10Error("FAILURE_ROLLBACK:"+str(rollback_exc)) from rollback_exc
                _observe_counts(roots,counts);counts["published"]=0
                try:
                    if not fp.exists():write_terminal(context,False,counts,type(exc).__name__+":"+str(exc),phase="PHASE_A" if ns.command in PHASE_A_COMMANDS else "PHASE_B")
                except BaseException:raise
        print(json.dumps({"status":"FAIL_CLOSED","error":type(exc).__name__+":"+str(exc),"authority_read_count":counts["authority_reads"]},sort_keys=True),file=sys.stderr);return 2


if __name__=="__main__":raise SystemExit(main())
