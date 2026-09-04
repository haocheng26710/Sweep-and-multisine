"""Build strict repair-03 lifecycle and typed-CAD schemas."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from scripts.gen_enc_b1_repair_03 import cad_projection_driver as cad
from scripts.gen_enc_b1_repair_03 import formal_driver as driver
from tests.helpers.gen_enc_b1_repair_03_fixture import contract, entries, objects

REPO=Path(__file__).resolve().parents[2];OLD=REPO/"schemas/gen_enc/b1_repair_02";OUT=REPO/"schemas/gen_enc/b1_repair_03"


def infer(values:Sequence[Any])->dict[str,Any]:
    kinds={"boolean" if isinstance(x,bool) else "object" if isinstance(x,dict) else "array" if isinstance(x,list) else "number" if isinstance(x,(int,float)) else "string" if isinstance(x,str) else "null" for x in values}
    if len(kinds)!=1:return {"anyOf":[infer([x for x in values if ("boolean" if isinstance(x,bool) else "object" if isinstance(x,dict) else "array" if isinstance(x,list) else "number" if isinstance(x,(int,float)) else "string" if isinstance(x,str) else "null")==kind]) for kind in sorted(kinds)]}
    kind=next(iter(kinds))
    if kind=="object":
        keys=list(values[0]);
        if any(list(x)!=keys for x in values):
            groups={tuple(x):[] for x in values}
            for x in values:groups[tuple(x)].append(x)
            return {"oneOf":[infer(group) for group in groups.values()]}
        return {"type":"object","required":keys,"properties":{k:infer([x[k] for x in values]) for k in keys},"additionalProperties":False}
    if kind=="array":
        children=[y for x in values for y in x];lengths=[len(x) for x in values]
        return {"type":"array","items":infer(children) if children else False,"minItems":min(lengths),"maxItems":max(lengths)}
    return {"type":kind}


def add_binding(schema:dict[str,Any])->None:
    props=schema["properties"]
    additions={"projection_contract_path":{"const":driver.PROJECTION_PATH},"projection_contract_sha256":{"type":"string","pattern":"^[0-9a-f]{64}$"},"dependency_matrix_path":{"const":driver.DEPENDENCY_PATH},"dependency_matrix_sha256":{"type":"string","pattern":"^[0-9a-f]{64}$"},"dependency_structure_sha256":{"type":"string","pattern":"^[0-9a-f]{64}$"}}
    props.update(additions)
    for key in additions:
        if key not in schema["required"]:schema["required"].append(key)
    props["mode"]={"const":driver.MODE}
    if "mode" not in schema["required"]:schema["required"].append("mode")


def main()->None:
    OUT.mkdir(parents=True,exist_ok=True);projected=cad.project(objects(),entries(),contract());binding={"projection_contract_sha256":projected["projection_contract_sha256"],"dependency_matrix_sha256":"d"*64,"dependency_structure_sha256":projected["dependency_matrix_sha256"]};members=driver.members_from_authority(objects(),entries(),contract(),binding)
    member={"$schema":"https://json-schema.org/draft/2020-12/schema",**infer(members)};member["$id"]="gen_enc_fast_b1_repair_03_member_identity_v1";member["properties"]["schema_version"]={"const":"gen_enc_fast_b1_repair_03_member_identity_v1"};member["properties"]["record_kind"]={"const":"BATCH_LOCAL_MEMBER_IDENTITY_TYPED_CAD_DERIVED"};member["properties"]["task_id"]={"const":driver.TASK_ID};member["properties"]["repair_id"]={"const":driver.REPAIR};member["properties"]["batch_id"]={"const":"B1"};member["properties"]["final_test_read"]={"const":False}
    schemas={"member_identity":member,"typed_projection":{"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"gen_enc_fast_b1_repair_03_typed_projection_v1",**infer([projected])}}
    for path in OLD.glob("*.schema.json"):
        if path.stem=="member_identity.schema":continue
        name=path.name.removesuffix(".schema.json");value=json.loads(path.read_text());value=json.loads(json.dumps(value).replace("repair_02","repair_03").replace("PRE-RELEASE-REPAIR-02","PRE-RELEASE-REPAIR-03"))
        if name in ("release","guardian_attestation","side_record","batch_index","independent_verification","commit_pointer","package_terminal"):add_binding(value)
        if name=="draft":
            value["properties"]["mode"]={"const":driver.MODE};value["required"].append("mode")
        schemas[name]=value
    for name,value in schemas.items():(OUT/f"{name}.schema.json").write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")


if __name__=="__main__":main()
