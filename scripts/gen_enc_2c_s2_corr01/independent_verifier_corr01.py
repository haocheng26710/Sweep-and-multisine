"""Independent CORR01 verifier. No driver, generator, orchestrator or CAD imports."""
from __future__ import annotations
import hashlib,json,math,os,platform,importlib.metadata
from datetime import datetime,timezone
from collections import deque
from pathlib import Path
from typing import Any
import jsonschema

LABEL="TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY";TASK_ID="01a048bd-dc5e-7e93-87e6-72d299ebaa4d"
FAMILIES=("HAND_DESIGNED","NEAR_INDEPENDENT","FIXED_SEED_RANDOM_DISORDERED","PHYSICS_METAMATERIAL_INSPIRED");PREFIX={"HAND_DESIGNED":"HAND","NEAR_INDEPENDENT":"NEAR","FIXED_SEED_RANDOM_DISORDERED":"RANDOM","PHYSICS_METAMATERIAL_INSPIRED":"PHYSICS"}
TARGET=3.014899604922098e-5;INTERFACE="U4_CARDINAL_4PORT_CENTRAL_M1_v1";CAPS=(0.227302,0.227302,0.0122)
ROOT_SPAN=.058926678767398356;ROOT_BOUNDS=(.002,.030);FIXED_VOLUME=2.1848e-6;INNER_AREA=4e-6;CAVITY_AREA=.0001054
SCHEMAS={"member":"scientific_instance_identity.schema.json","family":"family_manifest.schema.json","index":"identity_index.schema.json","analysis":"analysis_summary.schema.json","inventory":"artifact_inventory.schema.json","hashes":"scientific_hash_manifest.schema.json","verification":"independent_verification_report.schema.json","execution":"execution_record.schema.json"}
class VerifyError(RuntimeError):pass
def canonical(x:Any)->bytes:return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def filehash(p:Path)->str:return digest(p.read_bytes())
def validate(x:Any,root:Path,key:str)->None:jsonschema.validate(x,json.loads((root/SCHEMAS[key]).read_text()),cls=jsonschema.Draft202012Validator)
def selfhash(x:dict[str,Any],field:str)->str:y=dict(x);y[field]="0"*64;return digest(canonical(y))
def components(nodes,edges):
    a={n:set() for n in nodes}
    for x,y,z in edges:
        if z>0:a[x].add(y);a[y].add(x)
    left=set(nodes);count=0
    while left:
        count+=1;q=deque([left.pop()])
        while q:
            for n in a[q.popleft()]:
                if n in left:left.remove(n);q.append(n)
    return count
def width(a):return .002+.006*a
def controls(params,family,sector):
    if family==FAMILIES[0]:return params[f"aperture_{sector}"],[width(params["central_mix"])]
    if family==FAMILIES[1]:return params[f"aperture_{sector}"],[width((params["shared_alpha"]-.03)/.04)]
    if family==FAMILIES[2]:
        m={"0":("edge_0_90","edge_0_180","edge_0_270"),"90":("edge_0_90","edge_90_180","edge_90_270"),"180":("edge_0_180","edge_90_180","edge_180_270"),"270":("edge_0_270","edge_90_270","edge_180_270")}
        return .5,[0.0 if params[k]==0.0 else width(params[k]) for k in m[sector]]
    m={"0":("ring_0_90","ring_270_0"),"90":("ring_0_90","ring_90_180"),"180":("ring_90_180","ring_180_270"),"270":("ring_180_270","ring_270_0")}
    return params[f"aperture_{sector}"],[width(params[k]) for k in m[sector]]
def extra_volume(ws):
    s=(ws+[0.0,0.0,0.0])[:3];return .002*.002*(s[0]+max(.002,s[1])+s[2])
def solve(target,outer,extra):
    def v(length):return FIXED_VOLUME+(INNER_AREA+outer)*(ROOT_SPAN-length)/2+CAVITY_AREA*length+extra
    lo,hi=ROOT_BOUNDS
    if not(v(lo)<=target<=v(hi)):raise VerifyError("CAD_ROOT_NOT_BRACKETED")
    for _ in range(80):
        mid=(lo+hi)/2
        if v(mid)<target:lo=mid
        else:hi=mid
    length=(lo+hi)/2;return length,v(length)
def recompute(params,family):
    required={"q0","q90","q180","q270","aperture_0","aperture_90","aperture_180","aperture_270","loss_0","loss_90","loss_180","loss_270"}
    if not required<=params.keys():raise VerifyError("MISSING_PARAMETER")
    q=-(params["q0"]+params["q90"]+params["q180"])/3;bounds=all(-.12<=params[k]<=.12 for k in ("q0","q90","q180","q270")) and math.isclose(q,params["q270"],rel_tol=0,abs_tol=1e-15)
    qs=[params[k] for k in ("q0","q90","q180","q270")];ew=[math.exp(x) for x in qs];den=sum(ew);lengths=[];volumes=[]
    for sector,e in zip(("0","90","180","270"),ew):
        a,slots=controls(params,family,sector);length,measured=solve(.60*TARGET*e/den,width(a)*.002,extra_volume(slots));lengths.append(length);volumes.append(measured)
    volume=.40*TARGET+sum(volumes);env=[.210,.210,.0122];feature=min(.008,.030,.002,.006,.005,.004,.002,.0062,min(lengths));load=min(.002,.002);nodes=["PLENUM","P0","P90","P180","P270"];faces=[("PLENUM",n,INNER_AREA) for n in nodes[1:]]
    return {"bounds_pass":bounds,"dof":{"HAND_DESIGNED":12,"NEAR_INDEPENDENT":12,"FIXED_SEED_RANDOM_DISORDERED":13,"PHYSICS_METAMATERIAL_INSPIRED":15}[family],"volume_m3":volume,"envelope_m":env,"interface_identity":INTERFACE,"actual_fluid_component_count":components(nodes,faces),"minimum_feature_m":feature,"solid_load_path_m":load}
def expected_parameters(family,ordinal):
    phase=(ordinal-10.5)/100;q0=phase;q90=-.6*phase;q180=.2*phase;q270=-(q0+q90+q180)/3
    p={"q0":q0,"q90":q90,"q180":q180,"q270":q270,"aperture_0":.42+ordinal/1000,"aperture_90":.45+ordinal/1200,"aperture_180":.48-ordinal/1500,"aperture_270":.44+ordinal/1800,"loss_0":.03+ordinal/10000,"loss_90":.035+ordinal/11000,"loss_180":.04+ordinal/12000,"loss_270":.045+ordinal/13000}
    if family==FAMILIES[0]:p["central_mix"]=.18+ordinal/10000
    elif family==FAMILIES[1]:p["shared_alpha"]=.03+(ordinal-1)*.04/19
    elif family==FAMILIES[2]:
        for i,n in enumerate(("edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270")):p[n]=0.0 if (ordinal+i)%5==0 else .2+((ordinal*7+i*3)%17)/30
    else:
        for i,n in enumerate(("ring_0_90","ring_90_180","ring_180_270","ring_270_0")):p[n]=.25+((ordinal+i*5)%20)/50
    return p
def paths():
    p=[f"scientific/instances/{f}/{PREFIX[f]}_{i:02d}.identity.json" for f in FAMILIES for i in range(1,21)];p += [f"scientific/manifests/{i:02d}_{f}.manifest.json" for i,f in enumerate(FAMILIES,1)]+["scientific/scientific_identity_index.json","result/analysis_summary.json","result/artifact_inventory.json","result/scientific_hash_manifest.json","result/independent_verification_report.json","result/execution_record.json","result/SHA256SUMS.txt","progress/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION_RESULTS.md"];return p
def verify(root:Path,schema_root:Path,control_root:Path)->dict[str,Any]:
    failures=[];member_entries=[]
    for gi,(family,ordinal) in enumerate(((f,i) for f in FAMILIES for i in range(1,21)),1):
        path=f"scientific/instances/{family}/{PREFIX[family]}_{ordinal:02d}.identity.json";w=json.loads((root/path).read_text());
        if w.get("identity_class")!=LABEL:raise VerifyError("WRAPPER_LABEL")
        a=w.get("artifact");validate(a,schema_root,"member")
        expected_params=expected_parameters(family,ordinal);expected=recompute(expected_params,family)
        if a["global_ordinal"]!=gi or a["family_id"]!=family or a["parameters"]!=expected_params or a["cad_static_audit"]!=expected:failures.append(f"MEMBER:{gi}")
        if "TECHNICAL_FIXTURE" in json.dumps(a["parameters"]):failures.append(f"LABEL_LEAK:{gi}")
        ev=w.get("derived_evidence")
        if not isinstance(ev,dict) or ev.get("thresholds_copied_as_measurements") is not False:failures.append(f"EVIDENCE:{gi}")
        if family==FAMILIES[2]:
            reduced=ev.get("reduced_edges");
            if not isinstance(reduced,list) or any((x[2]==0)!=(x[3] is False) for x in reduced):failures.append(f"ZERO_EDGE:{gi}")
        member_entries.append({"ordinal":ordinal,"path":path,"sha256":filehash(root/path),"status":a["status"]})
    family_entries=[]
    for i,f in enumerate(FAMILIES,1):
        p=f"scientific/manifests/{i:02d}_{f}.manifest.json";a=json.loads((root/p).read_text())["artifact"];validate(a,schema_root,"family")
        if a["ordered_members"]!=member_entries[(i-1)*20:i*20] or a["family_manifest_sha256"]!=selfhash(a,"family_manifest_sha256"):failures.append(f"FAMILY:{i}")
        family_entries.append({"ordinal":i,"family_id":f,"path":p,"sha256":filehash(root/p)})
    ip="scientific/scientific_identity_index.json";index=json.loads((root/ip).read_text())["artifact"];validate(index,schema_root,"index")
    if index["ordered_families"]!=family_entries or index["identity_index_sha256"]!=selfhash(index,"identity_index_sha256"):failures.append("INDEX")
    for key,p in (("analysis","result/analysis_summary.json"),("inventory","result/artifact_inventory.json"),("hashes","result/scientific_hash_manifest.json"),("verification","result/independent_verification_report.json"),("execution","result/execution_record.json")):validate(json.loads((root/p).read_text())["artifact"],schema_root,key)
    lines=(root/"result/SHA256SUMS.txt").read_text().splitlines();listed={line.split("  ",1)[1]:line.split("  ",1)[0] for line in lines if not line.startswith("#")}
    for p in paths():
        if p=="result/SHA256SUMS.txt":continue
        if listed.get(p)!=filehash(root/p):failures.append(f"HASH:{p}")
    if len([p for p in root.rglob("*") if p.is_file()])!=92:failures.append("COUNT92")
    report={"schema_version":"gen_enc_2c_independent_verification_rev03_v1","mode":"READ_ONLY_INDEPENDENT_RECOMPUTATION","status":"PASS_STATIC_IDENTITY_RECOMPUTATION" if not failures else "FAIL_CLOSED_TECHNICAL_RECOMPUTATION","observed_counts":{"members":80,"artifacts":92},"recomputed_checks":["80_PARAMETERS","80_CAD_STATIC","RANDOM_EXACT_ZERO","ACTUAL_BFS","MEMBER_FAMILY_INDEX","SIX_RESULTS_PROGRESS_HASHES","NINE_FORMAL_SCHEMAS"],"failure_count":len(failures),"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False};validate(report,schema_root,"verification")
    rp=root/"result/independent_verification_report.json";temp=rp.with_name(rp.name+".tmp");temp.write_bytes(canonical({"identity_class":LABEL,"formal_schema":SCHEMAS["verification"],"artifact":report,"derived_evidence":{"failures":failures,"formal_hash_chain_recomputed":not failures},"formal_execution":False,"final_test_read":False}));os.replace(temp,rp)
    # refresh complete technical SHA list after report replacement
    sha=[f"# identity_class={LABEL}"]+[f"{filehash(root/p)}  {p}" for p in paths() if p!="result/SHA256SUMS.txt"];(root/"result/SHA256SUMS.txt").write_text("\n".join(sha)+"\n",encoding="utf-8",newline="\n")
    marker=control_root/("VERIFIED_SUCCESS.json" if not failures else "FAIL_CLOSED.json");control_root.mkdir(parents=True,exist_ok=True);marker.write_bytes(canonical({"schema_version":"gen_enc_2c_s2_corr01_terminal_marker_v1","identity_class":LABEL,"terminal_state":"VERIFIED_SUCCESS" if not failures else "FAIL_CLOSED","task_id":TASK_ID,"observed_counts":{"members":80,"artifacts":92,"failures":len(failures)},"formal_instance_count":0,"final_test_read":False}))
    return {"status":report["status"],"failure_count":len(failures),"formal_hash_chain_recomputed":not failures,"formal_input_read_count":0,"final_test_read":False}

def verify_fail_closed(root:Path,schema_root:Path,control_root:Path)->dict[str,Any]:
    try:return verify(root,schema_root,control_root)
    except Exception as exc:
        control_root.mkdir(parents=True,exist_ok=True);marker=control_root/"FAIL_CLOSED.json"
        marker.write_bytes(canonical({"schema_version":"gen_enc_2c_s2_corr01_fail_closed_v1","identity_class":LABEL,"record_kind":"TECHNICAL_FAIL_CLOSED","task_id":TASK_ID,"error_code":f"{type(exc).__name__}:{exc}","observed_counts":{"artifacts_observed":len([p for p in root.rglob('*') if p.is_file()]) if root.exists() else 0},"formal_instance_count":0,"static_eligibility_run_count":0,"formal_hashes":{"member":None,"family":None,"index":None},"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False}))
        return {"status":"FAIL_CLOSED_TECHNICAL_RECOMPUTATION","failure_count":1,"formal_hash_chain_recomputed":False,"formal_input_read_count":0,"final_test_read":False}

def validate_authorization_independent(record_path:Path,schema_path:Path,contract:dict[str,Any],command:str,mode:str,attestation_path:Path|None=None)->dict[str,Any]:
    raw=record_path.read_bytes();record=json.loads(raw);schema=json.loads(schema_path.read_text());jsonschema.validate(record,schema,cls=jsonschema.Draft202012Validator);p=record["payload"]
    if raw!=canonical(record) or digest(canonical(p))!=record["payload_sha256"]:raise VerifyError("AUTH_CANONICAL")
    if p["task_id"]!=TASK_ID or p["contract_path"]!=contract["contract_path"] or filehash(Path(contract["contract_path"]))!=p["contract_sha256"] or p["terminal_roots"]!=contract["terminal_roots"] or p["manifest_sha256"]!=contract["manifest_sha256"]:raise VerifyError("AUTH_BINDING")
    if p["runtime"]!={"python":platform.python_version(),"jsonschema":importlib.metadata.version("jsonschema")} or p["commands"]!=contract["commands"] or p["modes"]!=contract["modes"] or command not in p["commands"] or mode not in p["modes"]:raise VerifyError("AUTH_RUNTIME_COMMAND_MODE")
    if p["revoked"] or p["final_test_state"]!="SEALED" or p["final_test_read"] or datetime.fromisoformat(p["expires_at"].replace("Z","+00:00"))<=datetime.now(timezone.utc):raise VerifyError("AUTH_STATE")
    for key,path in contract["manifest_paths"].items():
        if filehash(Path(path))!=p["manifest_sha256"][key]:raise VerifyError("AUTH_MANIFEST")
    if p["record_kind"]=="DRAFT":raise VerifyError("DRAFT_NEVER_EXECUTABLE")
    if p["dispatch_id"]==contract["draft_dispatch_id"] or p["guardian_review_path"] is None or p["guardian_review_sha256"] is None:raise VerifyError("RELEASE_GUARDIAN")
    if p["permissions"].get("s2_formal_generation_and_static_audit") is not True or any(v for k,v in p["permissions"].items() if k!="s2_formal_generation_and_static_audit"):raise VerifyError("RELEASE_PERMISSIONS")
    if attestation_path is None:raise VerifyError("ATTESTATION_REQUIRED")
    att=json.loads(attestation_path.read_text());full=digest(raw)
    if att!={"release_full_sha256":full,"guardian_review_sha256":p["guardian_review_sha256"],"task_id":TASK_ID}:raise VerifyError("ATTESTATION")
    fields=[b"GEN-ENC-2C-S2-CORR01-RUN-ID-v1",full.encode(),TASK_ID.encode()]+[p["manifest_sha256"][k].encode() for k in ("source","schema","fixture","authority","allowlist")]
    return {"release_full_sha256":full,"run_id":digest(b"\x0a".join(fields))}
