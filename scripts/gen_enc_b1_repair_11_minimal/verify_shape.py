from __future__ import annotations

import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any
import jsonschema

TASK_ID="01a049a7-15ca-79e1-92a2-d3822ba8609d"; FUTURE={"OWNERSHIP_CELLS","OWNERSHIP_RULE"}
def canonical(v:Any)->bytes:return (json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
def load(p:Path)->Any:
    raw=p.read_bytes(); value=json.loads(raw.decode())
    if raw!=canonical(value):raise ValueError("NON_CANONICAL:"+p.as_posix())
    return value
def validate(value:Any,root:Path,name:str)->None:jsonschema.Draft202012Validator(load(root/name)).validate(value)
def typ(v:Any)->str:
    if v is None:return "null"
    if type(v) is bool:return "boolean"
    if type(v) is int:return "integer"
    if type(v) is float:return "number"
    if type(v) is str:return "string"
    if type(v) is list:return "array"
    if type(v) is dict:return "object"
    raise ValueError("NON_JSON")
def resolve(root:Any,pointer:str)->Any:
    cur=root
    for encoded in pointer[1:].split("/") if pointer else []:
        token=encoded.replace("~1","/").replace("~0","~");cur=cur[int(token)] if type(cur) is list else cur[token]
    return cur
def projection(root:Any)->dict[str,Any]:
    found=[]; objs=[]; arrs=[]; todo=[("",root)]
    while todo:
        addr,node=todo.pop(); found.append((addr,typ(node)))
        if type(node) is dict:
            names=sorted(node);objs.append((addr,{"child_count":len(names),"key_names":names}))
            for name in reversed(names):todo.append((addr+"/"+name.replace("~","~0").replace("/","~1"),node[name]))
        elif type(node) is list:
            arrs.append((addr,{"length":len(node),"element_types":sorted({typ(x) for x in node})}))
            for i in range(len(node)-1,-1,-1):todo.append((addr+"/"+str(i),node[i]))
    found.sort(); body={"available_json_pointer_set":[x for x,_ in found],"node_type_by_pointer":dict(found),"array_shape_by_pointer":dict(sorted(arrs)),"object_shape_by_pointer":dict(sorted(objs))}
    body["structural_digest"]=hashlib.sha256(canonical({"domain":"R11_MINIMAL_SHAPE_V1","shape":body})).hexdigest();return body
def rebuild(repo:Path,manifest:dict,selectors:dict,run_id:str,result_path:str)->dict:
    entries=manifest.get("entries")
    if manifest.get("task_id")!=TASK_ID or manifest.get("final_test_read") is not False or type(entries) is not list or len(entries)!=13 or len({e["purpose"] for e in entries})!=13:raise ValueError("MANIFEST_BINDING")
    rows=[]
    for e in entries:
        raw=(repo/e["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=e["sha256"]:raise ValueError("SOURCE_SHA256:"+e["purpose"])
        obj=json.loads(raw.decode())
        if raw!=canonical(obj):raise ValueError("SOURCE_NON_CANONICAL:"+e["purpose"])
        root=resolve(obj,e["pointer"]);status={}
        for s in selectors["selectors"]:
            if s["purpose"]!=e["purpose"]:continue
            try:value=resolve(root,s["pointer"])
            except (KeyError,IndexError,TypeError,ValueError):
                if s["id"] in FUTURE:status[s["id"]]="FUTURE_OUTPUT_NOT_AUTHORITY"
                else:raise ValueError("SELECTOR_MISSING:"+s["id"])
            else:
                if s["id"] in FUTURE:raise ValueError("FUTURE_OUTPUT_PRESENT_IN_AUTHORITY:"+s["id"])
                if typ(value)!=s["type"]:raise ValueError("SELECTOR_TYPE:"+s["id"])
                status[s["id"]]="PRESENT_TYPE_VERIFIED"
        rows.append({"purpose":e["purpose"],"source_path":e["path"],"source_sha256":e["sha256"],"source_pointer":e["pointer"],**projection(root),"selector_status":status})
    digest=hashlib.sha256(canonical({"domain":"R11_MINIMAL_MAPPING_V1","objects":rows})).hexdigest()
    return {"schema_version":"gen_enc_b1_r11_minimal_mapping_v1","record_kind":"READ_ONLY_AUTHORITY_SHAPE_MAPPING","task_id":TASK_ID,"run_id":run_id,"result_path":result_path,"final_test_read":False,"object_count":13,"objects":rows,"mapping_digest":digest}
def main(argv=None)->int:
    p=argparse.ArgumentParser();p.add_argument("--repo-root",required=True);p.add_argument("--authority-manifest",required=True);p.add_argument("--selector-contract",required=True);p.add_argument("--schema-root",required=True);p.add_argument("--run-id",required=True);p.add_argument("--result-dir",required=True);p.add_argument("--technical-mirror",action="store_true");a=p.parse_args(argv)
    repo=Path(a.repo_root).resolve();out=(repo/a.result_dir).resolve()
    try:
        if len(a.run_id)!=64 or any(c not in "0123456789abcdef" for c in a.run_id) or out.name!=a.run_id:raise ValueError("RUN_PATH_BINDING")
        manifest=load(repo/a.authority_manifest);selectors=load(repo/a.selector_contract);schema_root=repo/a.schema_root
        validate(manifest,schema_root,"authority_manifest.schema.json");validate(selectors,schema_root,"selector_contract.schema.json")
        if bool(manifest.get("technical_mirror"))!=a.technical_mirror:raise ValueError("IDENTITY_CLASS")
        expected=load(out/"driver_shape_mapping.json");validate(expected,schema_root,"shape_mapping.schema.json");actual=rebuild(repo,manifest,selectors,a.run_id,Path(a.result_dir).as_posix())
        if actual!=expected:raise ValueError("INDEPENDENT_MAPPING_MISMATCH")
        allowed={"driver_shape_mapping.json","provenance.json"}
        if {x.name for x in out.iterdir()}!=allowed:raise ValueError("UNEXPECTED_RESULT_FILE")
        report={"schema_version":"gen_enc_b1_r11_minimal_verification_v1","record_kind":"INDEPENDENT_SHAPE_VERIFICATION","task_id":TASK_ID,"run_id":a.run_id,"result_path":Path(a.result_dir).as_posix(),"verdict":"PASS","authority_read_count":13,"cumulative_authority_read_count":26,"mapping_digest":actual["mapping_digest"],"object_count":13,"final_test_read":False}
        validate(report,schema_root,"verification.schema.json");(out/"independent_shape_verification.json").write_bytes(canonical(report));return 0
    except Exception as exc:
        failure={"schema_version":"gen_enc_b1_r11_minimal_failure_v1","record_kind":"FAILURE_LOG","task_id":TASK_ID,"stage":"INDEPENDENT_VERIFICATION","error":f"{type(exc).__name__}:{exc}","final_test_read":False}
        out.mkdir(parents=True,exist_ok=True);(out/"FAILURE.json").write_bytes(canonical(failure));print("FAIL_CLOSED:"+str(exc),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
