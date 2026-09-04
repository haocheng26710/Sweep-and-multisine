from __future__ import annotations
import argparse,json,os,sys,time
from pathlib import Path
from typing import Any,Mapping,Sequence
import jsonschema
from .driver_core import canonical,read_canonical,sha_bytes,sha_file,snapshot

TASK="01a049a7-15ca-79e1-92a2-d3822ba8609d";MODE="FORMAL_B1_AUTHORITY_SHAPE_ONLY_EXACT_13X2";COMMANDS=["shape-preflight","extract-shape","verify-shape","package-shape"];CLAIM="E0_AUTHORITY_STRUCTURE_CONFORMANCE_ONLY"
PACKAGE="outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_11_shape_only_preexecution_corr01";SCHEMA_PATH="schemas/gen_enc/b1_repair_11_pre_01"
CONTRACT_PATH="outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/contracts/GEN_ENC_FAST_B1_REPAIR_11_AUTHORITY_SHAPE_ONLY_CONFORMANCE_CONTRACT.json";CONTRACT_SHA="944ecf3d7b7307d1f2df4ff9fbd887bf64896bb8393a88e8f2dba5fd0328cb7b"
REVIEW_PATH="outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_FAST_B1_REPAIR_11_SHAPE_ONLY_IMPLEMENTATION_FREEZE_PREEXECUTION_REVIEW.json";REVIEW_SHA="cc510911b2dbd1a902a018bfce8f3249518aa4140827163e6e1a39e1a208189f"
EXPECTED_PATHS={name:f"{PACKAGE}/{name}.json" for name in ("authority_manifest","selector_contract","source_manifest","schema_manifest","command_manifest","output_manifest","negative_capability_manifest")}
FIXED_HASHES={"authority_manifest":"be8a5874dffbbe8e4b3d552e0697e16f4add775956bba3e490456d45a53f6561","selector_contract":"6b3d4513fc9df99869a85bc7df6097b6a20a797c0371e65614abe1fb29115a69","command_manifest":"dfe00baea5aaf87d75d51412b4b36ea4debfb49c6d87d172685a957040366421","output_manifest":"63445b435e7901c67d84e1b4f3557ddf25274aa661c8d34e3bd3dcf444aee6cd","negative_capability_manifest":"0450f5d1a0f179fa8f992f1fbbb011f814d5aefb7edbd3092433230397bb9792"}
BINDING_KEYS=("task_id","batch_id","run_id","dispatch_id","mode","commands_exact","authority_manifest_path","authority_manifest_sha256","selector_contract_path","selector_contract_sha256","source_manifest_path","source_manifest_sha256","schema_manifest_path","schema_manifest_sha256","command_manifest_path","command_manifest_sha256","output_manifest_path","output_manifest_sha256","negative_capability_manifest_path","negative_capability_manifest_sha256","guardian_contract_path","guardian_contract_sha256","advisor_b_review_path","advisor_b_review_sha256","roots","final_test_read","technical_mirror","technical_bundle_path","technical_bundle_sha256","technical_fail_after_driver_read","technical_fail_after_verifier_read","technical_read_delay_ms")

class R11Error(RuntimeError):pass
class NoMutationReject(R11Error):pass
class LaneBusy(R11Error):pass
def _safe(repo:Path,label:str)->Path:
    rel=Path(label)
    if rel.is_absolute() or ".." in rel.parts:raise NoMutationReject("UNSAFE_PATH:"+label)
    out=(repo/rel).resolve()
    try:out.relative_to(repo)
    except ValueError as exc:raise NoMutationReject("PATH_ESCAPE") from exc
    return out
def _schemas(root:Path)->dict[str,Any]:
    out={}
    for p in root.glob("*.schema.json"):
        v=json.loads(p.read_text(encoding="utf-8"));jsonschema.Draft202012Validator.check_schema(v);out[p.name.removesuffix(".schema.json")]=v
    return out
def _validate(v:Any,c:Mapping[str,Any],name:str)->None:
    try:jsonschema.Draft202012Validator(c["schemas"][_schema(c,name)]).validate(v)
    except jsonschema.ValidationError as exc:raise NoMutationReject("SCHEMA_"+name+":"+exc.message) from exc
def _binding(release:Mapping[str,Any])->dict[str,Any]:return {k:release[k] for k in BINDING_KEYS}
def _exclusive(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open("xb") as f:f.write(canonical(value));f.flush();os.fsync(f.fileno())
    except FileExistsError as exc:raise LaneBusy("EXCLUSIVE_EXISTS:"+path.name) from exc
def _schema(c:Mapping[str,Any],base:str)->str:return base if base in {"authority_manifest","selector_contract","command_manifest","output_manifest","negative_capability_manifest","file_manifest"} else ("technical_" if c["technical"] else "")+base
def _identity(c:Mapping[str,Any],formal:str,technical:str)->str:return technical if c["technical"] else formal

def gate(repo:Path,ns:argparse.Namespace,raw:Sequence[str],allow_technical:bool)->dict[str,Any]:
    schemas=_schemas(ns.schema_root.resolve());probe,_=read_canonical(ns.release.resolve());technical=bool(probe.get("technical_mirror"));
    if technical!=allow_technical:raise NoMutationReject("FORMAL_TECHNICAL_IDENTITY_SEGREGATION")
    c={"schemas":schemas,"technical":technical};release,rraw=probe,ns.release.read_bytes();_validate(release,c,"shape_release")
    att,araw=read_canonical(ns.guardian_attestation.resolve());_validate(att,c,"shape_attestation");dispatch,draw=read_canonical(ns.dispatch.resolve());_validate(dispatch,c,"shape_dispatch")
    if release["task_id"]!=TASK or release["mode"]!=MODE or release["commands_exact"]!=COMMANDS:raise NoMutationReject("RELEASE_BINDING")
    base=(f".r11pre1/{release['run_id']}/technical_shape_run" if technical else f"outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_11_pre_01_shape_runs/{release['run_id']}");expected_roots={n:f"{base}/{n}" for n in ("staging","driver_receipts","verifier_receipts","side_records","package","terminal")}
    if release["roots"]!=expected_roots:raise NoMutationReject("RUN_ROOT_TEMPLATE")
    if att["release_path"]!=ns.release.as_posix() or att["release_sha256"]!=sha_bytes(rraw):raise NoMutationReject("ATTESTATION_RELEASE")
    if dispatch["release_path"]!=ns.release.as_posix() or dispatch["release_sha256"]!=sha_bytes(rraw) or dispatch["attestation_path"]!=ns.guardian_attestation.as_posix() or dispatch["attestation_sha256"]!=sha_bytes(araw):raise NoMutationReject("DISPATCH_CONTROLS")
    for k,w in _binding(release).items():
        if att.get(k)!=w or dispatch.get(k)!=w:raise NoMutationReject("FULL_BINDING:"+k)
    if dispatch["state"]!="SHAPE_ISSUED" or dispatch["revoked"] or not dispatch["one_use"]:raise NoMutationReject("DISPATCH_STATE")
    if (release["release_path"],release["attestation_path"],release["dispatch_path"])!=(ns.release.as_posix(),ns.guardian_attestation.as_posix(),ns.dispatch.as_posix()):raise NoMutationReject("CLI_CONTROL_PATHS")
    if release["guardian_contract_path"]!=CONTRACT_PATH or release["guardian_contract_sha256"]!=CONTRACT_SHA or sha_file(_safe(repo,CONTRACT_PATH))!=CONTRACT_SHA:raise NoMutationReject("EXACT_GUARDIAN_CONTRACT")
    if release["advisor_b_review_path"]!=REVIEW_PATH or release["advisor_b_review_sha256"]!=REVIEW_SHA or sha_file(_safe(repo,REVIEW_PATH))!=REVIEW_SHA:raise NoMutationReject("EXACT_ADVISOR_REVIEW")
    loaded={}
    for name,path in EXPECTED_PATHS.items():
        if release[name+"_path"]!=path:raise NoMutationReject("MANIFEST_PATH:"+name)
        actual=sha_file(_safe(repo,path))
        if release[name+"_sha256"]!=actual:raise NoMutationReject("MANIFEST_HASH:"+name)
        if name in FIXED_HASHES and actual!=FIXED_HASHES[name]:raise NoMutationReject("FROZEN_MANIFEST_HASH:"+name)
        loaded[name],_=read_canonical(_safe(repo,path));_validate(loaded[name],c,name if name in ("authority_manifest","selector_contract","command_manifest","output_manifest","negative_capability_manifest") else "file_manifest")
    contract,_=read_canonical(_safe(repo,CONTRACT_PATH))
    if loaded["authority_manifest"]["entries"]!=contract["authorized_shape_authority_scope"]["entries"] or len(loaded["authority_manifest"]["entries"])!=13:raise NoMutationReject("EXACT_13_AUTHORITY_MANIFEST")
    if loaded["command_manifest"]["commands_exact"]!=COMMANDS:raise NoMutationReject("EXACT_COMMANDS")
    row=next((x for x in loaded["command_manifest"]["entries"] if x["command"]==ns.command),None);repl={"<RELEASE_EXACT_PATH>":ns.release.as_posix(),"<ATTESTATION_EXACT_PATH>":ns.guardian_attestation.as_posix(),"<DISPATCH_EXACT_PATH>":ns.dispatch.as_posix()};expected=[repl.get(x,x) for x in row["argv_after_python"][2:]] if row else []
    if list(raw)!=expected:raise NoMutationReject("ARGV_BYTE_EXACT")
    roots={k:_safe(repo,v) for k,v in release["roots"].items()};return {**c,"repo":repo,"release":release,"release_sha256":sha_bytes(rraw),"attestation_sha256":sha_bytes(araw),"dispatch_sha256":sha_bytes(draw),"dispatch":dispatch,"authority":loaded["authority_manifest"],"selectors":loaded["selector_contract"]["selectors"],"output_manifest":loaded["output_manifest"],"negative":loaded["negative_capability_manifest"],"roots":roots,"run_base":_safe(repo,base)}

def _run_files(c:Mapping[str,Any])->set[str]:return {p.relative_to(c["run_base"]).as_posix() for p in c["run_base"].rglob("*") if p.is_file()} if c["run_base"].exists() else set()
def _zero_unlisted(c:Mapping[str,Any])->set[str]:
    actual=_run_files(c);allowed=set(c["output_manifest"]["allowed_run_relative_paths"])
    if not actual<=allowed:raise NoMutationReject("ZERO_UNLISTED:"+",".join(sorted(actual-allowed)))
    forbidden=set(c["negative"]["forbidden"])
    required={"SCALAR_VALUES","SCALAR_VALUE_HASHES","SCALAR_LENGTHS","MEMBER_IDENTITIES","STATIC_ELIGIBILITY","SCIENTIFIC_ARTIFACTS","PUBLICATION","PHASE_B","FINAL_TEST_READ","POINTER_SUBSTITUTION"}
    if not required<=forbidden or c["negative"]["pointer_substitution_allowed"]:raise NoMutationReject("NEGATIVE_MANIFEST_ENFORCEMENT")
    return actual
def _validate_consumed(c:Mapping[str,Any])->dict[str,Any]:
    p=c["roots"]["side_records"]/"SHAPE_DISPATCH_CONSUMED.json"
    try:v,_=read_canonical(p);_validate(v,c,"dispatch_consumed")
    except BaseException as exc:raise NoMutationReject("CONSUMED_INVALID:"+str(exc)) from exc
    expected={**_binding(c["release"]),"release_sha256":c["release_sha256"],"attestation_sha256":c["attestation_sha256"],"dispatch_sha256":c["dispatch_sha256"],"state":"SHAPE_CONSUMED","one_use":True}
    for k,w in expected.items():
        if v.get(k)!=w:raise NoMutationReject("CONSUMED_BINDING:"+k)
    return v
def _receipt_dir(c:Mapping[str,Any],lane:str)->Path:return c["roots"]["driver_receipts" if lane=="DRIVER" else "verifier_receipts"]
def validate_receipts(c:Mapping[str,Any],lane:str,require:int|None=None)->list[dict[str,Any]]:
    d=_receipt_dir(c,lane);paths=sorted(d.glob("*.json")) if d.exists() else []
    if [p.name for p in paths]!=[f"{i:04d}.json" for i in range(1,len(paths)+1)]:raise NoMutationReject("RECEIPT_FILENAMES:"+lane)
    if require is not None and len(paths)!=require:raise NoMutationReject("RECEIPT_COUNT:"+lane)
    out=[]
    for i,p in enumerate(paths,1):
        try:v,_=read_canonical(p);_validate(v,c,"authority_read_receipt")
        except BaseException as exc:raise NoMutationReject("RECEIPT_INVALID:"+lane+":"+p.name+":"+str(exc)) from exc
        e=c["authority"]["entries"][i-1];expected={"lane":lane,"lane_ordinal":i,"cumulative_ordinal":i if lane=="DRIVER" else 13+i,"purpose":e["purpose"],"source_path":e["path"],"source_sha256":e["sha256"],"source_pointer":e["pointer"],"task_id":TASK,"batch_id":"B1","run_id":c["release"]["run_id"],"dispatch_id":c["release"]["dispatch_id"],"release_sha256":c["release_sha256"],"attestation_sha256":c["attestation_sha256"],"dispatch_sha256":c["dispatch_sha256"],"final_test_read":False}
        for k,w in expected.items():
            if v.get(k)!=w:raise NoMutationReject("RECEIPT_BINDING:"+lane+":"+str(i)+":"+k)
        out.append(v)
    return out
def count(c:Mapping[str,Any])->int:return len(validate_receipts(c,"DRIVER"))+len(validate_receipts(c,"VERIFIER"))
def observed_count(c:Mapping[str,Any])->int:return sum(len(list(_receipt_dir(c,l).glob("*.json"))) if _receipt_dir(c,l).exists() else 0 for l in ("DRIVER","VERIFIER"))
def _record(c:Mapping[str,Any],lane:str,i:int,e:Mapping[str,Any])->None:
    v={"schema_version":"gen_enc_b1_r11_pre_01_"+("technical_" if c["technical"] else "")+"authority_read_receipt_v1","record_kind":_identity(c,"AUTHORITY_SHAPE_READ_RECEIPT","TECHNICAL_AUTHORITY_SHAPE_READ_RECEIPT"),"task_id":TASK,"batch_id":"B1","run_id":c["release"]["run_id"],"dispatch_id":c["release"]["dispatch_id"],"lane":lane,"lane_ordinal":i,"cumulative_ordinal":i if lane=="DRIVER" else 13+i,"purpose":e["purpose"],"source_path":e["path"],"source_sha256":e["sha256"],"source_pointer":e["pointer"],"release_sha256":c["release_sha256"],"attestation_sha256":c["attestation_sha256"],"dispatch_sha256":c["dispatch_sha256"],"final_test_read":False};_validate(v,c,"authority_read_receipt");_exclusive(_receipt_dir(c,lane)/f"{i:04d}.json",v)
def _alive(pid:int)->bool:
    if os.name=="nt":
        import ctypes
        handle=ctypes.windll.kernel32.OpenProcess(0x1000,False,pid)
        if not handle:return False
        code=ctypes.c_ulong();ok=ctypes.windll.kernel32.GetExitCodeProcess(handle,ctypes.byref(code));ctypes.windll.kernel32.CloseHandle(handle)
        return bool(ok) and code.value==259
    try:os.kill(pid,0);return True
    except OSError:return False
def _phase_value(c:Mapping[str,Any],phase:str,state:str,pid:int,claim_sha:str|None)->dict[str,Any]:return {"schema_version":"gen_enc_b1_r11_pre_01_"+("technical_" if c["technical"] else "")+"phase_state_v1","record_kind":_identity(c,"SHAPE_PHASE_STATE","TECHNICAL_SHAPE_PHASE_STATE"),"task_id":TASK,"batch_id":"B1","run_id":c["release"]["run_id"],"dispatch_id":c["release"]["dispatch_id"],"phase":phase,"state":state,"pid":pid,"claim_sha256":claim_sha,"release_sha256":c["release_sha256"],"attestation_sha256":c["attestation_sha256"],"dispatch_sha256":c["dispatch_sha256"],"final_test_read":False}
def claim_phase(c:Mapping[str,Any],phase:str)->str:
    claim=c["roots"]["side_records"]/(phase+"_CLAIM.json");done=c["roots"]["side_records"]/(phase+"_DONE.json")
    if claim.exists():
        v,_=read_canonical(claim);_validate(v,c,"phase_state")
        if done.exists():d,_=read_canonical(done);_validate(d,c,"phase_state");return "DONE"
        if _alive(v["pid"]):raise LaneBusy("LANE_BUSY:"+phase)
        return "RECOVER"
    v=_phase_value(c,phase,"CLAIMED",os.getpid(),None);_validate(v,c,"phase_state")
    try:_exclusive(claim,v)
    except LaneBusy:return claim_phase(c,phase)
    return "NEW"
def finish_phase(c:Mapping[str,Any],phase:str)->None:
    claim=c["roots"]["side_records"]/(phase+"_CLAIM.json");v,_=read_canonical(claim);done=_phase_value(c,phase,"DONE",v["pid"],sha_file(claim));_validate(done,c,"phase_state");_exclusive(c["roots"]["side_records"]/(phase+"_DONE.json"),done)
def validate_phase_pair(c:Mapping[str,Any],phase:str)->None:
    cp=c["roots"]["side_records"]/(phase+"_CLAIM.json");dp=c["roots"]["side_records"]/(phase+"_DONE.json")
    try:claim,_=read_canonical(cp);done,_=read_canonical(dp);_validate(claim,c,"phase_state");_validate(done,c,"phase_state")
    except BaseException as exc:raise NoMutationReject("PHASE_STATE_INVALID:"+phase+":"+str(exc)) from exc
    if claim["phase"]!=phase or claim["state"]!="CLAIMED" or done["phase"]!=phase or done["state"]!="DONE" or done["claim_sha256"]!=sha_file(cp):raise NoMutationReject("PHASE_STATE_BINDING:"+phase)
def _load_driver_objects(c:Mapping[str,Any])->dict[str,Any]:
    release=c["release"];entries=c["authority"]["entries"]
    if c["technical"]:
        bp=_safe(c["repo"],release["technical_bundle_path"])
        if sha_file(bp)!=release["technical_bundle_sha256"]:raise R11Error("BUNDLE_HASH")
        bundle,_=read_canonical(bp)
        if bundle.get("identity_class")!="TECHNICAL_SYNTHETIC_SHAPE_ONLY_NEVER_AUTHORITY":raise R11Error("BUNDLE_CLASS")
        for i,e in enumerate(entries,1):
            _record(c,"DRIVER",i,e)
            if release["technical_read_delay_ms"]:time.sleep(release["technical_read_delay_ms"]/1000)
            if release["technical_fail_after_driver_read"]==i:raise R11Error("INJECTED_PARTIAL_DRIVER_READ_FAILURE")
        return bundle["objects"]
    objects={}
    for i,e in enumerate(entries,1):
        with _safe(c["repo"],e["path"]).open("rb") as f:_record(c,"DRIVER",i,e);raw=f.read()
        if sha_bytes(raw)!=e["sha256"]:raise R11Error("AUTHORITY_HASH:"+e["purpose"])
        objects[e["purpose"]]=json.loads(raw.decode())
    return objects
def write_failure(c:Mapping[str,Any],reason:str)->None:
    p=c["roots"]["terminal"]/"TERMINAL.json"
    if p.exists():return
    n=count(c);v={"schema_version":"gen_enc_b1_r11_pre_01_"+("technical_" if c["technical"] else "")+"terminal_v1","record_kind":_identity(c,"SHAPE_RUN_TERMINAL","TECHNICAL_SHAPE_RUN_TERMINAL"),"task_id":TASK,"batch_id":"B1","run_id":c["release"]["run_id"],"status":"FAIL_CLOSED","reason":reason,"authority_read_count":n,"driver_read_count":min(n,13),"verifier_read_count":max(0,n-13),"shape_package_count":0,"member_count":0,"scientific_artifact_count":0,"publication_count":0,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False};_validate(v,c,"terminal");_exclusive(p,v)
def preflight(c:Mapping[str,Any])->dict[str,Any]:
    if _run_files(c):raise NoMutationReject("PREFLIGHT_NONEMPTY_RUN")
    v={"schema_version":"gen_enc_b1_r11_pre_01_"+("technical_" if c["technical"] else "")+"dispatch_consumed_v1","record_kind":_identity(c,"SHAPE_DISPATCH_CONSUMED","TECHNICAL_SHAPE_DISPATCH_CONSUMED"),**_binding(c["release"]),"release_sha256":c["release_sha256"],"attestation_sha256":c["attestation_sha256"],"dispatch_sha256":c["dispatch_sha256"],"state":"SHAPE_CONSUMED","one_use":True};_validate(v,c,"dispatch_consumed");_exclusive(c["roots"]["side_records"]/"SHAPE_DISPATCH_CONSUMED.json",v);return {"status":"SHAPE_PREFLIGHT_CONSUMED_ZERO_READS","authority_read_count":0}
def extract(c:Mapping[str,Any])->dict[str,Any]:
    _validate_consumed(c);actual=_zero_unlisted(c)
    if any(x.startswith("verifier_receipts/") or x.startswith("package/") or "VERIFIER_" in x or "PACKAGE_" in x for x in actual):raise NoMutationReject("EXTRACT_STAGE_CONTAMINATION")
    state=claim_phase(c,"DRIVER");snap_path=c["roots"]["staging"]/"driver_shape_snapshot.json"
    if state in ("DONE","RECOVER") and len(validate_receipts(c,"DRIVER"))==13 and snap_path.exists():
        v,_=read_canonical(snap_path);_validate(v,c,"structural_snapshot")
        if state=="RECOVER":finish_phase(c,"DRIVER")
        return {"status":"DRIVER_SHAPE_EXTRACTED_IDEMPOTENT","authority_read_count":13,"structural_snapshot_digest":v["structural_snapshot_digest"]}
    if state=="RECOVER":raise R11Error("ABANDONED_PARTIAL_DRIVER")
    if validate_receipts(c,"DRIVER"):raise R11Error("DRIVER_RECEIPTS_PREEXIST")
    result=snapshot(c["authority"]["entries"],_load_driver_objects(c),c["selectors"]);v={"schema_version":"gen_enc_b1_r11_pre_01_"+("technical_" if c["technical"] else "")+"structural_snapshot_v1","record_kind":_identity(c,"DRIVER_AUTHORITY_STRUCTURAL_SNAPSHOT","TECHNICAL_DRIVER_AUTHORITY_STRUCTURAL_SNAPSHOT"),"task_id":TASK,"batch_id":"B1","run_id":c["release"]["run_id"],"claim_ceiling":CLAIM,"authority_read_count":13,**result,"member_count":0,"scientific_artifact_count":0,"final_test_read":False};_validate(v,c,"structural_snapshot");_exclusive(snap_path,v);finish_phase(c,"DRIVER");return {"status":"DRIVER_SHAPE_EXTRACTED","authority_read_count":13,"structural_snapshot_digest":v["structural_snapshot_digest"]}
def package(c:Mapping[str,Any])->dict[str,Any]:
    _validate_consumed(c);actual=_zero_unlisted(c);validate_receipts(c,"DRIVER",13);validate_receipts(c,"VERIFIER",13);validate_phase_pair(c,"DRIVER");validate_phase_pair(c,"VERIFIER")
    required={"side_records/SHAPE_DISPATCH_CONSUMED.json","side_records/DRIVER_CLAIM.json","side_records/DRIVER_DONE.json","side_records/VERIFIER_CLAIM.json","side_records/VERIFIER_DONE.json","staging/driver_shape_snapshot.json","staging/independent_shape_report.json","staging/verifier_terminal.json",*[f"driver_receipts/{i:04d}.json" for i in range(1,14)],*[f"verifier_receipts/{i:04d}.json" for i in range(1,14)]}
    if not required<=actual:raise NoMutationReject("PACKAGE_MISSING_PRIOR_OUTPUT")
    driver,_=read_canonical(c["roots"]["staging"]/"driver_shape_snapshot.json");_validate(driver,c,"structural_snapshot");report,_=read_canonical(c["roots"]["staging"]/"independent_shape_report.json");_validate(report,c,"independent_report");vt,_=read_canonical(c["roots"]["staging"]/"verifier_terminal.json");_validate(vt,c,"verifier_terminal")
    if not(driver["structural_snapshot_digest"]==report["structural_snapshot_digest"]==vt["structural_snapshot_digest"]):raise NoMutationReject("DIGEST_BINDING")
    state=claim_phase(c,"PACKAGE");p=c["roots"]["package"]/"SHAPE_PACKAGE.json";terminal=c["roots"]["terminal"]/"TERMINAL.json"
    if state in ("DONE","RECOVER") and p.exists():
        pv,_=read_canonical(p);_validate(pv,c,"shape_package")
        if not terminal.exists():_write_success(c,report["structural_snapshot_digest"])
        if state=="RECOVER":finish_phase(c,"PACKAGE")
        return {"status":_identity(c,"SUCCESS_SHAPE_ONLY_AWAITING_GUARDIAN_RESULT_SEAL","TECHNICAL_SUCCESS_NEVER_FORMAL"),"authority_read_count":26,"structural_snapshot_digest":report["structural_snapshot_digest"]}
    if state=="RECOVER":raise R11Error("ABANDONED_PACKAGE_WITHOUT_RECOVERABLE_OUTPUT")
    run_entries=[{"path":rel,"sha256":sha_file(c["run_base"]/rel)} for rel in sorted(_run_files(c))]
    stage_entries=[{"path":name,"sha256":sha_file(c["roots"]["staging"]/name)} for name in ("driver_shape_snapshot.json","independent_shape_report.json","verifier_terminal.json")]
    pv={"schema_version":"gen_enc_b1_r11_pre_01_"+("technical_" if c["technical"] else "")+"shape_package_v1","record_kind":_identity(c,"SEALED_AUTHORITY_SHAPE_ONLY_PACKAGE","TECHNICAL_SEALED_AUTHORITY_SHAPE_ONLY_PACKAGE"),"task_id":TASK,"batch_id":"B1","run_id":c["release"]["run_id"],"status":_identity(c,"SEALED_AWAITING_GUARDIAN_RESULT_REVIEW","TECHNICAL_SEALED_NEVER_FORMAL"),"entry_count":3,"entries":stage_entries,"run_entry_count":len(run_entries),"run_entries":run_entries,"structural_snapshot_digest":report["structural_snapshot_digest"],"authority_read_count":26,"member_count":0,"scientific_artifact_count":0,"publication_count":0,"final_test_read":False};_validate(pv,c,"shape_package");_exclusive(p,pv);_write_success(c,report["structural_snapshot_digest"]);finish_phase(c,"PACKAGE");return {"status":_identity(c,"SUCCESS_SHAPE_ONLY_AWAITING_GUARDIAN_RESULT_SEAL","TECHNICAL_SUCCESS_NEVER_FORMAL"),"authority_read_count":26,"structural_snapshot_digest":report["structural_snapshot_digest"]}
def _write_success(c:Mapping[str,Any],digest:str)->None:
    v={"schema_version":"gen_enc_b1_r11_pre_01_"+("technical_" if c["technical"] else "")+"terminal_v1","record_kind":_identity(c,"SHAPE_RUN_TERMINAL","TECHNICAL_SHAPE_RUN_TERMINAL"),"task_id":TASK,"batch_id":"B1","run_id":c["release"]["run_id"],"status":_identity(c,"SUCCESS_SHAPE_ONLY_AWAITING_GUARDIAN_RESULT_SEAL","TECHNICAL_SUCCESS_NEVER_FORMAL"),"reason":None,"authority_read_count":26,"driver_read_count":13,"verifier_read_count":13,"shape_package_count":1,"member_count":0,"scientific_artifact_count":0,"publication_count":0,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False};_validate(v,c,"terminal");_exclusive(c["roots"]["terminal"]/"TERMINAL.json",v)
def parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser();p.add_argument("command",choices=["shape-preflight","extract-shape","package-shape"])
    for n in ("repo-root","release","guardian-attestation","dispatch","schema-root"):p.add_argument("--"+n,required=True,type=Path)
    return p
def main(argv:Sequence[str]|None=None,allow_technical:bool=False)->int:
    raw=list(sys.argv[1:] if argv is None else argv);ns=parser().parse_args(raw);c=None
    try:
        c=gate(ns.repo_root.resolve(),ns,raw,allow_technical);result=preflight(c) if ns.command=="shape-preflight" else extract(c) if ns.command=="extract-shape" else package(c);print(json.dumps(result,sort_keys=True));return 0
    except (NoMutationReject,LaneBusy) as exc:print(json.dumps({"status":"FAIL_CLOSED_NO_MUTATION","error":str(exc),"authority_read_count":0 if c is None else observed_count(c)},sort_keys=True),file=sys.stderr);return 2
    except BaseException as exc:
        if c is not None:
            try:write_failure(c,type(exc).__name__+":"+str(exc))
            except BaseException as marker:print(json.dumps({"status":"FAIL_CLOSED_MARKER_FAILURE","error":str(marker)},sort_keys=True),file=sys.stderr);return 3
        print(json.dumps({"status":"FAIL_CLOSED","error":type(exc).__name__+":"+str(exc),"authority_read_count":0 if c is None else count(c)},sort_keys=True),file=sys.stderr);return 2
