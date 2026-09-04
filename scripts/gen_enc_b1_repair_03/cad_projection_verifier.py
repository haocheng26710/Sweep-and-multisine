"""Independently written verifier-side typed CAD semantic projection."""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any, Mapping, Sequence

from scripts.gen_enc_b1_repair_03.primitives import pointer, sha_value

PURPOSES=tuple("CAD0_MULTI_SOURCE_%02d"%i for i in range(1,14))
CATEGORIES=("ownership","slots","volume_roots","u4_exceptions","minima","reduced_graph","actual_fluid_graph","random_zero_edge","approval")


class VerificationProjectionError(RuntimeError):pass


def _leaf_rows(node:Any,address:str=""):
    if type(node) is dict:
        for name in node:yield from _leaf_rows(node[name],address+"/"+name.replace("~","~0").replace("/","~1"))
    elif type(node) is list:
        for number,item in enumerate(node):yield from _leaf_rows(item,address+"/"+str(number))
    else:
        if type(node) is float and not isfinite(node):raise VerificationProjectionError("NONFINITE")
        yield address,node


def _kind(x:Any)->str:
    return "boolean" if type(x) is bool else "object" if type(x) is dict else "array" if type(x) is list else "number" if type(x) in (int,float) else "string" if type(x) is str else "null"


def _exact(record:Mapping[str,Any],names:set[str],tag:str)->None:
    if set(record.keys())!=names:raise VerificationProjectionError("FIELDS:"+tag)


def _check(v:Mapping[str,Any])->None:
    if type(v["OWNERSHIP_CELLS"]) is not list or len(v["OWNERSHIP_CELLS"])!=5:raise VerificationProjectionError("OWNERS")
    for cell in v["OWNERSHIP_CELLS"]:
        _exact(cell,{"cell_id","owner","positive_overlap_volume_m3"},"owner")
        if type(cell["cell_id"]) is not str or type(cell["owner"]) is not str or cell["positive_overlap_volume_m3"]<0:raise VerificationProjectionError("OWNER_TYPE")
    _exact(v["OWNERSHIP_RULE"],{"central","sector"},"ownership_rule")
    if len(v["SLOT_ROWS"])!=20:raise VerificationProjectionError("SLOTS")
    for slot in v["SLOT_ROWS"]:
        _exact(slot,{"slot_id","sector","owner_cell_id","coordinates_xy_m","width_m"},"slot")
        if len(slot["coordinates_xy_m"])!=2 or slot["width_m"]<0:raise VerificationProjectionError("SLOT_VALUE")
    if v["SLOT_SECTOR_ORDER"]!=["0","90","180","270"] or len(v["SLOT_MAPPING"])!=10 or len(v["SLOT_BURDEN"])!=12:raise VerificationProjectionError("SLOT_RULE")
    common=v["ROOT_COMMON"]
    _exact(common,{"domain_m","tolerance_m3","iterations","fixed_volume_m3","linear_coefficient_m2"},"root")
    if common["iterations"]!=80 or len(common["domain_m"])!=2 or not common["domain_m"][0]<common["domain_m"][1] or common["tolerance_m3"]<=0 or common["linear_coefficient_m2"]<=0:raise VerificationProjectionError("ROOT_COMMON")
    if len(v["ROOT_FAMILIES"])!=4 or v["ROOT_BRACKET"]!=common["domain_m"] or v["ROOT_DOMAIN"].get("root_length_m")!=common["domain_m"]:raise VerificationProjectionError("ROOT_BINDING")
    if v["ROOT_DERIVED_PROOF"].get("strict_monotone") is not True or v["ROOT_INDEPENDENT_PROOF"].get("bracket_verified") is not True:raise VerificationProjectionError("PROOF")
    if v["GEOMETRY_VOLUME"]<=0 or not 0<v["GEOMETRY_TARGET_FRACTION"]<1:raise VerificationProjectionError("GEOMETRY")
    _exact(v["U4_COORDINATES"],{"x_m","suffix_z_m"},"u4_coords")
    if len(v["U4_OBJECTS"])!=4 or v["U4_COUNTS"]!={"total":20,"per_sector":5} or v["U4_PARTICIPATION"]!="U4_INTERFACE_EXCEPTION_ONLY":raise VerificationProjectionError("U4")
    for group in v["U4_OBJECTS"]:
        _exact(group,{"sector","exceptions"},"u4_group")
        if len(group["exceptions"])!=5:raise VerificationProjectionError("U4_FIVE")
        for item in group["exceptions"]:_exact(item,{"suffix","feature_m","load_path_m"},"u4_item")
    fields=v["STATIC_FIELDS"]
    _exact(fields,{"general_feature_candidates","general_load_candidates","exception_feature_candidates","exception_load_candidates","minimum_general_feature_m","minimum_general_load_path_m"},"minima")
    for name in ("general_feature_candidates","general_load_candidates","exception_feature_candidates","exception_load_candidates"):
        if type(fields[name]) is not list or not fields[name]:raise VerificationProjectionError("CANDIDATES")
    if len(v["STATIC_FAIL_RULES"])!=4:raise VerificationProjectionError("FAIL_RULES")
    _exact(v["SOLID_METRICS"],{"feature_metric","load_path_metric"},"metrics");_exact(v["SOLID_ELIGIBLE_PAIR"],{"rule"},"pair")
    graph=v["GRAPH_DEFINITION"];_exact(graph,{"reduced_nodes","reduced_edges","actual_nodes","actual_edges"},"graph")
    if tuple(map(len,(graph["reduced_nodes"],graph["reduced_edges"],graph["actual_nodes"],graph["actual_edges"])))!=(4,6,5,4):raise VerificationProjectionError("GRAPH_COUNT")
    for edge in graph["reduced_edges"]:_exact(edge,{"edge_id","a","b","parameter_key"},"r_edge")
    if [edge["parameter_key"] for edge in graph["reduced_edges"]] != ["edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270"]:raise VerificationProjectionError("PARAMETER_KEYS")
    for edge in graph["actual_edges"]:
        _exact(edge,{"edge_id","a","b","positive_area_m2"},"a_edge")
        if edge["positive_area_m2"]<=0:raise VerificationProjectionError("AREA")
    _exact(v["GRAPH_TERMS"],{"positive_edge_rule","bfs_rule"},"terms")
    _exact(v["ZERO_EDGE_RULE"],{"family","exact_zero","branch","comparison"},"zero")
    if v["ZERO_EDGE_RULE"]!={"family":"FIXED_SEED_RANDOM_DISORDERED","exact_zero":0.0,"branch":"U_LT_0P5_ATOM","comparison":"u<0.5"}:raise VerificationProjectionError("ZERO_RULE")
    if any(type(v[k]) is not dict or not v[k] for k in ("APPROVAL_U1","APPROVAL_U2","APPROVAL_U3")) or type(v["APPROVAL_CARRY"]) is not list or not v["APPROVAL_CARRY"]:raise VerificationProjectionError("APPROVAL")


def project(objects:Mapping[str,Any],entries_input:Sequence[Mapping[str,Any]],contract:Mapping[str,Any])->dict[str,Any]:
    entries={e.get("purpose"):e for e in entries_input if e.get("purpose") in PURPOSES}
    if set(entries.keys())!=set(PURPOSES) or not set(PURPOSES).issubset(objects):raise VerificationProjectionError("THIRTEEN")
    selectors=contract.get("semantic_selectors",[])
    if tuple(contract.get("required_categories",[]))!=CATEGORIES:raise VerificationProjectionError("CATEGORIES")
    ids=[s.get("id") for s in selectors];locations=[(s.get("purpose"),s.get("pointer")) for s in selectors]
    if len(ids)!=len(set(ids)) or len(locations)!=len(set(locations)) or {s.get("category") for s in selectors}!=set(CATEGORIES):raise VerificationProjectionError("SELECTORS")
    values={};matrix=[]
    for spec in selectors:
        chosen=pointer(objects[spec["purpose"]],spec["pointer"])
        if _kind(chosen)!=spec["type"] or type(spec.get("consumers")) is not list or not spec["consumers"]:raise VerificationProjectionError("SELECTED_TYPE")
        values[spec["id"]]=deepcopy(chosen)
        for tail,leaf in _leaf_rows(chosen):matrix.append({"purpose":spec["purpose"],"pointer":spec["pointer"]+tail,"selector_id":spec["id"],"category":spec["category"],"consumers":spec["consumers"],"value_sha256":sha_value(leaf)})
    used={(row["purpose"],row["pointer"]) for row in matrix};unused=[]
    for purpose in PURPOSES:
        doc=objects[purpose];shape=entries[purpose]["object_shape"]
        # Independently enforce the exact key set/cardinality after canonical
        # JSON key sorting; insertion order is not semantic authority data.
        if type(doc) is not dict or set(doc)!=set(shape["field_names"]) or len(doc)!=shape["field_count"]:raise VerificationProjectionError("SHAPE:"+purpose)
        for field,count in shape.get("array_counts",{}).items():
            if type(doc[field]) is not list or len(doc[field])!=count:raise VerificationProjectionError("ARRAY:"+purpose)
        for address,leaf in _leaf_rows(doc):
            if (purpose,address) in used:continue
            candidates=[a for a in contract["unused_leaf_allowlist"] if a["purpose"]==purpose and (a["pointer_prefix"]=="" or address==a["pointer_prefix"] or address.startswith(a["pointer_prefix"]+"/"))]
            if len(candidates)!=1 or not candidates[0].get("reason"):raise VerificationProjectionError("UNCOVERED:"+purpose+address)
            unused.append({"purpose":purpose,"pointer":address,"reason":candidates[0]["reason"]})
    _check(values);matrix.sort(key=lambda row:(row["purpose"],row["pointer"],row["selector_id"]))
    structural=[{name:row[name] for name in ("purpose","pointer","selector_id","category","consumers")} for row in matrix]
    return {"schema_version":"gen_enc_fast_b1_repair_03_typed_cad_projection_v1","values":values,"semantic_leaf_count":len(matrix),"dependency_matrix":matrix,"dependency_matrix_sha256":sha_value(structural),"unused_leaf_allowlist":unused,"unused_leaf_count":len(unused),"projection_contract_sha256":sha_value(contract)}
