from __future__ import annotations

import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any
import jsonschema

TASK_ID = "01a049a7-15ca-79e1-92a2-d3822ba8609d"
FUTURE = {"OWNERSHIP_CELLS", "OWNERSHIP_RULE"}

def canonical(v: Any) -> bytes:
    return (json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()

def load(path: Path) -> Any:
    raw = path.read_bytes(); value = json.loads(raw.decode())
    if raw != canonical(value): raise ValueError("NON_CANONICAL:" + path.as_posix())
    return value

def validate(value: Any, schema_root: Path, name: str) -> None:
    jsonschema.Draft202012Validator(load(schema_root / name)).validate(value)

def kind(v: Any) -> str:
    if v is None: return "null"
    if type(v) is bool: return "boolean"
    if type(v) is int: return "integer"
    if type(v) is float: return "number"
    if type(v) is str: return "string"
    if type(v) is list: return "array"
    if type(v) is dict: return "object"
    raise ValueError("NON_JSON")

def get(root: Any, pointer: str) -> Any:
    cur = root
    for raw in pointer.split("/")[1:] if pointer else []:
        token = raw.replace("~1", "/").replace("~0", "~")
        cur = cur[int(token)] if type(cur) is list else cur[token]
    return cur

def shape(root: Any) -> dict[str, Any]:
    nodes: dict[str, str] = {}; objects = {}; arrays = {}; stack = [("", root)]
    while stack:
        ptr, node = stack.pop(); nodes[ptr] = kind(node)
        if type(node) is dict:
            keys = sorted(node); objects[ptr] = {"child_count": len(keys), "key_names": keys}
            for key in reversed(keys): stack.append((ptr + "/" + key.replace("~", "~0").replace("/", "~1"), node[key]))
        elif type(node) is list:
            arrays[ptr] = {"length": len(node), "element_types": sorted({kind(x) for x in node})}
            for i in range(len(node) - 1, -1, -1): stack.append((ptr + "/" + str(i), node[i]))
    body = {"available_json_pointer_set": sorted(nodes), "node_type_by_pointer": dict(sorted(nodes.items())),
            "array_shape_by_pointer": dict(sorted(arrays.items())), "object_shape_by_pointer": dict(sorted(objects.items()))}
    body["structural_digest"] = hashlib.sha256(canonical({"domain":"R11_MINIMAL_SHAPE_V1","shape":body})).hexdigest()
    return body

def inspect(repo: Path, manifest: dict, selectors: dict, run_id: str, result_path: str) -> dict:
    entries = manifest.get("entries")
    if manifest.get("task_id") != TASK_ID or manifest.get("final_test_read") is not False or not isinstance(entries, list) or len(entries) != 13 or len({x["purpose"] for x in entries}) != 13:
        raise ValueError("MANIFEST_BINDING")
    rows=[]
    for entry in entries:
        path=repo/entry["path"]; raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry["sha256"]: raise ValueError("SOURCE_SHA256:"+entry["purpose"])
        value=json.loads(raw.decode())
        if raw!=canonical(value): raise ValueError("SOURCE_NON_CANONICAL:"+entry["purpose"])
        selected=get(value,entry["pointer"])
        statuses={}
        for sel in selectors["selectors"]:
            if sel["purpose"] != entry["purpose"]: continue
            try: node=get(selected,sel["pointer"])
            except (KeyError, IndexError, TypeError, ValueError):
                if sel["id"] in FUTURE: statuses[sel["id"]]="FUTURE_OUTPUT_NOT_AUTHORITY"
                else: raise ValueError("SELECTOR_MISSING:"+sel["id"])
            else:
                if sel["id"] in FUTURE: raise ValueError("FUTURE_OUTPUT_PRESENT_IN_AUTHORITY:"+sel["id"])
                if kind(node)!=sel["type"]: raise ValueError("SELECTOR_TYPE:"+sel["id"])
                statuses[sel["id"]]="PRESENT_TYPE_VERIFIED"
        rows.append({"purpose":entry["purpose"],"source_path":entry["path"],"source_sha256":entry["sha256"],"source_pointer":entry["pointer"],**shape(selected),"selector_status":statuses})
    digest=hashlib.sha256(canonical({"domain":"R11_MINIMAL_MAPPING_V1","objects":rows})).hexdigest()
    return {"schema_version":"gen_enc_b1_r11_minimal_mapping_v1","record_kind":"READ_ONLY_AUTHORITY_SHAPE_MAPPING","task_id":TASK_ID,"run_id":run_id,"result_path":result_path,"final_test_read":False,"object_count":13,"objects":rows,"mapping_digest":digest}

def main(argv=None) -> int:
    p=argparse.ArgumentParser(); p.add_argument("--repo-root",required=True); p.add_argument("--authority-manifest",required=True); p.add_argument("--selector-contract",required=True); p.add_argument("--schema-root",required=True); p.add_argument("--run-id",required=True); p.add_argument("--result-dir",required=True); p.add_argument("--technical-mirror",action="store_true")
    a=p.parse_args(argv); repo=Path(a.repo_root).resolve(); out=(repo/a.result_dir).resolve()
    if out.exists(): print("FAIL_CLOSED:RESULT_EXISTS",file=sys.stderr); return 2
    try:
        if len(a.run_id)!=64 or any(c not in "0123456789abcdef" for c in a.run_id) or out.name!=a.run_id: raise ValueError("RUN_PATH_BINDING")
        manifest=load(repo/a.authority_manifest); selectors=load(repo/a.selector_contract); schema_root=repo/a.schema_root
        validate(manifest,schema_root,"authority_manifest.schema.json"); validate(selectors,schema_root,"selector_contract.schema.json")
        if bool(manifest.get("technical_mirror")) != a.technical_mirror: raise ValueError("IDENTITY_CLASS")
        result=inspect(repo,manifest,selectors,a.run_id,Path(a.result_dir).as_posix()); out.mkdir(parents=True)
        validate(result,schema_root,"shape_mapping.schema.json"); (out/"driver_shape_mapping.json").write_bytes(canonical(result))
        prov={"schema_version":"gen_enc_b1_r11_minimal_provenance_v1","record_kind":"TECHNICAL_FIXTURE_PROVENANCE" if a.technical_mirror else "FORMAL_READ_ONLY_PROVENANCE","task_id":TASK_ID,"run_id":a.run_id,"result_path":Path(a.result_dir).as_posix(),"stage":"SHAPE_INSPECTION_COMPLETE","authority_read_count":13,"result_files":["driver_shape_mapping.json"],"final_test_read":False}
        (out/"provenance.json").write_bytes(canonical(prov)); return 0
    except Exception as exc:
        out.mkdir(parents=True,exist_ok=True); failure={"schema_version":"gen_enc_b1_r11_minimal_failure_v1","record_kind":"FAILURE_LOG","task_id":TASK_ID,"stage":"SHAPE_INSPECTION","error":f"{type(exc).__name__}:{exc}","final_test_read":False}
        (out/"FAILURE.json").write_bytes(canonical(failure)); print("FAIL_CLOSED:"+str(exc),file=sys.stderr); return 2

if __name__ == "__main__": raise SystemExit(main())
