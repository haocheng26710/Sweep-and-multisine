from __future__ import annotations
import copy,hashlib,importlib.util,json,sys
from pathlib import Path
import jsonschema,pytest

REPO=Path(__file__).resolve().parents[1];SCHEMA_ROOT=REPO/"schemas/gen_enc/gen_enc_2c_rev03";CORR_SCHEMA=REPO/"schemas/gen_enc/gen_enc_2c_s2_corr01";FORMAL_ALLOW=REPO/"outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/s1_implementation_freeze/path_allowlist_manifest.json"
def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
E=module("corr_endpoint",REPO/"scripts/gen_enc_2c_s2_corr01/endpoint_corr01.py");V=module("corr_verifier",REPO/"scripts/gen_enc_2c_s2_corr01/independent_verifier_corr01.py")
def allfalse():return {k:False for k in E.EXECUTION_PERMISSIONS}
def contract(tmp):
    paths={};hashes={}
    for k in ("source","schema","fixture","authority","allowlist"):
        p=tmp/f"{k}.manifest";p.write_bytes(k.encode());paths[k]=str(p);hashes[k]=hashlib.sha256(k.encode()).hexdigest()
    cp=tmp/"contract.binding";cp.write_bytes(b"technical-contract-binding")
    return {"contract_path":str(cp),"terminal_roots":{"staging":str(tmp/"staging"),"success":str(tmp/"success"),"failure":str(tmp/"failure"),"progress":str(tmp/"progress")},"manifest_paths":paths,"manifest_sha256":hashes,"commands":["preflight","generate-static","verify","publish","package"],"modes":["S2_PREFLIGHT","S2_GENERATE_STATIC","S2_VERIFY","S2_PUBLISH","S2_PACKAGE"],"draft_dispatch_id":"GEN-ENC-2C-S2-CORR01-DRAFT-NONATTEMPT"}
def record(c,kind="DRAFT"):
    perms=allfalse();scope=allfalse();scope["s2_formal_generation_and_static_audit"]=True
    if kind=="RELEASE":perms["s2_formal_generation_and_static_audit"]=True
    p={"schema_version":"gen_enc_2c_s2_corr01_authorization_v1","record_kind":kind,"task_id":E.TASK_ID,"dispatch_id":"GEN-ENC-2C-S2-CORR01-DRAFT-NONATTEMPT" if kind=="DRAFT" else "GEN-ENC-2C-S2-CORR01-RELEASE-001","revoked":False,"issued_at":"2026-08-28T00:00:00Z","expires_at":"2026-08-31T00:00:00Z","guardian_review_path":None if kind=="DRAFT" else "guardian/review.json","guardian_review_sha256":None if kind=="DRAFT" else "1"*64,"contract_path":c["contract_path"],"contract_sha256":hashlib.sha256(Path(c["contract_path"]).read_bytes()).hexdigest(),"terminal_roots":c["terminal_roots"],"manifest_sha256":c["manifest_sha256"],"runtime":{"python":sys.version.split()[0],"jsonschema":__import__("importlib").metadata.version("jsonschema")},"commands":c["commands"],"modes":c["modes"],"permissions":perms,"requested_scope":scope,"final_test_state":"SEALED","final_test_read":False,"run_id":None}
    cb=E.canonical(p);return {"payload":p,"payload_sha256":hashlib.sha256(cb).hexdigest()}
def write(path,x):path.write_bytes(E.canonical(x))

def test_complete_4x20_92_mirror_and_all_nine_schemas(tmp_path):
    root=tmp_path/"mirror";r=E.build_technical_mirror(root,SCHEMA_ROOT);assert r["technical_target_count"]==92
    files=[p for p in root.rglob("*") if p.is_file()];assert len(files)==92
    assert all(str(p.resolve()) not in set(json.loads(FORMAL_ALLOW.read_text())["paths"]) for p in files)
    assert all(E.LABEL in p.read_text(encoding="utf-8") for p in files)
    assert len(E.SCHEMA_FILE)==9

def test_independent_verifier_full_success_and_marker(tmp_path):
    root=tmp_path/"mirror";control=tmp_path/"control";E.build_technical_mirror(root,SCHEMA_ROOT);r=V.verify_fail_closed(root,SCHEMA_ROOT,control)
    assert r=={"status":"PASS_STATIC_IDENTITY_RECOMPUTATION","failure_count":0,"formal_hash_chain_recomputed":True,"formal_input_read_count":0,"final_test_read":False}
    assert (control/"VERIFIED_SUCCESS.json").is_file() and not(control/"FAIL_CLOSED.json").exists()

def test_missing_field_is_atomic_fail_closed(tmp_path):
    root=tmp_path/"mirror";control=tmp_path/"control";E.build_technical_mirror(root,SCHEMA_ROOT);p=next(root.glob("scientific/instances/*/*.json"));x=json.loads(p.read_text());del x["artifact"]["cad_static_audit"]["volume_m3"];write(p,x)
    r=V.verify_fail_closed(root,SCHEMA_ROOT,control);assert r["formal_hash_chain_recomputed"] is False and (control/"FAIL_CLOSED.json").is_file()
    jsonschema.validate(json.loads((control/"FAIL_CLOSED.json").read_text()),json.loads((CORR_SCHEMA/"fail_closed.schema.json").read_text()))

def test_false_static_value_detected(tmp_path):
    root=tmp_path/"mirror";control=tmp_path/"control";E.build_technical_mirror(root,SCHEMA_ROOT);p=next(root.glob("scientific/instances/*/*.json"));x=json.loads(p.read_text());x["artifact"]["cad_static_audit"]["volume_m3"]+=1e-7;write(p,x)
    r=V.verify_fail_closed(root,SCHEMA_ROOT,control);assert r["failure_count"]>0 and not r["formal_hash_chain_recomputed"]

def test_provenance_conversion_strips_technical_label():
    params,prov=E.convert_provenance(E.technical_raw(E.FAMILIES[0],1),E.FAMILIES[0],1);assert E.LABEL not in json.dumps(params) and prov["kind"]=="EXACT_ROW"

def test_parameter_dependent_adapter_and_zero_edges():
    p1,_=E.convert_provenance(E.technical_raw(E.FAMILIES[2],1),E.FAMILIES[2],1);p2,_=E.convert_provenance(E.technical_raw(E.FAMILIES[2],2),E.FAMILIES[2],2);a1,e1,_=E.cad_static_adapter(p1,E.FAMILIES[2]);a2,e2,_=E.cad_static_adapter(p2,E.FAMILIES[2]);assert a1!=a2 and e1["thresholds_copied_as_measurements"] is False and any(x[2]==0 and x[3] is False for x in e1["reduced_edges"]+e2["reduced_edges"])

def test_publication_injected_failure_rolls_back_all(tmp_path):
    root=tmp_path/"mirror";E.build_technical_mirror(root,SCHEMA_ROOT);pub=tmp_path/"pub";progress=tmp_path/"progress_pub"
    with pytest.raises(E.Corr01Error,match="INJECTED"):E.publish_transaction(root,pub,progress,inject_after=47)
    assert not pub.exists() and not progress.exists();assert json.loads((tmp_path/"publication_journal.json").read_text())["state"]=="ROLLED_BACK"

def test_publication_success_is_exact_92(tmp_path):
    root=tmp_path/"mirror";E.build_technical_mirror(root,SCHEMA_ROOT);r=E.publish_transaction(root,tmp_path/"pub",tmp_path/"progress_pub");assert r["published"]==92 and len([p for p in (tmp_path/"pub").rglob("*") if p.is_file()])+len([p for p in (tmp_path/"progress_pub").rglob("*") if p.is_file()])==92

def test_draft_all_permissions_false_and_never_executable(tmp_path):
    c=contract(tmp_path);x=record(c);p=tmp_path/"draft.json";write(p,x);jsonschema.validate(x,json.loads((CORR_SCHEMA/"authorization.schema.json").read_text()))
    assert not any(x["payload"]["permissions"].values()) and x["payload"]["requested_scope"]["s2_formal_generation_and_static_audit"]
    with pytest.raises(E.Corr01Error,match="DRAFT_NEVER"):E.validate_authorization(p,CORR_SCHEMA/"authorization.schema.json",c,"preflight","S2_PREFLIGHT")

@pytest.mark.parametrize("mutation",["task","roots","manifest","runtime","commands","modes","revoked","expiry","final","payload_hash","noncanonical"])
def test_authorization_mutations(tmp_path,mutation):
    c=contract(tmp_path);x=record(c);p=tmp_path/"draft.json"
    if mutation=="task":x["payload"]["task_id"]="wrong"
    elif mutation=="roots":x["payload"]["terminal_roots"]={"wrong":"root"}
    elif mutation=="manifest":x["payload"]["manifest_sha256"]["source"]="0"*64
    elif mutation=="runtime":x["payload"]["runtime"]["python"]="0"
    elif mutation=="commands":x["payload"]["commands"]=[]
    elif mutation=="modes":x["payload"]["modes"]=[]
    elif mutation=="revoked":x["payload"]["revoked"]=True
    elif mutation=="expiry":x["payload"]["expires_at"]="2020-01-01T00:00:00Z"
    elif mutation=="final":x["payload"]["final_test_read"]=True
    elif mutation=="payload_hash":x["payload_sha256"]="0"*64
    if mutation not in ("payload_hash","noncanonical"):x["payload_sha256"]=hashlib.sha256(E.canonical(x["payload"])).hexdigest()
    write(p,x)
    if mutation=="noncanonical":p.write_bytes(p.read_bytes()+b"\n")
    with pytest.raises(Exception):E.validate_authorization(p,CORR_SCHEMA/"authorization.schema.json",c,"preflight","S2_PREFLIGHT")

def test_release_attestation_and_run_id_dual_derivation(tmp_path):
    c=contract(tmp_path);x=record(c,"RELEASE");p=tmp_path/"release.json";write(p,x);att=tmp_path/"att.json";full=hashlib.sha256(p.read_bytes()).hexdigest();att.write_text(json.dumps({"release_full_sha256":full,"guardian_review_sha256":"1"*64,"task_id":E.TASK_ID}))
    result=E.validate_authorization(p,CORR_SCHEMA/"authorization.schema.json",c,"preflight","S2_PREFLIGHT",att);independent=V.validate_authorization_independent(p,CORR_SCHEMA/"authorization.schema.json",c,"preflight","S2_PREFLIGHT",att);expected=hashlib.sha256(b"\x0a".join([b"GEN-ENC-2C-S2-CORR01-RUN-ID-v1",full.encode(),E.TASK_ID.encode()]+[c["manifest_sha256"][k].encode() for k in ("source","schema","fixture","authority","allowlist")])).hexdigest();assert result["run_id"]==independent["run_id"]==expected

def test_terminal_mixed_and_missing_rejected(tmp_path):
    c=tmp_path/"control";c.mkdir();
    with pytest.raises(E.Corr01Error):E.package_terminal(c,tmp_path/"s",tmp_path/"f")
    (c/"VERIFIED_SUCCESS.json").write_text("{}");(c/"FAIL_CLOSED.json").write_text("{}")
    with pytest.raises(E.Corr01Error):E.package_terminal(c,tmp_path/"s",tmp_path/"f")

def test_terminal_success_and_failure_package(tmp_path):
    c=tmp_path/"c1";E.terminal_marker(c,True,{"artifacts":92});assert E.package_terminal(c,tmp_path/"s1",tmp_path/"f1")=="SUCCESS" and (tmp_path/"s1/VERIFIED_SUCCESS.json").is_file()
    c=tmp_path/"c2";E.terminal_marker(c,False,{"artifacts":17},"INJECTED");assert E.package_terminal(c,tmp_path/"s2",tmp_path/"f2")=="FAIL_CLOSED" and (tmp_path/"f2/FAIL_CLOSED.json").is_file()

def test_formal_paths_still_absent():
    allow=json.loads(FORMAL_ALLOW.read_text())["paths"];assert len(allow)==92 and sum((REPO/p).exists() for p in allow)==0
