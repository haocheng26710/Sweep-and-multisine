"""Driver-side typed CAD semantic projection. Imports non-semantic primitives only."""
from __future__ import annotations

import copy
import math
from typing import Any, Mapping, Sequence

from scripts.gen_enc_b1_repair_02.primitives import pointer, sha_value

PURPOSES=tuple(f"CAD0_MULTI_SOURCE_{i:02d}" for i in range(1,14))
REQUIRED={"ownership","slots","volume_roots","u4_exceptions","minima","reduced_graph","actual_fluid_graph","random_zero_edge","approval"}


class ProjectionError(RuntimeError):pass


def leaves(value:Any,path:str=""):
    if isinstance(value,dict):
        for key,child in value.items():yield from leaves(child,path+"/"+key.replace("~","~0").replace("/","~1"))
    elif isinstance(value,list):
        for index,child in enumerate(value):yield from leaves(child,path+f"/{index}")
    else:
        if isinstance(value,float) and not math.isfinite(value):raise ProjectionError("NONFINITE_LEAF")
        yield path,value


def _type(value:Any)->str:
    if isinstance(value,bool):return "boolean"
    if isinstance(value,dict):return "object"
    if isinstance(value,list):return "array"
    if isinstance(value,(int,float)):return "number"
    if isinstance(value,str):return "string"
    return "null"


def _keys(value:Mapping[str,Any],expected:set[str],label:str)->None:
    if set(value)!=expected:raise ProjectionError("TYPED_KEYS:"+label)


def _typed(values:Mapping[str,Any])->None:
    cells=values["OWNERSHIP_CELLS"]
    if not isinstance(cells,list) or len(cells)!=5:raise ProjectionError("OWNERSHIP_COUNT")
    for cell in cells:
        _keys(cell,{"cell_id","owner","positive_overlap_volume_m3"},"cell")
        if not isinstance(cell["cell_id"],str) or not isinstance(cell["owner"],str) or float(cell["positive_overlap_volume_m3"])<0:raise ProjectionError("OWNERSHIP_TYPED")
    rule=values["OWNERSHIP_RULE"];_keys(rule,{"central","sector"},"rule")
    slots=values["SLOT_ROWS"]
    if not isinstance(slots,list) or len(slots)!=20:raise ProjectionError("SLOT_COUNT")
    for slot in slots:
        _keys(slot,{"slot_id","sector","owner_cell_id","coordinates_xy_m","width_m"},"slot")
        if len(slot["coordinates_xy_m"])!=2 or float(slot["width_m"])<0:raise ProjectionError("SLOT_TYPED")
    if values["SLOT_SECTOR_ORDER"]!=["0","90","180","270"] or len(values["SLOT_MAPPING"])!=10 or len(values["SLOT_BURDEN"])!=12:raise ProjectionError("SLOT_CONTRACT")
    common=values["ROOT_COMMON"]
    _keys(common,{"domain_m","tolerance_m3","iterations","fixed_volume_m3","linear_coefficient_m2"},"root_common")
    if common["iterations"]!=80 or len(common["domain_m"])!=2 or common["domain_m"][0]>=common["domain_m"][1] or common["tolerance_m3"]<=0 or common["linear_coefficient_m2"]<=0:raise ProjectionError("ROOT_COMMON")
    if len(values["ROOT_FAMILIES"])!=4 or values["ROOT_BRACKET"]!=common["domain_m"] or values["ROOT_DOMAIN"].get("root_length_m")!=common["domain_m"]:raise ProjectionError("ROOT_MULTI_SOURCE")
    if values["ROOT_DERIVED_PROOF"].get("strict_monotone") is not True or values["ROOT_INDEPENDENT_PROOF"].get("bracket_verified") is not True:raise ProjectionError("ROOT_PROOF")
    if not 0<float(values["GEOMETRY_TARGET_FRACTION"])<1 or float(values["GEOMETRY_VOLUME"])<=0:raise ProjectionError("GEOMETRY")
    coords=values["U4_COORDINATES"];_keys(coords,{"x_m","suffix_z_m"},"u4_coords")
    objects=values["U4_OBJECTS"]
    if len(objects)!=4 or values["U4_COUNTS"]!={"total":20,"per_sector":5} or values["U4_PARTICIPATION"]!="U4_INTERFACE_EXCEPTION_ONLY":raise ProjectionError("U4_COUNT_PARTICIPATION")
    for item in objects:
        _keys(item,{"sector","exceptions"},"u4_object")
        if len(item["exceptions"])!=5:raise ProjectionError("U4_PER_SECTOR")
        for exc in item["exceptions"]:_keys(exc,{"suffix","feature_m","load_path_m"},"u4_exception")
    fields=values["STATIC_FIELDS"]
    _keys(fields,{"general_feature_candidates","general_load_candidates","exception_feature_candidates","exception_load_candidates","minimum_general_feature_m","minimum_general_load_path_m"},"static_fields")
    if not all(isinstance(fields[x],list) and fields[x] for x in ("general_feature_candidates","general_load_candidates","exception_feature_candidates","exception_load_candidates")):raise ProjectionError("STATIC_CANDIDATES")
    if len(values["STATIC_FAIL_RULES"])!=4:raise ProjectionError("FAIL_RULES")
    _keys(values["SOLID_METRICS"],{"feature_metric","load_path_metric"},"solid_metrics");_keys(values["SOLID_ELIGIBLE_PAIR"],{"rule"},"eligible_pair")
    graph=values["GRAPH_DEFINITION"]
    _keys(graph,{"reduced_nodes","reduced_edges","actual_nodes","actual_edges"},"graphs")
    if len(graph["reduced_nodes"])!=4 or len(graph["reduced_edges"])!=6 or len(graph["actual_nodes"])!=5 or len(graph["actual_edges"])!=4:raise ProjectionError("GRAPH_COUNTS")
    for edge in graph["reduced_edges"]:_keys(edge,{"edge_id","a","b","parameter_key"},"reduced_edge")
    if [edge["parameter_key"] for edge in graph["reduced_edges"]] != ["edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270"]:raise ProjectionError("GRAPH_PARAMETER_KEYS")
    for edge in graph["actual_edges"]:
        _keys(edge,{"edge_id","a","b","positive_area_m2"},"actual_edge")
        if edge["positive_area_m2"]<=0:raise ProjectionError("ACTUAL_AREA")
    _keys(values["GRAPH_TERMS"],{"positive_edge_rule","bfs_rule"},"graph_terms")
    zero=values["ZERO_EDGE_RULE"];_keys(zero,{"family","exact_zero","branch","comparison"},"zero_rule")
    if zero!={"family":"FIXED_SEED_RANDOM_DISORDERED","exact_zero":0.0,"branch":"U_LT_0P5_ATOM","comparison":"u<0.5"}:raise ProjectionError("ZERO_RULE")
    for key in ("APPROVAL_U1","APPROVAL_U2","APPROVAL_U3"):
        if not isinstance(values[key],dict) or not values[key]:raise ProjectionError("APPROVAL")
    if not isinstance(values["APPROVAL_CARRY"],list) or not values["APPROVAL_CARRY"]:raise ProjectionError("APPROVAL_CARRY")


def project(objects:Mapping[str,Any],entries_input:Sequence[Mapping[str,Any]],contract:Mapping[str,Any])->dict[str,Any]:
    entries={x["purpose"]:x for x in entries_input if x.get("purpose") in PURPOSES}
    if set(entries)!=set(PURPOSES) or any(p not in objects for p in PURPOSES):raise ProjectionError("EXACT_13")
    selectors=contract.get("semantic_selectors")
    if contract.get("required_categories")!=["ownership","slots","volume_roots","u4_exceptions","minima","reduced_graph","actual_fluid_graph","random_zero_edge","approval"] or not isinstance(selectors,list):raise ProjectionError("CONTRACT_CATEGORIES")
    ids=[x.get("id") for x in selectors];pairs=[(x.get("purpose"),x.get("pointer")) for x in selectors]
    if len(ids)!=len(set(ids)) or len(pairs)!=len(set(pairs)) or {x.get("category") for x in selectors}!=REQUIRED:raise ProjectionError("SELECTOR_SET")
    values={};semantic=[]
    for selector in selectors:
        selected=pointer(objects[selector["purpose"]],selector["pointer"])
        if _type(selected)!=selector["type"] or not selector.get("consumers"):raise ProjectionError("SELECTOR_TYPE_OR_CONSUMER:"+selector["id"])
        values[selector["id"]]=copy.deepcopy(selected)
        for sub,value in leaves(selected):semantic.append({"purpose":selector["purpose"],"pointer":selector["pointer"]+sub,"selector_id":selector["id"],"category":selector["category"],"consumers":selector["consumers"],"value_sha256":sha_value(value)})
    semantic_paths={(x["purpose"],x["pointer"]) for x in semantic};unused=[]
    for purpose in PURPOSES:
        value=objects[purpose];shape=entries[purpose]["object_shape"]
        if not isinstance(value,dict) or list(value)!=shape["field_names"] or len(value)!=shape["field_count"]:raise ProjectionError("TOP_SHAPE:"+purpose)
        if any(not isinstance(value[k],list) or len(value[k])!=n for k,n in shape.get("array_counts",{}).items()):raise ProjectionError("ARRAY_SHAPE:"+purpose)
        for path,leaf in leaves(value):
            if (purpose,path) in semantic_paths:continue
            matches=[x for x in contract["unused_leaf_allowlist"] if x["purpose"]==purpose and (x["pointer_prefix"]=="" or path==x["pointer_prefix"] or path.startswith(x["pointer_prefix"]+"/"))]
            if len(matches)!=1 or not matches[0].get("reason"):raise ProjectionError("UNUSED_SEMANTIC_LEAF:"+purpose+path)
            unused.append({"purpose":purpose,"pointer":path,"reason":matches[0]["reason"]})
    _typed(values)
    matrix=sorted(semantic,key=lambda x:(x["purpose"],x["pointer"],x["selector_id"]))
    structural=[{k:row[k] for k in ("purpose","pointer","selector_id","category","consumers")} for row in matrix]
    return {"schema_version":"gen_enc_fast_b1_repair_02_typed_cad_projection_v1","values":values,"semantic_leaf_count":len(matrix),"dependency_matrix":matrix,"dependency_matrix_sha256":sha_value(structural),"unused_leaf_allowlist":unused,"unused_leaf_count":len(unused),"projection_contract_sha256":sha_value(contract)}
