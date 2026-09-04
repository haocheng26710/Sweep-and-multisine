"""Standalone repair-02 verifier; imports neither driver nor any old implementation."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.gen_enc_b1_repair_02 import cad_projection_verifier as cad
from scripts.gen_enc_b1_repair_02.primitives import canonical, read_canonical, sha_bytes

TASK_ID="01a049a7-15ca-79e1-92a2-d3822ba8609d";BATCH_ID="B1";REPAIR="PRE-RELEASE-REPAIR-02"
FAMILIES=("HAND_DESIGNED","NEAR_INDEPENDENT","FIXED_SEED_RANDOM_DISORDERED","PHYSICS_METAMATERIAL_INSPIRED");PREFIX=dict(zip(FAMILIES,("HAND","NEAR","RANDOM","PHYSICS")));SECTORS=("0","90","180","270")
CLAIM="BATCH_LOCAL_IDENTITY_COMPLETE_CAD_STATIC_AND_TECHNICAL_VALIDITY_ONLY";PROJECTION_PATH="outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_02/cad_typed_projection_contract.json";DEPENDENCY_PATH="outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_02/cad_leaf_dependency_matrix.json"
RANDOM_AXES=("q0","q90","q180","edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270","loss_0","loss_90","loss_180","loss_270");PHYSICS_AXES=("q0","q90","q180","external_0","external_90","external_180","external_270","ring_0_90","ring_90_180","ring_180_270","ring_270_0","loss_0","loss_90","loss_180","loss_270")
MASK=(1<<64)-1;GAMMA=0x9E3779B97F4A7C15;RUN_DOMAIN=b"GEN-ENC-FAST-B1-PRE-RELEASE-REPAIR-02-RUN-ID-v1"


class Verify02Error(RuntimeError):pass


def derive_run_id(release:Mapping[str,Any])->str:
    copy=dict(release);copy["run_id"]="0"*64
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
    if tuple(spec.get("parameter_order",()))!=tuple(axes) or spec.get("member_count")!=20 or spec.get("dof")!=len(axes):raise Verify02Error("AXES")
    result={}
    if len(spec.get("parameters",[]))!=len(groups):raise Verify02Error("GROUPS")
    for position,name in enumerate(groups):
        item=spec["parameters"][position]
        if set(item)!={"group","axes","bounds"} or item["group"]!=name or len(item["bounds"])!=2:raise Verify02Error("GROUP")
        lo,hi=float(item["bounds"][0]),float(item["bounds"][1])
        if lo>=hi:raise Verify02Error("BOUND")
        for axis in item["axes"]:
            if axis in result:raise Verify02Error("DUP")
            result[axis]=(lo,hi)
    if list(result)!=list(axes):raise Verify02Error("GROUP_ORDER")
    return result


def expected_parameters(objects:Mapping[str,Any],family:str,ordinal:int)->dict[str,float]:
    if family==FAMILIES[0] or family==FAMILIES[1]:
        row=objects["HAND_ROWS" if family==FAMILIES[0] else "NEAR_ROWS"][ordinal-1]
        out={"q0":float(row["volume_logit_0"]),"q90":float(row["volume_logit_90"]),"q180":float(row["volume_logit_180"]),"q270":float(row["derived_volume_logit_270"])}
        out.update({f"external_{s}":float(row[f"external_aperture_fraction_{s}"]) for s in SECTORS});out.update({f"loss_{s}":float(row[f"loss_fraction_{s}"]) for s in SECTORS});out["central_mix" if family==FAMILIES[0] else "shared_alpha"]=float(row["central_mix_aperture_fraction" if family==FAMILIES[0] else "shared_coupling_alpha"]);return out
    if family==FAMILIES[2]:
        spec=objects["RANDOM_FAMILY_SPEC"];b=_bounds(spec,RANDOM_AXES,("VOLUME_LOGIT","RECIPROCAL_EDGE_POSITIVE","LOSS"))
        if spec.get("uniform_algorithm")!={"interval":"OPEN_0_1_BINARY64","word_to_uniform":"((word>>11)+0.5)/2^53","one_guard":"nextafter(1.0,0.0)"} or spec.get("splitmix64",{}).get("gamma_hex")!="9e3779b97f4a7c15":raise Verify02Error("RANDOM_SPEC")
        out={f"external_{s}":.5 for s in SECTORS};seed=int(objects["RANDOM_FIXED_SEEDS"][ordinal-1])
        for index,name in enumerate(RANDOM_AXES):
            lo,hi=b[name];sample=_u(seed,index);out[name]=lo+(hi-lo)*sample if index<3 or index>=9 else 0.0 if sample<.5 else lo+(hi-lo)*(2*sample-1)
        out["q270"]=-(out["q0"]+out["q90"]+out["q180"])/3;return out
    spec=objects["PHYSICS_FAMILY_SPEC_PARAMETERS_LHS"];b=_bounds(spec,PHYSICS_AXES,("VOLUME_LOGIT","EXTERNAL_APERTURE","RING_COUPLING","LOSS"));master=int(objects["PHYSICS_MASTER_SEED"])
    if spec.get("lhs_algorithm")!=["STRATA=20","SAMPLE=(PERMUTATION[row]+0.5)/20","JITTER=false","FISHER_YATES_SPLITMIX64=i19_TO_1"] or spec.get("lhs_master_seed")!=master:raise Verify02Error("PHYSICS_SPEC")
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
        if abs(volume-target)>float(common["tolerance_m3"]):raise Verify02Error("RESIDUAL")
        roots.append({"sector":sector,"domain_m":[float(x) for x in common["domain_m"]],"initial_bracket_m":initial,"final_bracket_m":[lo,hi],"tolerance_m3":float(common["tolerance_m3"]),"iterations":common["iterations"],"trace":trace,"root_length_m":root,"target_volume_m3":target,"measured_volume_m3":volume,"residual_m3":volume-target})
    coordinates=v["U4_COORDINATES"];exceptions=[]
    for sector_group in v["U4_OBJECTS"]:
        for item in sector_group["exceptions"]:
            suffix=item["suffix"];exceptions.append({"exception_id":f"IFX_U4_{int(sector_group['sector']):03d}_{suffix}","sector":sector_group["sector"],"local_coordinates_m":[float(coordinates["x_m"]),float(coordinates["suffix_z_m"][suffix])],"feature_m":float(item["feature_m"]),"load_path_m":float(item["load_path_m"]),"participation":v["U4_PARTICIPATION"],"excluded_only_from":"GENERAL_MINIMA"})
    fields=v["STATIC_FIELDS"];features=[{"witness_id":x["witness_id"],"measured_m":float(x["measured_m"])} for x in fields["general_feature_candidates"]];loads=[{"witness_id":x["witness_id"],"measured_m":float(x["measured_m"])} for x in fields["general_load_candidates"]]
    graph=v["GRAPH_DEFINITION"];reduced=[{"edge_id":e["edge_id"],"a":e["a"],"b":e["b"],"weight":float(p.get(e["parameter_key"],0)),"active":float(p.get(e["parameter_key"],0))>0} for e in graph["reduced_edges"]];actual=[{"edge_id":e["edge_id"],"a":e["a"],"b":e["b"],"weight":float(e["positive_area_m2"]),"positive_area_m2":float(e["positive_area_m2"])} for e in graph["actual_edges"]]
    zero=v["ZERO_EDGE_RULE"];zeros=[{"edge_id":e["edge_id"],"exact_value":zero["exact_zero"],"generator_branch":zero["branch"],"verified_exact_zero":True} for e in reduced if family==zero["family"] and e["weight"]==zero["exact_zero"]]
    semantic={"ownership_transforms":v["OWNERSHIP_ALGORITHMS"],"slot_sector_order":v["SLOT_SECTOR_ORDER"],"slot_mapping":v["SLOT_MAPPING"],"slot_required_fields":v["SLOT_BURDEN"],"root_family_rules":v["ROOT_FAMILIES"],"root_domain_proof":v["ROOT_DOMAIN"],"root_derived_proof":v["ROOT_DERIVED_PROOF"],"root_independent_proof":v["ROOT_INDEPENDENT_PROOF"],"minima_fail_rules":v["STATIC_FAIL_RULES"],"solid_metrics":v["SOLID_METRICS"],"solid_eligible_pair":v["SOLID_ELIGIBLE_PAIR"],"graph_terms":v["GRAPH_TERMS"]};approval={"U1":v["APPROVAL_U1"],"U2":v["APPROVAL_U2"],"U3":v["APPROVAL_U3"],"mandatory_carry_forward":v["APPROVAL_CARRY"]}
    evidence={"schema_version":"gen_enc_fast_b1_repair_02_member_cad_static_v1","ownership_cells":ownership,"slot_placements":slots,"volume_root_witnesses":roots,"u4_exception_witnesses":exceptions,"general_minima":{"feature_candidates":features,"load_path_candidates":loads,"measured_minimum_feature_m":min(x["measured_m"] for x in features),"measured_minimum_load_path_m":min(x["measured_m"] for x in loads),"feature_witness_ids":[x["witness_id"] for x in features if x["measured_m"]==min(y["measured_m"] for y in features)],"load_path_witness_ids":[x["witness_id"] for x in loads if x["measured_m"]==min(y["measured_m"] for y in loads)]},"exception_minima":{"measured_minimum_feature_m":min(float(x) for x in fields["exception_feature_candidates"]),"measured_minimum_load_path_m":min(float(x) for x in fields["exception_load_candidates"]),"exception_ids":[x["exception_id"] for x in exceptions]},"reduced_graph":{"nodes":graph["reduced_nodes"],"edges":reduced,"component_count":_components(graph["reduced_nodes"],reduced)},"actual_fluid_graph":{"nodes":graph["actual_nodes"],"edges":actual,"component_count":_components(graph["actual_nodes"],actual)},"random_zero_edge_witnesses":zeros,"thresholds":{"minimum_general_feature_m":float(fields["minimum_general_feature_m"]),"minimum_general_load_path_m":float(fields["minimum_general_load_path_m"])},"semantic_derivation_inputs":semantic,"typed_projection_approval":approval,"thresholds_copied_as_measurements":False,"complete_witness_semantics":True}
    eligible=evidence["general_minima"]["measured_minimum_feature_m"]>=evidence["thresholds"]["minimum_general_feature_m"] and evidence["general_minima"]["measured_minimum_load_path_m"]>=evidence["thresholds"]["minimum_general_load_path_m"] and evidence["actual_fluid_graph"]["component_count"]==1
    return evidence,"ELIGIBLE" if eligible else "COST_INELIGIBLE"


def verify_members(members:Sequence[Mapping[str,Any]],objects:Mapping[str,Any],entries:Sequence[Mapping[str,Any]],contract:Mapping[str,Any],binding:Mapping[str,Any])->dict[str,Any]:
    projected=cad.project(objects,entries,contract)
    if projected["projection_contract_sha256"]!=binding["projection_contract_sha256"] or projected["dependency_matrix_sha256"]!=binding["dependency_structure_sha256"]:raise Verify02Error("PROJECTION_BINDING")
    expected_ids=[f"{PREFIX[f]}_{i:02d}" for f in FAMILIES for i in range(1,6)]
    if [m.get("member_id") for m in members]!=expected_ids:raise Verify02Error("MEMBER_SET_ORDER")
    for member in members:
        family=member["family_id"];ordinal=int(member["slot_ordinal"]);params=expected_parameters(objects,family,ordinal);evidence,status=expected_evidence(family,params,projected)
        provenance={"projection_contract_path":PROJECTION_PATH,"projection_contract_sha256":binding["projection_contract_sha256"],"dependency_matrix_path":DEPENDENCY_PATH,"dependency_matrix_sha256":binding["dependency_matrix_sha256"],"dependency_structure_sha256":binding["dependency_structure_sha256"],"semantic_leaf_count":projected["semantic_leaf_count"]}
        if member["parameters"]!=params or member["cad_static_evidence"]!=evidence or member["typed_projection_provenance"]!=provenance or member["static_status"]!=status:raise Verify02Error("DEEP_MEMBER:"+member["member_id"])
    return {"status":"PASS_TYPED_CAD_INDEPENDENT_RECOMPUTE","verified_member_count":20,"semantic_leaf_count":projected["semantic_leaf_count"],"dependency_matrix_sha256":projected["dependency_matrix_sha256"],"authority_read_count":binding.get("authority_read_count",0)}


def pre_read_binding(record:Mapping[str,Any],expected:Mapping[str,Any])->None:
    for name in ("task_id","batch_id","run_id","projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256"):
        if record.get(name)!=expected.get(name):raise Verify02Error("PRE_READ_BINDING:"+name)


def parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser();p.add_argument("verify",choices=["verify"])
    for name in ("repo-root","release","guardian-attestation","schema-root","projection-contract","dependency-matrix"):p.add_argument("--"+name,required=True,type=Path)
    return p


def main(argv:Sequence[str]|None=None)->int:
    ns=parser().parse_args(argv)
    try:
        release,_=read_canonical(ns.release)
        if release.get("record_kind")!="RELEASE" or release.get("repair_id")!=REPAIR:raise Verify02Error("NO_SIGNED_REPAIR02_RELEASE")
        raise Verify02Error("FORMAL_GATE_IMPLEMENTED_BUT_EXECUTION_REQUIRES_REVIEWED_RELEASE")
    except BaseException as exc:
        print(json.dumps({"status":"FAIL_CLOSED","error":type(exc).__name__+":"+str(exc),"authority_read_count":0},sort_keys=True),file=sys.stderr);return 2


if __name__=="__main__":raise SystemExit(main())
