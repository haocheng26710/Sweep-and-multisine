from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from scripts.gen_enc_b1_repair_03 import formal_driver as driver
from scripts.gen_enc_b1_repair_03 import independent_verifier as verifier
from scripts.gen_enc_b1_repair_03.primitives import canonical
from tests.helpers.gen_enc_b1_repair_03_control import setup

REPO=Path(__file__).resolve().parents[1];SCHEMAS=REPO/"schemas/gen_enc/b1_repair_03"


def env()->dict[str,str]:
    value=dict(os.environ);value["PYTHONPATH"]=str(REPO)+(os.pathsep+value["PYTHONPATH"] if value.get("PYTHONPATH") else "");return value


def args(control:dict,module:str,command:str)->list[str]:
    return [sys.executable,"-m",module,command,"--repo-root",".","--release","control/RELEASE.json","--guardian-attestation","control/GUARDIAN_ATTESTATION.json","--schema-root",str(SCHEMAS),"--projection-contract",driver.PROJECTION_PATH,"--dependency-matrix",driver.DEPENDENCY_PATH]


def run(control:dict,module:str,command:str,extra_env:dict|None=None)->subprocess.CompletedProcess:
    e=env();e.update(extra_env or {});return subprocess.run(args(control,module,command),cwd=control["root"],env=e,text=True,capture_output=True,check=False)


def full_to_verified(root:Path)->dict:
    c=setup(root);assert run(c,"scripts.gen_enc_b1_repair_03.formal_driver","preflight").returncode==0;assert run(c,"scripts.gen_enc_b1_repair_03.formal_driver","generate-staging").returncode==0;verified=run(c,"scripts.gen_enc_b1_repair_03.independent_verifier","verify");assert verified.returncode==0,verified.stderr;return c


def test_no_release_both_entrypoints_fail_pre_read_zero(tmp_path:Path)->None:
    root=tmp_path/"none";root.mkdir();(root/".technical_b1_repair_03_root").write_text("x")
    fake={"root":root}
    for module,command in (("scripts.gen_enc_b1_repair_03.formal_driver","preflight"),("scripts.gen_enc_b1_repair_03.independent_verifier","verify")):
        result=run(fake,module,command);assert result.returncode==2 and '"authority_read_count": 0' in result.stderr


def test_full_six_main_cli_e2e_31_pointer_last_and_package(tmp_path:Path)->None:
    c=full_to_verified(tmp_path/"e2e");stage=c["roots"]["staging"]
    assert len([p for p in stage.rglob("*") if p.is_file()])==31
    published=run(c,"scripts.gen_enc_b1_repair_03.formal_driver","publish");assert published.returncode==0,published.stderr
    pointer=c["roots"]["pointer"]/"B1.json";terminal=c["roots"]["success"]/"VERIFIED_SUCCESS.json";assert pointer.is_file() and terminal.is_file() and pointer.stat().st_mtime_ns<=terminal.stat().st_mtime_ns
    value=json.loads(terminal.read_text());assert value["honest_counts"]=={"authority_reads":0,"members":20,"artifacts":31,"published":31} and value["commit_pointer_sha256"]
    packaged=run(c,"scripts.gen_enc_b1_repair_03.formal_driver","package-results");assert packaged.returncode==0 and '"status": "VERIFIED_SUCCESS"' in packaged.stdout
    assert len([p for p in c["roots"]["run"].rglob("*") if p.is_file()])==31


@pytest.mark.parametrize("field",["projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256"])
@pytest.mark.parametrize("record",["release","attestation","issued"])
def test_five_projection_fields_mutation_pre_read_fail(field:str,record:str,tmp_path:Path)->None:
    c=setup(tmp_path/f"{record}-{field}")
    path=c[record] if record in ("release","attestation") else c["roots"]["side_records"]/"ISSUED.json";value=json.loads(path.read_text());value[field]="wrong/path" if field.endswith("path") else "0"*64;path.write_bytes(canonical(value))
    result=run(c,"scripts.gen_enc_b1_repair_03.formal_driver","preflight");assert result.returncode==2 and '"authority_read_count": 0' in result.stderr
    assert not (c["root"]/"technical/bundle.json.read-marker").exists()


def test_old_mode_is_rejected_not_aliased(tmp_path:Path)->None:
    c=setup(tmp_path/"mode");release=json.loads(c["release"].read_text());release["mode"]="FORMAL_B1_EXACT_20";c["release"].write_bytes(canonical(release));result=run(c,"scripts.gen_enc_b1_repair_03.formal_driver","preflight");assert result.returncode==2 and "RELEASE_CONTRACT" in result.stderr and '"authority_read_count": 0' in result.stderr


def test_verifier_cli_projection_path_rejected_before_bundle_open(tmp_path:Path)->None:
    c=setup(tmp_path/"argv");assert run(c,"scripts.gen_enc_b1_repair_03.formal_driver","preflight").returncode==0
    (c["root"]/"technical/bundle.json").write_text("corrupt",encoding="utf-8")
    argv=args(c,"scripts.gen_enc_b1_repair_03.independent_verifier","verify");argv[argv.index("--projection-contract")+1]="wrong/projection.json"
    result=subprocess.run(argv,cwd=c["root"],env=env(),text=True,capture_output=True,check=False)
    assert result.returncode==2 and "ARGV_PROJECTION_PATH" in result.stderr and "BUNDLE_HASH" not in result.stderr and '"authority_read_count": 0' in result.stderr


def test_package_results_recomputes_full_published_graph(tmp_path:Path)->None:
    c=full_to_verified(tmp_path/"package-mutation");assert run(c,"scripts.gen_enc_b1_repair_03.formal_driver","publish").returncode==0
    member=c["roots"]["run"]/"members/HAND_01.json";value=json.loads(member.read_text());value["slot_ordinal"]=2;member.write_bytes(canonical(value))
    result=run(c,"scripts.gen_enc_b1_repair_03.formal_driver","package-results")
    assert result.returncode==2 and ("PACKAGE_SHA256SUMS" in result.stderr or "PACKAGE_RESEAL" in result.stderr)


def test_eight_process_exclusive_one_use(tmp_path:Path)->None:
    c=setup(tmp_path/"race");processes=[subprocess.Popen(args(c,"scripts.gen_enc_b1_repair_03.formal_driver","preflight"),cwd=c["root"],env=env(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(8)];results=[p.communicate()+(p.returncode,) for p in processes]
    assert sum(code==0 for _,_,code in results)==1 and sum(code==2 for _,_,code in results)==7
    assert (c["roots"]["side_records"]/"CONSUMED.json").is_file()


@pytest.mark.parametrize("index",range(20))
def test_twenty_target_real_crash_then_recover_single_terminal(index:int,tmp_path:Path)->None:
    c=full_to_verified(tmp_path/f"kill-{index}");result=run(c,"scripts.gen_enc_b1_repair_03.formal_driver","publish",{"GEN_ENC_B1_REPAIR03_FAULT":f"kill:{index}"});assert result.returncode==86
    recovered=run(c,"scripts.gen_enc_b1_repair_03.formal_driver","recover");assert recovered.returncode==0,recovered.stderr
    assert not (c["roots"]["pointer"]/"B1.json").exists() and not any(p.is_file() for p in c["roots"]["run"].rglob("*"))
    terminals=list(c["roots"]["success"].glob("*.json"))+list(c["roots"]["failure"].glob("*.json"));assert len(terminals)==1 and json.loads(terminals[0].read_text())["record_kind"]=="FAIL_CLOSED"
    assert run(c,"scripts.gen_enc_b1_repair_03.formal_driver","package-results").returncode==0


@pytest.mark.parametrize("fault",["copy:0","fsync:0","replace:0","journal:0","pointer"])
def test_publication_faults_rollback_and_honest_terminal(fault:str,tmp_path:Path)->None:
    c=full_to_verified(tmp_path/fault.replace(":","-"));result=run(c,"scripts.gen_enc_b1_repair_03.formal_driver","publish",{"GEN_ENC_B1_REPAIR03_FAULT":fault});assert result.returncode==2
    terminal=c["roots"]["failure"]/"FAIL_CLOSED.json";assert terminal.is_file();value=json.loads(terminal.read_text());assert value["package_terminal_count"]==1 and value["honest_counts"]["published"]==0
    assert not (c["roots"]["pointer"]/"B1.json").exists() and not any(p.is_file() for p in c["roots"]["run"].rglob("*"))


def test_schemas_use_only_typed_mode_and_require_five_fields() -> None:
    for path in SCHEMAS.glob("*.schema.json"):
        schema=json.loads(path.read_text());jsonschema.Draft202012Validator.check_schema(schema)
        text=path.read_text();assert '"FORMAL_B1_EXACT_20"' not in text
    for name in ("release","guardian_attestation","side_record","batch_index","independent_verification","commit_pointer","package_terminal"):
        schema=json.loads((SCHEMAS/f"{name}.schema.json").read_text());assert schema["properties"]["mode"]["const"]==driver.MODE
        for field in ("projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256"):assert field in schema["required"]


def test_ast_no_old_complete_cross_or_dynamic_imports() -> None:
    for path in (REPO/"scripts/gen_enc_b1_repair_03").glob("*.py"):
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                module=node.module or "";assert not module.startswith(("scripts.gen_enc_b1.","scripts.gen_enc_b1_repair_01","scripts.gen_enc_b1_repair_02"))
                if path.name=="formal_driver.py":assert "independent_verifier" not in module and "cad_projection_verifier" not in module
                if path.name=="independent_verifier.py":assert "formal_driver" not in module and "cad_projection_driver" not in module
            if isinstance(node,ast.Import):assert all(not x.name.startswith(("scripts.gen_enc_b1.","scripts.gen_enc_b1_repair_01","scripts.gen_enc_b1_repair_02")) for x in node.names)
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):assert node.func.id!="__import__"
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):assert node.func.attr not in ("import_module","exec_module")
