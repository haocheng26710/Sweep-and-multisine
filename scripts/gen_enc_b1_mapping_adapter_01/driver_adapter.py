from __future__ import annotations
import math,re
from copy import deepcopy
from typing import Any,Mapping

FUTURE=("OWNERSHIP_CELLS","OWNERSHIP_RULE")
SLOTS=("SPINE","WINDOW_1","WINDOW_2","WINDOW_3","OUTER_1")
TYPE_FIXES={"ROOT_BRACKET":"object","SLOT_ROWS":"object","U4_PARTICIPATION":"object","ZERO_EDGE_RULE":"string"}

class AdapterError(RuntimeError):pass
def at(root:Any,pointer:str)->Any:
    value=root
    for raw in pointer[1:].split("/") if pointer else []:
        key=raw.replace("~1","/").replace("~0","~");value=value[int(key)] if isinstance(value,list) else value[key]
    return value
def kind(x:Any)->str:
    if type(x)is dict:return "object"
    if type(x)is list:return "array"
    if type(x)is str:return "string"
    if type(x)is bool:return "boolean"
    if type(x)is int:return "integer"
    if type(x)is float:return "number"
    return "null"
def interval(x:Any,label:str)->list[float]:
    if type(x)is not list or len(x)!=2 or any(type(v)not in (int,float) or type(v)is bool or not math.isfinite(v) for v in x) or not x[0]<x[1]:raise AdapterError("INTERVAL:"+label)
    return [float(x[0]),float(x[1])]
def build(documents:Mapping[str,Any],members:list[str])->dict[str,Any]:
    if len(members)!=20 or len(set(members))!=20:raise AdapterError("EXACT20")
    numeric=documents["NUMERIC_IDENTITY"];geometry=documents["CAD0_MULTI_SOURCE_02"];ownership=documents["CAD0_MULTI_SOURCE_03"];slots=documents["CAD0_MULTI_SOURCE_05"]
    corrected={"ROOT_BRACKET":documents["CAD0_MULTI_SOURCE_10"]["root_bracket"],"SLOT_ROWS":slots["slots"],"U4_PARTICIPATION":documents["CAD0_MULTI_SOURCE_11"]["participation"],"ZERO_EDGE_RULE":documents["CAD0_MULTI_SOURCE_07"]["later_summary_rule"]}
    if any(kind(corrected[k])!=t for k,t in TYPE_FIXES.items()):raise AdapterError("TYPE_CORRECTION")
    common=at(numeric,"/common_connected_volume_and_cad_mapping");target=common["target_m3"];fraction=common["central_share"];formula=at(geometry,"/central/union_volume_formula")
    match=re.fullmatch(r"4\*A\^2\*H_internal\+V_sensor=([0-9]+(?:\.[0-9]+)?)\*V_target",formula)
    if not match or float(match.group(1))!=float(fraction) or not target>0 or not 0<fraction<1:raise AdapterError("VOLUME_FORMULA_BINDING")
    primary=interval(at(geometry,"/sector/collector/z_m"),"collector")
    slot_intervals={name:interval(slots["slots"][name]["z_m"],name) for name in SLOTS}
    transforms=ownership["transforms"];rules=ownership["ownership"];order=transforms["sector_order_deg"]
    if order!=[0,90,180,270]:raise AdapterError("SECTOR_ORDER")
    if any(type(transforms.get(k))is not str for k in ("e_u","e_v","local_to_global","global_to_local")) or any(type(rules.get(k))is not str for k in ("central_plan","sensor","outside_central","boundary_tie","z")):raise AdapterError("OWNERSHIP_ALGORITHM")
    ownership_specs=[]
    for member in members:
        witnesses=[{"witness_id":member+":CENTRAL","owner":"CENTRAL","rule_pointers":["/ownership/central_plan","/ownership/sensor","/ownership/boundary_tie"],"transform_pointer":"/transforms/global_to_local"}]
        witnesses += [{"witness_id":member+":SECTOR_"+str(deg),"owner":"SECTOR_"+str(deg),"sector_deg":deg,"rule_pointers":["/ownership/outside_central","/ownership/boundary_tie","/ownership/z"],"transform_pointers":["/transforms/e_u","/transforms/e_v","/transforms/local_to_global","/transforms/global_to_local"]} for deg in order]
        ownership_specs.append({"member_id":member,"witnesses":witnesses})
    interval_rules={"finite_ordered_endpoints":True,"containment":"child_min>=container_min and child_max<=container_max","non_empty_overlap":"max(left_min,right_min)<min(left_max,right_max)","thickness_or_clearance":"upper_endpoint-lower_endpoint","midpoint_lower_upper_for_identity_eligibility_metrics":False}
    return {"schema_version":"gen_enc_b1_real_shape_adapter_v1","geometry_volume":{"source":"NUMERIC_IDENTITY","pointer":"/common_connected_volume_and_cad_mapping/target_m3"},"geometry_target_fraction":{"source":"NUMERIC_IDENTITY","pointer":"/common_connected_volume_and_cad_mapping/central_share","cross_check_source":"CAD0_MULTI_SOURCE_02","cross_check_pointer":"/central/union_volume_formula"},"geometry_slot_z_interval_m":{"primary_source":"CAD0_MULTI_SOURCE_02","primary_pointer":"/sector/collector/z_m","slot_source":"CAD0_MULTI_SOURCE_05","slot_pointers":{name:"/slots/"+name+"/z_m" for name in SLOTS},"runtime_primary_interval":primary,"runtime_slot_intervals":slot_intervals,"static_rules":interval_rules},"type_corrections":deepcopy(TYPE_FIXES),"future_outputs":list(FUTURE),"ownership_derivation":{"source":"CAD0_MULTI_SOURCE_03","transforms_pointer":"/transforms","ownership_algorithm_pointer":"/ownership","members":ownership_specs},"runtime_values":{"geometry_volume":target,"geometry_target_fraction":fraction,"corrected_objects":corrected},"final_test_read":False}
