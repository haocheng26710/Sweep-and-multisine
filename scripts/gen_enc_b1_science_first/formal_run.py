from __future__ import annotations
import argparse,hashlib,json,math,shutil,sys
from pathlib import Path
from typing import Any
from scripts.gen_enc_b1_mapping_adapter_01.driver_adapter import build as build_adapter

TASK="01a049a7-15ca-79e1-92a2-d3822ba8609d";FAMILIES=("HAND_DESIGNED","NEAR_INDEPENDENT","FIXED_SEED_RANDOM_DISORDERED","PHYSICS_METAMATERIAL_INSPIRED");PREFIX=dict(zip(FAMILIES,("HAND","NEAR","RANDOM","PHYSICS")));SECTORS=("0","90","180","270");MASK=(1<<64)-1;GAMMA=0x9E3779B97F4A7C15
CLAIM="BATCH_LOCAL_IDENTITY_COMPLETE_CAD_STATIC_AND_TECHNICAL_VALIDITY_ONLY"
def canonical(v:Any)->bytes:return (json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)+"\n").encode()
def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha_file(p:Path)->str:return sha_bytes(p.read_bytes())
def write(p:Path,v:Any):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(canonical(v))
def pointer(root:Any,address:str)->Any:
    cur=root
    for raw in address[1:].split("/") if address else []:
        key=raw.replace("~1","/").replace("~0","~");cur=cur[int(key)] if type(cur)is list else cur[key]
    return cur
def load_inputs(repo:Path):
    allow=json.loads((repo/"outputs/gen_enc/GEN_ENC_FAST_START/fast_0_authority_batch_contract_freeze/authority_allowlist.json").read_text());cache={};objects={}
    if allow["entry_count"]!=20:raise ValueError("ALLOWLIST_COUNT")
    for e in allow["entries"]:
        p=repo/e["path"]
        if e["path"] not in cache:
            raw=p.read_bytes()
            if sha_bytes(raw)!=e["sha256"]:raise ValueError("AUTHORITY_SHA:"+e["purpose"])
            cache[e["path"]]=json.loads(raw.decode("utf-8"))
        objects[e["purpose"]]=pointer(cache[e["path"]],e["pointer"])
    numeric_path=repo/"outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/family_identity_manifest_rev01.json";numeric_raw=numeric_path.read_bytes()
    if sha_bytes(numeric_raw)!="e09bcd2293f8c4b6acc2e61e74eeb31b4218b719d023d8387a15f69d980e2ee6":raise ValueError("NUMERIC_SHA")
    objects["NUMERIC_IDENTITY"]=json.loads(numeric_raw.decode());return objects,{"unique_file_reads":len(cache),"allowlist_entries":20}
def mix(x:int)->int:
    z=(x+GAMMA)&MASK;z=((z^(z>>30))*0xBF58476D1CE4E5B9)&MASK;z=((z^(z>>27))*0x94D049BB133111EB)&MASK;return (z^(z>>31))&MASK
def uniform(seed:int,j:int)->float:return ((mix((seed+GAMMA*(j+1))&MASK)>>11)+.5)/(1<<53)
def permutation(seed:int,p:int):
    a=list(range(20))
    for i in range(19,0,-1):
        j=mix((seed+GAMMA*(1+32*p+19-i))&MASK)%(i+1);a[i],a[j]=a[j],a[i]
    return a
def bounds(spec):
    result={}
    for group in spec["parameters"]:
        for name in group["names"]:result[name]=tuple(map(float,group["bounds"]))
    return result
def parameters(o,family,ordinal):
    if family in FAMILIES[:2]:
        row=o["HAND_ROWS" if family==FAMILIES[0] else "NEAR_ROWS"][ordinal-1];result={"q0":float(row["volume_logit_0"]),"q90":float(row["volume_logit_90"]),"q180":float(row["volume_logit_180"]),"q270":float(row["derived_volume_logit_270"]),**{f"external_{s}":float(row[f"external_aperture_fraction_{s}"]) for s in SECTORS},**{f"loss_{s}":float(row[f"loss_fraction_{s}"]) for s in SECTORS}};result["central_mix" if family==FAMILIES[0] else "shared_alpha"]=float(row["central_mix_aperture_fraction" if family==FAMILIES[0] else "shared_coupling_alpha"]);return result,{"kind":"SEALED_ROW","row_index_zero_based":ordinal-1}
    if family==FAMILIES[2]:
        spec=o["RANDOM_FAMILY_SPEC"];order=spec["parameter_order"];b=bounds(spec);seed=int(o["RANDOM_FIXED_SEEDS"][ordinal-1]);result={f"external_{s}":.5 for s in SECTORS}
        for j,name in enumerate(order):
            lo,hi=b[name];u=uniform(seed,j);result[name]=lo+(hi-lo)*u if j<3 or j>=9 else 0.0 if u<.5 else lo+(hi-lo)*(2*u-1)
        result["q270"]=-(result["q0"]+result["q90"]+result["q180"])/3;return result,{"kind":"RANDOM_FIXED_MEMBER_SEED","member_seed":seed,"draw_count":13,"nextafter_guard":True}
    spec=o["PHYSICS_FAMILY_SPEC_PARAMETERS_LHS"];order=spec["parameter_order"];b=bounds(spec);master=int(o["PHYSICS_MASTER_SEED"]);result={}
    for j,name in enumerate(order):lo,hi=b[name];result[name]=lo+(hi-lo)*(permutation(master,j)[ordinal-1]+.5)/20
    result["q270"]=-(result["q0"]+result["q90"]+result["q180"])/3;return result,{"kind":"PHYSICS_FISHER_YATES_MIDPOINT_LHS","master_seed":master,"member_identity_seed":o["PHYSICS_MEMBER_IDENTITY_SEEDS"][ordinal-1],"lhs_jitter":False}
def window_volume(family,sector,params):
    width=lambda a:.002+.006*a
    if family==FAMILIES[0]:return width(params["central_mix"])*.002*.002
    if family==FAMILIES[1]:return width((params["shared_alpha"]-.03)/.04)*.002*.002
    if family==FAMILIES[2]:
        incident={"0":("edge_0_90","edge_0_180","edge_0_270"),"90":("edge_0_90","edge_90_180","edge_90_270"),"180":("edge_0_180","edge_90_180","edge_180_270"),"270":("edge_0_270","edge_90_270","edge_180_270")}[sector];return sum(width(params[x])*.002*.002 for x in incident if params[x]>0) or .002*.002*.002
    incident={"0":("ring_0_90","ring_270_0"),"90":("ring_0_90","ring_90_180"),"180":("ring_90_180","ring_180_270"),"270":("ring_180_270","ring_270_0")}[sector];return sum(width(params[x])*.002*.002 for x in incident)
def evidence(o,adapter,family,member_id,params):
    numeric=o["NUMERIC_IDENTITY"]["common_connected_volume_and_cad_mapping"];root=o["CAD0_MULTI_SOURCE_04"]["common"];slots=o["CAD0_MULTI_SOURCE_05"]["slots"];static=o["CAD0_MULTI_SOURCE_12"]["fields"];geometry=o["CAD0_MULTI_SOURCE_02"];primary=list(map(float,geometry["sector"]["collector"]["z_m"]));fluid=list(map(float,geometry["z_intervals_m"]["internal_fluid"]));slot_rows=[];interval_ok=True
    for name in ("SPINE","WINDOW_1","WINDOW_2","WINDOW_3","OUTER_1"):
        z=list(map(float,slots[name]["z_m"]));contained=fluid[0]<=z[0]<z[1]<=fluid[1];overlap=max(z[0],primary[0])<min(z[1],primary[1]);interval_ok &= contained and overlap;slot_rows.append({"slot_id":name,"z_interval_m":z,"collector_z_interval_m":primary,"finite_ordered":math.isfinite(z[0]) and math.isfinite(z[1]) and z[0]<z[1],"contained_in_internal_fluid":contained,"non_empty_collector_overlap":overlap,"thickness_m":z[1]-z[0]})
    ownership=next(x for x in adapter["ownership_derivation"]["members"] if x["member_id"]==member_id)["witnesses"]
    weights=[math.exp(params[f"q{s}"]) for s in SECTORS];roots=[];root_ok=True
    for sector,w in zip(SECTORS,weights):
        target=numeric["target_m3"]*(1-numeric["central_share"])*w/sum(weights);lo,hi=map(float,root["L_bounds_m"]);aout=(.002+.006*params[f"external_{sector}"])*.002;vwindow=window_volume(family,sector,params)
        def volume(L):return root["V_fixed_m3"]+(root["A_in_m2"]+aout)*(root["S_m"]-L)/2+root["A_cav_m2"]*L+vwindow
        if not volume(lo)<=target<=volume(hi):root_ok=False;roots.append({"sector":sector,"status":"UNBRACKETED","target_volume_m3":target,"domain_m":[lo,hi]});continue
        trace=[]
        for i in range(80):mid=(lo+hi)/2;measured=volume(mid);trace.append({"iteration":i+1,"low_m":lo,"high_m":hi,"mid_m":mid,"measured_volume_m3":measured});lo,hi=(mid,hi) if measured<target else (lo,mid)
        L=(lo+hi)/2;measured=volume(L);residual=measured-target;root_ok &= abs(residual)<=1e-12;roots.append({"sector":sector,"status":"PASS" if abs(residual)<=1e-12 else "RESIDUAL_FAIL","domain_m":list(root["L_bounds_m"]),"iterations":80,"trace":trace,"root_length_m":L,"target_volume_m3":target,"measured_volume_m3":measured,"residual_m3":residual})
    feature=static["general_minimum_feature_m"];load=static["general_minimum_load_path_m"];general_ok=feature["proposed_analytic_value"]>=feature["threshold_m"] and load["proposed_analytic_value"]>=load["threshold_m"]
    ev={"ownership_witnesses":ownership,"slot_interval_witnesses":slot_rows,"volume_root_witnesses":roots,"general_minima":{"feature_m":feature["proposed_analytic_value"],"feature_threshold_m":feature["threshold_m"],"feature_witness_ids":feature["witness_ids"],"load_path_m":load["proposed_analytic_value"],"load_path_threshold_m":load["threshold_m"],"load_path_witness_ids":load["witness_ids"]},"exception_minima":{"feature_m":static["interface_exception_min_feature_m"]["proposed_analytic_value"],"feature_witness_ids":static["interface_exception_min_feature_m"]["witness_ids"],"load_path_m":static["interface_exception_min_load_path_m"]["proposed_analytic_value"],"load_path_witness_ids":static["interface_exception_min_load_path_m"]["witness_ids"]},"interval_native":True,"midpoint_or_endface_used":False,"thresholds_copied_as_measurements":False,"final_test_read":False};reasons=[]
    if not interval_ok:reasons.append("INTERVAL_STATIC_FAIL")
    if not root_ok:reasons.append("VOLUME_ROOT_FAIL")
    if not general_ok:reasons.append("GENERAL_MINIMUM_FAIL")
    return ev,("ELIGIBLE" if not reasons else "COST_INELIGIBLE"),reasons
def execute(repo:Path,run_id:str):
    run=repo/"outputs/gen_enc/GEN_ENC_FAST_START/b1_science_first_exact20_runs"/run_id;staging=run/"staging";results=run/"results"
    if run.exists():raise ValueError("RUN_EXISTS")
    try:
        o,reads=load_inputs(repo);members=[f"{p}_{i:02d}" for p in ("HAND","NEAR","RANDOM","PHYSICS") for i in range(1,6)];adapter=build_adapter(o,members);records=[]
        for family in FAMILIES:
            for ordinal in range(1,6):
                member_id=f"{PREFIX[family]}_{ordinal:02d}";params,source=parameters(o,family,ordinal);ev,status,reasons=evidence(o,adapter,family,member_id,params);base={"schema_version":"gen_enc_fast_b1_science_first_member_v1","record_kind":"B1_BATCH_LOCAL_IDENTITY_CAD_STATIC","task_id":TASK,"run_id":run_id,"batch_id":"B1","family_id":family,"member_id":member_id,"slot_ordinal":ordinal,"failure_slot_retained":True,"input_provenance":source,"parameter_order":list(params),"parameters":params,"cad_static_evidence":ev,"static_status":status,"failure_reasons":reasons,"claim_ceiling":CLAIM,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False};base["identity_sha256"]=sha_bytes(canonical(base));write(staging/"members"/(member_id+".json"),base);records.append(base)
        families=[]
        for family in FAMILIES:
            subset=[x for x in records if x["family_id"]==family];manifest={"family_id":family,"member_count":5,"member_ids":[x["member_id"] for x in subset],"member_hashes":[x["identity_sha256"] for x in subset],"eligible_count":sum(x["static_status"]=="ELIGIBLE" for x in subset),"ineligible_count":sum(x["static_status"]!="ELIGIBLE" for x in subset),"claim_ceiling":CLAIM,"final_test_read":False};write(staging/"families"/(PREFIX[family]+".json"),manifest);families.append(manifest)
        index={"schema_version":"gen_enc_fast_b1_science_first_index_v1","task_id":TASK,"run_id":run_id,"batch_id":"B1","member_count":20,"family_count":4,"members":[{"member_id":x["member_id"],"path":"members/"+x["member_id"]+".json","identity_sha256":x["identity_sha256"],"static_status":x["static_status"]} for x in records],"family_manifests":[{"family_id":x["family_id"],"path":"families/"+PREFIX[x["family_id"]]+".json"} for x in families],"claim_ceiling":CLAIM,"final_test_read":False};write(staging/"batch_index.json",index)
        audit={"member_count":20,"ownership_witness_count":sum(len(x["cad_static_evidence"]["ownership_witnesses"]) for x in records),"eligible_count":sum(x["static_status"]=="ELIGIBLE" for x in records),"ineligible_count":sum(x["static_status"]!="ELIGIBLE" for x in records),"failed_count":sum(bool(x["failure_reasons"]) for x in records),"reason_counts":{},"interval_native":True,"midpoint_or_endface_used":False,"final_test_read":False}
        for x in records:
            for reason in x["failure_reasons"]:audit["reason_counts"][reason]=audit["reason_counts"].get(reason,0)+1
        write(staging/"static_audit.json",audit);write(staging/"generation_provenance.json",{"task_id":TASK,"run_id":run_id,"authority":reads,"adapter_sha256s_sha256":"963b2a90f6f333510c84bcf86071e921fb1727a722026e86c382946b803d5a00","member_count":20,"artifact_count":26,"final_test_read":False})
        from scripts.gen_enc_b1_science_first.independent_verifier import verify
        report=verify(staging,run_id);shutil.copytree(staging,results);write(results/"independent_verification.json",report);lines=[]
        for p in sorted(results.rglob("*.json")):lines.append({"path":p.relative_to(results).as_posix(),"sha256":sha_file(p)})
        write(results/"SHA256SUMS.json",{"files":lines});return run
    except Exception as exc:
        run.mkdir(parents=True,exist_ok=True);write(run/"FAILURE.json",{"task_id":TASK,"run_id":run_id,"error":f"{type(exc).__name__}:{exc}","final_test_read":False});raise
def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument("--repo-root",required=True);p.add_argument("--run-id",required=True);a=p.parse_args(argv)
    try:execute(Path(a.repo_root).resolve(),a.run_id);return 0
    except Exception as exc:print("FAIL_CLOSED:"+str(exc),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
