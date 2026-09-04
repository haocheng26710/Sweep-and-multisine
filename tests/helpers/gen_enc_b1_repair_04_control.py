"""Task-owned technical RELEASE/attestation factory for full CLI tests only."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.gen_enc_b1_repair_04 import cad_projection_driver as cad
from scripts.gen_enc_b1_repair_04 import formal_driver as driver
from scripts.gen_enc_b1_repair_04.primitives import canonical, sha_file
from tests.helpers.gen_enc_b1_repair_04_fixture import contract, entries, objects

REPO=Path(__file__).resolve().parents[2]


def write(path:Path,value)->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(value))


def setup(root:Path,simulate_formal_reads:bool=False,fail_after_reads:int|None=None,fail_after_verifier_reads:int|None=None)->dict:
    root.mkdir(parents=True,exist_ok=True);(root/".technical_b1_repair_04_root").write_text("TECHNICAL ONLY\n")
    package=root/"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_04";package.mkdir(parents=True)
    projection_value=contract();write(package/"cad_typed_projection_contract.json",projection_value);projected=cad.project(objects(),entries(),projection_value)
    structural=[{k:row[k] for k in ("purpose","pointer","selector_id","category","consumers")} for row in projected["dependency_matrix"]]
    matrix={"schema_version":"gen_enc_fast_b1_repair_04_leaf_dependency_matrix_v1","task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"projection_contract_path":driver.PROJECTION_PATH,"projection_contract_sha256":sha_file(package/"cad_typed_projection_contract.json"),"semantic_leaf_count":len(structural),"rows":structural,"dependency_structure_sha256":projected["dependency_matrix_sha256"],"unused_leaf_allowlist":projection_value["unused_leaf_allowlist"],"formal_authority_read_count":0,"final_test_read":False};write(package/"cad_leaf_dependency_matrix.json",matrix)
    bundle={"identity_class":"TECHNICAL_MIRROR_ONLY_NEVER_FORMAL_AUTHORITY","objects":objects(),"authority_entries":entries(),"formal_authority_read_count":0,"final_test_read":False};write(root/"technical/bundle.json",bundle)
    for name in ("source","schema"):write(package/f"{name}_manifest.json",{"identity_class":"TECHNICAL_MIRROR_MANIFEST_ONLY","name":name,"task_id":driver.TASK_ID,"repair_id":driver.REPAIR,"final_test_read":False})
    write(package/"command_manifest.json",json.loads((REPO/"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_04/command_manifest.json").read_text()))
    release={"schema_version":"gen_enc_fast_b1_repair_04_technical_release_v1","record_kind":"TECHNICAL_MIRROR_RELEASE","identity_class":"TECHNICAL_MIRROR_RELEASE_NEVER_FORMAL","authoritative":False,"technical_only":True,"attempt":1,"repair_id":driver.REPAIR,"task_id":driver.TASK_ID,"batch_id":"B1","mode":driver.MODE,"commands_exact":list(driver.COMMANDS),"authority_allowlist_sha256":"49263e3cab9825840284d18a4d628be73d1273bf6940493878bac5da529c958c","issued_at":datetime.now(timezone.utc).isoformat(),"expires_at":(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),"run_id":"0"*64,"roots":driver.exact_roots("0"*64,True),"projection_contract_path":driver.PROJECTION_PATH,"projection_contract_sha256":sha_file(package/"cad_typed_projection_contract.json"),"dependency_matrix_path":driver.DEPENDENCY_PATH,"dependency_matrix_sha256":sha_file(package/"cad_leaf_dependency_matrix.json"),"dependency_structure_sha256":projected["dependency_matrix_sha256"],"source_manifest_path":"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_04/source_manifest.json","source_manifest_sha256":sha_file(package/"source_manifest.json"),"schema_manifest_path":"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_04/schema_manifest.json","schema_manifest_sha256":sha_file(package/"schema_manifest.json"),"command_manifest_path":"outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_repair_04/command_manifest.json","command_manifest_sha256":sha_file(package/"command_manifest.json"),"technical_bundle_path":"technical/bundle.json","technical_bundle_sha256":sha_file(root/"technical/bundle.json"),"simulate_formal_read_accounting":simulate_formal_reads,"technical_fail_after_reads":fail_after_reads,"technical_fail_after_reads_verifier":fail_after_verifier_reads,"final_test_read":False}
    release["run_id"]=driver.derive_run_id(release);release["roots"]=driver.exact_roots(release["run_id"],True);write(root/"control/RELEASE.json",release);release_sha=sha_file(root/"control/RELEASE.json")
    bind={k:release[k] for k in ("task_id","batch_id","run_id","mode","commands_exact","authority_allowlist_sha256","projection_contract_path","projection_contract_sha256","dependency_matrix_path","dependency_matrix_sha256","dependency_structure_sha256","source_manifest_path","source_manifest_sha256","schema_manifest_path","schema_manifest_sha256","command_manifest_path","command_manifest_sha256","roots")}
    att={"schema_version":"gen_enc_fast_b1_repair_04_technical_attestation_v1","record_kind":"TECHNICAL_MIRROR_ONE_WAY_ATTESTATION","identity_class":"TECHNICAL_MIRROR_ONLY","repair_id":driver.REPAIR,**bind,"release_sha256":release_sha,"one_way":True,"final_test_read":False};write(root/"control/GUARDIAN_ATTESTATION.json",att);att_sha=sha_file(root/"control/GUARDIAN_ATTESTATION.json")
    issued={"schema_version":"gen_enc_fast_b1_repair_04_side_record_v1","state":"ISSUED","repair_id":driver.REPAIR,**bind,"release_sha256":release_sha,"attestation_sha256":att_sha,"one_use":True,"revoked":False,"final_test_read":False};write(root/release["roots"]["side_records"]/"ISSUED.json",issued)
    return {"root":root,"release":root/"control/RELEASE.json","attestation":root/"control/GUARDIAN_ATTESTATION.json","projection":package/"cad_typed_projection_contract.json","matrix":package/"cad_leaf_dependency_matrix.json","run_id":release["run_id"],"roots":{k:root/v for k,v in release["roots"].items()}}
