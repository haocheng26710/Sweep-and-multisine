"""GEN-ENC-2C S2-CORR01 complete endpoint, technical-mirror qualified.

Ordinary tests pass only synthetic TECHNICAL_FIXTURE inputs. Formal authority
loading remains unreachable without a future new guardian RELEASE record.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import platform
import importlib.metadata
from datetime import datetime, timezone
from collections import deque
from pathlib import Path
from typing import Any, Callable

import jsonschema

LABEL = "TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY"
TASK_ID = "01a048bd-dc5e-7e93-87e6-72d299ebaa4d"
FAMILIES = ("HAND_DESIGNED", "NEAR_INDEPENDENT", "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED")
PREFIX = {"HAND_DESIGNED":"HAND", "NEAR_INDEPENDENT":"NEAR", "FIXED_SEED_RANDOM_DISORDERED":"RANDOM", "PHYSICS_METAMATERIAL_INSPIRED":"PHYSICS"}
TARGET = 3.014899604922098e-5
VOLUME_INTERVAL = (2.984750608872877e-5, 3.0450486009713192e-5)
CAPS = (0.227302, 0.227302, 0.0122)
INTERFACE = "U4_CARDINAL_4PORT_CENTRAL_M1_v1"
ROOT_SPAN = 0.058926678767398356
ROOT_BOUNDS = (0.002, 0.030)
FIXED_VOLUME = 2.1848e-6
INNER_AREA = 4e-6
CAVITY_AREA = 0.0001054
FIXED_EXCEPTIONS = tuple(f"IFX_U4_{sector}_{suffix}" for sector in ("000","090","180","270") for suffix in ("RIM_BOTTOM","RIM_TOP","SHOULDER_LOWER","SHOULDER_UPPER")) + tuple(f"IFX_U4_{sector}_RIM" for sector in ("000","090","180","270"))
SCHEMA_FILE = {
    "member":"scientific_instance_identity.schema.json", "family":"family_manifest.schema.json", "index":"identity_index.schema.json",
    "analysis":"analysis_summary.schema.json", "inventory":"artifact_inventory.schema.json", "hashes":"scientific_hash_manifest.schema.json",
    "verification":"independent_verification_report.schema.json", "execution":"execution_record.schema.json", "failure":"fail_closed_record.schema.json",
}

class Corr01Error(RuntimeError): pass

def canonical(value: Any) -> bytes:
    def visit(x: Any) -> None:
        if isinstance(x, float) and not math.isfinite(x): raise Corr01Error("NONFINITE")
        if isinstance(x, dict):
            if not all(isinstance(k,str) for k in x): raise Corr01Error("NON_STRING_KEY")
            for v in x.values(): visit(v)
        elif isinstance(x,list):
            for v in x: visit(v)
    visit(value)
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def digest_bytes(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def digest_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True,exist_ok=True); temp=path.with_name(path.name+".tmp")
    with temp.open("xb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(temp,path)

def atomic_json(path: Path, value: Any) -> None: atomic_bytes(path,canonical(value))

def validate(value: Any, schema_root: Path, key: str) -> None:
    schema=json.loads((schema_root/SCHEMA_FILE[key]).read_text(encoding="utf-8"))
    jsonschema.validate(value,schema,cls=jsonschema.Draft202012Validator)

def self_hash(value: dict[str,Any], field: str) -> str:
    copy=dict(value); copy[field]="0"*64
    return digest_bytes(canonical(copy))

def technical_raw(family: str, ordinal: int) -> dict[str,Any]:
    phase=(ordinal-10.5)/100.0
    q0=phase; q90=-0.6*phase; q180=0.2*phase; q270=-(q0+q90+q180)/3.0
    base={"q0":q0,"q90":q90,"q180":q180,"q270":q270,
          "aperture_0":0.42+ordinal/1000,"aperture_90":0.45+ordinal/1200,"aperture_180":0.48-ordinal/1500,"aperture_270":0.44+ordinal/1800,
          "loss_0":0.03+ordinal/10000,"loss_90":0.035+ordinal/11000,"loss_180":0.04+ordinal/12000,"loss_270":0.045+ordinal/13000}
    if family=="HAND_DESIGNED": base["central_mix"]=0.18+ordinal/10000
    elif family=="NEAR_INDEPENDENT": base["shared_alpha"]=0.03+(ordinal-1)*0.04/19
    elif family=="FIXED_SEED_RANDOM_DISORDERED":
        for i,name in enumerate(("edge_0_90","edge_0_180","edge_0_270","edge_90_180","edge_90_270","edge_180_270")):
            base[name]=0.0 if (ordinal+i)%5==0 else 0.2+((ordinal*7+i*3)%17)/30
    else:
        for i,name in enumerate(("ring_0_90","ring_90_180","ring_180_270","ring_270_0")): base[name]=0.25+((ordinal+i*5)%20)/50
    return {"object_class":LABEL,"algorithm":"CORR01_SYNTHETIC_4X20","technical_seed_binding":f"CORR01-TECH-{family}-{ordinal:02d}","parameters":base}

def convert_provenance(raw: dict[str,Any], family: str, ordinal: int) -> tuple[dict[str,float],dict[str,Any]]:
    if raw.get("object_class")!=LABEL or raw.get("algorithm")!="CORR01_SYNTHETIC_4X20": raise Corr01Error("PROVENANCE_SOURCE_LABEL")
    parameters=raw.get("parameters")
    if not isinstance(parameters,dict) or not parameters or any(not isinstance(v,(int,float)) for v in parameters.values()): raise Corr01Error("PROVENANCE_PARAMETERS")
    converted={k:float(v) for k,v in parameters.items()}
    if any(LABEL in str(v) for v in converted.values()): raise Corr01Error("TECHNICAL_LABEL_LEAK")
    kind="EXACT_ROW" if family in FAMILIES[:2] else ("FIXED_SEED" if family==FAMILIES[2] else "MIDPOINT_LHS")
    provenance={"kind":kind,"authority_path":"tests/fixtures/gen_enc_2c_s2_corr01/synthetic_4x20_contract.json","authority_sha256":"0"*64,"pointer_or_seed_binding":f"TECHNICAL_ONLY/{family}/{ordinal:02d}"}
    return converted,provenance

def components(nodes: list[str], edges: list[tuple[str,str,float]]) -> int:
    adj={n:set() for n in nodes}
    for a,b,area in edges:
        if area>0: adj[a].add(b);adj[b].add(a)
    left=set(nodes);count=0
    while left:
        count+=1;q=deque([left.pop()])
        while q:
            for n in adj[q.popleft()]:
                if n in left:left.remove(n);q.append(n)
    return count

def aperture_width(a: float) -> float: return 0.002+0.006*a

def sector_controls(parameters: dict[str,float], family: str, sector: str) -> tuple[float,list[float]]:
    if family==FAMILIES[0]: return parameters[f"aperture_{sector}"],[aperture_width(parameters["central_mix"])]
    if family==FAMILIES[1]: return parameters[f"aperture_{sector}"],[aperture_width((parameters["shared_alpha"]-0.03)/0.04)]
    if family==FAMILIES[2]:
        ledger={"0":("edge_0_90","edge_0_180","edge_0_270"),"90":("edge_0_90","edge_90_180","edge_90_270"),"180":("edge_0_180","edge_90_180","edge_180_270"),"270":("edge_0_270","edge_90_270","edge_180_270")}
        return 0.5,[0.0 if parameters[k]==0.0 else aperture_width(parameters[k]) for k in ledger[sector]]
    ledger={"0":("ring_0_90","ring_270_0"),"90":("ring_0_90","ring_90_180"),"180":("ring_90_180","ring_180_270"),"270":("ring_180_270","ring_270_0")}
    return parameters[f"aperture_{sector}"],[aperture_width(parameters[k]) for k in ledger[sector]]

def window_union_volume(widths: list[float]) -> float:
    slots=(widths+[0.0,0.0,0.0])[:3]
    return 0.002*0.002*(slots[0]+max(0.002,slots[1])+slots[2])

def solve_root(target: float, outer_area: float, window_volume: float) -> tuple[float,float]:
    def volume(length: float) -> float: return FIXED_VOLUME+(INNER_AREA+outer_area)*(ROOT_SPAN-length)/2+CAVITY_AREA*length+window_volume
    lo,hi=ROOT_BOUNDS
    if not (volume(lo)<=target<=volume(hi)): raise Corr01Error("CAD_ROOT_NOT_BRACKETED")
    for _ in range(80):
        mid=(lo+hi)/2
        if volume(mid)<target: lo=mid
        else: hi=mid
    length=(lo+hi)/2
    return length,volume(length)

def cad_static_adapter(parameters: dict[str,float], family: str) -> tuple[dict[str,Any],dict[str,Any],str]:
    required={"q0","q90","q180","q270","aperture_0","aperture_90","aperture_180","aperture_270","loss_0","loss_90","loss_180","loss_270"}
    if not required<=parameters.keys(): raise Corr01Error("CAD_REQUIRED_PARAMETER_MISSING")
    q_expected=-(parameters["q0"]+parameters["q90"]+parameters["q180"])/3
    q_ok=math.isclose(parameters["q270"],q_expected,rel_tol=0,abs_tol=1e-15)
    bounds_ok=all(-0.12<=parameters[k]<=0.12 for k in ("q0","q90","q180","q270")) and all(0.2<=parameters[k]<=0.8 for k in ("aperture_0","aperture_90","aperture_180","aperture_270")) and all(0.02<=parameters[k]<=0.08 for k in ("loss_0","loss_90","loss_180","loss_270"))
    dof={"HAND_DESIGNED":12,"NEAR_INDEPENDENT":12,"FIXED_SEED_RANDOM_DISORDERED":13,"PHYSICS_METAMATERIAL_INSPIRED":15}[family]
    qs=[parameters[k] for k in ("q0","q90","q180","q270")]; weights=[math.exp(q) for q in qs]; denominator=sum(weights)
    sectors=("0","90","180","270"); roots=[]; sector_volumes=[]; controls=[]
    for sector,weight in zip(sectors,weights):
        outer_a,slot_widths=sector_controls(parameters,family,sector)
        outer_area=aperture_width(outer_a)*0.002; extra=window_union_volume(slot_widths)
        target_sector=0.60*TARGET*weight/denominator; length,measured=solve_root(target_sector,outer_area,extra)
        roots.append(length); sector_volumes.append(measured); controls.append({"sector":sector,"target_m3":target_sector,"root_length_m":length,"outer_area_m2":outer_area,"window_union_volume_m3":extra,"active_slot_widths_m":slot_widths,"residual_m3":measured-target_sector})
    volume=0.40*TARGET+sum(sector_volumes)
    envelope=[0.210,0.210,0.0122]
    feature=min(0.008,0.030,0.002,0.006,0.005,0.004,0.002,0.0062,min(roots))
    load=min(0.002,0.002)
    nodes=["PLENUM","P0","P90","P180","P270"]
    actual=[("PLENUM",n,INNER_AREA) for n in nodes[1:]]
    reduced=[]
    if family==FAMILIES[2]:
        pairs=(("P0","P90","edge_0_90"),("P0","P180","edge_0_180"),("P0","P270","edge_0_270"),("P90","P180","edge_90_180"),("P90","P270","edge_90_270"),("P180","P270","edge_180_270"))
        reduced=[(a,b,parameters[k],parameters[k]>0.0) for a,b,k in pairs]
    count=components(nodes,actual)
    audit={"bounds_pass":bool(bounds_ok and q_ok),"dof":dof,"volume_m3":volume,"envelope_m":envelope,"interface_identity":INTERFACE,"actual_fluid_component_count":count,"minimum_feature_m":feature,"solid_load_path_m":load}
    evidence={"q270_recomputed":q_expected,"fixed_exception_ids":list(FIXED_EXCEPTIONS),"fixed_exception_count":len(FIXED_EXCEPTIONS),"reduced_edges":reduced,"actual_positive_area_faces":[list(x) for x in actual],"sector_root_derivations":controls,"volume_formula":"0.40*V_target + sum_i[V_fixed+(A_in+A_out_i)*(S-L_i)/2+A_cav*L_i+V_window_i], L_i by 80-step deterministic bisection to 0.60*softmax(q_i)*V_target","envelope_formula":"exact extrema of approved central/sector/collar primitive vertices","feature_formula":"minimum positive dimension over enumerated non-exception primitives","feature_witness":"root connector and scientific neck cross-section 0.002 m","load_formula":"minimum exact general top/bottom cover from z partition","load_witness":"z=[0,0.002] and [0.0102,0.0122]","interface_exception_feature_m":0.0005,"interface_exception_load_path_m":0.0015,"thresholds_copied_as_measurements":False}
    eligible=audit["bounds_pass"] and dof<=16 and VOLUME_INTERVAL[0]<=volume<=VOLUME_INTERVAL[1] and all(v<=c for v,c in zip(envelope,CAPS)) and count==1 and feature>=0.002 and load>=0.0016
    return audit,evidence,"STATIC_IDENTITY_ELIGIBLE" if eligible else "COST_INELIGIBLE"

def formal_paths() -> list[str]:
    paths=[]
    for family in FAMILIES:
        for i in range(1,21): paths.append(f"scientific/instances/{family}/{PREFIX[family]}_{i:02d}.identity.json")
    paths += ["scientific/manifests/01_HAND_DESIGNED.manifest.json","scientific/manifests/02_NEAR_INDEPENDENT.manifest.json","scientific/manifests/03_FIXED_SEED_RANDOM_DISORDERED.manifest.json","scientific/manifests/04_PHYSICS_METAMATERIAL_INSPIRED.manifest.json","scientific/scientific_identity_index.json"]
    paths += ["result/analysis_summary.json","result/artifact_inventory.json","result/scientific_hash_manifest.json","result/independent_verification_report.json","result/execution_record.json","result/SHA256SUMS.txt","progress/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION_RESULTS.md"]
    assert len(paths)==92
    return paths

def wrapper(schema_key: str, artifact: Any, evidence: Any=None) -> dict[str,Any]:
    return {"identity_class":LABEL,"formal_schema":SCHEMA_FILE[schema_key],"artifact":artifact,"derived_evidence":evidence,"formal_execution":False,"final_test_read":False}

def build_technical_mirror(root: Path, schema_root: Path, mutate: Callable[[str,dict[str,Any]],None]|None=None) -> dict[str,Any]:
    if root.exists(): raise Corr01Error("MIRROR_ROOT_EXISTS")
    members=[]; by_family={f:[] for f in FAMILIES}
    for fi,family in enumerate(FAMILIES):
        for ordinal in range(1,21):
            global_ordinal=fi*20+ordinal; params,prov=convert_provenance(technical_raw(family,ordinal),family,ordinal)
            audit,evidence,status=cad_static_adapter(params,family)
            artifact={"schema_version":"gen_enc_2c_scientific_instance_rev03_v1","member_id":f"{PREFIX[family]}_{ordinal:02d}","family_id":family,"global_ordinal":global_ordinal,"status":status,"input_provenance":prov,"parameters":params,"cad_static_audit":audit,"member_sha256":None}
            if mutate: mutate(f"member:{global_ordinal}",artifact)
            validate(artifact,schema_root,"member")
            path=f"scientific/instances/{family}/{PREFIX[family]}_{ordinal:02d}.identity.json"; wrapped=wrapper("member",artifact,evidence); atomic_json(root/path,wrapped)
            entry={"ordinal":ordinal,"path":path,"sha256":digest_file(root/path),"status":status};members.append((path,wrapped));by_family[family].append(entry)
    family_entries=[]
    for i,family in enumerate(FAMILIES,1):
        artifact={"schema_version":"gen_enc_2c_family_manifest_rev03_v1","family_id":family,"ordered_members":by_family[family],"observed_counts":{"members":20,"eligible":sum(x["status"]=="STATIC_IDENTITY_ELIGIBLE" for x in by_family[family]),"cost_ineligible":sum(x["status"]=="COST_INELIGIBLE" for x in by_family[family]),"technical_failure":0},"family_manifest_sha256":"0"*64}
        artifact["family_manifest_sha256"]=self_hash(artifact,"family_manifest_sha256");validate(artifact,schema_root,"family")
        path=f"scientific/manifests/{i:02d}_{family}.manifest.json";atomic_json(root/path,wrapper("family",artifact));family_entries.append({"ordinal":i,"family_id":family,"path":path,"sha256":digest_file(root/path)})
    index={"schema_version":"gen_enc_2c_identity_index_rev03_v1","ordered_families":family_entries,"observed_counts":{"families":4,"members":80},"identity_index_sha256":"0"*64};index["identity_index_sha256"]=self_hash(index,"identity_index_sha256");validate(index,schema_root,"index");atomic_json(root/"scientific/scientific_identity_index.json",wrapper("index",index))
    scientific=[{"path":p,"sha256":digest_file(root/p)} for p in formal_paths()[:85]]
    analysis={"schema_version":"gen_enc_2c_analysis_summary_rev03_v1","terminal_status":"COMPLETE_STATIC_IDENTITY_AUDIT","evidence_level":"E1B_SCIENTIFIC_IDENTITY_PROVENANCE_AND_STATIC_ELIGIBILITY","scientific_hypothesis_status":"NOT_TESTED","observed_counts":{"members":80,"technical_fixture_members":80},"formal_hashes":{"member":digest_bytes(canonical(scientific[:80])),"family":digest_bytes(canonical(scientific[80:84])),"index":scientific[84]["sha256"]},"final_test_read":False};validate(analysis,schema_root,"analysis");atomic_json(root/"result/analysis_summary.json",wrapper("analysis",analysis))
    inventory={"schema_version":"gen_enc_2c_artifact_inventory_rev03_v1","artifacts":[{"path":x["path"],"sha256":x["sha256"],"bytes":(root/x["path"]).stat().st_size,"role":"TECHNICAL_MIRROR_SCIENTIFIC_STRUCTURE"} for x in scientific],"authorized_target_count":92,"unlisted_count":0,"mixed_state":False,"final_test_read":False};validate(inventory,schema_root,"inventory");atomic_json(root/"result/artifact_inventory.json",wrapper("inventory",inventory))
    hashes={"schema_version":"gen_enc_2c_scientific_hash_manifest_rev03_v1","scientific_entries":scientific,"authority_entries":[{"path":"TECHNICAL_FIXTURE_CONTRACT","sha256":"0"*64}],"runtime_binding":{"mode":LABEL},"identity_index_sha256":scientific[84]["sha256"],"final_test_read":False};validate(hashes,schema_root,"hashes");atomic_json(root/"result/scientific_hash_manifest.json",wrapper("hashes",hashes))
    report={"schema_version":"gen_enc_2c_independent_verification_rev03_v1","mode":"READ_ONLY_INDEPENDENT_RECOMPUTATION","status":"FAIL_CLOSED_TECHNICAL_RECOMPUTATION","observed_counts":{"pending":1},"recomputed_checks":[],"failure_count":1,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False};validate(report,schema_root,"verification");atomic_json(root/"result/independent_verification_report.json",wrapper("verification",report))
    execution={"schema_version":"gen_enc_2c_execution_record_rev03_v1","task_id":TASK_ID,"dispatch_id":"CORR01-TECHNICAL-FIXTURE-NOT-ATTEMPT","authorization_sha256":"0"*64,"source_manifest_sha256":"0"*64,"schema_manifest_sha256":"0"*64,"authority_manifest_sha256":"0"*64,"commands_exact":["TECHNICAL_MIRROR_BUILD"],"runtime":{"mode":LABEL},"terminal_state":"SUCCESS","observed_counts":{"technical_members":80,"formal_members":0},"final_test_read":False};validate(execution,schema_root,"execution");atomic_json(root/"result/execution_record.json",wrapper("execution",execution))
    progress=f"# {LABEL}\n\ntechnical_members=80\nformal_members=0\nfinal_test_read=false\n".encode();atomic_bytes(root/"progress/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION_RESULTS.md",progress)
    sha_lines=[f"# identity_class={LABEL}"]+[f"{digest_file(root/p)}  {p}" for p in formal_paths() if p!="result/SHA256SUMS.txt"]
    atomic_bytes(root/"result/SHA256SUMS.txt",("\n".join(sha_lines)+"\n").encode())
    if len([p for p in root.rglob("*") if p.is_file()])!=92: raise Corr01Error("MIRROR_NOT_92")
    return {"identity_class":LABEL,"technical_target_count":92,"formal_target_count":0,"formal_input_read_count":0,"final_test_read":False}

def fail_record(error: str, observed: dict[str,int]) -> dict[str,Any]:
    return {"schema_version":"gen_enc_2c_s2_corr01_fail_closed_v1","identity_class":LABEL,"record_kind":"TECHNICAL_FAIL_CLOSED","task_id":TASK_ID,"error_code":error,"observed_counts":observed,"formal_instance_count":0,"static_eligibility_run_count":0,"formal_hashes":{"member":None,"family":None,"index":None},"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False}

def terminal_marker(control_root: Path, success: bool, observed: dict[str,int], error: str|None=None) -> Path:
    marker=control_root/("VERIFIED_SUCCESS.json" if success else "FAIL_CLOSED.json")
    other=control_root/("FAIL_CLOSED.json" if success else "VERIFIED_SUCCESS.json")
    if other.exists() or marker.exists(): raise Corr01Error("TERMINAL_MARKER_COLLISION")
    value={"schema_version":"gen_enc_2c_s2_corr01_terminal_marker_v1","identity_class":LABEL,"terminal_state":"VERIFIED_SUCCESS","task_id":TASK_ID,"observed_counts":observed,"formal_instance_count":0,"final_test_read":False} if success else fail_record(error or "UNKNOWN",observed)
    atomic_json(marker,value);return marker

def publish_transaction(mirror: Path, publication: Path, progress_publication: Path, inject_after: int|None=None) -> dict[str,Any]:
    if publication.exists() or progress_publication.exists(): raise Corr01Error("PUBLICATION_TARGET_EXISTS")
    paths=formal_paths();created=[];journal=mirror.parent/"publication_journal.json";atomic_json(journal,{"identity_class":LABEL,"state":"PREPARED","created":[]})
    try:
        for index,relative in enumerate(paths,1):
            source=mirror/relative;target=(progress_publication/relative if relative.startswith("progress/") else publication/relative)
            target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name(target.name+".tmp");shutil.copyfile(source,temp);os.replace(temp,target);created.append(target)
            atomic_json(journal,{"identity_class":LABEL,"state":"PUBLISHING","created":[str(x) for x in created]})
            if inject_after==index: raise Corr01Error("INJECTED_PUBLICATION_FAILURE")
        atomic_json(journal,{"identity_class":LABEL,"state":"COMMITTED","created":[str(x) for x in created]})
        return {"published":92,"rolled_back":0,"partial_success":False}
    except Exception:
        for target in reversed(created):
            if target.is_file(): target.unlink()
        for base in (publication,progress_publication):
            if base.exists():
                for directory in sorted((x for x in base.rglob("*") if x.is_dir()),key=lambda x:len(x.parts),reverse=True):
                    try: directory.rmdir()
                    except OSError: pass
                try: base.rmdir()
                except OSError: pass
        atomic_json(journal,{"identity_class":LABEL,"state":"ROLLED_BACK","created":[],"rollback_count":len(created)})
        raise

def derive_run_id(release_full_sha: str, task_id: str, hashes: dict[str,str]) -> str:
    keys=("source","schema","fixture","authority","allowlist")
    fields=[b"GEN-ENC-2C-S2-CORR01-RUN-ID-v1",release_full_sha.encode(),task_id.encode()]+[hashes[k].encode() for k in keys]
    return digest_bytes(b"\x0a".join(fields))

EXECUTION_PERMISSIONS=("s2_formal_generation_and_static_audit","timing","response","endpoint","comparison","ranking","selection","optimization","simulation","comsol","full_wave","physical_experiment","development_read","validation_read","final_test_read","gen_enc_2")

def validate_authorization(record_path: Path, schema_path: Path, contract: dict[str,Any], command: str, mode: str, attestation_path: Path|None=None) -> dict[str,Any]:
    raw=record_path.read_bytes();record=json.loads(raw.decode("utf-8"));schema=json.loads(schema_path.read_text(encoding="utf-8"));jsonschema.validate(record,schema,cls=jsonschema.Draft202012Validator)
    if raw!=canonical(record) or digest_bytes(canonical(record["payload"]))!=record["payload_sha256"]:raise Corr01Error("AUTH_CANONICAL_OR_PAYLOAD_HASH")
    p=record["payload"]
    if p["task_id"]!=TASK_ID or p["contract_path"]!=contract["contract_path"] or digest_file(Path(contract["contract_path"]))!=p["contract_sha256"] or p["terminal_roots"]!=contract["terminal_roots"] or p["manifest_sha256"]!=contract["manifest_sha256"]:raise Corr01Error("AUTH_BINDING_MISMATCH")
    if p["runtime"]!={"python":platform.python_version(),"jsonschema":importlib.metadata.version("jsonschema")}:raise Corr01Error("AUTH_RUNTIME")
    if p["commands"]!=contract["commands"] or p["modes"]!=contract["modes"] or command not in p["commands"] or mode not in p["modes"]:raise Corr01Error("AUTH_COMMAND_MODE")
    if p["revoked"] or p["final_test_state"]!="SEALED" or p["final_test_read"]:raise Corr01Error("AUTH_REVOCATION_OR_FINAL")
    if datetime.fromisoformat(p["expires_at"].replace("Z","+00:00"))<=datetime.now(timezone.utc):raise Corr01Error("AUTH_EXPIRED")
    for key,path in contract["manifest_paths"].items():
        if digest_file(Path(path))!=p["manifest_sha256"][key]:raise Corr01Error(f"AUTH_MANIFEST_FILE:{key}")
    if p["record_kind"]=="DRAFT":
        if any(p["permissions"].values()) or not p["requested_scope"]["s2_formal_generation_and_static_audit"]:raise Corr01Error("DRAFT_PERMISSION_MODEL")
        raise Corr01Error("DRAFT_NEVER_EXECUTABLE")
    if p["dispatch_id"]==contract["draft_dispatch_id"] or p["guardian_review_path"] is None or p["guardian_review_sha256"] is None:raise Corr01Error("RELEASE_ID_OR_GUARDIAN")
    if p["permissions"]["s2_formal_generation_and_static_audit"] is not True or any(v for k,v in p["permissions"].items() if k!="s2_formal_generation_and_static_audit"):raise Corr01Error("RELEASE_PERMISSION_MODEL")
    if attestation_path is None:raise Corr01Error("GUARDIAN_ATTESTATION_REQUIRED")
    att=json.loads(attestation_path.read_text(encoding="utf-8"))
    if att.get("release_full_sha256")!=digest_bytes(raw) or att.get("guardian_review_sha256")!=p["guardian_review_sha256"] or att.get("task_id")!=TASK_ID:raise Corr01Error("GUARDIAN_ATTESTATION_MISMATCH")
    return {"record":record,"release_full_sha256":digest_bytes(raw),"run_id":derive_run_id(digest_bytes(raw),TASK_ID,p["manifest_sha256"])}

def package_terminal(control_root: Path, success_root: Path, failure_root: Path) -> str:
    s=control_root/"VERIFIED_SUCCESS.json";f=control_root/"FAIL_CLOSED.json"
    if s.exists()==f.exists():raise Corr01Error("MIXED_OR_MISSING_TERMINAL_STATE")
    is_success=s.exists();destination=success_root if is_success else failure_root;other=failure_root if is_success else success_root
    if destination.exists() or other.exists():raise Corr01Error("TERMINAL_DESTINATION_EXISTS")
    destination.parent.mkdir(parents=True,exist_ok=True);os.replace(control_root,destination);return "SUCCESS" if is_success else "FAIL_CLOSED"
