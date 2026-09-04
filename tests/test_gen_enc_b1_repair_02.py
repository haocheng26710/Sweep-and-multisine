from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from scripts.gen_enc_b1_repair_02 import cad_projection_driver as driver_cad
from scripts.gen_enc_b1_repair_02 import cad_projection_verifier as verifier_cad
from scripts.gen_enc_b1_repair_02 import formal_driver as driver
from scripts.gen_enc_b1_repair_02 import independent_verifier as verifier
from scripts.gen_enc_b1_repair_02.primitives import sha_value
from tests.helpers.gen_enc_b1_repair_02_fixture import contract, entries, objects

REPO=Path(__file__).resolve().parents[1]
PACKAGE=REPO/"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_02"
REVIEW=REPO/"outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/reviews/GEN_ENC_FAST_B1_PRE_RELEASE_REPAIR_01_CONFORMANCE_REREVIEW.json"


def projected():return driver_cad.project(objects(),entries(),contract())
def binding():
    p=projected();return {"task_id":driver.TASK_ID,"batch_id":"B1","run_id":"a"*64,"projection_contract_path":driver.PROJECTION_PATH,"projection_contract_sha256":p["projection_contract_sha256"],"dependency_matrix_path":driver.DEPENDENCY_PATH,"dependency_matrix_sha256":"d"*64,"dependency_structure_sha256":p["dependency_matrix_sha256"],"authority_read_count":0}


def mutate_at(root,path):
    node=root
    tokens=path.lstrip("/").split("/")
    for raw in tokens[:-1]:
        token=raw.replace("~1","/").replace("~0","~");node=node[int(token)] if isinstance(node,list) else node[token]
    key=tokens[-1].replace("~1","/").replace("~0","~");old=node[int(key)] if isinstance(node,list) else node[key]
    new=(not old) if isinstance(old,bool) else old+max(abs(old)*.01,1e-12) if isinstance(old,(int,float)) else old+"_MUT"
    if isinstance(node,list):node[int(key)]=new
    else:node[key]=new


def test_review_hash_and_additive_baselines_unchanged() -> None:
    assert hashlib.sha256(REVIEW.read_bytes()).hexdigest()=="3f51b22a8e4929dfce88a7de72996ea60e57b4f3b220f146ed3afcc66427f9de"
    assert hashlib.sha256((REPO/"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_freeze/SHA256SUMS.txt").read_bytes()).hexdigest()=="a7daa2013d4f84e9f2b8d355f47498634edfd35ec1a4fbbd6551daced6b6c369"
    assert hashlib.sha256((REPO/"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_01/SHA256SUMS.txt").read_bytes()).hexdigest()=="07c2abde9bfebd778f1b8f8bbf511e4681303a89c7aadb043df94d04e7c8b058"


def test_two_independent_typed_projections_equal_and_cover_every_semantic_leaf() -> None:
    left=projected();right=verifier_cad.project(objects(),entries(),contract())
    assert left==right and left["semantic_leaf_count"]==349 and left["dependency_matrix_sha256"]=="127b47b28fa76981f908a056fb4815233cf786fd4c15e255e90110b6d6863c07"
    assert all(row["consumers"] and row["category"] in set(contract()["required_categories"]) for row in left["dependency_matrix"])
    assert all(x["reason"] and "metadata" in x["reason"] or "narrative" in x["reason"] or "outside" in x["reason"] for x in left["unused_leaf_allowlist"])


def test_build_20_members_and_independent_recompute_without_hash_attachment() -> None:
    b=binding();members=driver.members_from_authority(objects(),entries(),contract(),b);checked=verifier.verify_members(members,objects(),entries(),contract(),b)
    assert len(members)==20 and checked["verified_member_count"]==20
    evidence=members[0]["cad_static_evidence"]
    assert "authority_binding" not in evidence and "model_sha256" not in evidence and "dependency_matrix_sha256" not in evidence
    assert len(evidence["ownership_cells"])==5 and len(evidence["slot_placements"])==20 and all(len(x["trace"])==80 for x in evidence["volume_root_witnesses"])
    assert len(evidence["u4_exception_witnesses"])==20 and evidence["actual_fluid_graph"]["component_count"]==1


def test_each_of_349_semantic_leaves_changes_witness_payload_or_fails_closed() -> None:
    baseline_objects=objects();base_projection=driver_cad.project(baseline_objects,entries(),contract());base_params=driver.parameters(baseline_objects,driver.FAMILIES[2],1);baseline=driver.derive_cad_evidence(driver.FAMILIES[2],base_params,base_projection)[0]
    for row in base_projection["dependency_matrix"]:
        changed=copy.deepcopy(baseline_objects);mutate_at(changed[row["purpose"]],row["pointer"])
        try:
            candidate_projection=driver_cad.project(changed,entries(),contract());candidate=driver.derive_cad_evidence(driver.FAMILIES[2],base_params,candidate_projection)[0]
        except Exception:continue
        assert candidate!=baseline,(row["purpose"],row["pointer"],row["consumers"])


def test_all_13_replaced_does_not_leave_20_of_20_witness_payloads_unchanged() -> None:
    original=objects();b=binding();before=driver.members_from_authority(original,entries(),contract(),b);changed=copy.deepcopy(original)
    for purpose in ("CAD0_MULTI_SOURCE_01","CAD0_MULTI_SOURCE_08","CAD0_MULTI_SOURCE_09"):changed[purpose][next(iter(changed[purpose]))]+="_REPLACED"
    changed["CAD0_MULTI_SOURCE_02"]["central"]["total_acoustic_volume_m3"]*=1.001;changed["CAD0_MULTI_SOURCE_03"]["transforms"]["coordinate_frame"]+="_REPLACED";changed["CAD0_MULTI_SOURCE_04"]["common"]["tolerance_m3"]*=2;changed["CAD0_MULTI_SOURCE_05"]["slots"][0]["width_m"]+=1e-5;changed["CAD0_MULTI_SOURCE_06"]["metrics"]["feature_metric"]+="_REPLACED";changed["CAD0_MULTI_SOURCE_07"]["definitions"]["bfs_rule"]+="_REPLACED";changed["CAD0_MULTI_SOURCE_10"]["independent_sector_proof"]["method"]+="_REPLACED";changed["CAD0_MULTI_SOURCE_11"]["collar_common_local_coordinates_m"]["x_m"]+=1e-5;changed["CAD0_MULTI_SOURCE_12"]["fields"]["general_feature_candidates"][0]["measured_m"]+=1e-5;changed["CAD0_MULTI_SOURCE_13"]["selections"]["U1"]["selection"]+="_REPLACED"
    changed_projection=driver_cad.project(changed,entries(),contract());changed_binding={**b,"dependency_structure_sha256":changed_projection["dependency_matrix_sha256"]}
    after=driver.members_from_authority(changed,entries(),contract(),changed_binding)
    unchanged=sum(a["cad_static_evidence"]==z["cad_static_evidence"] for a,z in zip(before,after))
    assert unchanged==0


def test_uncovered_semantic_leaf_and_selector_mutations_fail_closed() -> None:
    changed=objects();changed["CAD0_MULTI_SOURCE_03"]["ownership"]["new_semantic_leaf"]=1
    with pytest.raises(Exception,match="UNUSED|UNCOVERED"):driver_cad.project(changed,entries(),contract())
    for mutation in ("remove","duplicate","category"):
        c=contract()
        if mutation=="remove":c["semantic_selectors"].pop()
        elif mutation=="duplicate":c["semantic_selectors"].append(copy.deepcopy(c["semantic_selectors"][0]))
        else:c["semantic_selectors"][0]["category"]="missing"
        with pytest.raises(Exception):driver_cad.project(objects(),entries(),c)


@pytest.mark.parametrize("record_name",["release","guardian_attestation","ISSUED","CONSUMED"])
@pytest.mark.parametrize("field",["projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256"])
def test_projection_dependency_binding_is_pre_read_and_all_records_reject_mismatch(record_name:str,field:str) -> None:
    expected=binding();record=dict(expected);driver.pre_read_binding(record,expected);verifier.pre_read_binding(record,expected);record[field]="0"*64 if field.endswith("sha256") else "wrong/path.json"
    with pytest.raises(Exception,match="PRE_READ_BINDING"):driver.pre_read_binding(record,expected)
    with pytest.raises(Exception,match="PRE_READ_BINDING"):verifier.pre_read_binding(record,expected)


def test_member_provenance_binds_projection_and_dependency() -> None:
    b=binding();members=driver.members_from_authority(objects(),entries(),contract(),b);p=members[0]["typed_projection_provenance"]
    assert p=={"projection_contract_path":driver.PROJECTION_PATH,"projection_contract_sha256":b["projection_contract_sha256"],"dependency_matrix_path":driver.DEPENDENCY_PATH,"dependency_matrix_sha256":b["dependency_matrix_sha256"],"dependency_structure_sha256":b["dependency_structure_sha256"],"semantic_leaf_count":349}
    bad={**b,"dependency_structure_sha256":"0"*64}
    with pytest.raises(driver.Repair02Error,match="BINDING"):driver.members_from_authority(objects(),entries(),contract(),bad)


def test_ast_forbidden_imports_and_dynamic_imports_absent() -> None:
    root=REPO/"scripts/gen_enc_b1_repair_02";trees={p.name:ast.parse(p.read_text()) for p in root.glob("*.py")}
    for name,tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                assert all(not x.name.startswith("scripts.gen_enc_b1") or x.name.startswith("scripts.gen_enc_b1_repair_02") for x in node.names),(name,ast.unparse(node))
            if isinstance(node,ast.ImportFrom):
                module=node.module or "";assert not module.startswith("scripts.gen_enc_b1.") and not module.startswith("scripts.gen_enc_b1_repair_01"),(name,module)
                if name=="formal_driver.py":assert "independent_verifier" not in module and "cad_projection_verifier" not in module
                if name=="independent_verifier.py":assert "formal_driver" not in module and "cad_projection_driver" not in module
                if name=="cad_projection_driver.py":assert "cad_projection_verifier" not in module
                if name=="cad_projection_verifier.py":assert "cad_projection_driver" not in module
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):assert node.func.id!="__import__"
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):assert node.func.attr not in ("import_module","exec_module")


def test_driver_and_verifier_cli_draft_fail_before_authority_read(tmp_path:Path) -> None:
    draft=tmp_path/"DRAFT.json";draft.write_bytes(canonical_draft())
    common=["--repo-root",str(REPO),"--release",str(draft),"--guardian-attestation",str(tmp_path/"none.json"),"--schema-root",str(REPO/"schemas/gen_enc/b1_repair_02"),"--projection-contract",str(PACKAGE/"cad_typed_projection_contract.json"),"--dependency-matrix",str(PACKAGE/"cad_leaf_dependency_matrix.json")]
    for module,command in (("scripts.gen_enc_b1_repair_02.formal_driver","preflight"),("scripts.gen_enc_b1_repair_02.independent_verifier","verify")):
        result=subprocess.run([sys.executable,"-m",module,command,*common],cwd=REPO,text=True,capture_output=True)
        assert result.returncode==2 and '"authority_read_count": 0' in result.stderr


def canonical_draft()->bytes:
    value={"schema_version":"gen_enc_fast_b1_repair_02_draft_v1","record_kind":"DRAFT","repair_id":"PRE-RELEASE-REPAIR-02","authoritative":False,"attempt":0,"task_id":driver.TASK_ID,"batch_id":"B1","run_id":None,"permissions":{f"p{i}":False for i in range(20)},"may_flip_or_promote":False,"future_release_must_be_new_canonical_bytes":True}
    return json.dumps(value,sort_keys=True,separators=(",",":")).encode()+b"\n"


def test_strict_schemas_validate_members_and_bind_all_projection_fields() -> None:
    schema_root=REPO/"schemas/gen_enc/b1_repair_02";files=list(schema_root.glob("*.schema.json"));assert len(files)==16
    for path in files:
        schema=json.loads(path.read_text());jsonschema.Draft202012Validator.check_schema(schema);assert schema.get("additionalProperties") is False
    member_schema=json.loads((schema_root/"member_identity.schema.json").read_text());members=driver.members_from_authority(objects(),entries(),contract(),binding())
    for member in members:jsonschema.Draft202012Validator(member_schema).validate(member)
    for name in ("release","guardian_attestation","side_record","batch_index"):
        schema=json.loads((schema_root/f"{name}.schema.json").read_text())
        for field in ("projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256"):assert field in schema["required"] and field in schema["properties"]


def test_package_dependency_matrix_and_draft_after_freeze_exists() -> None:
    if not (PACKAGE/"SHA256SUMS.txt").exists():pytest.skip("package builder runs after source tests")
    for line in (PACKAGE/"SHA256SUMS.txt").read_text(encoding="ascii").splitlines():assert hashlib.sha256((PACKAGE/line[66:]).read_bytes()).hexdigest()==line[:64]
    matrix=json.loads((PACKAGE/"cad_leaf_dependency_matrix.json").read_text());assert matrix["semantic_leaf_count"]==349 and matrix["dependency_structure_sha256"]==projected()["dependency_matrix_sha256"]
    draft=json.loads((PACKAGE/"DRAFT.json").read_text());assert draft["attempt"]==0 and draft["run_id"] is None and not any(draft["permissions"].values())
