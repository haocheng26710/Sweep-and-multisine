from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema

from .driver_core import ShapeDriverError, canonical, read_canonical, sha_bytes, sha_file, snapshot

TASK_ID = "01a049a7-15ca-79e1-92a2-d3822ba8609d"
REPAIR = "PRE-RELEASE-REPAIR-11"
MODE = "FORMAL_B1_AUTHORITY_SHAPE_ONLY_EXACT_13X2"
COMMANDS = ["shape-preflight", "extract-shape", "verify-shape", "package-shape"]
CLAIM = "E0_AUTHORITY_STRUCTURE_CONFORMANCE_ONLY"


class Driver11Error(RuntimeError):
    pass


def _safe(repo: Path, label: str) -> Path:
    rel = Path(label)
    if rel.is_absolute() or ".." in rel.parts:
        raise Driver11Error("UNSAFE_PATH:" + label)
    resolved = (repo / rel).resolve()
    try: resolved.relative_to(repo)
    except ValueError as exc: raise Driver11Error("PATH_ESCAPE:" + label) from exc
    return resolved


def _load_schemas(root: Path) -> dict[str, Any]:
    result = {}
    for path in root.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        result[path.name.removesuffix(".schema.json")] = schema
    return result


def _validate(value: Any, schemas: Mapping[str, Any], name: str) -> None:
    try: jsonschema.Draft202012Validator(schemas[name]).validate(value)
    except jsonschema.ValidationError as exc: raise Driver11Error("SCHEMA_" + name + ":" + exc.message) from exc


def _binding(release: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("task_id", "batch_id", "run_id", "dispatch_id", "mode", "commands_exact", "authority_manifest_path", "authority_manifest_sha256", "selector_contract_path", "selector_contract_sha256", "source_manifest_path", "source_manifest_sha256", "schema_manifest_path", "schema_manifest_sha256", "command_manifest_path", "command_manifest_sha256", "output_manifest_path", "output_manifest_sha256", "negative_capability_manifest_path", "negative_capability_manifest_sha256", "guardian_contract_path", "guardian_contract_sha256", "roots", "final_test_read", "technical_mirror", "technical_bundle_path", "technical_bundle_sha256", "technical_fail_after_driver_read", "technical_fail_after_verifier_read", "technical_read_delay_ms")
    return {key: release[key] for key in keys}


def gate(repo: Path, ns: argparse.Namespace, raw_argv: Sequence[str]) -> dict[str, Any]:
    schemas = _load_schemas(ns.schema_root.resolve())
    release, release_raw = read_canonical(ns.release.resolve()); _validate(release, schemas, "shape_release")
    attestation, att_raw = read_canonical(ns.guardian_attestation.resolve()); _validate(attestation, schemas, "shape_attestation")
    dispatch, dispatch_raw = read_canonical(ns.dispatch.resolve()); _validate(dispatch, schemas, "shape_dispatch")
    if release["record_kind"] != "SHAPE_ONLY_RELEASE" or release["task_id"] != TASK_ID or release["mode"] != MODE or release["commands_exact"] != COMMANDS: raise Driver11Error("RELEASE_BINDING")
    root_base=(f".r11t/{release['run_id']}/shape_run" if release["technical_mirror"] else f"outputs/gen_enc/GEN_ENC_FAST_START/b1_repair_11_shape_runs/{release['run_id']}")
    expected_roots={name:f"{root_base}/{name}" for name in ("staging","receipts","side_records","package","terminal")}
    if release["roots"]!=expected_roots:raise Driver11Error("RUN_ROOT_TEMPLATE")
    if attestation["release_path"] != ns.release.as_posix() or attestation["release_sha256"] != sha_bytes(release_raw): raise Driver11Error("ATTESTATION_RELEASE_BINDING")
    if dispatch["release_path"] != ns.release.as_posix() or dispatch["release_sha256"] != sha_bytes(release_raw) or dispatch["attestation_path"] != ns.guardian_attestation.as_posix() or dispatch["attestation_sha256"] != sha_bytes(att_raw): raise Driver11Error("DISPATCH_CONTROL_BINDING")
    for key, wanted in _binding(release).items():
        if attestation.get(key) != wanted or dispatch.get(key) != wanted: raise Driver11Error("FULL_BINDING:" + key)
    if dispatch["state"] != "SHAPE_ISSUED" or not dispatch["one_use"] or dispatch["revoked"]: raise Driver11Error("DISPATCH_STATE")
    if release["release_path"] != ns.release.as_posix() or release["attestation_path"] != ns.guardian_attestation.as_posix() or release["dispatch_path"] != ns.dispatch.as_posix(): raise Driver11Error("CLI_PATH_BINDING")
    for field in ("authority_manifest", "selector_contract", "source_manifest", "schema_manifest", "command_manifest", "output_manifest", "negative_capability_manifest", "guardian_contract"):
        path = _safe(repo, release[field + "_path"])
        if sha_file(path) != release[field + "_sha256"]: raise Driver11Error("BOUND_FILE_HASH:" + field)
    authority_manifest, _ = read_canonical(_safe(repo, release["authority_manifest_path"])); _validate(authority_manifest, schemas, "authority_manifest")
    selector_contract, _ = read_canonical(_safe(repo, release["selector_contract_path"])); _validate(selector_contract, schemas, "selector_contract")
    command_manifest, _ = read_canonical(_safe(repo, release["command_manifest_path"])); _validate(command_manifest, schemas, "command_manifest")
    row = next((x for x in command_manifest["entries"] if x["command"] == ns.command), None)
    if row is None: raise Driver11Error("COMMAND_NOT_FROZEN")
    replacements = {"<RELEASE_EXACT_PATH>": ns.release.as_posix(), "<ATTESTATION_EXACT_PATH>": ns.guardian_attestation.as_posix(), "<DISPATCH_EXACT_PATH>": ns.dispatch.as_posix()}
    expected = [replacements.get(x, x) for x in row["argv_after_python"][2:]]
    if list(raw_argv) != expected: raise Driver11Error("ARGV_NOT_BYTE_EXACT")
    roots = {name: _safe(repo, value) for name, value in release["roots"].items()}
    failure = roots["terminal"] / "TERMINAL.json"
    if failure.exists():
        existing, _ = read_canonical(failure)
        if existing.get("status") == "FAIL_CLOSED": raise Driver11Error("RUN_PERMANENTLY_FAILED")
    return {"repo": repo, "schemas": schemas, "release": release, "release_sha256": sha_bytes(release_raw), "attestation_sha256": sha_bytes(att_raw), "dispatch_sha256": sha_bytes(dispatch_raw), "authority_manifest": authority_manifest, "selectors": selector_contract["selectors"], "roots": roots}


def _receipt_count(context: Mapping[str, Any]) -> int:
    directory = context["roots"]["receipts"]
    if not directory.exists(): return 0
    paths = sorted(directory.glob("*.json"))
    if [p.name for p in paths] != [f"{i:04d}.json" for i in range(1, len(paths) + 1)]: raise Driver11Error("RECEIPT_SEQUENCE")
    return len(paths)


def _write_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    except FileExistsError as exc: raise Driver11Error("EXCLUSIVE_EXISTS:" + path.name) from exc


def _record_read(context: Mapping[str, Any], entry: Mapping[str, Any], lane: str) -> None:
    ordinal = _receipt_count(context) + 1
    value = {"schema_version":"gen_enc_b1_r11_authority_read_receipt_v1","record_kind":"AUTHORITY_SHAPE_READ_RECEIPT","task_id":TASK_ID,"batch_id":"B1","run_id":context["release"]["run_id"],"dispatch_id":context["release"]["dispatch_id"],"lane":lane,"ordinal":ordinal,"purpose":entry["purpose"],"source_path":entry["path"],"source_sha256":entry["sha256"],"source_pointer":entry["pointer"],"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"],"final_test_read":False}
    _validate(value, context["schemas"], "authority_read_receipt")
    _write_exclusive(context["roots"]["receipts"] / f"{ordinal:04d}.json", value)


def _load_objects(context: Mapping[str, Any], lane: str) -> dict[str, Any]:
    release = context["release"]; entries = context["authority_manifest"]["entries"]
    if release["technical_mirror"]:
        bundle_path = _safe(context["repo"], release["technical_bundle_path"])
        if sha_file(bundle_path) != release["technical_bundle_sha256"]: raise Driver11Error("TECHNICAL_BUNDLE_HASH")
        bundle, _ = read_canonical(bundle_path)
        if bundle.get("identity_class") != "TECHNICAL_SYNTHETIC_SHAPE_ONLY_NEVER_AUTHORITY": raise Driver11Error("TECHNICAL_BUNDLE_CLASS")
        objects = bundle["objects"]
        for lane_index, entry in enumerate(entries, 1):
            _record_read(context, entry, lane)
            if release["technical_read_delay_ms"]: time.sleep(release["technical_read_delay_ms"]/1000)
            if lane == "DRIVER" and release.get("technical_fail_after_driver_read") == lane_index:
                raise Driver11Error("INJECTED_PARTIAL_DRIVER_READ_FAILURE")
        return objects
    objects = {}
    for entry in entries:
        path = _safe(context["repo"], entry["path"])
        with path.open("rb") as stream:
            _record_read(context, entry, lane)
            raw = stream.read()
        if sha_bytes(raw) != entry["sha256"]: raise Driver11Error("AUTHORITY_HASH:" + entry["purpose"])
        objects[entry["purpose"]] = json.loads(raw.decode("utf-8"))
    return objects


def _write_failure(context: Mapping[str, Any], reason: str) -> None:
    path = context["roots"]["terminal"] / "TERMINAL.json"
    if path.exists(): return
    value = {"schema_version":"gen_enc_b1_r11_terminal_v1","record_kind":"SHAPE_RUN_TERMINAL","task_id":TASK_ID,"batch_id":"B1","run_id":context["release"]["run_id"],"status":"FAIL_CLOSED","reason":reason,"authority_read_count":_receipt_count(context),"driver_read_count":min(_receipt_count(context),13),"verifier_read_count":max(0,_receipt_count(context)-13),"shape_package_count":0,"member_count":0,"scientific_artifact_count":0,"publication_count":0,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False}
    _validate(value, context["schemas"], "terminal"); _write_exclusive(path, value)


def preflight(context: Mapping[str, Any]) -> dict[str, Any]:
    if _receipt_count(context) != 0: raise Driver11Error("PREFLIGHT_READS_NONZERO")
    consumed = {"schema_version":"gen_enc_b1_r11_dispatch_consumed_v1","record_kind":"SHAPE_DISPATCH_CONSUMED","task_id":TASK_ID,"batch_id":"B1","run_id":context["release"]["run_id"],"dispatch_id":context["release"]["dispatch_id"],"release_sha256":context["release_sha256"],"attestation_sha256":context["attestation_sha256"],"dispatch_sha256":context["dispatch_sha256"],"state":"SHAPE_CONSUMED","one_use":True,"final_test_read":False}
    _validate(consumed, context["schemas"], "dispatch_consumed"); _write_exclusive(context["roots"]["side_records"] / "SHAPE_DISPATCH_CONSUMED.json", consumed)
    return {"status":"SHAPE_PREFLIGHT_CONSUMED_ZERO_READS","authority_read_count":0}


def extract(context: Mapping[str, Any]) -> dict[str, Any]:
    if not (context["roots"]["side_records"] / "SHAPE_DISPATCH_CONSUMED.json").exists(): raise Driver11Error("DISPATCH_NOT_CONSUMED")
    if _receipt_count(context) != 0: raise Driver11Error("DRIVER_READ_BUDGET_ALREADY_USED")
    objects = _load_objects(context, "DRIVER")
    result = snapshot(context["authority_manifest"]["entries"], objects, context["selectors"])
    value = {"schema_version":"gen_enc_b1_r11_structural_snapshot_v1","record_kind":"DRIVER_AUTHORITY_STRUCTURAL_SNAPSHOT","task_id":TASK_ID,"batch_id":"B1","run_id":context["release"]["run_id"],"claim_ceiling":CLAIM,"authority_read_count":13,**result,"member_count":0,"scientific_artifact_count":0,"final_test_read":False}
    _validate(value, context["schemas"], "structural_snapshot")
    _write_exclusive(context["roots"]["staging"] / "driver_shape_snapshot.json", value)
    return {"status":"DRIVER_SHAPE_EXTRACTED","authority_read_count":13,"structural_snapshot_digest":value["structural_snapshot_digest"]}


def package(context: Mapping[str, Any]) -> dict[str, Any]:
    if _receipt_count(context) != 26: raise Driver11Error("PACKAGE_REQUIRES_26_READS")
    actual={p.relative_to(context["roots"]["staging"]).as_posix() for p in context["roots"]["staging"].rglob("*") if p.is_file()}
    if actual!={"driver_shape_snapshot.json","independent_shape_report.json","verifier_terminal.json"}: raise Driver11Error("ZERO_UNLISTED_STAGE")
    for name in ("driver_shape_snapshot.json","independent_shape_report.json","verifier_terminal.json"):
        if not (context["roots"]["staging"] / name).exists(): raise Driver11Error("PACKAGE_INPUT_MISSING:" + name)
    driver, _ = read_canonical(context["roots"]["staging"] / "driver_shape_snapshot.json"); _validate(driver,context["schemas"],"structural_snapshot")
    report, _ = read_canonical(context["roots"]["staging"] / "independent_shape_report.json"); _validate(report,context["schemas"],"independent_report")
    verifier, _ = read_canonical(context["roots"]["staging"] / "verifier_terminal.json"); _validate(verifier,context["schemas"],"verifier_terminal")
    if report.get("status") != "PASS" or not (driver["structural_snapshot_digest"]==report["structural_snapshot_digest"]==verifier["structural_snapshot_digest"]): raise Driver11Error("REPORT_NOT_PASS_OR_DIGEST_MISMATCH")
    entries = [{"path":name,"sha256":sha_file(context["roots"]["staging"] / name)} for name in ("driver_shape_snapshot.json","independent_shape_report.json","verifier_terminal.json")]
    package_value = {"schema_version":"gen_enc_b1_r11_shape_package_v1","record_kind":"SEALED_AUTHORITY_SHAPE_ONLY_PACKAGE","task_id":TASK_ID,"batch_id":"B1","run_id":context["release"]["run_id"],"status":"SEALED_AWAITING_GUARDIAN_RESULT_REVIEW","entry_count":3,"entries":entries,"structural_snapshot_digest":report["structural_snapshot_digest"],"authority_read_count":26,"member_count":0,"scientific_artifact_count":0,"publication_count":0,"final_test_read":False}
    _validate(package_value, context["schemas"], "shape_package")
    package_path=context["roots"]["package"] / "SHAPE_PACKAGE.json"
    if package_path.exists():
        existing,_=read_canonical(package_path);_validate(existing,context["schemas"],"shape_package")
        if existing!=package_value:raise Driver11Error("CONFLICTING_EXISTING_PACKAGE")
    else:_write_exclusive(package_path, package_value)
    terminal = {"schema_version":"gen_enc_b1_r11_terminal_v1","record_kind":"SHAPE_RUN_TERMINAL","task_id":TASK_ID,"batch_id":"B1","run_id":context["release"]["run_id"],"status":"SUCCESS_SHAPE_ONLY_AWAITING_GUARDIAN_RESULT_SEAL","reason":None,"authority_read_count":26,"driver_read_count":13,"verifier_read_count":13,"shape_package_count":1,"member_count":0,"scientific_artifact_count":0,"publication_count":0,"scientific_hypothesis_status":"NOT_TESTED","final_test_read":False}
    _validate(terminal, context["schemas"], "terminal"); _write_exclusive(context["roots"]["terminal"] / "TERMINAL.json", terminal)
    return {"status":terminal["status"],"authority_read_count":26,"structural_snapshot_digest":report["structural_snapshot_digest"]}


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(); p.add_argument("command",choices=["shape-preflight","extract-shape","package-shape"])
    for name in ("repo-root","release","guardian-attestation","dispatch","schema-root"): p.add_argument("--"+name,required=True,type=Path)
    return p


def main(argv: Sequence[str] | None=None) -> int:
    raw=list(sys.argv[1:] if argv is None else argv); ns=parser().parse_args(raw); context=None
    try:
        context=gate(ns.repo_root.resolve(),ns,raw)
        result=preflight(context) if ns.command=="shape-preflight" else extract(context) if ns.command=="extract-shape" else package(context)
        print(json.dumps(result,sort_keys=True)); return 0
    except BaseException as exc:
        if context is not None and ns.command!="shape-preflight": _write_failure(context,type(exc).__name__+":"+str(exc))
        print(json.dumps({"status":"FAIL_CLOSED","error":type(exc).__name__+":"+str(exc),"authority_read_count":0 if context is None else _receipt_count(context)},sort_keys=True),file=sys.stderr); return 2


if __name__=="__main__": raise SystemExit(main())
