from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema

from .verifier_core import ShapeVerifierError, canonical, read_canonical, sha_bytes, sha_file, verify_snapshot

TASK_ID="01a049a7-15ca-79e1-92a2-d3822ba8609d"; REPAIR="PRE-RELEASE-REPAIR-11"; MODE="FORMAL_B1_AUTHORITY_SHAPE_ONLY_EXACT_13X2"; COMMANDS=["shape-preflight","extract-shape","verify-shape","package-shape"]; CLAIM="E0_AUTHORITY_STRUCTURE_CONFORMANCE_ONLY"

class Verify11Error(RuntimeError): pass

def _safe(repo:Path,label:str)->Path:
    rel=Path(label)
    if rel.is_absolute() or ".." in rel.parts: raise Verify11Error("UNSAFE_PATH:"+label)
    path=(repo/rel).resolve()
    try:path.relative_to(repo)
    except ValueError as exc:raise Verify11Error("PATH_ESCAPE") from exc
    return path

def _schemas(root:Path)->dict[str,Any]:
    out={}
    for path in root.glob("*.schema.json"):
        value=json.loads(path.read_text(encoding="utf-8"));jsonschema.Draft202012Validator.check_schema(value);out[path.name.removesuffix(".schema.json")]=value
    return out

def _validate(value:Any,schemas:Mapping[str,Any],name:str)->None:
    try:jsonschema.Draft202012Validator(schemas[name]).validate(value)
    except jsonschema.ValidationError as exc:raise Verify11Error("SCHEMA_"+name+":"+exc.message) from exc

def _binding(release:Mapping[str,Any])->dict[str,Any]:
    names=("task_id","batch_id","run_id","dispatch_id","mode","commands_exact","authority_manifest_path","authority_manifest_sha256","selector_contract_path","selector_contract_sha256","source_manifest_path","source_manifest_sha256","schema_manifest_path","schema_manifest_sha256","command_manifest_path","command_manifest_sha256","output_manifest_path","output_manifest_sha256","negative_capability_manifest_path","negative_capability_manifest_sha256","guardian_contract_path","guardian_contract_sha256","roots","final_test_read","technical_mirror","technical_bundle_path","technical_bundle_sha256","technical_fail_after_driver_read","technical_fail_after_verifier_read","technical_read_delay_ms")
    return {name:release[name] for name in names}

def gate(repo:Path,ns:argparse.Namespace,raw_argv:Sequence[str])->dict[str,Any]:
    schemas=_schemas(ns.schema_root.resolve());release,rraw=read_canonical(ns.release.resolve());_validate(release,schemas,"shape_release");att,araw=read_canonical(ns.guardian_attestation.resolve());_validate(att,schemas,"shape_attestation");dispatch,draw=read_canonical(ns.dispatch.resolve());_validate(dispatch,schemas,"shape_dispatch")
    if release["task_id"]!=TASK_ID or release["mode"]!=MODE or release["commands_exact"]!=COMMANDS:raise Verify11Error("RELEASE_BINDING")
    root_base=(f".r11t/{release['run_id']}/shape_run" if release["technical_mirror"] else f"outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_11_shape_runs/{release['run_id']}")
    if release["roots"]!={name:f"{root_base}/{name}" for name in ("staging","receipts","side_records","package","terminal")}:raise Verify11Error("RUN_ROOT_TEMPLATE")
    if att["release_path"]!=ns.release.as_posix() or att["release_sha256"]!=sha_bytes(rraw):raise Verify11Error("ATTESTATION_BINDING")
    if dispatch["release_path"]!=ns.release.as_posix() or dispatch["release_sha256"]!=sha_bytes(rraw) or dispatch["attestation_path"]!=ns.guardian_attestation.as_posix() or dispatch["attestation_sha256"]!=sha_bytes(araw):raise Verify11Error("DISPATCH_BINDING")
    for key,want in _binding(release).items():
        if att.get(key)!=want or dispatch.get(key)!=want:raise Verify11Error("FULL_BINDING:"+key)
    if dispatch["state"]!="SHAPE_ISSUED" or dispatch["revoked"] or not dispatch["one_use"]:raise Verify11Error("DISPATCH_STATE")
    if (release["release_path"],release["attestation_path"],release["dispatch_path"])!=(ns.release.as_posix(),ns.guardian_attestation.as_posix(),ns.dispatch.as_posix()):raise Verify11Error("CLI_PATH_BINDING")
    for field in ("authority_manifest","selector_contract","source_manifest","schema_manifest","command_manifest","output_manifest","negative_capability_manifest","guardian_contract"):
        if sha_file(_safe(repo,release[field+"_path"]))!=release[field+"_sha256"]:raise Verify11Error("BOUND_HASH:"+field)
    authority,_=read_canonical(_safe(repo,release["authority_manifest_path"]));_validate(authority,schemas,"authority_manifest");selector,_=read_canonical(_safe(repo,release["selector_contract_path"]));_validate(selector,schemas,"selector_contract");commands,_=read_canonical(_safe(repo,release["command_manifest_path"]));_validate(commands,schemas,"command_manifest")
    row=next((x for x in commands["entries"] if x["command"]=="verify-shape"),None); repl={"<RELEASE_EXACT_PATH>":ns.release.as_posix(),"<ATTESTATION_EXACT_PATH>":ns.guardian_attestation.as_posix(),"<DISPATCH_EXACT_PATH>":ns.dispatch.as_posix()}; expected=[repl.get(x,x) for x in row["argv_after_python"][2:]] if row else []
    if list(raw_argv)!=expected:raise Verify11Error("ARGV_NOT_BYTE_EXACT")
    roots={name:_safe(repo,label) for name,label in release["roots"].items()}
    terminal=roots["terminal"]/"TERMINAL.json"
    if terminal.exists():raise Verify11Error("TERMINAL_ALREADY_EXISTS")
    return {"repo":repo,"schemas":schemas,"release":release,"release_sha256":sha_bytes(rraw),"attestation_sha256":sha_bytes(araw),"authority":authority,"selectors":selector["selectors"],"roots":roots}

def _count(c:Mapping[str,Any])->int:
    d=c["roots"]["receipts"]
    if not d.exists():return 0
    ps=sorted(d.glob("*.json"))
    if [x.name for x in ps]!=[f"{i:04d}.json" for i in range(1,len(ps)+1)]:raise Verify11Error("RECEIPT_SEQUENCE")
    return len(ps)

def _exclusive(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open("xb") as stream:stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
    except FileExistsError as exc:raise Verify11Error("EXCLUSIVE_EXISTS") from exc

def _receipt(c:Mapping[str,Any],entry:Mapping[str,Any])->None:
    n=_count(c)+1;value={"schema_version":"gen_enc_b1_r11_authority_read_receipt_v1","record_kind":"AUTHORITY_SHAPE_READ_RECEIPT","task_id":TASK_ID,"batch_id":"B1","run_id":c["release"]["run_id"],"dispatch_id":c["release"]["dispatch_id"],"lane":"VERIFIER","ordinal":n,"purpose":entry["purpose"],"source_path":entry["path"],"source_sha256":entry["sha256"],"source_pointer":entry["pointer"],"release_sha256":c["release_sha256"],"attestation_sha256":c["attestation_sha256"],"final_test_read":False};_validate(value,c["schemas"],"authority_read_receipt");_exclusive(c["roots"]["receipts"]/f"{n:04d}.json",value)

def _objects(c:Mapping[str,Any])->dict[str,Any]:
    release=c["release"];entries=c["authority"]["entries"]
    if release["technical_mirror"]:
        bp=_safe(c["repo"],release["technical_bundle_path"])
        if sha_file(bp)!=release["technical_bundle_sha256"]:raise Verify11Error("BUNDLE_HASH")
        bundle,_=read_canonical(bp)
        if bundle.get("identity_class")!="TECHNICAL_SYNTHETIC_SHAPE_ONLY_NEVER_AUTHORITY":raise Verify11Error("BUNDLE_CLASS")
        objects=bundle["objects"]
        for lane_index,e in enumerate(entries,1):
            _receipt(c,e)
            if release["technical_read_delay_ms"]:time.sleep(release["technical_read_delay_ms"]/1000)
            if release.get("technical_fail_after_verifier_read")==lane_index:raise Verify11Error("INJECTED_PARTIAL_VERIFIER_READ_FAILURE")
        return objects
    objects={}
    for e in entries:
        with _safe(c["repo"],e["path"]).open("rb") as stream:
            _receipt(c,e)
            raw=stream.read()
        if sha_bytes(raw)!=e["sha256"]:raise Verify11Error("AUTHORITY_HASH:"+e["purpose"])
        objects[e["purpose"]]=json.loads(raw.decode("utf-8"))
    return objects

def _failure(c:Mapping[str,Any],reason:str)->None:
    p=c["roots"]["terminal"]/"TERMINAL.json"
    if p.exists():return
    n=_count(c);value={"schema_version":"gen_enc_b1_r11_terminal_v1","record_kind":"SHAPE_RUN_TERMINAL","task_id":TASK_ID,"batch_id":"B1","run_id":c["release"]["run_id"],"status":"FAIL_CLOSED","reason":reason,"authority_read_count":n,"driver_read_count":min(n,13),"verifier_read_count":max(0,n-13),"shape_package_count":0,"member_count":0,"scientific_artifact_count":0,"publication_count":0,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False};_validate(value,c["schemas"],"terminal");_exclusive(p,value)

def verify(c:Mapping[str,Any])->dict[str,Any]:
    if _count(c)!=13:raise Verify11Error("VERIFY_REQUIRES_13_DRIVER_READS")
    driver,_=read_canonical(c["roots"]["staging"]/"driver_shape_snapshot.json");_validate(driver,c["schemas"],"structural_snapshot")
    objects=_objects(c);result=verify_snapshot(c["authority"]["entries"],objects,c["selectors"],driver)
    report={"schema_version":"gen_enc_b1_r11_independent_report_v1","record_kind":"INDEPENDENT_AUTHORITY_SHAPE_VERIFICATION","task_id":TASK_ID,"batch_id":"B1","run_id":c["release"]["run_id"],"status":"PASS","driver_read_count":13,"verifier_read_count":13,"authority_read_count":26,"object_count":13,"structural_snapshot_digest":result["structural_snapshot_digest"],"scalar_values_persisted":False,"scalar_value_hashes_persisted":False,"scalar_lengths_persisted":False,"member_count":0,"scientific_artifact_count":0,"publication_count":0,"claim_ceiling":CLAIM,"final_test_read":False};_validate(report,c["schemas"],"independent_report");_exclusive(c["roots"]["staging"]/"independent_shape_report.json",report)
    terminal={"schema_version":"gen_enc_b1_r11_verifier_terminal_v1","record_kind":"INDEPENDENT_SHAPE_VERIFIER_TERMINAL","task_id":TASK_ID,"batch_id":"B1","run_id":c["release"]["run_id"],"status":"VERIFIED_SHAPE_AWAITING_PACKAGE","structural_snapshot_digest":result["structural_snapshot_digest"],"authority_read_count":26,"object_count":13,"final_test_read":False};_validate(terminal,c["schemas"],"verifier_terminal");_exclusive(c["roots"]["staging"]/"verifier_terminal.json",terminal)
    return {"status":terminal["status"],"authority_read_count":26,"structural_snapshot_digest":result["structural_snapshot_digest"]}

def parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser();p.add_argument("command",choices=["verify-shape"])
    for name in ("repo-root","release","guardian-attestation","dispatch","schema-root"):p.add_argument("--"+name,required=True,type=Path)
    return p

def main(argv:Sequence[str]|None=None)->int:
    raw=list(sys.argv[1:] if argv is None else argv);ns=parser().parse_args(raw);context=None
    try:context=gate(ns.repo_root.resolve(),ns,raw);result=verify(context);print(json.dumps(result,sort_keys=True));return 0
    except BaseException as exc:
        if context is not None:_failure(context,type(exc).__name__+":"+str(exc))
        print(json.dumps({"status":"FAIL_CLOSED","error":type(exc).__name__+":"+str(exc),"authority_read_count":0 if context is None else _count(context)},sort_keys=True),file=sys.stderr);return 2

if __name__=="__main__":raise SystemExit(main())
