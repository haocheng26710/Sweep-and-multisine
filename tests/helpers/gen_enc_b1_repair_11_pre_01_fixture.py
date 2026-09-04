from __future__ import annotations

import copy
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from scripts.gen_enc_b1_repair_11_pre_01.build_freeze_package import PACKAGE, build

TASK="01a049a7-15ca-79e1-92a2-d3822ba8609d";MODE="FORMAL_B1_AUTHORITY_SHAPE_ONLY_EXACT_13X2";COMMANDS=["shape-preflight","extract-shape","verify-shape","package-shape"]
BINDING_KEYS=("task_id","batch_id","run_id","dispatch_id","mode","commands_exact","authority_manifest_path","authority_manifest_sha256","selector_contract_path","selector_contract_sha256","source_manifest_path","source_manifest_sha256","schema_manifest_path","schema_manifest_sha256","command_manifest_path","command_manifest_sha256","output_manifest_path","output_manifest_sha256","negative_capability_manifest_path","negative_capability_manifest_sha256","guardian_contract_path","guardian_contract_sha256","advisor_b_review_path","advisor_b_review_sha256","roots","final_test_read","technical_mirror","technical_bundle_path","technical_bundle_sha256","technical_fail_after_driver_read","technical_fail_after_verifier_read","technical_read_delay_ms")

def canonical(value:Any)->bytes:return (json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def write(path:Path,value:Any)->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(value))

def _sample(kind:str,selector_id:str)->Any:
    if kind=="object":return {"synthetic_key":"ULTRA_SECRET_SCALAR_"+selector_id}
    if kind=="array":return [{"synthetic_item":"ULTRA_SECRET_SCALAR_"+selector_id},7]
    if kind=="string":return "ULTRA_SECRET_SCALAR_"+selector_id
    if kind=="integer":return 987654321
    if kind=="number":return 12345.6789
    if kind=="boolean":return True
    return None

def _put(root:dict[str,Any],pointer:str,value:Any)->None:
    parts=[x.replace("~1","/").replace("~0","~") for x in pointer.split("/")[1:]]
    current=root
    for part in parts[:-1]:current=current.setdefault(part,{})
    current[parts[-1]]=value

def synthetic_objects(inject_future_outputs:bool=False,missing_selector:str|None=None,type_mismatch_selector:str|None=None)->dict[str,Any]:
    projection=json.loads(Path("outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_10/cad_typed_projection_contract.json").read_text())
    objects={f"CAD0_MULTI_SOURCE_{i:02d}":{"technical_document":f"SYNTHETIC_{i:02d}"} for i in range(1,14)}
    for selector in projection["semantic_selectors"]:
        sid=selector["id"]
        if sid in {"OWNERSHIP_CELLS","OWNERSHIP_RULE"}:
            if inject_future_outputs:_put(objects[selector["purpose"]],selector["pointer"],_sample(selector["type"],sid))
            continue
        if sid==missing_selector:continue
        value=[] if selector["type"]=="array" else {} if selector["type"]=="object" else _sample(selector["type"],sid)
        if sid==type_mismatch_selector:value={} if selector["type"]!="object" else []
        _put(objects[selector["purpose"]],selector["pointer"],value)
    return objects

def make_case(objects:dict[str,Any]|None=None,fail_driver:int|None=None,fail_verifier:int|None=None,read_delay_ms:int=0)->dict[str,Any]:
    build()
    repo=Path.cwd();tag=uuid.uuid4().hex;base=Path(".r11pre1")/tag;control=base/"control";run_id=hashlib.sha256(("run:"+tag).encode()).hexdigest();dispatch_id=hashlib.sha256(("dispatch:"+tag).encode()).hexdigest()
    bundle={"schema_version":"gen_enc_b1_r11_technical_bundle_v1","identity_class":"TECHNICAL_SYNTHETIC_SHAPE_ONLY_NEVER_AUTHORITY","objects":objects or synthetic_objects()};bundle_path=base/"technical_bundle.json";write(bundle_path,bundle)
    roots={name:(Path(".r11pre1")/run_id/"technical_shape_run"/name).as_posix() for name in ("staging","driver_receipts","verifier_receipts","side_records","package","terminal")}
    release_path=(control/"R.json").as_posix();attestation_path=(control/"A.json").as_posix();dispatch_path=(control/"D.json").as_posix()
    files={name:(PACKAGE/f"{name}.json") for name in ("authority_manifest","selector_contract","source_manifest","schema_manifest","command_manifest","output_manifest","negative_capability_manifest")}
    release={"schema_version":"gen_enc_b1_r11_pre_01_technical_shape_release_v1","record_kind":"TECHNICAL_SHAPE_ONLY_RELEASE","task_id":TASK,"batch_id":"B1","run_id":run_id,"dispatch_id":dispatch_id,"mode":MODE,"commands_exact":COMMANDS,**{key+"_path":path.as_posix() for key,path in files.items()},**{key+"_sha256":sha(path.read_bytes()) for key,path in files.items()},"guardian_contract_path":"outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/contracts/GEN_ENC_FAST_B1_REPAIR_11_AUTHORITY_SHAPE_ONLY_CONFORMANCE_CONTRACT.json","guardian_contract_sha256":"944ecf3d7b7307d1f2df4ff9fbd887bf64896bb8393a88e8f2dba5fd0328cb7b","advisor_b_review_path":"outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_FAST_B1_REPAIR_11_SHAPE_ONLY_IMPLEMENTATION_FREEZE_PREEXECUTION_REVIEW.json","advisor_b_review_sha256":"cc510911b2dbd1a902a018bfce8f3249518aa4140827163e6e1a39e1a208189f","roots":roots,"final_test_read":False,"release_path":release_path,"attestation_path":attestation_path,"dispatch_path":dispatch_path,"permissions":{"shape_preflight":True,"extract_shape":True,"verify_shape":True,"package_shape":True,"identity":False,"static":False,"publication":False,"phase_b":False},"technical_mirror":True,"technical_bundle_path":bundle_path.as_posix(),"technical_bundle_sha256":sha((repo/bundle_path).read_bytes()),"technical_fail_after_driver_read":fail_driver,"technical_fail_after_verifier_read":fail_verifier,"technical_read_delay_ms":read_delay_ms}
    write(repo/release_path,release);rhash=sha((repo/release_path).read_bytes())
    binding={key:copy.deepcopy(release[key]) for key in BINDING_KEYS}
    att={"schema_version":"gen_enc_b1_r11_pre_01_technical_shape_attestation_v1","record_kind":"TECHNICAL_GUARDIAN_SHAPE_ONLY_ATTESTATION",**binding,"release_path":release_path,"release_sha256":rhash,"one_way":True};write(repo/attestation_path,att);ahash=sha((repo/attestation_path).read_bytes())
    dispatch={"schema_version":"gen_enc_b1_r11_pre_01_technical_shape_dispatch_v1","record_kind":"TECHNICAL_TASK_BOUND_SHAPE_DISPATCH",**binding,"release_path":release_path,"release_sha256":rhash,"attestation_path":attestation_path,"attestation_sha256":ahash,"state":"SHAPE_ISSUED","one_use":True,"revoked":False};write(repo/dispatch_path,dispatch)
    return {"base":base,"run_id":run_id,"dispatch_id":dispatch_id,"release":Path(release_path),"attestation":Path(attestation_path),"dispatch":Path(dispatch_path),"roots":{k:Path(v) for k,v in roots.items()},"bundle":bundle_path}

def reseal_controls(case:dict[str,Any])->None:
    release=json.loads(case["release"].read_text());write(case["release"],release);rhash=sha(case["release"].read_bytes());binding={key:copy.deepcopy(release[key]) for key in BINDING_KEYS}
    att=json.loads(case["attestation"].read_text());att={"schema_version":att["schema_version"],"record_kind":att["record_kind"],**binding,"release_path":case["release"].as_posix(),"release_sha256":rhash,"one_way":True};write(case["attestation"],att);ahash=sha(case["attestation"].read_bytes())
    dispatch=json.loads(case["dispatch"].read_text());dispatch={"schema_version":dispatch["schema_version"],"record_kind":dispatch["record_kind"],**binding,"release_path":case["release"].as_posix(),"release_sha256":rhash,"attestation_path":case["attestation"].as_posix(),"attestation_sha256":ahash,"state":"SHAPE_ISSUED","one_use":True,"revoked":False};write(case["dispatch"],dispatch)

def argv(case:dict[str,Any],command:str)->list[str]:
    module="scripts.gen_enc_b1_repair_11_pre_01.technical_verifier" if command=="verify-shape" else "scripts.gen_enc_b1_repair_11_pre_01.technical_driver"
    return ["python","-m",module,command,"--repo-root",".","--release",case["release"].as_posix(),"--guardian-attestation",case["attestation"].as_posix(),"--dispatch",case["dispatch"].as_posix(),"--schema-root","schemas/gen_enc/b1_repair_11_pre_01"]
