from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
import pytest
from scripts.gen_enc_b1_repair_11_format_01.build_freeze_package import build,PACKAGE
ROOT=Path(__file__).resolve().parents[1];TASK="01a049a7-15ca-79e1-92a2-d3822ba8609d"
def canon(v):return (json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def put(root,pointer,value):
    cur=root;parts=pointer[1:].split("/")
    for p in parts[:-1]:cur=cur.setdefault(p,{})
    cur[parts[-1]]=value
def sample(t,s):return {"k":"SECRET_"+s} if t=="object" else [{"k":"SECRET_"+s}] if t=="array" else "SECRET_"+s if t=="string" else 731 if t=="integer" else 7.31 if t=="number" else True
def make(tmp,mutation=None):
    build();selectors=json.loads((PACKAGE/"selector_contract.json").read_text());objects={f"CAD0_MULTI_SOURCE_{i:02d}":{"fixture":"SECRET_ROOT"} for i in range(1,14)}
    for s in selectors["selectors"]:
        if s["id"] in {"OWNERSHIP_CELLS","OWNERSHIP_RULE"}:continue
        if mutation==("missing",s["id"]):continue
        value=[] if mutation==("type",s["id"]) and s["type"]!="array" else {} if mutation==("type",s["id"]) else sample(s["type"],s["id"]);put(objects[s["purpose"]],s["pointer"],value)
    entries=[]
    for purpose,obj in objects.items():
        p=tmp/"legacy"/(purpose+".json");p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=4)+"\n",encoding="utf-8")
        entries.append({"path":p.relative_to(ROOT).as_posix(),"pointer":"","purpose":purpose,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    manifest={"schema_version":"gen_enc_b1_r11_minimal_authority_v1","record_kind":"TECHNICAL_SYNTHETIC_EXACT_13_MANIFEST","task_id":TASK,"technical_mirror":True,"final_test_read":False,"entries":sorted(entries,key=lambda e:e["purpose"])}
    mp=tmp/"manifest.json";mp.write_bytes(canon(manifest));sp=tmp/"selectors.json";sp.write_bytes(canon(selectors));rid=hashlib.sha256(str(tmp).encode()).hexdigest();out=tmp/"results"/rid
    args=["--repo-root",str(ROOT),"--authority-manifest",mp.relative_to(ROOT).as_posix(),"--selector-contract",sp.relative_to(ROOT).as_posix(),"--schema-root","schemas/gen_enc/b1_repair_11_format_01","--run-id",rid,"--result-dir",out.relative_to(ROOT).as_posix(),"--technical-mirror"]
    return args,out,entries
def run(module,args):return subprocess.run([sys.executable,"-m",module,*args],cwd=ROOT,text=True,capture_output=True)
def test_pretty_legacy_json_passes_raw_sha_then_standard_parse(tmp_path):
    args,out,_=make(tmp_path);assert run("scripts.gen_enc_b1_repair_11_format_01.shape_inspect",args).returncode==0;assert run("scripts.gen_enc_b1_repair_11_format_01.verify_shape",args).returncode==0
    mapping=json.loads((out/"driver_shape_mapping.json").read_text());report=json.loads((out/"independent_shape_verification.json").read_text());assert mapping["object_count"]==13 and report["cumulative_authority_read_count"]==26;assert "SECRET_" not in (out/"driver_shape_mapping.json").read_text()
    ownership=next(x for x in mapping["objects"] if x["purpose"]=="CAD0_MULTI_SOURCE_03");assert ownership["selector_status"]["OWNERSHIP_CELLS"]==ownership["selector_status"]["OWNERSHIP_RULE"]=="FUTURE_OUTPUT_NOT_AUTHORITY"
    assert {p.name for p in out.iterdir()}=={"driver_shape_mapping.json","provenance.json","independent_shape_verification.json"}
def test_raw_sha_mismatch_rejected_before_parse(tmp_path):
    args,out,entries=make(tmp_path);p=ROOT/entries[0]["path"];p.write_text("{}",encoding="utf-8");r=run("scripts.gen_enc_b1_repair_11_format_01.shape_inspect",args);assert r.returncode==2 and "SOURCE_SHA256" in r.stderr and (out/"FAILURE.json").exists()
@pytest.mark.parametrize("mutation",[("missing","SLOT_ROWS"),("type","SLOT_ROWS")])
def test_basic_selector_checks(tmp_path,mutation):
    args,out,_=make(tmp_path,mutation);assert run("scripts.gen_enc_b1_repair_11_format_01.shape_inspect",args).returncode==2 and (out/"FAILURE.json").exists()
def test_independent_sources_and_zero_state():
    build();assert "gen_enc_b1_repair_11_format_01.shape_inspect" not in (ROOT/"scripts/gen_enc_b1_repair_11_format_01/verify_shape.py").read_text();p=json.loads((PACKAGE/"provenance.json").read_text());d=json.loads((PACKAGE/"DRAFT.json").read_text());assert p["formal_authority_read_count_during_correction"]==p["formal_run_count"]==0 and d["run_id"] is None and d["final_test_read"] is False
