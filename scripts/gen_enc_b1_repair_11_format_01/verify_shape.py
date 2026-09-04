from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
from typing import Any
import jsonschema
TASK="01a049a7-15ca-79e1-92a2-d3822ba8609d";FUTURE={"OWNERSHIP_CELLS","OWNERSHIP_RULE"}
def canonical(v:Any)->bytes:return (json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
def control(p:Path)->Any:
    raw=p.read_bytes();v=json.loads(raw.decode("utf-8"))
    if raw!=canonical(v):raise ValueError("NON_CANONICAL_CONTROL:"+p.as_posix())
    return v
def authority(p:Path,digest:str)->Any:
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError("SOURCE_SHA256:"+p.as_posix())
    try:return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise ValueError("SOURCE_INVALID_JSON:"+p.as_posix()) from exc
def kind(x:Any)->str:
    if x is None:return "null"
    if type(x)is bool:return "boolean"
    if type(x)is int:return "integer"
    if type(x)is float:return "number"
    if type(x)is str:return "string"
    if type(x)is list:return "array"
    if type(x)is dict:return "object"
    raise ValueError("NON_JSON_NODE")
def at(root:Any,pointer:str)->Any:
    node=root
    for encoded in pointer[1:].split("/") if pointer else []:
        token=encoded.replace("~1","/").replace("~0","~");node=node[int(token)] if type(node)is list else node[token]
    return node
def structure(root:Any)->dict[str,Any]:
    found=[];objmeta=[];arrmeta=[];stack=[("",root)]
    while stack:
        address,node=stack.pop();found.append((address,kind(node)))
        if type(node)is dict:
            names=sorted(node);objmeta.append((address,{"child_count":len(names),"key_names":names}))
            for name in reversed(names):stack.append((address+"/"+name.replace("~","~0").replace("/","~1"),node[name]))
        elif type(node)is list:
            arrmeta.append((address,{"length":len(node),"element_types":sorted({kind(x) for x in node})}))
            for index in range(len(node)-1,-1,-1):stack.append((address+"/"+str(index),node[index]))
    found.sort();body={"available_json_pointer_set":[p for p,_ in found],"node_type_by_pointer":dict(found),"array_shape_by_pointer":dict(sorted(arrmeta)),"object_shape_by_pointer":dict(sorted(objmeta))}
    body["structural_digest"]=hashlib.sha256(canonical({"domain":"R11_FORMAT01_SHAPE_V1","shape":body})).hexdigest();return body
def recompute(repo:Path,m:dict,s:dict,run_id:str,result_path:str)->dict:
    entries=m.get("entries")
    if m.get("task_id")!=TASK or m.get("final_test_read")is not False or type(entries)is not list or len(entries)!=13 or len({e["purpose"] for e in entries})!=13:raise ValueError("EXACT13_BINDING")
    rows=[]
    for e in entries:
        root=at(authority(repo/e["path"],e["sha256"]),e["pointer"]);statuses={}
        for selector in s["selectors"]:
            if selector["purpose"]!=e["purpose"]:continue
            try:selected=at(root,selector["pointer"])
            except (KeyError,IndexError,TypeError,ValueError):
                if selector["id"] in FUTURE:statuses[selector["id"]]="FUTURE_OUTPUT_NOT_AUTHORITY"
                else:raise ValueError("SELECTOR_MISSING:"+selector["id"])
            else:
                if selector["id"] in FUTURE:raise ValueError("FUTURE_OUTPUT_PRESENT_IN_AUTHORITY:"+selector["id"])
                if kind(selected)!=selector["type"]:raise ValueError("SELECTOR_TYPE:"+selector["id"])
                statuses[selector["id"]]="PRESENT_TYPE_VERIFIED"
        rows.append({"purpose":e["purpose"],"source_path":e["path"],"source_sha256":e["sha256"],"source_pointer":e["pointer"],**structure(root),"selector_status":statuses})
    digest=hashlib.sha256(canonical({"domain":"R11_FORMAT01_MAPPING_V1","objects":rows})).hexdigest();return {"schema_version":"gen_enc_b1_r11_format01_mapping_v1","record_kind":"READ_ONLY_AUTHORITY_SHAPE_MAPPING","task_id":TASK,"run_id":run_id,"result_path":result_path,"object_count":13,"objects":rows,"mapping_digest":digest,"final_test_read":False}
def main(argv=None)->int:
    p=argparse.ArgumentParser();p.add_argument("--repo-root",required=True);p.add_argument("--authority-manifest",required=True);p.add_argument("--selector-contract",required=True);p.add_argument("--schema-root",required=True);p.add_argument("--run-id",required=True);p.add_argument("--result-dir",required=True);p.add_argument("--technical-mirror",action="store_true");a=p.parse_args(argv);repo=Path(a.repo_root).resolve();out=(repo/a.result_dir).resolve()
    try:
        if len(a.run_id)!=64 or any(c not in "0123456789abcdef" for c in a.run_id) or out.name!=a.run_id:raise ValueError("RUN_PATH_BINDING")
        sr=repo/a.schema_root;m=control(repo/a.authority_manifest);s=control(repo/a.selector_contract)
        jsonschema.Draft202012Validator(control(sr/"authority_manifest.schema.json")).validate(m);jsonschema.Draft202012Validator(control(sr/"selector_contract.schema.json")).validate(s)
        if bool(m["technical_mirror"])!=a.technical_mirror:raise ValueError("IDENTITY_CLASS")
        expected=control(out/"driver_shape_mapping.json");jsonschema.Draft202012Validator(control(sr/"shape_mapping.schema.json")).validate(expected);actual=recompute(repo,m,s,a.run_id,Path(a.result_dir).as_posix())
        if expected!=actual:raise ValueError("INDEPENDENT_MAPPING_MISMATCH")
        if {p.name for p in out.iterdir()}!={"driver_shape_mapping.json","provenance.json"}:raise ValueError("UNEXPECTED_RESULT_FILE")
        report={"schema_version":"gen_enc_b1_r11_format01_verification_v1","record_kind":"INDEPENDENT_SHAPE_VERIFICATION","task_id":TASK,"run_id":a.run_id,"result_path":Path(a.result_dir).as_posix(),"verdict":"PASS","authority_read_count":13,"cumulative_authority_read_count":26,"mapping_digest":actual["mapping_digest"],"object_count":13,"final_test_read":False};jsonschema.Draft202012Validator(control(sr/"verification.schema.json")).validate(report);(out/"independent_shape_verification.json").write_bytes(canonical(report));return 0
    except Exception as exc:
        out.mkdir(parents=True,exist_ok=True);(out/"FAILURE.json").write_bytes(canonical({"record_kind":"FAILURE_LOG","task_id":TASK,"stage":"INDEPENDENT_VERIFICATION","error":f"{type(exc).__name__}:{exc}","final_test_read":False}));print("FAIL_CLOSED:"+str(exc),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
