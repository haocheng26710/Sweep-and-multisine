from __future__ import annotations
import hashlib,json,subprocess,sys
from pathlib import Path
from scripts.gen_enc_b1_repair_11_collector_02.build_freeze_package import build,PACKAGE
ROOT=Path(__file__).resolve().parents[1];TASK="01a049a7-15ca-79e1-92a2-d3822ba8609d"
def canon(v):return (json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def put(root,pointer,value):
    cur=root;parts=pointer[1:].split("/")
    for p in parts[:-1]:cur=cur.setdefault(p,{})
    cur[parts[-1]]=value
def sample(t,s):return {"k":"PRIVATE_"+s} if t=="object" else [{"k":"PRIVATE_"+s}] if t=="array" else "PRIVATE_"+s if t=="string" else 4567 if t=="integer" else 45.67 if t=="number" else True
def case(tmp,future=False):
    build();selectors=json.loads((PACKAGE/"selector_contract.json").read_text());objects={f"CAD0_MULTI_SOURCE_{i:02d}":{"fixture":"PRIVATE_ROOT"} for i in range(1,14)}
    for s in selectors["selectors"]:
        if s["id"] in {"OWNERSHIP_CELLS","OWNERSHIP_RULE"}:
            if future:put(objects[s["purpose"]],s["pointer"],sample(s["type"],s["id"]))
        elif s["id"]=="GEOMETRY_VOLUME":continue
        elif s["id"]=="SLOT_ROWS":put(objects[s["purpose"]],s["pointer"],{})
        else:put(objects[s["purpose"]],s["pointer"],sample(s["type"],s["id"]))
    entries=[]
    for purpose,obj in objects.items():
        p=tmp/"legacy"/(purpose+".json");p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8");entries.append({"path":p.relative_to(ROOT).as_posix(),"pointer":"","purpose":purpose,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    manifest={"schema_version":"gen_enc_b1_r11_minimal_authority_v1","record_kind":"TECHNICAL_SYNTHETIC_EXACT_13_MANIFEST","task_id":TASK,"technical_mirror":True,"final_test_read":False,"entries":sorted(entries,key=lambda e:e["purpose"])};mp=tmp/"manifest.json";mp.write_bytes(canon(manifest));sp=tmp/"selectors.json";sp.write_bytes(canon(selectors));rid=hashlib.sha256(str(tmp).encode()).hexdigest();out=tmp/"results"/rid;args=["--repo-root",str(ROOT),"--authority-manifest",mp.relative_to(ROOT).as_posix(),"--selector-contract",sp.relative_to(ROOT).as_posix(),"--schema-root","schemas/gen_enc/b1_repair_11_collector_02","--run-id",rid,"--result-dir",out.relative_to(ROOT).as_posix(),"--technical-mirror"];return args,out,entries
def run(module,args):return subprocess.run([sys.executable,"-m",module,*args],cwd=ROOT,text=True,capture_output=True)
def test_collects_all_shapes_and_diagnostic_states_without_early_stop(tmp_path):
    args,out,_=case(tmp_path);assert run("scripts.gen_enc_b1_repair_11_collector_02.shape_collect",args).returncode==0;assert run("scripts.gen_enc_b1_repair_11_collector_02.verify_collection",args).returncode==0
    mapping=json.loads((out/"shape_mapping.json").read_text());report=json.loads((out/"independent_verification.json").read_text());assert len(mapping["objects"])==13 and len(mapping["selector_status"])==31;assert mapping["selector_status"]["GEOMETRY_VOLUME"]=="MISSING";assert mapping["selector_status"]["SLOT_ROWS"]=="PRESENT_TYPE_MISMATCH";assert mapping["selector_status"]["OWNERSHIP_CELLS"]==mapping["selector_status"]["OWNERSHIP_RULE"]=="FUTURE_OUTPUT_ABSENT";assert report["cumulative_authority_read_count"]==26;assert "PRIVATE_" not in (out/"shape_mapping.json").read_text();assert {p.name for p in out.iterdir()}=={"shape_mapping.json","provenance.json","independent_verification.json"}
def test_future_outputs_present_are_recorded_not_authorized(tmp_path):
    args,out,_=case(tmp_path,True);assert run("scripts.gen_enc_b1_repair_11_collector_02.shape_collect",args).returncode==0;m=json.loads((out/"shape_mapping.json").read_text());assert m["selector_status"]["OWNERSHIP_CELLS"]==m["selector_status"]["OWNERSHIP_RULE"]=="FUTURE_OUTPUT_PRESENT"
def test_raw_sha_failure_still_fails_closed(tmp_path):
    args,out,entries=case(tmp_path);(ROOT/entries[0]["path"]).write_text("{}",encoding="utf-8");r=run("scripts.gen_enc_b1_repair_11_collector_02.shape_collect",args);assert r.returncode==2 and "SOURCE_SHA256" in r.stderr and {p.name for p in out.iterdir()}=={"FAILURE.json"}
def test_independent_implementations_and_zero_state():
    build();assert "shape_collect" not in (ROOT/"scripts/gen_enc_b1_repair_11_collector_02/verify_collection.py").read_text();p=json.loads((PACKAGE/"provenance.json").read_text());d=json.loads((PACKAGE/"DRAFT.json").read_text());assert p["formal_authority_read_count_during_correction"]==p["formal_run_count"]==0 and d["run_id"] is None and d["final_test_read"] is False
