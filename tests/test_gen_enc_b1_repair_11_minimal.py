from __future__ import annotations
import copy, hashlib, json, subprocess, sys
from pathlib import Path

import pytest
from scripts.gen_enc_b1_repair_11_minimal.build_freeze_package import build, PACKAGE

ROOT=Path(__file__).resolve().parents[1]
def canon(v):return (json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(canon(v))
def put(root,pointer,value):
    parts=pointer[1:].split("/");cur=root
    for part in parts[:-1]:cur=cur.setdefault(part,{})
    cur[parts[-1]]=value
def sample(t,sid):
    return {"synthetic":"SCALAR_SENTINEL_"+sid} if t=="object" else [{"synthetic":"SCALAR_SENTINEL_"+sid}] if t=="array" else "SCALAR_SENTINEL_"+sid if t=="string" else 991337 if t=="integer" else 991.337 if t=="number" else True
def case(tmp_path, mutation=None):
    build();selectors=json.loads((PACKAGE/"selector_contract.json").read_text());entries=[]
    objects={f"CAD0_MULTI_SOURCE_{i:02d}":{"technical":"SCALAR_SENTINEL_ROOT"} for i in range(1,14)}
    for s in selectors["selectors"]:
        if s["id"] in {"OWNERSHIP_CELLS","OWNERSHIP_RULE"}:continue
        if mutation==("missing",s["id"]):continue
        value=sample(s["type"],s["id"])
        if mutation==("type",s["id"]):value=[] if s["type"]!="array" else {}
        put(objects[s["purpose"]],s["pointer"],value)
    if mutation==("future","OWNERSHIP_CELLS"):put(objects["CAD0_MULTI_SOURCE_03"],"/ownership/cells",[])
    for purpose,obj in objects.items():
        p=tmp_path/"inputs"/(purpose+".json");write(p,obj);entries.append({"purpose":purpose,"path":p.relative_to(ROOT).as_posix(),"pointer":"","sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    manifest={"schema_version":"gen_enc_b1_r11_minimal_authority_v1","record_kind":"TECHNICAL_SYNTHETIC_EXACT_13_MANIFEST","task_id":"01a049a7-15ca-79e1-92a2-d3822ba8609d","technical_mirror":True,"final_test_read":False,"entries":sorted(entries,key=lambda x:x["purpose"])}
    mp=tmp_path/"manifest.json";write(mp,manifest);sp=tmp_path/"selectors.json";write(sp,selectors);run_id=hashlib.sha256(str(tmp_path).encode()).hexdigest();out=tmp_path/"results"/run_id
    base=["--repo-root",str(ROOT),"--authority-manifest",mp.relative_to(ROOT).as_posix(),"--selector-contract",sp.relative_to(ROOT).as_posix(),"--schema-root","schemas/gen_enc/b1_repair_11_minimal","--run-id",run_id,"--result-dir",out.relative_to(ROOT).as_posix(),"--technical-mirror"]
    return base,out
def run(module,args):return subprocess.run([sys.executable,"-m",module,*args],cwd=ROOT,text=True,capture_output=True)

def test_minimal_sequential_shape_and_independent_verification(tmp_path):
    args,out=case(tmp_path);a=run("scripts.gen_enc_b1_repair_11_minimal.shape_inspect",args);assert a.returncode==0,a.stderr
    b=run("scripts.gen_enc_b1_repair_11_minimal.verify_shape",args);assert b.returncode==0,b.stderr
    mapping=json.loads((out/"driver_shape_mapping.json").read_text());report=json.loads((out/"independent_shape_verification.json").read_text())
    assert mapping["object_count"]==13 and report["cumulative_authority_read_count"]==26
    assert report["mapping_digest"]==mapping["mapping_digest"]
    assert "SCALAR_SENTINEL" not in (out/"driver_shape_mapping.json").read_text()
    row=next(x for x in mapping["objects"] if x["purpose"]=="CAD0_MULTI_SOURCE_03")
    assert row["selector_status"]["OWNERSHIP_CELLS"]=="FUTURE_OUTPUT_NOT_AUTHORITY"
    assert row["selector_status"]["OWNERSHIP_RULE"]=="FUTURE_OUTPUT_NOT_AUTHORITY"
    assert {x.name for x in out.iterdir()}=={"driver_shape_mapping.json","provenance.json","independent_shape_verification.json"}

@pytest.mark.parametrize("mutation",[("missing","SLOT_ROWS"),("type","SLOT_ROWS"),("future","OWNERSHIP_CELLS")])
def test_real_shape_errors_fail_with_provenance(tmp_path,mutation):
    args,out=case(tmp_path,mutation);result=run("scripts.gen_enc_b1_repair_11_minimal.shape_inspect",args)
    assert result.returncode==2 and (out/"FAILURE.json").exists()

def test_basic_canonical_and_identity_gate(tmp_path):
    args,out=case(tmp_path);manifest=ROOT/args[args.index("--authority-manifest")+1]
    manifest.write_text(json.dumps(json.loads(manifest.read_text()),indent=2),encoding="utf-8")
    result=run("scripts.gen_enc_b1_repair_11_minimal.shape_inspect",args)
    assert result.returncode==2 and "NON_CANONICAL" in result.stderr

def test_scope_and_zero_formal_state():
    build();scope=json.loads((PACKAGE/"scope_freeze.json").read_text());prov=json.loads((PACKAGE/"provenance.json").read_text());draft=json.loads((PACKAGE/"DRAFT.json").read_text())
    assert scope["b1_member_count"]==20 and len(scope["b1_members"])==20 and scope["final_design"]["total"]==80
    assert prov["formal_authority_read_count"]==prov["formal_shape_run_count"]==prov["formal_control_count"]==0
    assert draft["run_id"] is None and not any(draft["permissions"].values()) and draft["final_test_read"] is False

def test_source_independence_and_override_binding():
    assert "gen_enc_b1_repair_11_minimal.shape_inspect" not in (ROOT/"scripts/gen_enc_b1_repair_11_minimal/verify_shape.py").read_text()
    provenance=json.loads((PACKAGE/"provenance.json").read_text())
    assert provenance["science_first_override"]["sha256"]=="31a0dac1b8aeadcf95e8c5305981b11f94b8587365d18104b97d7aa8425af835"
