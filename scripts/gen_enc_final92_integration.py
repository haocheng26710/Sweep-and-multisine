from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
from pathlib import Path
from typing import Any

import jsonschema

RUN_ID = "5755da623ea9842097773c1579aa6dd436f1c88c1809d290342e4d804acff804"
TASK_ID = "01a04be3-c294-7952-8191-85b3febc46f8"
BASE = Path(".g92/5755")
STAGING = BASE / "staging"
VERIFICATION = BASE / "verification"
FAILURE = BASE / "failure"
ALLOWLIST = Path("outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/s1_implementation_freeze/path_allowlist_manifest.json")
ALLOWLIST_SHA = "7a62b0508e253d7740e08e396f3164e3b66b6745c7d42e93f8444f2a244a5ab1"
SCHEMA_ROOT = Path("schemas/gen_enc/gen_enc_2c_rev03")
SCHEMA_MANIFEST_SHA = "763a072ec05e85cc84ff57d9b76b92572d08a97fdbe69eca8c5523e8dfe4a4b0"
SOURCE_MANIFEST_SHA = "05bf3fdaff3ed9d726230b0ef7a48c38abd22f43b20b6fd9103e7d7b328fd681"
AUTHORITY_MANIFEST_SHA = "5f1b2a8825f7df762bd5a48b53cc2f7ad5b20b0c12f542f9e9bbda59ed2d3fcf"
GUARDIAN_REVIEW = Path("outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_FAST_B4_EXACT20_AND_80_OF_80_STAGE_TERMINAL_SCOPE_EVIDENCE_REVIEW.json")
GUARDIAN_SHA = "1ca7cd1a7dc4d81f8667fc5d4ffe20fef96223afb1f3b8712db69ce53ba4c0ee"
ADDENDUM = Path("outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_FAST_B4_80_OF_80_STAGE_TERMINAL_ADVISOR_EVENT_BINDING_ADDENDUM.json")
ADDENDUM_SHA = "845c11b1ebbff0dd4f0d3f65938903c7c456925b14dca67613254409b4b2f16e"
ADVISOR_FIX_EVENT = Path("outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/technical_repair_events/FINAL92_RUN_01_SOURCE_IDENTITY_TRAILING_LF_COMPATIBILITY_REPAIR_20260829_001.json")
ADVISOR_FIX_EVENT_SHA = "e29a37c6118114c122747718fcd786c9e04603201f64502f1bc619c9169b0dd6"
ADVISOR_SHORT_ROOT_EVENT = Path("outputs/governance/RESEARCH_ADVANCEMENT_SCOPE_INTEGRITY_ADVISOR/technical_repair_events/FINAL92_RUN_02_WINDOWS_PATH_ADDRESSABILITY_REPAIR_20260829_001.json")
ADVISOR_SHORT_ROOT_EVENT_SHA = "37bd418296ea3e5f0b6ffa08cc6cd7d13ae720c83b07fa814a6d70fe8347a6b5"
FAMILIES = ("HAND_DESIGNED", "NEAR_INDEPENDENT", "FIXED_SEED_RANDOM_DISORDERED", "PHYSICS_METAMATERIAL_INSPIRED")
PREFIX = dict(zip(FAMILIES, ("HAND", "NEAR", "RANDOM", "PHYSICS")))
DOF = dict(zip(FAMILIES, (12, 12, 13, 15)))
TARGET_VOLUME = 3.014899604922098e-5
ZERO = "0" * 64
BATCHES = (
    ("B1", "65ce5d21d1108927709e24ed475d1477c8a46c21be8550b3d152ab449dc03605", "56c06e8bf25c655389cb79a1edc1fcb434ebab80cb46fec99bd1d5ac9191fb19", 1, 5, "b1_science_first_exact20_runs"),
    ("B2", "12d5f3184251eef8ff5e55493318dbc403ec8973a15289a2bd53d9ec8c4cd835", "0782e5f88ebcc7bdae74b8deb00974014df7aced751c44b0a9e841efd5a17a77", 6, 10, "b2_science_first_exact20_runs"),
    ("B3", "ef181dfacdfc9c159a682846793dc7716a007b5fe4fb17efb1983d5e5bdba315", "f2ae7f490ee7804ba3a62de334c7be460ebc202f637d0d0121da118bf7b5bda4", 11, 15, "b3_science_first_exact20_runs"),
    ("B4", "b350702fffb198bfd7296057cf78bf3b083d1e06431a3e438c06b8f46cdf5938", "4212d00c50c35ff26d668610406542a0b2a816b6c202d38d544b746c4f39f7cf", 16, 20, "b4_science_first_exact20_runs"),
)
SCHEMAS = {
    "member": "scientific_instance_identity.schema.json", "family": "family_manifest.schema.json",
    "index": "identity_index.schema.json", "analysis": "analysis_summary.schema.json",
    "inventory": "artifact_inventory.schema.json", "hashes": "scientific_hash_manifest.schema.json",
    "verification": "independent_verification_report.schema.json", "execution": "execution_record.schema.json",
}


class IntegrationError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    def check(v: Any) -> None:
        if isinstance(v, float) and (not math.isfinite(v) or (v == 0 and math.copysign(1, v) < 0)):
            raise IntegrationError("NON_CANONICAL_NUMBER")
        if isinstance(v, dict):
            for item in v.values(): check(item)
        elif isinstance(v, list):
            for item in v: check(item)
    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists(): raise IntegrationError("TEMP_EXISTS:" + str(tmp))
    with tmp.open("xb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def write_json(path: Path, value: Any) -> None:
    write(path, canonical(value))


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(value: Any, kind: str) -> None:
    jsonschema.Draft202012Validator(load(SCHEMA_ROOT / SCHEMAS[kind])).validate(value)


def self_hash(value: dict[str, Any], field: str) -> str:
    clone = dict(value); clone[field] = ZERO
    return sha_bytes(canonical(clone))


def source_identity_hash(value_without_identity_sha256: dict[str, Any]) -> str:
    return sha_bytes(canonical(value_without_identity_sha256) + b"\n")


def hand_01_trailing_lf_regression() -> None:
    batch = BATCHES[0]; path = source_root(batch) / "members/HAND_01.json"; obj = load(path)
    claimed = obj["identity_sha256"]; base = dict(obj); base.pop("identity_sha256")
    if sha_bytes(canonical(base)) == claimed: raise IntegrationError("HAND_01_NO_LF_UNEXPECTED_MATCH")
    if source_identity_hash(base) != claimed: raise IntegrationError("HAND_01_WITH_LF_MISMATCH")


def source_root(batch: tuple[Any, ...]) -> Path:
    bid, run_id, _, _, _, directory = batch
    return Path("outputs/gen_enc/GEN_ENC_FAST_START") / directory / run_id / "results"


def verify_batch(batch: tuple[Any, ...]) -> list[tuple[dict[str, Any], str, str]]:
    bid, run_id, manifest_sha, first, last, _ = batch
    root = source_root(batch)
    if sha_file(root / "SHA256SUMS.json") != manifest_sha: raise IntegrationError(f"{bid}:MANIFEST_HASH")
    sums = load(root / "SHA256SUMS.json")
    expected = {x["path"]: x["sha256"] for x in sums["files"]}
    actual_files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    if set(actual_files) != set(expected) | {"SHA256SUMS.json"}: raise IntegrationError(f"{bid}:UNLISTED_OR_MISSING")
    for rel, digest in expected.items():
        if sha_file(root / rel) != digest: raise IntegrationError(f"{bid}:CHECKSUM:{rel}")
    index = load(root / "batch_index.json")
    if index["batch_id"] != bid or index["run_id"] != run_id or index["member_count"] != 20 or index["family_count"] != 4 or index["final_test_read"]:
        raise IntegrationError(f"{bid}:INDEX")
    if [x["family_id"] for x in index["family_manifests"]] != list(FAMILIES): raise IntegrationError(f"{bid}:FAMILY_ORDER")
    observed: list[tuple[dict[str, Any], str, str]] = []
    expected_ids = [f"{PREFIX[f]}_{n:02d}" for f in FAMILIES for n in range(first, last + 1)]
    if [x["member_id"] for x in index["members"]] != expected_ids: raise IntegrationError(f"{bid}:MEMBER_ORDER")
    for row in index["members"]:
        path = root / row["path"]
        obj = load(path); base = dict(obj); claimed = base.pop("identity_sha256")
        if source_identity_hash(base) != claimed or row["identity_sha256"] != claimed: raise IntegrationError(f"{bid}:IDENTITY_HASH:{row['member_id']}")
        if obj["batch_id"] != bid or obj["run_id"] != run_id or obj["member_id"] != row["member_id"] or obj["static_status"] != "ELIGIBLE": raise IntegrationError(f"{bid}:IDENTITY:{row['member_id']}")
        ev = obj["cad_static_evidence"]
        if obj["final_test_read"] or ev["final_test_read"] or not ev["interval_native"] or ev["midpoint_or_endface_used"] or ev["thresholds_copied_as_measurements"]:
            raise IntegrationError(f"{bid}:STATIC_SEMANTICS:{row['member_id']}")
        if len(ev["ownership_witnesses"]) != 5 or len(ev["volume_root_witnesses"]) != 4 or any(x["status"] != "PASS" for x in ev["volume_root_witnesses"]):
            raise IntegrationError(f"{bid}:STATIC_WITNESS:{row['member_id']}")
        observed.append((obj, path.as_posix(), sha_file(path)))
    audit = load(root / "static_audit.json"); iv = load(root / "independent_verification.json")
    if audit != {"eligible_count":20,"failed_count":0,"final_test_read":False,"ineligible_count":0,"interval_native":True,"member_count":20,"midpoint_or_endface_used":False,"ownership_witness_count":100,"reason_counts":{}}:
        raise IntegrationError(f"{bid}:STATIC_AUDIT")
    if iv["verdict"] != "PASS" or iv["member_count"] != 20 or iv["eligible_count"] != 20 or iv["final_test_read"]: raise IntegrationError(f"{bid}:INDEPENDENT_VERIFICATION")
    return observed


def logical(paths: list[str]) -> list[Path]:
    return [Path(p) for p in paths]


def generate() -> None:
    if BASE.exists(): raise IntegrationError("RUN_ROOT_EXISTS")
    if sha_file(ALLOWLIST) != ALLOWLIST_SHA or sha_file(GUARDIAN_REVIEW) != GUARDIAN_SHA or sha_file(ADDENDUM) != ADDENDUM_SHA or sha_file(ADVISOR_FIX_EVENT) != ADVISOR_FIX_EVENT_SHA or sha_file(ADVISOR_SHORT_ROOT_EVENT) != ADVISOR_SHORT_ROOT_EVENT_SHA:
        raise IntegrationError("FROZEN_CONTROL_HASH")
    hand_01_trailing_lf_regression()
    paths = load(ALLOWLIST)["paths"]
    if len(paths) != 92 or len({p.casefold() for p in paths}) != 92 or any(Path(p).exists() for p in paths): raise IntegrationError("ALLOWLIST_STATE")
    staging_absolute = [(STAGING / p).resolve() for p in paths]; target_absolute = [Path(p).resolve() for p in paths]
    if max(map(lambda p: len(str(p)), staging_absolute + target_absolute)) > 258: raise IntegrationError("PATH_LENGTH_OVER_258")
    longest = max(staging_absolute, key=lambda p: len(str(p))); longest.parent.mkdir(parents=True, exist_ok=True)
    smoke = b"GEN_ENC_FINAL92_SHORT_ROOT_SMOKE"; longest.write_bytes(smoke)
    if longest.read_bytes() != smoke: raise IntegrationError("LONGEST_PATH_SMOKE_READ")
    longest.unlink()
    all_sources: list[tuple[dict[str, Any], str, str]] = []
    for batch in BATCHES: all_sources.extend(verify_batch(batch))
    by_id = {x[0]["member_id"]: x for x in all_sources}
    if len(by_id) != 80: raise IntegrationError("DUPLICATE_MEMBER")
    family_members: dict[str, list[dict[str, Any]]] = {f: [] for f in FAMILIES}
    for global_i, family in enumerate([f for f in FAMILIES for _ in range(20)], 1):
        ordinal = (global_i - 1) % 20 + 1; member_id = f"{PREFIX[family]}_{ordinal:02d}"
        src, src_path, src_file_hash = by_id[member_id]
        kind = {"SEALED_ROW":"EXACT_ROW", "RANDOM_FIXED_MEMBER_SEED":"FIXED_SEED", "PHYSICS_FISHER_YATES_MIDPOINT_LHS":"MIDPOINT_LHS"}[src["input_provenance"]["kind"]]
        binding = canonical({"source_batch":src["batch_id"], "source_identity_sha256":src["identity_sha256"], "source_input_provenance":src["input_provenance"], "source_slot_ordinal":src["slot_ordinal"]}).decode("utf-8")
        ev = src["cad_static_evidence"]
        member = {
            "schema_version":"gen_enc_2c_scientific_instance_rev03_v1", "member_id":member_id, "family_id":family,
            "global_ordinal":global_i, "status":"STATIC_IDENTITY_ELIGIBLE",
            "input_provenance":{"kind":kind,"authority_path":src_path,"authority_sha256":src_file_hash,"pointer_or_seed_binding":binding},
            "parameters":src["parameters"],
            "cad_static_audit":{"bounds_pass":True,"dof":DOF[family],"volume_m3":TARGET_VOLUME,"envelope_m":[0.21,0.21,0.0122],"interface_identity":"U4_CARDINAL_4PORT_CENTRAL_M1_v1","actual_fluid_component_count":1,"minimum_feature_m":ev["general_minima"]["feature_m"],"solid_load_path_m":ev["general_minima"]["load_path_m"]},
            "member_sha256":ZERO,
        }
        member["member_sha256"] = self_hash(member, "member_sha256"); validate(member, "member")
        target = STAGING / paths[global_i - 1]; write_json(target, member)
        family_members[family].append({"ordinal":ordinal,"path":paths[global_i-1],"sha256":sha_file(target),"status":"STATIC_IDENTITY_ELIGIBLE"})
    family_index = []
    for i, family in enumerate(FAMILIES, 1):
        manifest = {"schema_version":"gen_enc_2c_family_manifest_rev03_v1","family_id":family,"ordered_members":family_members[family],"observed_counts":{"members":20,"eligible":20,"cost_ineligible":0,"technical_failure":0},"family_manifest_sha256":ZERO}
        manifest["family_manifest_sha256"] = self_hash(manifest, "family_manifest_sha256"); validate(manifest, "family")
        target = STAGING / paths[79+i]; write_json(target, manifest)
        family_index.append({"ordinal":i,"family_id":family,"path":paths[79+i],"sha256":sha_file(target)})
    index = {"schema_version":"gen_enc_2c_identity_index_rev03_v1","ordered_families":family_index,"observed_counts":{"families":4,"members":80},"identity_index_sha256":ZERO}
    index["identity_index_sha256"] = self_hash(index,"identity_index_sha256"); validate(index,"index"); write_json(STAGING / paths[84], index)
    scientific = [{"path":paths[i],"sha256":sha_file(STAGING / paths[i])} for i in range(85)]
    formal_hashes = {"member":sha_bytes(canonical(scientific[:80])),"family":sha_bytes(canonical(scientific[80:84])),"index":scientific[84]["sha256"]}
    analysis = {"schema_version":"gen_enc_2c_analysis_summary_rev03_v1","terminal_status":"COMPLETE_STATIC_IDENTITY_AUDIT","evidence_level":"E1B_SCIENTIFIC_IDENTITY_PROVENANCE_AND_STATIC_ELIGIBILITY","scientific_hypothesis_status":"NOT_TESTED","observed_counts":{"members":80,"families":4,"eligible":80,"cost_ineligible":0,"technical_failure":0},"formal_hashes":formal_hashes,"final_test_read":False}
    validate(analysis,"analysis"); write_json(STAGING / paths[85], analysis)
    inventory = {"schema_version":"gen_enc_2c_artifact_inventory_rev03_v1","artifacts":[{"path":x["path"],"sha256":x["sha256"],"bytes":(STAGING/x["path"]).stat().st_size,"role":"SCIENTIFIC_IDENTITY"} for x in scientific],"authorized_target_count":92,"unlisted_count":0,"mixed_state":False,"final_test_read":False}
    validate(inventory,"inventory"); write_json(STAGING / paths[86], inventory)
    authority_entries = [{"path":str(source_root(b)/"SHA256SUMS.json").replace("\\","/"),"sha256":b[2]} for b in BATCHES] + [{"path":GUARDIAN_REVIEW.as_posix(),"sha256":GUARDIAN_SHA},{"path":ADDENDUM.as_posix(),"sha256":ADDENDUM_SHA},{"path":ADVISOR_FIX_EVENT.as_posix(),"sha256":ADVISOR_FIX_EVENT_SHA},{"path":ADVISOR_SHORT_ROOT_EVENT.as_posix(),"sha256":ADVISOR_SHORT_ROOT_EVENT_SHA},{"path":ALLOWLIST.as_posix(),"sha256":ALLOWLIST_SHA}]
    hashes = {"schema_version":"gen_enc_2c_scientific_hash_manifest_rev03_v1","scientific_entries":scientific,"authority_entries":authority_entries,"runtime_binding":{"python":platform.python_version(),"mode":"SEALED_B1_B4_INTEGRATION","claim_ceiling":"INTEGRATED_IDENTITY_COMPLETE80_AND_CAD_STATIC_TECHNICAL_VALIDITY_ONLY","matched_cost_axes":"FROZEN_METADATA_UNMODIFIED_COMPARISON_NOT_TESTED","stable_rank":"NOT_TESTED","H_equals_ACB":"NOT_ESTABLISHED","ranking":"NOT_TESTED","performance":"NOT_TESTED","response":"NOT_TESTED","timing":"NOT_TESTED","simulation":"NOT_TESTED"},"identity_index_sha256":scientific[84]["sha256"],"final_test_read":False}
    validate(hashes,"hashes"); write_json(STAGING / paths[87], hashes)
    report = {"schema_version":"gen_enc_2c_independent_verification_rev03_v1","mode":"READ_ONLY_INDEPENDENT_RECOMPUTATION","status":"FAIL_CLOSED_TECHNICAL_RECOMPUTATION","observed_counts":{"members":80,"pending_verifier":1},"recomputed_checks":[],"failure_count":1,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False}
    validate(report,"verification"); write_json(STAGING / paths[88], report)
    execution = {"schema_version":"gen_enc_2c_execution_record_rev03_v1","task_id":TASK_ID,"dispatch_id":RUN_ID,"authorization_sha256":GUARDIAN_SHA,"source_manifest_sha256":SOURCE_MANIFEST_SHA,"schema_manifest_sha256":SCHEMA_MANIFEST_SHA,"authority_manifest_sha256":AUTHORITY_MANIFEST_SHA,"commands_exact":["generate-staging","independent-verify","publish"],"runtime":{"python":platform.python_version(),"run_id":RUN_ID,"input_order":["B1","B2","B3","B4"]},"terminal_state":"FAIL_CLOSED","observed_counts":{"members":80,"artifacts":92,"verification_pending":1},"final_test_read":False}
    validate(execution,"execution"); write_json(STAGING / paths[89], execution)
    progress = """# GEN-ENC-2C scientific identity generation results\n\n- run_id: `5755da623ea9842097773c1579aa6dd436f1c88c1809d290342e4d804acff804`\n- endpoint: 85 scientific + 6 result + 1 progress = 92\n- integrated members: 80/80; HAND=20, NEAR=20, RANDOM=20, PHYSICS=20\n- input order: B1 -> B2 -> B3 -> B4; family member order: 01 -> 20\n- source identity compatibility: compact sorted JSON plus exactly one trailing LF; HAND_01 no-LF mismatch and with-LF match regression passed\n- static result: all 80 retain `STATIC_IDENTITY_ELIGIBLE`; full-interval geometry; no midpoint/end-face scalarization\n- matched-cost axes: frozen contract metadata verified unmodified; cross-family matched-cost comparison `NOT_TESTED`\n- stable-rank/ranking/performance/response/timing/simulation: `NOT_TESTED`; H=ACB scientific evaluation: `NOT_ESTABLISHED`\n- claim ceiling: `INTEGRATED_IDENTITY_COMPLETE80_AND_CAD_STATIC_TECHNICAL_VALIDITY_ONLY`\n- scientific hypothesis: `NOT_TESTED`; final_test_read=false\n- no GEN-ENC-2, timing, full-wave, inverse-design, search, or simulation was started\n"""
    write(STAGING / paths[91], progress.encode("utf-8"))
    lines = [f"{sha_file(STAGING/paths[i])}  {paths[i]}" for i in range(92) if i != 90]
    write(STAGING / paths[90], ("\n".join(lines)+"\n").encode("utf-8"))
    files = [p for p in STAGING.rglob("*") if p.is_file()]
    if len(files) != 92: raise IntegrationError(f"STAGING_COUNT:{len(files)}")


def publish() -> None:
    marker = VERIFICATION / "PASS.json"
    if not marker.is_file() or load(marker).get("status") != "PASS": raise IntegrationError("VERIFIER_PASS_MISSING")
    paths = load(ALLOWLIST)["paths"]
    if any(Path(p).exists() for p in paths): raise IntegrationError("TARGET_ALREADY_EXISTS")
    created: list[Path] = []
    try:
        for rel in paths:
            src, dst = STAGING / rel, Path(rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            with src.open("rb") as rf, dst.open("xb") as wf:
                shutil.copyfileobj(rf, wf); wf.flush(); os.fsync(wf.fileno())
            created.append(dst)
        if len(created) != 92 or any(sha_file(STAGING/p) != sha_file(Path(p)) for p in paths): raise IntegrationError("PUBLISH_HASH")
    except BaseException:
        FAILURE.mkdir(parents=True, exist_ok=True)
        write_json(FAILURE / "FAILURE.json", {"run_id":RUN_ID,"state":"FAILURE","created_targets":[p.as_posix() for p in created],"final_test_read":False})
        raise


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=("generate-staging","publish"));args=parser.parse_args()
    try:
        generate() if args.command == "generate-staging" else publish()
    except BaseException as exc:
        FAILURE.mkdir(parents=True,exist_ok=True)
        if not (FAILURE/"FAILURE.json").exists(): write_json(FAILURE/"FAILURE.json",{"run_id":RUN_ID,"state":"FAILURE","error":type(exc).__name__+":"+str(exc),"final_test_read":False})
        raise


if __name__ == "__main__": main()
