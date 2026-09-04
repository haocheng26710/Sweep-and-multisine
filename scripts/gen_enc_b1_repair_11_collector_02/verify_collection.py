from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
from typing import Any
import jsonschema
TASK="01a049a7-15ca-79e1-92a2-d3822ba8609d";FUTURE_IDS=("OWNERSHIP_CELLS","OWNERSHIP_RULE")
def canonical(x:Any)->bytes:return (json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode()
def sealed(p:Path)->Any:
    data=p.read_bytes();parsed=json.loads(data.decode("utf-8"))
    if data!=canonical(parsed):raise ValueError("NON_CANONICAL_CONTROL:"+p.as_posix())
    return parsed
def historical(p:Path,want:str)->Any:
    data=p.read_bytes()
    if hashlib.sha256(data).hexdigest()!=want:raise ValueError("SOURCE_SHA256:"+p.as_posix())
    try:return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise ValueError("SOURCE_INVALID_JSON:"+p.as_posix()) from exc
def node_type(x:Any)->str:
    if x is None:return "null"
    table={bool:"boolean",int:"integer",float:"number",str:"string",list:"array",dict:"object"}
    if type(x)not in table:raise ValueError("NON_JSON_NODE")
    return table[type(x)]
def pointer(root:Any,address:str)->Any:
    cursor=root
    for encoded in address.split("/")[1:] if address else []:
        part=encoded.replace("~1","/").replace("~0","~");cursor=cursor[int(part)] if type(cursor)is list else cursor[part]
    return cursor
def inventory(root:Any)->dict[str,Any]:
    typed=[];object_rows=[];array_rows=[];todo=[("",root)]
    while todo:
        address,value=todo.pop();typed.append((address,node_type(value)))
        if type(value)is dict:
            names=sorted(value);object_rows.append((address,{"child_count":len(names),"key_names":names}))
            for name in reversed(names):todo.append((address+"/"+name.replace("~","~0").replace("/","~1"),value[name]))
        elif type(value)is list:
            array_rows.append((address,{"length":len(value),"element_types":sorted({node_type(v) for v in value})}))
            for index in range(len(value)-1,-1,-1):todo.append((address+"/"+str(index),value[index]))
    typed.sort();return {"all_json_pointers":[p for p,_ in typed],"type_by_pointer":dict(typed),"array_shape_by_pointer":dict(sorted(array_rows)),"object_shape_by_pointer":dict(sorted(object_rows))}
def diagnose(root:Any,s:dict)->str:
    try:value=pointer(root,s["pointer"])
    except (KeyError,IndexError,TypeError,ValueError):return "FUTURE_OUTPUT_ABSENT" if s["id"] in FUTURE_IDS else "MISSING"
    if s["id"] in FUTURE_IDS:return "FUTURE_OUTPUT_PRESENT"
    return "PRESENT_MATCH" if node_type(value)==s["type"] else "PRESENT_TYPE_MISMATCH"
def rebuild(repo:Path,manifest:dict,contract:dict,run_id:str,result_path:str)->dict:
    entries=manifest.get("entries")
    if manifest.get("task_id")!=TASK or manifest.get("final_test_read")is not False or type(entries)is not list or len(entries)!=13 or len({e["purpose"] for e in entries})!=13:raise ValueError("EXACT13_BINDING")
    objects=[];statuses={}
    for entry in entries:
        root=pointer(historical(repo/entry["path"],entry["sha256"]),entry["pointer"]);local={s["id"]:diagnose(root,s) for s in contract["selectors"] if s["purpose"]==entry["purpose"]};statuses.update(local);item=inventory(root);item["structural_digest"]=hashlib.sha256(canonical({"domain":"R11_COLLECTOR02_SHAPE_V1","shape":item})).hexdigest();objects.append({"purpose":entry["purpose"],"source_path":entry["path"],"source_sha256":entry["sha256"],"source_pointer":entry["pointer"],**item,"selector_status":local})
    if len(statuses)!=31:raise ValueError("SELECTOR_CARDINALITY")
    digest=hashlib.sha256(canonical({"domain":"R11_COLLECTOR02_MAPPING_V1","objects":objects,"selector_status":statuses})).hexdigest();return {"schema_version":"gen_enc_b1_r11_collector02_mapping_v1","record_kind":"COMPLETE_READ_ONLY_AUTHORITY_SHAPE_MAPPING","task_id":TASK,"run_id":run_id,"result_path":result_path,"object_count":13,"selector_count":31,"selector_status":dict(sorted(statuses.items())),"objects":objects,"mapping_digest":digest,"final_test_read":False}
def main(argv=None)->int:
    p=argparse.ArgumentParser();p.add_argument("--repo-root",required=True);p.add_argument("--authority-manifest",required=True);p.add_argument("--selector-contract",required=True);p.add_argument("--schema-root",required=True);p.add_argument("--run-id",required=True);p.add_argument("--result-dir",required=True);p.add_argument("--technical-mirror",action="store_true");a=p.parse_args(argv);repo=Path(a.repo_root).resolve();out=(repo/a.result_dir).resolve()
    try:
        if len(a.run_id)!=64 or any(c not in "0123456789abcdef" for c in a.run_id) or out.name!=a.run_id:raise ValueError("RUN_PATH_BINDING")
        sr=repo/a.schema_root;m=sealed(repo/a.authority_manifest);s=sealed(repo/a.selector_contract);jsonschema.Draft202012Validator(sealed(sr/"authority_manifest.schema.json")).validate(m);jsonschema.Draft202012Validator(sealed(sr/"selector_contract.schema.json")).validate(s)
        if bool(m["technical_mirror"])!=a.technical_mirror:raise ValueError("IDENTITY_CLASS")
        expected=sealed(out/"shape_mapping.json");jsonschema.Draft202012Validator(sealed(sr/"shape_mapping.schema.json")).validate(expected);actual=rebuild(repo,m,s,a.run_id,Path(a.result_dir).as_posix())
        if actual!=expected:raise ValueError("INDEPENDENT_MAPPING_MISMATCH")
        if {p.name for p in out.iterdir()}!={"shape_mapping.json","provenance.json"}:raise ValueError("UNEXPECTED_RESULT_FILE")
        report={"schema_version":"gen_enc_b1_r11_collector02_verification_v1","record_kind":"INDEPENDENT_COMPLETE_SHAPE_VERIFICATION","task_id":TASK,"run_id":a.run_id,"result_path":Path(a.result_dir).as_posix(),"verdict":"PASS","object_count":13,"selector_count":31,"authority_read_count":13,"cumulative_authority_read_count":26,"mapping_digest":actual["mapping_digest"],"final_test_read":False};jsonschema.Draft202012Validator(sealed(sr/"verification.schema.json")).validate(report);(out/"independent_verification.json").write_bytes(canonical(report));return 0
    except Exception as exc:
        out.mkdir(parents=True,exist_ok=True);(out/"FAILURE.json").write_bytes(canonical({"record_kind":"FAILURE_LOG","task_id":TASK,"stage":"INDEPENDENT_VERIFICATION","error":f"{type(exc).__name__}:{exc}","final_test_read":False}));print("FAIL_CLOSED:"+str(exc),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
