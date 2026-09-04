from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
from typing import Any
import jsonschema
TASK="01a049a7-15ca-79e1-92a2-d3822ba8609d";FUTURE={"OWNERSHIP_CELLS","OWNERSHIP_RULE"}
def canon(v:Any)->bytes:return (json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
def control(p:Path)->Any:
    raw=p.read_bytes();v=json.loads(raw.decode())
    if raw!=canon(v):raise ValueError("NON_CANONICAL_CONTROL:"+p.as_posix())
    return v
def source(p:Path,digest:str)->Any:
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError("SOURCE_SHA256:"+p.as_posix())
    try:return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise ValueError("SOURCE_INVALID_JSON:"+p.as_posix()) from exc
def kind(v:Any)->str:
    if v is None:return "null"
    if type(v)is bool:return "boolean"
    if type(v)is int:return "integer"
    if type(v)is float:return "number"
    if type(v)is str:return "string"
    if type(v)is list:return "array"
    if type(v)is dict:return "object"
    raise ValueError("NON_JSON_NODE")
def resolve(root:Any,pointer:str)->Any:
    cur=root
    for raw in pointer[1:].split("/") if pointer else []:
        key=raw.replace("~1","/").replace("~0","~");cur=cur[int(key)] if type(cur)is list else cur[key]
    return cur
def shape(root:Any)->dict[str,Any]:
    nodes={};objects={};arrays={};stack=[("",root)]
    while stack:
        ptr,node=stack.pop();nodes[ptr]=kind(node)
        if type(node)is dict:
            keys=sorted(node);objects[ptr]={"child_count":len(keys),"key_names":keys}
            for key in reversed(keys):stack.append((ptr+"/"+key.replace("~","~0").replace("/","~1"),node[key]))
        elif type(node)is list:
            arrays[ptr]={"length":len(node),"element_types":sorted({kind(x) for x in node})}
            for i in range(len(node)-1,-1,-1):stack.append((ptr+"/"+str(i),node[i]))
    return {"all_json_pointers":sorted(nodes),"type_by_pointer":dict(sorted(nodes.items())),"array_shape_by_pointer":dict(sorted(arrays.items())),"object_shape_by_pointer":dict(sorted(objects.items()))}
def status(root:Any,selector:dict)->str:
    try:value=resolve(root,selector["pointer"])
    except (KeyError,IndexError,TypeError,ValueError):return "FUTURE_OUTPUT_ABSENT" if selector["id"] in FUTURE else "MISSING"
    if selector["id"] in FUTURE:return "FUTURE_OUTPUT_PRESENT"
    return "PRESENT_MATCH" if kind(value)==selector["type"] else "PRESENT_TYPE_MISMATCH"
def collect(repo:Path,m:dict,s:dict,run_id:str,result_path:str)->dict:
    entries=m.get("entries")
    if m.get("task_id")!=TASK or m.get("final_test_read")is not False or type(entries)is not list or len(entries)!=13 or len({e["purpose"] for e in entries})!=13:raise ValueError("EXACT13_BINDING")
    rows=[];all_status={}
    for entry in entries:
        root=resolve(source(repo/entry["path"],entry["sha256"]),entry["pointer"]);local={x["id"]:status(root,x) for x in s["selectors"] if x["purpose"]==entry["purpose"]};all_status.update(local)
        structural=shape(root);structural["structural_digest"]=hashlib.sha256(canon({"domain":"R11_COLLECTOR02_SHAPE_V1","shape":structural})).hexdigest()
        rows.append({"purpose":entry["purpose"],"source_path":entry["path"],"source_sha256":entry["sha256"],"source_pointer":entry["pointer"],**structural,"selector_status":local})
    if len(all_status)!=31:raise ValueError("SELECTOR_CARDINALITY")
    digest=hashlib.sha256(canon({"domain":"R11_COLLECTOR02_MAPPING_V1","objects":rows,"selector_status":all_status})).hexdigest()
    return {"schema_version":"gen_enc_b1_r11_collector02_mapping_v1","record_kind":"COMPLETE_READ_ONLY_AUTHORITY_SHAPE_MAPPING","task_id":TASK,"run_id":run_id,"result_path":result_path,"object_count":13,"selector_count":31,"selector_status":dict(sorted(all_status.items())),"objects":rows,"mapping_digest":digest,"final_test_read":False}
def main(argv=None)->int:
    p=argparse.ArgumentParser();p.add_argument("--repo-root",required=True);p.add_argument("--authority-manifest",required=True);p.add_argument("--selector-contract",required=True);p.add_argument("--schema-root",required=True);p.add_argument("--run-id",required=True);p.add_argument("--result-dir",required=True);p.add_argument("--technical-mirror",action="store_true");a=p.parse_args(argv);repo=Path(a.repo_root).resolve();out=(repo/a.result_dir).resolve()
    try:
        if out.exists():raise ValueError("RESULT_EXISTS")
        if len(a.run_id)!=64 or any(c not in "0123456789abcdef" for c in a.run_id) or out.name!=a.run_id:raise ValueError("RUN_PATH_BINDING")
        sr=repo/a.schema_root;m=control(repo/a.authority_manifest);s=control(repo/a.selector_contract);jsonschema.Draft202012Validator(control(sr/"authority_manifest.schema.json")).validate(m);jsonschema.Draft202012Validator(control(sr/"selector_contract.schema.json")).validate(s)
        if bool(m["technical_mirror"])!=a.technical_mirror:raise ValueError("IDENTITY_CLASS")
        result=collect(repo,m,s,a.run_id,Path(a.result_dir).as_posix());jsonschema.Draft202012Validator(control(sr/"shape_mapping.schema.json")).validate(result);out.mkdir(parents=True);(out/"shape_mapping.json").write_bytes(canon(result));(out/"provenance.json").write_bytes(canon({"record_kind":"TECHNICAL_FIXTURE_PROVENANCE" if a.technical_mirror else "FORMAL_READ_ONLY_PROVENANCE","task_id":TASK,"run_id":a.run_id,"authority_read_count":13,"input_rule":"RAW_SHA256_THEN_STANDARD_JSON_PARSE","selector_diagnostics_complete":True,"final_test_read":False}));return 0
    except Exception as exc:
        out.mkdir(parents=True,exist_ok=True);(out/"FAILURE.json").write_bytes(canon({"record_kind":"FAILURE_LOG","task_id":TASK,"stage":"SHAPE_COLLECTION","error":f"{type(exc).__name__}:{exc}","final_test_read":False}));print("FAIL_CLOSED:"+str(exc),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
