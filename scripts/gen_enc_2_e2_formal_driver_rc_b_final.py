"""Minimal RC-B-final driver overlay preserving the closed RC-A/C/D/E driver."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path: sys.path.insert(0, str(REPO))
SRC = REPO / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

import scripts.gen_enc_2_e2_formal_driver_rc03 as base
import scripts.gen_enc_2_e2_merge_reconstruct_rc03 as predecessor_merge
import scripts.gen_enc_2_e2_merge_reconstruct_rc_b_final as final_merge
from acoustic_encoder.gen_enc.e2_rc03_stats import sha256_file


class FinalDriverError(RuntimeError):
    pass


def update_dedup_index(manifest: dict[str, Any], receipt_path: Path, output_root: Path) -> tuple[Path, str]:
    partition = manifest["partition"]
    index_path = output_root / "reference_stats" / partition / "dedup_index.json"
    if index_path.exists():
        index = base.read_json(index_path)
    else:
        index = {"schema_version":"gen_enc_2_e2_reference_dedup_index_rc_b_final_v1","partition":partition,"entries":{}}
    receipt_sha = sha256_file(receipt_path)
    for entry in manifest["entries"]:
        if entry["role"] not in final_merge.REFERENCE_ROLES: continue
        source = Path(entry["path"])
        key = final_merge.dedup_key(partition,manifest["chunk_id"],entry["role"])
        canonical = output_root / "reference_stats" / partition / "payloads" / f"{manifest['chunk_id']}.{entry['role']}.npy"
        record = index["entries"].get(key)
        if record is None:
            canonical.parent.mkdir(parents=True,exist_ok=True)
            os.replace(source,canonical)
            record={"partition":partition,"key":key,"chunk_id":manifest["chunk_id"],"role":entry["role"],
                    "source_sha256":entry["sha256"],"canonical_payload_path":canonical.as_posix(),"canonical_payload_sha256":sha256_file(canonical),"origins":[]}
            index["entries"][key]=record
        else:
            if record["source_sha256"]!=entry["sha256"] or record["canonical_payload_sha256"]!=sha256_file(Path(record["canonical_payload_path"])):
                raise FinalDriverError("DEDUP_REFERENCE_HASH_MISMATCH")
            source.unlink()
        record["origins"].append({"identity_id":manifest["identity_id"],"original_manifest_path":manifest["_manifest_path"],
                                  "original_role_path":entry["path"],"original_role_sha256":entry["sha256"],
                                  "receipt_path":receipt_path.as_posix(),"receipt_sha256":receipt_sha})
    base.write_json_atomic(index_path,index)
    return index_path,sha256_file(index_path)


def complete_role_delete_gate(**kwargs: Any) -> None:
    raw=kwargs["raw"]; receipt=kwargs["receipt"]; manifest_path=kwargs["manifest"]; verifier_argv=kwargs["verifier_argv"]
    phase=kwargs["phase"]; expected_roles=kwargs["expected_roles"]; output_root=kwargs["output_root"]; checkpoint=kwargs["checkpoint"]
    quarantine=kwargs["quarantine"]; audit=kwargs["audit"]; retain_audit=kwargs["retain_audit"]; ledger=kwargs["ledger"]
    merge_position=kwargs["merge_position"]; w_accumulator=kwargs.get("w_accumulator"); w_merge_checkpoint=kwargs.get("w_merge_checkpoint")
    completed=ledger.run_child(verifier_argv,cwd=REPO.as_posix())
    if completed.returncode!=0:
        quarantine.parent.mkdir(parents=True,exist_ok=True); os.replace(raw,quarantine)
        base.write_json_atomic(checkpoint,{"status":"PARTITION_STOP","failure_chunk":quarantine.name,"merge_position":merge_position,"same_run_retry":False,"later_merge":False,"resource":ledger.snapshot()})
        raise FinalDriverError("VERIFY_FAIL_QUARANTINE_PARTITION_STOP")
    receipt_value=base.read_json(receipt)
    manifest=predecessor_merge.validate_role_manifest(manifest_path,expected_roles); manifest["_manifest_path"]=manifest_path.as_posix()
    if receipt_value.get("status")!="PASS" or receipt_value.get("full_role_manifest_sha256")!=sha256_file(manifest_path) or receipt_value.get("role_count")!=len(expected_roles):
        raise FinalDriverError("COMPLETE_ROLE_RECEIPT_FAIL")
    if phase=="COMMON_W_PASS":
        if w_accumulator is None or w_merge_checkpoint is None: raise FinalDriverError("W_MERGE_TARGET_REQUIRED")
        merge=predecessor_merge.merge_common_w_contribution(manifest_path,w_accumulator,w_merge_checkpoint,expected_position=merge_position)
        contribution_hash=merge["accumulator_sha256"]
    else:
        index_path,contribution_hash=update_dedup_index(manifest,receipt,output_root)
        if not index_path.is_file(): raise FinalDriverError("DEDUP_INDEX_NOT_DURABLE")
    resource=base.gate(output_root,ledger)
    base.write_json_atomic(checkpoint,{"status":"PASS_COMPLETE_ROLES_CHECKPOINTED","phase":phase,"merge_position":merge_position,
        "receipt_sha256":sha256_file(receipt),"manifest_sha256":sha256_file(manifest_path),"merge_contribution_sha256":contribution_hash,
        "resource":resource,"same_run_retry":False,"later_merge":True})
    if retain_audit: audit.parent.mkdir(parents=True,exist_ok=True); os.replace(raw,audit)
    else: raw.unlink()
    if phase=="COMMON_W_PASS":
        for entry in manifest["entries"]: Path(entry["path"]).unlink()


def reconstruct_adapter(stats_root: Path, target: Path) -> dict[str, Any]:
    phase=stats_root.parent.name
    partition="development" if phase=="DEVELOPMENT_METRIC_PASS" else "single_use_validation"
    identity=stats_root.name
    prefix=identity.split("_",1)[0]
    families={"HAND":"HAND_DESIGNED","NEAR":"NEAR_INDEPENDENT","RANDOM":"FIXED_SEED_RANDOM_DISORDERED","PHYSICS":"PHYSICS_METAMATERIAL_INSPIRED"}
    formal_root=stats_root.parents[2]
    try:
        return final_merge.reconstruct_candidate_from_root(stats_root,formal_root/"candidate_outputs"/identity,partition=partition,
            dedup_index=formal_root/"reference_stats"/partition/"dedup_index.json",identity_id=identity,family_id=families[prefix])
    except final_merge.FinalReconstructionError as exc:
        failure={"schema_version":"gen_enc_2_e2_candidate_technical_failure_rc_b_final_v1","identity_id":identity,"family_id":families[prefix],
                 "partition":partition,"technical_status":"TECHNICAL_FAILURE","scientific_status":"TECHNICAL_FAILURE",
                 "reason":str(exc),"all_required_roles_consumed":False,"final_test_read":False}
        base.write_json_atomic(target,failure)
        raise FinalDriverError("CANDIDATE_RECONSTRUCTION_TECHNICAL_FAILURE") from exc


def install_overlay() -> None:
    base.__file__=__file__
    base.complete_role_delete_gate=complete_role_delete_gate
    predecessor_merge.reconstruct_candidate_from_root=reconstruct_adapter
    predecessor_merge.aggregate_families=final_merge.aggregate_families


def parser() -> argparse.ArgumentParser:
    return base.parser()


def main(argv: list[str]|None=None)->int:
    args=parser().parse_args(argv)
    try:
        if args.mode=="self-test": print(json.dumps({"status":"PASS","formal_units":0,"overlay":"RC_B_FINAL_ALL_ROLE_RECONSTRUCTION_AND_DEDUP_INDEX","final_test_read":False},sort_keys=True)); return 0
        required=[args.authorization,args.contract,args.exact80,args.nuisance_csv,args.seed_split,args.source_manifest,args.runtime_manifest,args.output_root,args.verifier,args.stats_code,args.merge_code,args.through_reference]
        if any(value is None for value in required) or (args.mode=="single-use-validation" and(not args.development_seal or not args.sealed_w)): raise FinalDriverError("FORMAL_ARGUMENTS_REQUIRED")
        install_overlay(); return base.run(args)
    except (OSError,ValueError,KeyError,base.DriverError,FinalDriverError,final_merge.FinalReconstructionError) as exc: print(f"FAIL_CLOSED:{exc}",file=sys.stderr); return 2


if __name__=="__main__": raise SystemExit(main())
