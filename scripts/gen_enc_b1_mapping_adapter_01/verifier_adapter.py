from __future__ import annotations
from copy import deepcopy
from math import isfinite
from re import fullmatch
from typing import Any,Mapping

class VerificationError(RuntimeError):pass
NAMES=("SPINE","WINDOW_1","WINDOW_2","WINDOW_3","OUTER_1");FUTURE=("OWNERSHIP_CELLS","OWNERSHIP_RULE");FIXED={"ROOT_BRACKET":"object","SLOT_ROWS":"object","U4_PARTICIPATION":"object","ZERO_EDGE_RULE":"string"}
def resolve(root:Any,address:str)->Any:
    cursor=root
    for encoded in address.split("/")[1:] if address else []:
        token=encoded.replace("~1","/").replace("~0","~");cursor=cursor[int(token)] if type(cursor)is list else cursor[token]
    return cursor
def node_type(v:Any)->str:
    return "object" if type(v)is dict else "array" if type(v)is list else "string" if type(v)is str else "boolean" if type(v)is bool else "integer" if type(v)is int else "number" if type(v)is float else "null"
def ordered_pair(v:Any,tag:str)->list[float]:
    if type(v)is not list or len(v)!=2 or any(type(x)not in (int,float) or type(x)is bool or not isfinite(x) for x in v) or v[0]>=v[1]:raise VerificationError("BAD_INTERVAL:"+tag)
    return [float(v[0]),float(v[1])]
def verify(documents:Mapping[str,Any],member_ids:list[str])->dict[str,Any]:
    if len(member_ids)!=20 or len(set(member_ids))!=20:raise VerificationError("MEMBERS")
    numeric=documents["NUMERIC_IDENTITY"];geometry=documents["CAD0_MULTI_SOURCE_02"];owner_doc=documents["CAD0_MULTI_SOURCE_03"];slot_doc=documents["CAD0_MULTI_SOURCE_05"]
    actual={"ROOT_BRACKET":documents["CAD0_MULTI_SOURCE_10"]["root_bracket"],"SLOT_ROWS":slot_doc["slots"],"U4_PARTICIPATION":documents["CAD0_MULTI_SOURCE_11"]["participation"],"ZERO_EDGE_RULE":documents["CAD0_MULTI_SOURCE_07"]["later_summary_rule"]}
    for key,want in FIXED.items():
        if node_type(actual[key])!=want:raise VerificationError("TYPE:"+key)
    mapping=resolve(numeric,"/common_connected_volume_and_cad_mapping");volume=mapping["target_m3"];share=mapping["central_share"];equation=resolve(geometry,"/central/union_volume_formula");parsed=fullmatch(r"4\*A\^2\*H_internal\+V_sensor=([0-9]+(?:\.[0-9]+)?)\*V_target",equation)
    if parsed is None or float(parsed.group(1))!=float(share) or volume<=0 or not 0<share<1:raise VerificationError("FORMULA")
    main_interval=ordered_pair(resolve(geometry,"/sector/collector/z_m"),"primary");per_slot={n:ordered_pair(resolve(slot_doc,"/slots/"+n+"/z_m"),n) for n in NAMES}
    transforms=owner_doc["transforms"];rules=owner_doc["ownership"];angles=transforms["sector_order_deg"]
    for field in ("e_u","e_v","local_to_global","global_to_local"):
        if type(transforms[field])is not str:raise VerificationError("TRANSFORM:"+field)
    for field in ("central_plan","sensor","outside_central","boundary_tie","z"):
        if type(rules[field])is not str:raise VerificationError("RULE:"+field)
    if angles!=[0,90,180,270]:raise VerificationError("ANGLES")
    member_rows=[]
    for member in member_ids:
        rows=[{"witness_id":member+":CENTRAL","owner":"CENTRAL","rule_pointers":["/ownership/central_plan","/ownership/sensor","/ownership/boundary_tie"],"transform_pointer":"/transforms/global_to_local"}]
        for angle in angles:rows.append({"witness_id":member+":SECTOR_"+str(angle),"owner":"SECTOR_"+str(angle),"sector_deg":angle,"rule_pointers":["/ownership/outside_central","/ownership/boundary_tie","/ownership/z"],"transform_pointers":["/transforms/e_u","/transforms/e_v","/transforms/local_to_global","/transforms/global_to_local"]})
        member_rows.append({"member_id":member,"witnesses":rows})
    interval_rules={"finite_ordered_endpoints":True,"containment":"child_min>=container_min and child_max<=container_max","non_empty_overlap":"max(left_min,right_min)<min(left_max,right_max)","thickness_or_clearance":"upper_endpoint-lower_endpoint","midpoint_lower_upper_for_identity_eligibility_metrics":False}
    return {"schema_version":"gen_enc_b1_real_shape_adapter_v1","geometry_volume":{"source":"NUMERIC_IDENTITY","pointer":"/common_connected_volume_and_cad_mapping/target_m3"},"geometry_target_fraction":{"source":"NUMERIC_IDENTITY","pointer":"/common_connected_volume_and_cad_mapping/central_share","cross_check_source":"CAD0_MULTI_SOURCE_02","cross_check_pointer":"/central/union_volume_formula"},"geometry_slot_z_interval_m":{"primary_source":"CAD0_MULTI_SOURCE_02","primary_pointer":"/sector/collector/z_m","slot_source":"CAD0_MULTI_SOURCE_05","slot_pointers":{n:"/slots/"+n+"/z_m" for n in NAMES},"runtime_primary_interval":main_interval,"runtime_slot_intervals":per_slot,"static_rules":interval_rules},"type_corrections":deepcopy(FIXED),"future_outputs":list(FUTURE),"ownership_derivation":{"source":"CAD0_MULTI_SOURCE_03","transforms_pointer":"/transforms","ownership_algorithm_pointer":"/ownership","members":member_rows},"runtime_values":{"geometry_volume":volume,"geometry_target_fraction":share,"corrected_objects":actual},"final_test_read":False}
