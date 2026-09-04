from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
from typing import Any
import jsonschema
TASK="01a049a7-15ca-79e1-92a2-d3822ba8609d";FUTURE={"OWNERSHIP_CELLS","OWNERSHIP_RULE"}
def canonical(v:Any)->bytes:return (json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
def canonical_load(p:Path)->Any:
    raw=p.read_bytes();v=json.loads(raw.decode("utf-8"))
    if raw!=canonical(v):raise ValueError("NON_CANONICAL_CONTROL:"+p.as_posix())
    return v
def source_load(p:Path,expected:str)->Any:
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError("SOURCE_SHA256:"+p.as_posix())
    try:return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise ValueError("SOURCE_INVALID_JSON:"+p.as_posix()) from exc
def typ(v:Any)->str:
    return "null" if v is None else "boolean" if type(v)is bool else "integer" if type(v)is int else "number" if type(v)is float else "string" if type(v)is str else "array" if type(v)is list else "object" if type(v)is dict else (_ for _ in ()).throw(ValueError("NON_JSON_NODE"))
def resolve(root:Any,pointer:str)->Any:
    cur=root
    for raw in pointer[1:].split("/") if pointer else []:
        key=raw.replace("~1","/").replace("~0","~");cur=cur[int(key)] if type(cur)is list else cur[key]
    return cur
def shape(root:Any)->dict[str,Any]:
    nodes={};objects={};arrays={};todo=[("",root)]
    while todo:
        ptr,node=todo.pop();nodes[ptr]=typ(node)
        if type(node)is dict:
            keys=sorted(node);objects[ptr]={"child_count":len(keys),"key_names":keys}
            for key in reversed(keys):todo.append((ptr+"/"+key.replace("~","~0").replace("/","~1"),node[key]))
        elif type(node)is list:
            arrays[ptr]={"length":len(node),"element_types":sorted({typ(x) for x in node})}
            for i in range(len(node)-1,-1,-1):todo.append((ptr+"/"+str(i),node[i]))
    body={"available_json_pointer_set":sorted(nodes),"node_type_by_pointer":dict(sorted(nodes.items())),"array_shape_by_pointer":dict(sorted(arrays.items())),"object_shape_by_pointer":dict(sorted(objects.items()))}
    body["structural_digest"]=hashlib.sha256(canonical({"domain":"R11_FORMAT01_SHAPE_V1","shape":body})).hexdigest();return body
def inspect(repo:Path,manifest:dict,selectors:dict,run_id:str,result_path:str)->dict:
    entries=manifest.get("entries")
    if manifest.get("task_id")!=TASK or manifest.get("final_test_read")is not False or type(entries)is not list or len(entries)!=13 or len({e["purpose"] for e in entries})!=13:raise ValueError("EXACT13_BINDING")
    rows=[]
    for e in entries:
        root=resolve(source_load(repo/e["path"],e["sha256"]),e["pointer"]);statuses={}
        for s in selectors["selectors"]:
            if s["purpose"]!=e["purpose"]:continue
            try:value=resolve(root,s["pointer"])
            except (KeyError,IndexError,TypeError,ValueError):
                if s["id"] in FUTURE:statuses[s["id"]]="FUTURE_OUTPUT_NOT_AUTHORITY"
                else:raise ValueError("SELECTOR_MISSING:"+s["id"])
            else:
                if s["id"] in FUTURE:raise ValueError("FUTURE_OUTPUT_PRESENT_IN_AUTHORITY:"+s["id"])
                if typ(value)!=s["type"]:raise ValueError("SELECTOR_TYPE:"+s["id"])
                statuses[s["id"]]="PRESENT_TYPE_VERIFIED"
        rows.append({"purpose":e["purpose"],"source_path":e["path"],"source_sha256":e["sha256"],"source_pointer":e["pointer"],**shape(root),"selector_status":statuses})
    digest=hashlib.sha256(canonical({"domain":"R11_FORMAT01_MAPPING_V1","objects":rows})).hexdigest()
    return {"schema_version":"gen_enc_b1_r11_format01_mapping_v1","record_kind":"READ_ONLY_AUTHORITY_SHAPE_MAPPING","task_id":TASK,"run_id":run_id,"result_path":result_path,"object_count":13,"objects":rows,"mapping_digest":digest,"final_test_read":False}
def main(argv=None)->int:
    p=argparse.ArgumentParser();p.add_argument("--repo-root",required=True);p.add_argument("--authority-manifest",required=True);p.add_argument("--selector-contract",required=True);p.add_argument("--schema-root",required=True);p.add_argument("--run-id",required=True);p.add_argument("--result-dir",required=True);p.add_argument("--technical-mirror",action="store_true");a=p.parse_args(argv)
    repo=Path(a.repo_root).resolve();out=(repo/a.result_dir).resolve()
    try:
        if out.exists():raise ValueError("RESULT_EXISTS")
        if len(a.run_id)!=64 or any(c not in "0123456789abcdef" for c in a.run_id) or out.name!=a.run_id:raise ValueError("RUN_PATH_BINDING")
        sr=repo/a.schema_root;m=canonical_load(repo/a.authority_manifest);s=canonical_load(repo/a.selector_contract)
        jsonschema.Draft202012Validator(canonical_load(sr/"authority_manifest.schema.json")).validate(m);jsonschema.Draft202012Validator(canonical_load(sr/"selector_contract.schema.json")).validate(s)
        if bool(m["technical_mirror"])!=a.technical_mirror:raise ValueError("IDENTITY_CLASS")
        result=inspect(repo,m,s,a.run_id,Path(a.result_dir).as_posix());jsonschema.Draft202012Validator(canonical_load(sr/"shape_mapping.schema.json")).validate(result)
        out.mkdir(parents=True);(out/"driver_shape_mapping.json").write_bytes(canonical(result));(out/"provenance.json").write_bytes(canonical({"record_kind":"TECHNICAL_FIXTURE_PROVENANCE" if a.technical_mirror else "FORMAL_READ_ONLY_PROVENANCE","task_id":TASK,"run_id":a.run_id,"result_path":Path(a.result_dir).as_posix(),"authority_read_count":13,"input_rule":"RAW_SHA256_THEN_STANDARD_JSON_PARSE","final_test_read":False}));return 0
    except Exception as exc:
        out.mkdir(parents=True,exist_ok=True);(out/"FAILURE.json").write_bytes(canonical({"record_kind":"FAILURE_LOG","task_id":TASK,"stage":"SHAPE_INSPECTION","error":f"{type(exc).__name__}:{exc}","final_test_read":False}));print("FAIL_CLOSED:"+str(exc),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
