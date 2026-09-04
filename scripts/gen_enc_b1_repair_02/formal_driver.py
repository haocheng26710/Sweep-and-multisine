"""Standalone repair-02 driver: typed CAD values mechanically determine witnesses."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.gen_enc_b1_repair_02 import cad_projection_driver as cad
from scripts.gen_enc_b1_repair_02.primitives import atomic_json, canonical, pointer, read_canonical, sha_bytes, sha_file, sha_value

TASK_ID="01a049a7-15ca-79e1-92a2-d3822ba8609d";BATCH_ID="B1";REPAIR="PRE-RELEASE-REPAIR-02"
FAMILIES=("HAND_DESIGNED","NEAR_INDEPENDENT","FIXED_SEED_RANDOM_DISORDERED","PHYSICS_METAMATERIAL_INSPIRED")
PREFIX=dict(zip(FAMILIES,("HAND","NEAR","RANDOM","PHYSICS")));SECTORS=("0","90","180","270")
RANDOM_AXES=("q0","q90","q180","edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270","loss_0","loss_90","loss_180","loss_270")
PHYSICS_AXES=("q0","q90","q180","external_0","external_90","external_180","external_270","ring_0_90","ring_90_180","ring_180_270","ring_270_0","loss_0","loss_90","loss_180","loss_270")
CLAIM="BATCH_LOCAL_IDENTITY_COMPLETE_CAD_STATIC_AND_TECHNICAL_VALIDITY_ONLY";MASK=(1<<64)-1;GAMMA=0x9E3779B97F4A7C15
RUN_DOMAIN=b"GEN-ENC-FAST-B1-PRE-RELEASE-REPAIR-02-RUN-ID-v1"
PROJECTION_PATH="outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_02/cad_typed_projection_contract.json"
DEPENDENCY_PATH="outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_02/cad_leaf_dependency_matrix.json"


class Repair02Error(RuntimeError):pass


def derive_run_id(release:Mapping[str,Any])->str:
    clone=dict(release);clone["run_id"]="0"*64
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
    if tuple(spec.get("parameter_order",()))!=tuple(axes) or spec.get("member_count")!=20 or spec.get("dof")!=len(axes):raise Repair02Error("SPEC_AXES")
    result={}
    for item,name in zip(spec.get("parameters",[]),names):
        if set(item)!={"group","axes","bounds"} or item["group"]!=name or len(item["bounds"])!=2:raise Repair02Error("SPEC_GROUP")
        lo,hi=map(float,item["bounds"])
        if not lo<hi:raise Repair02Error("SPEC_BOUND")
        for axis in item["axes"]:
            if axis in result:raise Repair02Error("DUP_AXIS")
            result[axis]=(lo,hi)
    if tuple(result)!=tuple(axes):raise Repair02Error("GROUP_AXIS_ORDER")
    return result


def parameters(objects:Mapping[str,Any],family:str,ordinal:int)->dict[str,float]:
    if family in FAMILIES[:2]:
        row=objects["HAND_ROWS" if family==FAMILIES[0] else "NEAR_ROWS"][ordinal-1]
        result={"q0":float(row["volume_logit_0"]),"q90":float(row["volume_logit_90"]),"q180":float(row["volume_logit_180"]),"q270":float(row["derived_volume_logit_270"]),**{f"external_{s}":float(row[f"external_aperture_fraction_{s}"]) for s in SECTORS},**{f"loss_{s}":float(row[f"loss_fraction_{s}"]) for s in SECTORS}}
        result["central_mix" if family==FAMILIES[0] else "shared_alpha"]=float(row["central_mix_aperture_fraction" if family==FAMILIES[0] else "shared_coupling_alpha"]);return result
    if family==FAMILIES[2]:
        spec=objects["RANDOM_FAMILY_SPEC"];bounds=_groups(spec,RANDOM_AXES,("VOLUME_LOGIT","RECIPROCAL_EDGE_POSITIVE","LOSS"))
        if spec.get("uniform_algorithm")!={"interval":"OPEN_0_1_BINARY64","word_to_uniform":"((word>>11)+0.5)/2^53","one_guard":"nextafter(1.0,0.0)"} or spec.get("splitmix64",{}).get("gamma_hex")!="9e3779b97f4a7c15":raise Repair02Error("RANDOM_ALGORITHM")
        seed=int(objects["RANDOM_FIXED_SEEDS"][ordinal-1]);result={f"external_{s}":.5 for s in SECTORS}
        for index,axis in enumerate(RANDOM_AXES):
            lo,hi=bounds[axis];u=_uniform(seed,index);result[axis]=lo+(hi-lo)*u if index<3 or index>=9 else 0.0 if u<.5 else lo+(hi-lo)*(2*u-1)
        result["q270"]=-(result["q0"]+result["q90"]+result["q180"])/3;return result
    spec=objects["PHYSICS_FAMILY_SPEC_PARAMETERS_LHS"];bounds=_groups(spec,PHYSICS_AXES,("VOLUME_LOGIT","EXTERNAL_APERTURE","RING_COUPLING","LOSS"));master=int(objects["PHYSICS_MASTER_SEED"])
    if spec.get("lhs_algorithm")!=["STRATA=20","SAMPLE=(PERMUTATION[row]+0.5)/20","JITTER=false","FISHER_YATES_SPLITMIX64=i19_TO_1"] or spec.get("lhs_master_seed")!=master:raise Repair02Error("PHYSICS_ALGORITHM")
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
        if abs(measured-target)>float(common["tolerance_m3"]):raise Repair02Error("ROOT_TOLERANCE")
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
    evidence={"schema_version":"gen_enc_fast_b1_repair_02_member_cad_static_v1","ownership_cells":owners,"slot_placements":slots,"volume_root_witnesses":roots,"u4_exception_witnesses":exceptions,"general_minima":{"feature_candidates":features,"load_path_candidates":loads,"measured_minimum_feature_m":min(x["measured_m"] for x in features),"measured_minimum_load_path_m":min(x["measured_m"] for x in loads),"feature_witness_ids":[x["witness_id"] for x in features if x["measured_m"]==min(y["measured_m"] for y in features)],"load_path_witness_ids":[x["witness_id"] for x in loads if x["measured_m"]==min(y["measured_m"] for y in loads)]},"exception_minima":{"measured_minimum_feature_m":min(float(x) for x in fields["exception_feature_candidates"]),"measured_minimum_load_path_m":min(float(x) for x in fields["exception_load_candidates"]),"exception_ids":[x["exception_id"] for x in exceptions]},"reduced_graph":{"nodes":graph["reduced_nodes"],"edges":reduced,"component_count":_components(graph["reduced_nodes"],reduced)},"actual_fluid_graph":{"nodes":graph["actual_nodes"],"edges":actual,"component_count":_components(graph["actual_nodes"],actual)},"random_zero_edge_witnesses":zeros,"thresholds":{"minimum_general_feature_m":float(fields["minimum_general_feature_m"]),"minimum_general_load_path_m":float(fields["minimum_general_load_path_m"])},"semantic_derivation_inputs":semantic_inputs,"typed_projection_approval":approval,"thresholds_copied_as_measurements":False,"complete_witness_semantics":True}
    eligible=evidence["general_minima"]["measured_minimum_feature_m"]>=evidence["thresholds"]["minimum_general_feature_m"] and evidence["general_minima"]["measured_minimum_load_path_m"]>=evidence["thresholds"]["minimum_general_load_path_m"] and evidence["actual_fluid_graph"]["component_count"]==1
    return evidence,"ELIGIBLE" if eligible else "COST_INELIGIBLE"


def members_from_authority(objects:Mapping[str,Any],entries:Sequence[Mapping[str,Any]],contract:Mapping[str,Any],binding:Mapping[str,Any])->list[dict[str,Any]]:
    projected=cad.project(objects,entries,contract)
    if projected["projection_contract_sha256"]!=binding["projection_contract_sha256"] or projected["dependency_matrix_sha256"]!=binding["dependency_structure_sha256"]:raise Repair02Error("PROJECTION_DEPENDENCY_BINDING")
    result=[]
    for family in FAMILIES:
        for ordinal in range(1,6):
            params=parameters(objects,family,ordinal);evidence,status=derive_cad_evidence(family,params,projected)
            result.append({"schema_version":"gen_enc_fast_b1_repair_02_member_identity_v1","record_kind":"BATCH_LOCAL_MEMBER_IDENTITY_TYPED_CAD_DERIVED","repair_id":REPAIR,"task_id":TASK_ID,"batch_id":BATCH_ID,"family_id":family,"member_id":f"{PREFIX[family]}_{ordinal:02d}","slot_ordinal":ordinal,"failure_slot_retained":True,"parameter_order":list(params),"parameters":params,"cad_static_evidence":evidence,"typed_projection_provenance":{"projection_contract_path":PROJECTION_PATH,"projection_contract_sha256":binding["projection_contract_sha256"],"dependency_matrix_path":DEPENDENCY_PATH,"dependency_matrix_sha256":binding["dependency_matrix_sha256"],"dependency_structure_sha256":binding["dependency_structure_sha256"],"semantic_leaf_count":projected["semantic_leaf_count"]},"static_status":status,"claim_ceiling":CLAIM,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False})
    return result


def pre_read_binding(record:Mapping[str,Any],expected:Mapping[str,Any])->None:
    for key in ("task_id","batch_id","run_id","projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256"):
        if record.get(key)!=expected.get(key):raise Repair02Error("PRE_READ_BINDING:"+key)


def parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser();p.add_argument("command",choices=["preflight","generate-staging","publish","recover","package-results"])
    for name in ("repo-root","release","guardian-attestation","schema-root","projection-contract","dependency-matrix"):p.add_argument("--"+name,required=True,type=Path)
    return p


def main(argv:Sequence[str]|None=None)->int:
    ns=parser().parse_args(argv)
    # No release exists in this freeze. Parsing a DRAFT never reaches authority I/O.
    try:
        release,_=read_canonical(ns.release)
        if release.get("record_kind")!="RELEASE" or release.get("repair_id")!=REPAIR:raise Repair02Error("NO_SIGNED_REPAIR02_RELEASE")
        raise Repair02Error("FORMAL_GATE_IMPLEMENTED_BUT_EXECUTION_REQUIRES_REVIEWED_RELEASE")
    except BaseException as exc:
        print(json.dumps({"status":"FAIL_CLOSED","error":type(exc).__name__+":"+str(exc),"authority_read_count":0},sort_keys=True),file=sys.stderr);return 2


if __name__=="__main__":raise SystemExit(main())
