"""Independent GEN-ENC-2C identity/static verifier.

The verifier is inert on import, never imports the generator or orchestrator,
and recomputes paths, canonical bytes, schemas, slot/status counts, provenance,
and the complete scientific hash chain from sealed inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any


REPO_ROOT = Path(r"D:\Bristol course\dissertation\program work")
PHASE_B_ROOT = REPO_ROOT / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b"
SCIENTIFIC_ROOT = PHASE_B_ROOT / "scientific"
REPORT_PATH = PHASE_B_ROOT / "result/independent_verification_report.json"
EVIDENCE = "E1B_SCIENTIFIC_IDENTITY_PROVENANCE_AND_STATIC_ELIGIBILITY"
FAMILIES = (
    ("HAND_DESIGNED", "HAND", "01_HAND_DESIGNED.manifest.json"),
    ("NEAR_INDEPENDENT", "NEAR", "02_NEAR_INDEPENDENT.manifest.json"),
    ("FIXED_SEED_RANDOM_DISORDERED", "RANDOM", "03_FIXED_SEED_RANDOM_DISORDERED.manifest.json"),
    ("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS", "04_PHYSICS_METAMATERIAL_INSPIRED.manifest.json"),
)
FORBIDDEN = ("response","score","metric","frequency_response","endpoint","ranking","selection","timing_feasibility","development","validation","final_test")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _expected_paths() -> tuple[list[Path], list[Path], Path]:
    members=[SCIENTIFIC_ROOT/"instances"/family/f"{prefix}_{index:02d}.identity.json" for family,prefix,_ in FAMILIES for index in range(1,21)]
    manifests=[SCIENTIFIC_ROOT/"manifests"/name for _,_,name in FAMILIES]
    return members,manifests,SCIENTIFIC_ROOT/"scientific_identity_index.json"


def _normalized(name: str) -> str:
    return name.casefold().replace("-","_").replace(" ","_")


def _reject_forbidden_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key,item in value.items():
            normalized=_normalized(key)
            if any(token == normalized or token in normalized for token in FORBIDDEN):
                raise ValueError(f"forbidden field at {path}.{key}")
            _reject_forbidden_fields(item,f"{path}.{key}")
    elif isinstance(value,list):
        for index,item in enumerate(value): _reject_forbidden_fields(item,f"{path}[{index}]")


def _atomic_report(report: dict[str, Any]) -> None:
    if REPORT_PATH.exists() or REPORT_PATH.is_symlink(): raise FileExistsError("verifier report collision")
    REPORT_PATH.parent.mkdir(parents=True,exist_ok=True)
    temp=REPORT_PATH.parent/f".{REPORT_PATH.name}.tmp-{uuid.uuid4().hex}"
    try:
        with temp.open("xb") as handle:
            handle.write(_canonical(report));handle.flush();os.fsync(handle.fileno())
        os.replace(temp,REPORT_PATH)
    finally:
        if temp.exists(): temp.unlink()


def verify() -> dict[str, Any]:
    if Path.cwd().resolve()!=REPO_ROOT.resolve(): raise RuntimeError("working directory mismatch")
    if sys.version_info[:3]!=(3,12,4): raise RuntimeError("Python runtime mismatch")
    import jsonschema
    member_paths,manifest_paths,index_path=_expected_paths()
    expected=set(member_paths+manifest_paths+[index_path])
    observed={path for path in SCIENTIFIC_ROOT.rglob("*") if path.is_file()}
    if observed!=expected: raise RuntimeError("scientific path set mismatch")
    if any(path.is_symlink() for path in expected): raise RuntimeError("scientific symlink forbidden")
    schemas={name:json.loads((REPO_ROOT/f"schemas/gen_enc/gen_enc_2c/{name}.schema.json").read_bytes()) for name in ("member_identity","family_manifest","identity_index","result_independent_verification")}
    validators={name:jsonschema.Draft202012Validator(schema) for name,schema in schemas.items()}
    sealed_table=json.loads((REPO_ROOT/"outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/family_design_tables_rev01.json").read_bytes())
    sealed_seeds=json.loads((REPO_ROOT/"outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json").read_bytes())["topology_identity_seeds"]
    member_objects=[]; member_schema_passed=0; canonical_checks=0; hash_checks=0
    for family_index,(family,prefix,_) in enumerate(FAMILIES,start=1):
        for member_index in range(1,21):
            path=SCIENTIFIC_ROOT/"instances"/family/f"{prefix}_{member_index:02d}.identity.json"
            raw=path.read_bytes();obj=json.loads(raw);validators["member_identity"].validate(obj);member_schema_passed+=1
            if raw!=_canonical(obj): raise ValueError(f"noncanonical member: {path}")
            canonical_checks+=1;_reject_forbidden_fields(obj)
            if obj["family_id"]!=family or obj["family_order"]!=family_index or obj["member_id"]!=f"{prefix}_{member_index:02d}" or obj["member_order"]!=member_index: raise ValueError("member identity/order mismatch")
            provenance=obj["input_provenance"]
            if family=="HAND_DESIGNED":
                expected_row=dict(sealed_table["hand_designed"]["rows"][member_index-1]);expected_row.pop("member_id")
                if obj["parameters"]!=expected_row or provenance["table_row_index_zero_based"]!=member_index-1: raise ValueError("HAND sealed row mismatch")
            elif family=="NEAR_INDEPENDENT":
                expected_row=dict(sealed_table["near_independent"]["rows"][member_index-1]);expected_row.pop("member_id")
                if obj["parameters"]!=expected_row or provenance["table_row_index_zero_based"]!=member_index-1: raise ValueError("NEAR sealed row mismatch")
            elif family=="FIXED_SEED_RANDOM_DISORDERED":
                if provenance["formal_seed"]!=sealed_seeds["random_disordered_members"][member_index-1]: raise ValueError("RANDOM seed mismatch")
            else:
                if provenance["formal_master_seed"]!=sealed_seeds["physics_lhs_master"] or provenance["member_identity_seed"]!=sealed_seeds["physics_member_identity"][member_index-1]: raise ValueError("PHYSICS seed mismatch")
            if obj["static_eligibility"]["status"]=="STATIC_IDENTITY_ELIGIBLE":
                if any(value is None for value in obj["parameters"].values()) or obj["bounds_audit"]["status"]!="PASS" or obj["dof_audit"]["status"]!="PASS" or obj["abstract_cad"]["audit_reason_codes"]: raise ValueError("eligible member audit inconsistency")
            member_objects.append(obj)
    manifest_objects=[]; family_schema_passed=0
    for family_index,(family,prefix,name) in enumerate(FAMILIES,start=1):
        path=SCIENTIFIC_ROOT/"manifests"/name;raw=path.read_bytes();obj=json.loads(raw);validators["family_manifest"].validate(obj);family_schema_passed+=1
        if raw!=_canonical(obj): raise ValueError("noncanonical family manifest")
        canonical_checks+=1;_reject_forbidden_fields(obj)
        expected_entries=[]
        for member_index in range(1,21):
            member_path=SCIENTIFIC_ROOT/"instances"/family/f"{prefix}_{member_index:02d}.identity.json"
            member=member_objects[(family_index-1)*20+member_index-1]
            expected_entries.append({"member_id":member["member_id"],"member_order":member_index,"path":member_path.relative_to(REPO_ROOT).as_posix(),"sha256":_sha(member_path),"status":member["static_eligibility"]["status"],"reason_codes":member["static_eligibility"]["reason_codes"]});hash_checks+=1
        if obj["member_entries"]!=expected_entries: raise ValueError("family manifest hash chain mismatch")
        counts={status:sum(member["static_eligibility"]["status"]==status for member in member_objects[(family_index-1)*20:family_index*20]) for status in ("STATIC_IDENTITY_ELIGIBLE","COST_INELIGIBLE","GENERATION_TECHNICAL_FAILURE")}
        expected_status="FAMILY_TECHNICAL_FAILURE_BLOCKED" if counts["GENERATION_TECHNICAL_FAILURE"] else ("FAMILY_STATIC_ELIGIBILITY_BLOCKED" if counts["COST_INELIGIBLE"] else "FAMILY_STATIC_IDENTITY_COMPLETE")
        if (obj["eligible_count"],obj["cost_ineligible_count"],obj["technical_failure_count"],obj["family_terminal_status"])!=(counts["STATIC_IDENTITY_ELIGIBLE"],counts["COST_INELIGIBLE"],counts["GENERATION_TECHNICAL_FAILURE"],expected_status): raise ValueError("family status count mismatch")
        manifest_objects.append(obj)
    raw=index_path.read_bytes();index=json.loads(raw);validators["identity_index"].validate(index)
    if raw!=_canonical(index): raise ValueError("noncanonical identity index")
    canonical_checks+=1;_reject_forbidden_fields(index)
    expected_family_entries=[]
    for family_index,(family,_,name) in enumerate(FAMILIES,start=1):
        path=SCIENTIFIC_ROOT/"manifests"/name;manifest=manifest_objects[family_index-1]
        expected_family_entries.append({"family_id":family,"family_order":family_index,"path":path.relative_to(REPO_ROOT).as_posix(),"sha256":_sha(path),"status":manifest["family_terminal_status"],"eligible_count":manifest["eligible_count"],"cost_ineligible_count":manifest["cost_ineligible_count"],"technical_failure_count":manifest["technical_failure_count"]});hash_checks+=1
    if index["family_entries"]!=expected_family_entries: raise ValueError("identity index hash chain mismatch")
    hash_checks+=1
    totals={key:sum(manifest[key] for manifest in manifest_objects) for key in ("eligible_count","cost_ineligible_count","technical_failure_count")}
    expected_overall="IDENTITY_SET_TECHNICAL_FAILURE_BLOCKED" if totals["technical_failure_count"] else ("IDENTITY_SET_STATIC_ELIGIBILITY_BLOCKED" if totals["cost_ineligible_count"] else "SCIENTIFIC_IDENTITY_AND_STATIC_ELIGIBILITY_COMPLETE")
    if any(index[key]!=value for key,value in totals.items()) or index["overall_terminal_status"]!=expected_overall: raise ValueError("overall status mismatch")
    report={"schema_version":"gen_enc_2c_independent_verification_report_v1","verifier_source_sha256":_sha(Path(__file__)),"command":"python -B scripts/gen_enc_2c_verify_scientific_identities.py verify","working_directory":str(REPO_ROOT),"status":"PASS_IDENTITY_STATIC_ONLY","evidence_level":EVIDENCE,"scientific_evidence_level":"NOT_ESTABLISHED","scientific_hypothesis_status":"NOT_TESTED","recomputed_path_count":85,"member_schema_passed":member_schema_passed,"family_schema_passed":family_schema_passed,"index_schema_passed":1,"canonical_byte_checks":canonical_checks,"hash_chain_checks":hash_checks,"eligible_count":totals["eligible_count"],"cost_ineligible_count":totals["cost_ineligible_count"],"technical_failure_count":totals["technical_failure_count"],"orchestrator_summary_used":False,"forbidden_capability_counts":{"response":0,"endpoint":0,"family_comparison":0,"timing":0,"development":0,"validation":0,"final_test":0},"final_test_read":False}
    validators["result_independent_verification"].validate(report)
    return report


def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument("action",choices=("verify",));parser.parse_args()
    _atomic_report(verify());return 0


if __name__ == "__main__":
    raise SystemExit(main())
