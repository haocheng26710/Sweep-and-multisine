from __future__ import annotations

import hashlib
import json
import math
import os
import platform
from pathlib import Path
from typing import Any

import jsonschema

RUN_ID="5755da623ea9842097773c1579aa6dd436f1c88c1809d290342e4d804acff804"
BASE=Path(".g92/5755")
STAGING=BASE/"staging"; VERIFY=BASE/"verification"; FAILURE=BASE/"failure"
ALLOW=Path("outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/s1_implementation_freeze/path_allowlist_manifest.json")
ALLOW_SHA="7a62b0508e253d7740e08e396f3164e3b66b6745c7d42e93f8444f2a244a5ab1"
SCHEMA_ROOT=Path("schemas/gen_enc/gen_enc_2c_rev03")
FAMILIES=("HAND_DESIGNED","NEAR_INDEPENDENT","FIXED_SEED_RANDOM_DISORDERED","PHYSICS_METAMATERIAL_INSPIRED")
PREFIX=dict(zip(FAMILIES,("HAND","NEAR","RANDOM","PHYSICS")));DOF=dict(zip(FAMILIES,(12,12,13,15)));ZERO="0"*64
BATCHES=(
("B1","65ce5d21d1108927709e24ed475d1477c8a46c21be8550b3d152ab449dc03605","56c06e8bf25c655389cb79a1edc1fcb434ebab80cb46fec99bd1d5ac9191fb19",1,5,"b1_science_first_exact20_runs"),
("B2","12d5f3184251eef8ff5e55493318dbc403ec8973a15289a2bd53d9ec8c4cd835","0782e5f88ebcc7bdae74b8deb00974014df7aced751c44b0a9e841efd5a17a77",6,10,"b2_science_first_exact20_runs"),
("B3","ef181dfacdfc9c159a682846793dc7716a007b5fe4fb17efb1983d5e5bdba315","f2ae7f490ee7804ba3a62de334c7be460ebc202f637d0d0121da118bf7b5bda4",11,15,"b3_science_first_exact20_runs"),
("B4","b350702fffb198bfd7296057cf78bf3b083d1e06431a3e438c06b8f46cdf5938","4212d00c50c35ff26d668610406542a0b2a816b6c202d38d544b746c4f39f7cf",16,20,"b4_science_first_exact20_runs"),)
SCHEMAS=("scientific_instance_identity.schema.json","family_manifest.schema.json","identity_index.schema.json","analysis_summary.schema.json","artifact_inventory.schema.json","scientific_hash_manifest.schema.json","independent_verification_report.schema.json","execution_record.schema.json")

class VerifyError(RuntimeError): pass
def canonical(v:Any)->bytes:
    def ck(x:Any)->None:
        if isinstance(x,float) and (not math.isfinite(x) or (x==0 and math.copysign(1,x)<0)):raise VerifyError("NUMBER")
        if isinstance(x,dict):
            for y in x.values():ck(y)
        elif isinstance(x,list):
            for y in x:ck(y)
    ck(v);return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1<<20),b""):h.update(c)
    return h.hexdigest()
def load(p:Path)->Any:return json.loads(p.read_text(encoding="utf-8"))
def write_json(p:Path,v:Any)->None:
    p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+".tmp")
    with q.open("xb") as f:f.write(canonical(v));f.flush();os.fsync(f.fileno())
    os.replace(q,p)
def self_hash(v:dict[str,Any],field:str)->str:c=dict(v);c[field]=ZERO;return sha_bytes(canonical(c))
def source_identity_hash(v:dict[str,Any])->str:return sha_bytes(canonical(v)+b"\n")
def source_root(b:tuple[Any,...])->Path:return Path("outputs/gen_enc/GEN_ENC_FAST_START")/b[5]/b[1]/"results"

def independently_read_sources()->dict[str,tuple[dict[str,Any],str,str]]:
    out={}
    for bid,run_id,manifest_sha,first,last,directory in BATCHES:
        root=Path("outputs/gen_enc/GEN_ENC_FAST_START")/directory/run_id/"results"
        if sha_file(root/"SHA256SUMS.json")!=manifest_sha:raise VerifyError(bid+":MANIFEST")
        sums=load(root/"SHA256SUMS.json");listed={x["path"]:x["sha256"] for x in sums["files"]}
        disk={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        if disk!=set(listed)|{"SHA256SUMS.json"}:raise VerifyError(bid+":UNLISTED")
        for rel,digest in listed.items():
            if sha_file(root/rel)!=digest:raise VerifyError(bid+":HASH:"+rel)
        index=load(root/"batch_index.json");ids=[f"{PREFIX[f]}_{i:02d}" for f in FAMILIES for i in range(first,last+1)]
        if [x["member_id"] for x in index["members"]]!=ids:raise VerifyError(bid+":ORDER")
        for row in index["members"]:
            path=root/row["path"];src=load(path);base=dict(src);claim=base.pop("identity_sha256")
            if source_identity_hash(base)!=claim or row["identity_sha256"]!=claim:raise VerifyError(bid+":IDENTITY_HASH")
            ev=src["cad_static_evidence"]
            if src["static_status"]!="ELIGIBLE" or src["final_test_read"] or not ev["interval_native"] or ev["midpoint_or_endface_used"] or len(ev["ownership_witnesses"])!=5:raise VerifyError(bid+":STATIC")
            if len(ev["volume_root_witnesses"])!=4 or any(x["status"]!="PASS" for x in ev["volume_root_witnesses"]):raise VerifyError(bid+":ROOTS")
            rel=path.as_posix();out[src["member_id"]]=(src,rel,sha_file(path))
    if len(out)!=80:raise VerifyError("SOURCE_UNIQUE80")
    return out

def main()->None:
    try:
        if sha_file(ALLOW)!=ALLOW_SHA:raise VerifyError("ALLOW_HASH")
        hand=load(source_root(BATCHES[0])/"members/HAND_01.json");base=dict(hand);claim=base.pop("identity_sha256")
        if sha_bytes(canonical(base))==claim or source_identity_hash(base)!=claim:raise VerifyError("HAND_01_TRAILING_LF_REGRESSION")
        paths=load(ALLOW)["paths"]
        files=[p for p in STAGING.rglob("*") if p.is_file()]
        if len(files)!=92 or {p.relative_to(STAGING).as_posix() for p in files}!=set(paths):raise VerifyError("STAGING_EXACT92")
        sources=independently_read_sources();scientific=[]
        for i in range(80):
            obj=load(STAGING/paths[i]);jsonschema.Draft202012Validator(load(SCHEMA_ROOT/SCHEMAS[0])).validate(obj)
            family=FAMILIES[i//20];ordinal=i%20+1;mid=f"{PREFIX[family]}_{ordinal:02d}";src,src_path,src_hash=sources[mid]
            if obj["member_id"]!=mid or obj["family_id"]!=family or obj["global_ordinal"]!=i+1 or obj["parameters"]!=src["parameters"] or obj["status"]!="STATIC_IDENTITY_ELIGIBLE":raise VerifyError("OUTPUT_MEMBER:"+mid)
            if obj["member_sha256"]!=self_hash(obj,"member_sha256"):raise VerifyError("OUTPUT_SELF_HASH:"+mid)
            prov=obj["input_provenance"];binding=json.loads(prov["pointer_or_seed_binding"])
            if prov["authority_path"]!=src_path or prov["authority_sha256"]!=src_hash or binding!={"source_batch":src["batch_id"],"source_identity_sha256":src["identity_sha256"],"source_input_provenance":src["input_provenance"],"source_slot_ordinal":src["slot_ordinal"]}:raise VerifyError("SOURCE_BINDING:"+mid)
            ev=src["cad_static_evidence"];expected={"bounds_pass":True,"dof":DOF[family],"volume_m3":3.014899604922098e-5,"envelope_m":[.21,.21,.0122],"interface_identity":"U4_CARDINAL_4PORT_CENTRAL_M1_v1","actual_fluid_component_count":1,"minimum_feature_m":ev["general_minima"]["feature_m"],"solid_load_path_m":ev["general_minima"]["load_path_m"]}
            if obj["cad_static_audit"]!=expected:raise VerifyError("STATIC_MAP:"+mid)
            scientific.append({"path":paths[i],"sha256":sha_file(STAGING/paths[i])})
        family_entries=[]
        for fi,family in enumerate(FAMILIES,1):
            m=load(STAGING/paths[79+fi]);jsonschema.Draft202012Validator(load(SCHEMA_ROOT/SCHEMAS[1])).validate(m)
            expected=[{"ordinal":j+1,"path":paths[fi*20-20+j],"sha256":scientific[fi*20-20+j]["sha256"],"status":"STATIC_IDENTITY_ELIGIBLE"} for j in range(20)]
            if m["family_id"]!=family or m["ordered_members"]!=expected or m["family_manifest_sha256"]!=self_hash(m,"family_manifest_sha256"):raise VerifyError("FAMILY:"+family)
            scientific.append({"path":paths[79+fi],"sha256":sha_file(STAGING/paths[79+fi])});family_entries.append({"ordinal":fi,"family_id":family,"path":paths[79+fi],"sha256":scientific[-1]["sha256"]})
        index=load(STAGING/paths[84]);jsonschema.Draft202012Validator(load(SCHEMA_ROOT/SCHEMAS[2])).validate(index)
        if index["ordered_families"]!=family_entries or index["identity_index_sha256"]!=self_hash(index,"identity_index_sha256"):raise VerifyError("INDEX")
        scientific.append({"path":paths[84],"sha256":sha_file(STAGING/paths[84])})
        analysis=load(STAGING/paths[85]);inventory=load(STAGING/paths[86]);hashes=load(STAGING/paths[87])
        for obj,schema in ((analysis,SCHEMAS[3]),(inventory,SCHEMAS[4]),(hashes,SCHEMAS[5])):jsonschema.Draft202012Validator(load(SCHEMA_ROOT/schema)).validate(obj)
        expected_formal={"member":sha_bytes(canonical(scientific[:80])),"family":sha_bytes(canonical(scientific[80:84])),"index":scientific[84]["sha256"]}
        if analysis["formal_hashes"]!=expected_formal or analysis["scientific_hypothesis_status"]!="NOT_TESTED" or hashes["scientific_entries"]!=scientific:raise VerifyError("RESULT_CHAIN")
        rb=hashes["runtime_binding"]
        if rb.get("matched_cost_axes")!="FROZEN_METADATA_UNMODIFIED_COMPARISON_NOT_TESTED" or rb.get("stable_rank")!="NOT_TESTED" or rb.get("H_equals_ACB")!="NOT_ESTABLISHED" or any(rb.get(k)!="NOT_TESTED" for k in ("ranking","performance","response","timing","simulation")):raise VerifyError("CLAIM_BOUNDARY")
        checks=["HAND_01_NO_LF_MISMATCH_WITH_LF_MATCH_REGRESSION","FOUR_BATCH_SHA256_AND_ZERO_UNLISTED","SOURCE_IDENTITY_SELF_HASH_WITH_TRAILING_LF_AND_PROVENANCE","EXACT80_UNIQUE_AND_20_PER_FAMILY","B1_TO_B4_INPUT_AND_FAMILY_01_TO_20_OUTPUT_ORDER","FULL_INTERVAL_NO_MIDPOINT_OR_ENDFACE","STATIC_AUDIT_MAPPING_AND_FROZEN_THRESHOLDS","MATCHED_COST_AXES_METADATA_UNMODIFIED_COMPARISON_NOT_TESTED","STABLE_RANK_AND_RANKING_NOT_TESTED","H_EQUALS_ACB_NOT_ESTABLISHED","PERFORMANCE_RESPONSE_TIMING_SIMULATION_NOT_TESTED","EXACT92_ALLOWLIST_AND_HASH_CHAIN","FINAL_TEST_READ_FALSE"]
        report={"schema_version":"gen_enc_2c_independent_verification_rev03_v1","mode":"READ_ONLY_INDEPENDENT_RECOMPUTATION","status":"PASS_STATIC_IDENTITY_RECOMPUTATION","observed_counts":{"members":80,"families":4,"eligible":80,"source_batches":4,"artifacts":92,"unlisted":0},"recomputed_checks":checks,"failure_count":0,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False}
        jsonschema.Draft202012Validator(load(SCHEMA_ROOT/SCHEMAS[6])).validate(report);write_json(STAGING/paths[88],report)
        execution=load(STAGING/paths[89]);execution["terminal_state"]="SUCCESS";execution["observed_counts"]={"members":80,"families":4,"eligible":80,"artifacts":92,"verification_failure":0};jsonschema.Draft202012Validator(load(SCHEMA_ROOT/SCHEMAS[7])).validate(execution);write_json(STAGING/paths[89],execution)
        lines=[f"{sha_file(STAGING/paths[i])}  {paths[i]}" for i in range(92) if i!=90];(STAGING/paths[90]).write_bytes(("\n".join(lines)+"\n").encode())
        for line in (STAGING/paths[90]).read_text().splitlines():
            digest,rel=line.split("  ",1)
            if sha_file(STAGING/rel)!=digest:raise VerifyError("SHA256SUMS")
        schema_subjects=((0,SCHEMAS[0]),(80,SCHEMAS[1]),(84,SCHEMAS[2]),(85,SCHEMAS[3]),(86,SCHEMAS[4]),(87,SCHEMAS[5]),(88,SCHEMAS[6]),(89,SCHEMAS[7]))
        for idx,schema in schema_subjects:jsonschema.Draft202012Validator(load(SCHEMA_ROOT/schema)).validate(load(STAGING/paths[idx]))
        VERIFY.mkdir(parents=True,exist_ok=True);write_json(VERIFY/"PASS.json",{"schema_version":"gen_enc_final92_independent_verification_v1","run_id":RUN_ID,"status":"PASS","recomputed_checks":checks,"member_count":80,"family_counts":{"HAND":20,"NEAR":20,"RANDOM":20,"PHYSICS":20},"artifact_count":92,"claim_ceiling":"INTEGRATED_IDENTITY_COMPLETE80_AND_CAD_STATIC_TECHNICAL_VALIDITY_ONLY","scientific_hypothesis_status":"NOT_TESTED","final_test_read":False})
    except BaseException as exc:
        FAILURE.mkdir(parents=True,exist_ok=True);write_json(FAILURE/"FAILURE.json",{"run_id":RUN_ID,"state":"FAILURE","error":type(exc).__name__+":"+str(exc),"final_test_read":False});raise

if __name__=="__main__":main()
