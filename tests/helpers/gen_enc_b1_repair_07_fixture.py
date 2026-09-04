"""Exact-shape/value technical mirror. Never a formal-authority adapter."""
from __future__ import annotations

import json
import math
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
BINDING=REPO/"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_freeze/authority_binding.json"
CONTRACT=REPO/"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_07/cad_typed_projection_contract.json"
FAMILIES=("HAND_DESIGNED","NEAR_INDEPENDENT","FIXED_SEED_RANDOM_DISORDERED","PHYSICS_METAMATERIAL_INSPIRED")
RANDOM_AXES=("q0","q90","q180","edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270","loss_0","loss_90","loss_180","loss_270")
PHYSICS_AXES=("q0","q90","q180","external_0","external_90","external_180","external_270","ring_0_90","ring_90_180","ring_180_270","ring_270_0","loss_0","loss_90","loss_180","loss_270")


def entries()->list[dict]:return json.loads(BINDING.read_text())["triples"]
def contract()->dict:return json.loads(CONTRACT.read_text())


def objects()->dict:
    hand=[];near=[]
    for i in range(1,21):
        q0=(i-10.5)/200;q90=-q0/2;q180=q0/4
        common={"volume_logit_0":q0,"volume_logit_90":q90,"volume_logit_180":q180,"derived_volume_logit_270":-(q0+q90+q180)/3,"external_aperture_fraction_0":.41+i/1000,"external_aperture_fraction_90":.42+i/1000,"external_aperture_fraction_180":.43+i/1000,"external_aperture_fraction_270":.44+i/1000,"loss_fraction_0":.03+i/10000,"loss_fraction_90":.035+i/10000,"loss_fraction_180":.04+i/10000,"loss_fraction_270":.045+i/10000}
        hand.append({"member_id":f"HAND_{i:02d}",**common,"central_mix_aperture_fraction":.2+i/1000});near.append({"member_id":f"NEAR_{i:02d}",**common,"shared_coupling_alpha":.03+(i-1)*.04/19})
    random={"family_id":FAMILIES[2],"version":"TECHNICAL_MIRROR","member_count":20,"stochastic":True,"seeds_ref":"TECHNICAL_MIRROR","parameter_order":list(RANDOM_AXES),"parameters":[{"group":"VOLUME_LOGIT","axes":list(RANDOM_AXES[:3]),"bounds":[-.12,.12]},{"group":"RECIPROCAL_EDGE_POSITIVE","axes":list(RANDOM_AXES[3:9]),"bounds":[.2,.8]},{"group":"LOSS","axes":list(RANDOM_AXES[9:]),"bounds":[.02,.08]}],"dof":13,"uniform_algorithm":{"interval":"OPEN_0_1_BINARY64","word_to_uniform":"((word>>11)+0.5)/2^53","one_guard":"nextafter(1.0,0.0)"},"splitmix64":{"gamma_hex":"9e3779b97f4a7c15","mix":"SPLITMIX64_FROZEN","address":"seed+gamma*(axis+1) mod 2^64"},"reciprocity":True,"canonical_generator":{"draw_count":13,"redraw_count":0,"edge_zero_atom_probability":.5,"edge_positive":"0.2+0.6*(2*u-1)"}}
    physics={"family_id":FAMILIES[3],"version":"TECHNICAL_MIRROR","member_count":20,"stochastic":True,"lhs_master_seed":2026090200,"member_identity_seeds_ref":"TECHNICAL_MIRROR","parameter_order":list(PHYSICS_AXES),"parameters":[{"group":"VOLUME_LOGIT","axes":list(PHYSICS_AXES[:3]),"bounds":[-.12,.12]},{"group":"EXTERNAL_APERTURE","axes":list(PHYSICS_AXES[3:7]),"bounds":[.2,.8]},{"group":"RING_COUPLING","axes":list(PHYSICS_AXES[7:11]),"bounds":[.2,.8]},{"group":"LOSS","axes":list(PHYSICS_AXES[11:]),"bounds":[.02,.08]}],"dof":15,"lhs_algorithm":["STRATA=20","SAMPLE=(PERMUTATION[row]+0.5)/20","JITTER=false","FISHER_YATES_SPLITMIX64=i19_TO_1"],"physics_identity":["TECHNICAL_MIRROR"]*4,"unstructured_random_matrix_substitution":False}
    out={"HAND_ROWS":hand,"NEAR_ROWS":near,"RANDOM_FAMILY_SPEC":random,"RANDOM_FIXED_SEEDS":[1000+i*7919 for i in range(20)],"PHYSICS_FAMILY_SPEC_PARAMETERS_LHS":physics,"PHYSICS_MASTER_SEED":2026090200,"PHYSICS_MEMBER_IDENTITY_SEEDS":[2000+i*6151 for i in range(20)]}
    for number,entry in enumerate((x for x in entries() if x["purpose"].startswith("CAD")),1):
        shape=entry["object_shape"];value={}
        for field in shape["field_names"]:
            count=shape.get("array_counts",{}).get(field);value[field]=[f"metadata:{number}:{field}:{i}" for i in range(count)] if count is not None else f"metadata:{number}:{field}"
        out[entry["purpose"]]=value
    out["CAD0_MULTI_SOURCE_02"]["z_intervals_m"]={"slot_plane_z_m":.0061};out["CAD0_MULTI_SOURCE_02"]["central"]={"total_acoustic_volume_m3":3.014899604922098e-5};out["CAD0_MULTI_SOURCE_02"]["sector"]={"target_fraction":.60}
    out["CAD0_MULTI_SOURCE_03"]["transforms"]={"coordinate_frame":"CAD_LOCAL_METRES","sector_rotations_deg":[0,90,180,270]};out["CAD0_MULTI_SOURCE_03"]["ownership"]={"cells":[{"cell_id":"CELL_CENTRAL","owner":"CENTRAL","positive_overlap_volume_m3":0.0}]+[{"cell_id":f"CELL_SECTOR_{s}","owner":s,"positive_overlap_volume_m3":0.0} for s in ("0","90","180","270")],"rule":{"central":"CENTRAL_HALF_OPEN","sector":"MAX_RADIAL_DOT_THEN_MIN_SECTOR_ORDER"}}
    out["CAD0_MULTI_SOURCE_04"]["common"]={"domain_m":[.002,.030],"tolerance_m3":1e-18,"iterations":80,"fixed_volume_m3":2.1848e-6,"linear_coefficient_m2":1.094e-4};out["CAD0_MULTI_SOURCE_04"]["families"]=[{"family_id":x,"same_root_contract":True} for x in FAMILIES]
    slot_rows=[]
    for si,sector in enumerate(("0","90","180","270")):
        for j,x in enumerate((-.0096,-.0048,0.0,.0048,.0096)):slot_rows.append({"slot_id":f"S{si+1}_{j+1:02d}","sector":sector,"owner_cell_id":f"CELL_SECTOR_{sector}","coordinates_xy_m":[x,0.0],"width_m":.002+.0001*(si*5+j)})
    out["CAD0_MULTI_SOURCE_05"]["sector_order"]=["0","90","180","270"];out["CAD0_MULTI_SOURCE_05"]["slots"]=slot_rows;out["CAD0_MULTI_SOURCE_05"]["mapping_by_family_and_sector"]=[f"MAP_{i:02d}" for i in range(10)];out["CAD0_MULTI_SOURCE_05"]["required_burden_fields"]=[f"FIELD_{i:02d}" for i in range(12)]
    out["CAD0_MULTI_SOURCE_06"]["eligible_pair"]={"rule":"POSITIVE_AREA_AND_DISTINCT_COMPONENT"};out["CAD0_MULTI_SOURCE_06"]["metrics"]={"feature_metric":"EXACT_EUCLIDEAN_DISTANCE_M","load_path_metric":"SOLID_GRAPH_SHORTEST_PATH_M"}
    edges=(("P0","P90","edge_0_90"),("P0","P180","edge_0_180"),("P0","P270","edge_0_270"),("P90","P180","edge_90_180"),("P90","P270","edge_90_270"),("P180","P270","edge_180_270"))
    out["CAD0_MULTI_SOURCE_07"]["D2_A"]={"reduced_nodes":["P0","P90","P180","P270"],"reduced_edges":[{"edge_id":k.upper(),"a":a,"b":b,"parameter_key":k} for a,b,k in edges],"actual_nodes":["PLENUM","P0","P90","P180","P270"],"actual_edges":[{"edge_id":f"PLENUM_P{s}","a":"PLENUM","b":f"P{s}","positive_area_m2":4e-6} for s in ("0","90","180","270")]};out["CAD0_MULTI_SOURCE_07"]["definitions"]={"positive_edge_rule":"weight>0","bfs_rule":"UNDIRECTED_POSITIVE_EDGE_BFS"};out["CAD0_MULTI_SOURCE_07"]["later_summary_rule"]={"family":FAMILIES[2],"exact_zero":0.0,"branch":"U_LT_0P5_ATOM","comparison":"u<0.5"}
    out["CAD0_MULTI_SOURCE_10"]["domain"]={"root_length_m":[.002,.030]};out["CAD0_MULTI_SOURCE_10"]["derived_sector_proof"]={"strict_monotone":True,"equation":"fixed_volume+linear_coefficient*root"};out["CAD0_MULTI_SOURCE_10"]["independent_sector_proof"]={"bracket_verified":True,"method":"ENDPOINT_SIGN"};out["CAD0_MULTI_SOURCE_10"]["root_bracket"]=[.002,.030]
    suffixes=("RIM_BOTTOM","RIM_TOP","SHOULDER_LOWER","SHOULDER_UPPER","RIM");out["CAD0_MULTI_SOURCE_11"]["collar_common_local_coordinates_m"]={"x_m":0.0,"suffix_z_m":{x:(.0015 if "BOTTOM" in x or x=="RIM" else .0107) for x in suffixes}};out["CAD0_MULTI_SOURCE_11"]["objects"]=[{"sector":s,"exceptions":[{"suffix":x,"feature_m":.0005,"load_path_m":.0015} for x in suffixes]} for s in ("0","90","180","270")];out["CAD0_MULTI_SOURCE_11"]["counts"]={"total":20,"per_sector":5};out["CAD0_MULTI_SOURCE_11"]["participation"]="U4_INTERFACE_EXCEPTION_ONLY"
    out["CAD0_MULTI_SOURCE_12"]["fields"]={"general_feature_candidates":[{"witness_id":"GENERAL_SPINE","measured_m":.002},{"witness_id":"GENERAL_WINDOW_DEPTH","measured_m":.002}],"general_load_candidates":[{"witness_id":"GENERAL_BOTTOM_COVER","measured_m":.002},{"witness_id":"GENERAL_TOP_COVER","measured_m":.002}],"exception_feature_candidates":[.0005],"exception_load_candidates":[.0015],"minimum_general_feature_m":.002,"minimum_general_load_path_m":.0016};out["CAD0_MULTI_SOURCE_12"]["fail_rules"]=["FEATURE_BELOW_THRESHOLD","LOAD_BELOW_THRESHOLD","ACTUAL_GRAPH_DISCONNECTED","WITNESS_INCOMPLETE"]
    out["CAD0_MULTI_SOURCE_13"]["selections"]={"U1":{"selection":"FIXED_SECTOR_MAPPING"},"U2":{"selection":"STRICT_STATIC_WITNESSES"},"U3":{"selection":"BATCH_LOCAL_ONLY"}}
    return out
