from __future__ import annotations
import hashlib,json,math
from pathlib import Path
from typing import Any
TASK="01a049a7-15ca-79e1-92a2-d3822ba8609d";PREFIXES=("HAND","NEAR","RANDOM","PHYSICS");CLAIM="BATCH_LOCAL_IDENTITY_COMPLETE_CAD_STATIC_AND_TECHNICAL_VALIDITY_ONLY"
EXPECTED_MEMBER_IDS=tuple(f"{prefix}_{i:02d}" for prefix in PREFIXES for i in range(1,6))
def canonical(v:Any)->bytes:return (json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)+"\n").encode()
def digest(v:Any)->str:return hashlib.sha256(canonical(v)).hexdigest()
def load(p:Path):return json.loads(p.read_text(encoding="utf-8"))
def verify_member(m:dict):
    claimed=m["identity_sha256"];base=dict(m);base.pop("identity_sha256")
    if digest(base)!=claimed:raise ValueError("IDENTITY_HASH:"+m["member_id"])
    p=m["parameters"]
    if not math.isclose(p["q270"],-(p["q0"]+p["q90"]+p["q180"])/3,rel_tol=0,abs_tol=1e-15):raise ValueError("Q270:"+m["member_id"])
    ev=m["cad_static_evidence"]
    if len(ev["ownership_witnesses"])!=5 or len({x["witness_id"] for x in ev["ownership_witnesses"]})!=5:raise ValueError("OWNERSHIP5:"+m["member_id"])
    for row in ev["slot_interval_witnesses"]:
        z=row["z_interval_m"];c=row["collector_z_interval_m"]
        if len(z)!=2 or not all(math.isfinite(x) for x in z) or not z[0]<z[1] or row["thickness_m"]!=z[1]-z[0] or row["contained_in_internal_fluid"] is not True or (max(z[0],c[0])<min(z[1],c[1]))!=row["non_empty_collector_overlap"]:raise ValueError("INTERVAL:"+m["member_id"])
    if ev["midpoint_or_endface_used"] is not False or ev["interval_native"] is not True:raise ValueError("SCALAR_Z:"+m["member_id"])
    root_fail=False
    for root in ev["volume_root_witnesses"]:
        if root["status"]!="PASS" or root["iterations"]!=80 or len(root["trace"])!=80 or abs(root["residual_m3"])>1e-12:root_fail=True
        elif not math.isclose(root["measured_volume_m3"]-root["target_volume_m3"],root["residual_m3"],rel_tol=0,abs_tol=1e-18):raise ValueError("ROOT_RESIDUAL:"+m["member_id"])
    general=ev["general_minima"];general_ok=general["feature_m"]>=general["feature_threshold_m"] and general["load_path_m"]>=general["load_path_threshold_m"]
    expected="ELIGIBLE" if general_ok and not root_fail else "COST_INELIGIBLE"
    if m["static_status"]!=expected or bool(m["failure_reasons"])!=(expected!="ELIGIBLE") or m["claim_ceiling"]!=CLAIM or m["final_test_read"] is not False:raise ValueError("STATUS:"+m["member_id"])
def _ordered_member_paths(member_root:Path):
    observed=list(member_root.glob("*.json"));expected_names={member_id+".json" for member_id in EXPECTED_MEMBER_IDS}
    if {path.name for path in observed}!=expected_names:raise ValueError("EXACT20_FILE_SET")
    return [member_root/(member_id+".json") for member_id in EXPECTED_MEMBER_IDS]
def verify(staging:Path,run_id:str):
    expected=list(EXPECTED_MEMBER_IDS);files=_ordered_member_paths(staging/"members");members=[load(p) for p in files]
    if [x["member_id"] for x in members]!=expected:raise ValueError("EXACT20_ORDER")
    for m in members:verify_member(m)
    index=load(staging/"batch_index.json");audit=load(staging/"static_audit.json")
    if index["member_count"]!=20 or index["family_count"]!=4 or index["run_id"]!=run_id or len(index["members"])!=20:raise ValueError("INDEX")
    for row,m in zip(index["members"],members):
        if row["member_id"]!=m["member_id"] or row["identity_sha256"]!=m["identity_sha256"] or row["static_status"]!=m["static_status"]:raise ValueError("INDEX_MEMBER")
    family_hashes={}
    for prefix in PREFIXES:
        f=load(staging/"families"/(prefix+".json"));subset=[m for m in members if m["member_id"].startswith(prefix+"_")]
        if f["member_count"]!=5 or f["member_ids"]!=[m["member_id"] for m in subset] or f["member_hashes"]!=[m["identity_sha256"] for m in subset]:raise ValueError("FAMILY:"+prefix)
        family_hashes[prefix]=digest(f)
    eligible=sum(m["static_status"]=="ELIGIBLE" for m in members);ineligible=20-eligible
    if audit["member_count"]!=20 or audit["ownership_witness_count"]!=100 or audit["eligible_count"]!=eligible or audit["ineligible_count"]!=ineligible or audit["failed_count"]!=sum(bool(m["failure_reasons"]) for m in members) or audit["midpoint_or_endface_used"] is not False:raise ValueError("AUDIT")
    allowed={"batch_index.json","static_audit.json","generation_provenance.json"}
    if {p.name for p in staging.iterdir() if p.is_file()}!=allowed or len(files)!=20 or len(list((staging/"families").glob("*.json")))!=4:raise ValueError("ZERO_UNLISTED")
    return {"schema_version":"gen_enc_fast_b1_science_first_verification_v1","record_kind":"INDEPENDENT_B1_EXACT20_VERIFICATION","task_id":TASK,"run_id":run_id,"verdict":"PASS","member_count":20,"family_count":4,"ownership_witness_count":100,"eligible_count":eligible,"ineligible_count":ineligible,"failed_count":audit["failed_count"],"member_identity_hashes":{m["member_id"]:m["identity_sha256"] for m in members},"family_manifest_hashes":family_hashes,"batch_index_sha256":digest(index),"static_audit_sha256":digest(audit),"claim_ceiling":CLAIM,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False}
