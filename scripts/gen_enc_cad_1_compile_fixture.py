import argparse
import ast
import datetime
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from acoustic_encoder.gen_enc.cad_mapping import audit_static, canonical_json_bytes, compile_mapping

DISPATCH_ROOT = "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/dispatch/GEN_ENC_CAD_1/"
DISPATCH_SCHEMA = "schemas/gen_enc/gen_enc_cad_1/dispatch_authorization.schema.json"
DISPATCH_SCHEMA_SHA256 = "f21d49c86fb0f2dcaa7d6d47e3f0d06ed35555a885b64683e7b01a52d55cc75a"
BOUNDARY_PROFILE_SHA256 = "4b30217bc150d8d47fb5dfb4203a67f5286246d1d9f3e118a52c532592bcc258"
SEALED_MANIFEST_PATH = "tests/fixtures/gen_enc_cad_1/complete_fixture_manifest.json"
SEALED_MANIFEST_SHA256 = "0c5944324535ae082c1246765e10a63d3c8035906476ccc175133a2102cfc521"
SEALED_MANIFEST_BYTE_LENGTH = 21334
SEALED_MANIFEST_DESCRIPTOR = "UTF8_NO_BOM_RECURSIVE_UNICODE_KEY_SORT_ARRAYS_PRESERVED_SHORTEST_ROUNDTRIP_FINITE_BINARY64_NO_WHITESPACE_WITH_EXACTLY_ONE_TRAILING_LF_EXCEPTION_FOR_THIS_SEALED_MANIFEST"
TASK_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
CORRECTED_REVISED_PATHS = {
    "revised_contract_path": "docs/experiment/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT_PROPOSAL_REV03_CORR02.md",
    "revised_progress_path": "docs/progress/GEN_ENC_CAD_1_PHASE_A_CONTRACT_PROPOSAL_REV03_CORR02.md",
    "revised_manifest_path": "outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/phase_a_rev03_corr02/SHA256SUMS.txt",
}
SUCCESS = ["compiled_mapping.json", "static_audit.json", "verification_report.json", "audit_log.json", "source_hash_manifest.json", "schema_hash_manifest.json", "fixture_hash_manifest.json", "complete_run_manifest.json", "result_summary.json", "artifact_inventory.json", "SHA256SUMS.txt"]
SUCCESS_ROOT_AUTHORITY_EXACT = "outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/phase_b/technical/"
NULL_SUBJECTS = {"FX_HASH_MISMATCH", "FX_SCHEMA_MISSING_FIELD", "FX_SCHEMA_EXTRA_FIELD", "FX_CANONICAL_NONFINITE", "FX_AUTHORIZATION_MISSING", "FX_AUTHORIZATION_WRONG_CONTRACT", "FX_AUTHORIZATION_WRONG_SCOPE", "FX_PATH_SYMLINK_ESCAPE", "FX_PATH_JUNCTION_ESCAPE", "FX_OUTPUT_UNLISTED", "FX_OUTPUT_COLLISION", "FX_VERIFIER_FORBIDDEN_IMPORT"}


class _WindowsExtendedPathAdapter:
    _PREFIX = "\\\\?\\"
    _REPARSE = 0x400

    def __init__(self, repository_root):
        root = pathlib.Path(repository_root)
        root_text = str(root)
        if (
            os.name != "nt"
            or len(root_text) < 3
            or not root_text[0].isalpha()
            or root_text[1:3] != ":\\"
            or root_text.startswith((self._PREFIX, "\\\\", "\\\\.\\"))
            or not root.is_absolute()
        ):
            raise ValueError("PATH_REPOSITORY_ROOT_INVALID")
        self.root = root
        self.root_text = root_text.rstrip("\\")
        self.root_extended = self._PREFIX + self.root_text
        root_stat = os.lstat(self.root_extended)
        self._reject_reparse(root_stat)
        self._root_identity = self._identity(root_stat)
        self._owned = set()

    @staticmethod
    def _identity(value):
        return (
            value.st_mode,
            value.st_dev,
            value.st_ino,
            getattr(value, "st_file_attributes", 0),
            getattr(value, "st_reparse_tag", 0),
        )

    def _reject_reparse(self, value):
        attributes = getattr(value, "st_file_attributes", 0)
        tag = getattr(value, "st_reparse_tag", 0)
        if attributes & self._REPARSE or tag:
            raise ValueError("PATH_REPARSE_POINT_FORBIDDEN")

    def _derive(self, logical):
        if not isinstance(logical, str) or not logical:
            raise ValueError("PATH_LOGICAL_RELATIVE_REQUIRED")
        folded = logical.casefold()
        if (
            logical.startswith(("/", "\\"))
            or "\\" in logical
            or ":" in logical
            or any(token in logical for token in ("*", "?", "[", "]", "%", "$", "~", "\x00"))
            or "globalroot" in folded
        ):
            raise ValueError("PATH_NAMESPACE_OR_EXPANSION_FORBIDDEN")
        components = logical.split("/")
        if any(not part or part in (".", "..") or len(part) >= 255 for part in components):
            raise ValueError("PATH_COMPONENT_INVALID")
        normal = self.root.joinpath(*components)
        normal_text = str(normal)
        if os.path.commonpath((self.root_text, normal_text)) != self.root_text:
            raise ValueError("PATH_OUTSIDE_REPOSITORY")
        extended = self._PREFIX + normal_text
        if extended[len(self._PREFIX):] != normal_text:
            raise ValueError("PATH_IDENTITY_OR_BOUNDARY_MISMATCH")
        return components, normal_text, extended

    def representations(self, logical):
        unused, normal, extended = self._derive(logical)
        return normal, extended, logical

    def _capture(self, logical):
        components, normal, extended = self._derive(logical)
        records = []
        parent_identity = None
        for index in range(-1, len(components)):
            current_normal = self.root_text if index < 0 else str(self.root.joinpath(*components[: index + 1]))
            current_extended = self._PREFIX + current_normal
            try:
                value = os.lstat(current_extended)
            except FileNotFoundError:
                return {"logical": logical, "normal": normal, "extended": extended, "records": records, "exists": False, "missing_index": index, "parent_identity": parent_identity}
            self._reject_reparse(value)
            identity = self._identity(value)
            if index < 0 and identity != self._root_identity:
                raise ValueError("PATH_IDENTITY_OR_BOUNDARY_MISMATCH")
            records.append((index, current_normal, current_extended, identity, parent_identity))
            parent_identity = (value.st_dev, value.st_ino)
        return {"logical": logical, "normal": normal, "extended": extended, "records": records, "exists": True, "missing_index": None, "parent_identity": parent_identity}

    def _recheck(self, snapshot):
        unused, normal, extended = self._derive(snapshot["logical"])
        if normal != snapshot["normal"] or extended != snapshot["extended"]:
            raise ValueError("PATH_IDENTITY_OR_BOUNDARY_MISMATCH")
        checked_value = None
        for unused_index, unused_normal, current_extended, identity, unused_parent in snapshot["records"]:
            try:
                value = os.lstat(current_extended)
            except FileNotFoundError as exc:
                raise ValueError("PATH_IDENTITY_OR_BOUNDARY_MISMATCH") from exc
            self._reject_reparse(value)
            if self._identity(value) != identity:
                raise ValueError("PATH_IDENTITY_OR_BOUNDARY_MISMATCH")
            checked_value = value
        if not snapshot["exists"]:
            try:
                os.lstat(snapshot["extended"])
            except FileNotFoundError:
                return snapshot
            raise ValueError("PATH_IDENTITY_OR_BOUNDARY_MISMATCH")
        snapshot["checked_stat"] = checked_value
        return snapshot

    def _guard(self, logical, must_exist=None):
        snapshot = self._recheck(self._capture(logical))
        if must_exist is True and not snapshot["exists"]:
            raise FileNotFoundError(logical)
        if must_exist is False and snapshot["exists"]:
            raise FileExistsError(logical)
        return snapshot

    def exists(self, logical):
        return self._guard(logical)["exists"]

    def is_file(self, logical):
        snapshot = self._guard(logical)
        return snapshot["exists"] and snapshot["records"][-1][3][0] & 0o170000 == 0o100000

    def is_dir(self, logical):
        snapshot = self._guard(logical)
        return snapshot["exists"] and snapshot["records"][-1][3][0] & 0o170000 == 0o040000

    def lstat(self, logical):
        snapshot = self._guard(logical, True)
        return snapshot["checked_stat"]

    def read_bytes(self, logical):
        snapshot = self._guard(logical, True)
        with open(snapshot["extended"], "rb") as handle:
            return handle.read()

    def read_text(self, logical, encoding="utf-8"):
        return self.read_bytes(logical).decode(encoding)

    def sha256(self, logical):
        digest = hashlib.sha256()
        snapshot = self._guard(logical, True)
        with open(snapshot["extended"], "rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def mkdir(self, logical, parents=False, exist_ok=False):
        components, unused_normal, unused_extended = self._derive(logical)
        targets = ["/".join(components[:index]) for index in range(1, len(components) + 1)] if parents else [logical]
        for target in targets:
            snapshot = self._guard(target)
            if snapshot["exists"]:
                if not self.is_dir(target) or (target == logical and not exist_ok):
                    raise FileExistsError(target)
                continue
            snapshot = self._guard(target, False)
            os.mkdir(snapshot["extended"])
            self._owned.add(target)

    def write_exclusive(self, logical, raw):
        parent = logical.rsplit("/", 1)[0]
        self.mkdir(parent, parents=True, exist_ok=True)
        snapshot = self._guard(logical, False)
        with open(snapshot["extended"], "xb") as handle:
            self._owned.add(logical)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())

    def replace(self, source, destination):
        source_snapshot = self._capture(source)
        destination_snapshot = self._capture(destination)
        self._recheck(destination_snapshot)
        self._recheck(source_snapshot)
        if not source_snapshot["exists"]:
            raise FileNotFoundError(source)
        os.replace(source_snapshot["extended"], destination_snapshot["extended"])
        self._owned.discard(source)
        self._owned.add(destination)

    def unlink(self, logical, require_owned=False):
        if require_owned and logical not in self._owned:
            raise ValueError("PATH_NOT_OWNED")
        snapshot = self._guard(logical, True)
        os.unlink(snapshot["extended"])
        self._owned.discard(logical)

    def rmdir(self, logical, require_owned=False):
        if require_owned and logical not in self._owned:
            raise ValueError("PATH_NOT_OWNED")
        snapshot = self._guard(logical, True)
        os.rmdir(snapshot["extended"])
        self._owned.discard(logical)

    def list_files(self, logical):
        observed = set()
        pending = [logical]
        while pending:
            current = pending.pop()
            snapshot = self._guard(current, True)
            with os.scandir(snapshot["extended"]) as entries:
                names = sorted(entry.name for entry in entries)
            for name in names:
                child = current + "/" + name
                if self.is_dir(child):
                    pending.append(child)
                elif self.is_file(child):
                    observed.add(child)
                else:
                    raise ValueError("PATH_OBJECT_TYPE_FORBIDDEN")
        return observed


PATHS = _WindowsExtendedPathAdapter(REPO)


def _schema_validate(value, schema):
    if "const" in schema and value != schema["const"]:
        raise ValueError("DISPATCH_SCHEMA_CONST_MISMATCH")
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            raise ValueError("DISPATCH_SCHEMA_TYPE_MISMATCH")
        required = set(schema.get("required", ()))
        if not required.issubset(value):
            raise ValueError("DISPATCH_SCHEMA_REQUIRED_MISSING")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and not set(value).issubset(properties):
            raise ValueError("DISPATCH_SCHEMA_ADDITIONAL_PROPERTY")
        for key, child in value.items():
            if key in properties:
                _schema_validate(child, properties[key])
    elif expected_type == "array" and not isinstance(value, list):
        raise ValueError("DISPATCH_SCHEMA_TYPE_MISMATCH")
    elif expected_type == "boolean" and not isinstance(value, bool):
        raise ValueError("DISPATCH_SCHEMA_TYPE_MISMATCH")


def _utc(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value) is None:
        raise ValueError("AUTHORIZATION_TIMESTAMP_INVALID")
    return datetime.datetime.fromisoformat(value[:-1] + "+00:00")


def _boundary_profile(value, dispatch, task):
    if isinstance(value, dict):
        return {key: "<AUTHORITY_CHAIN>" if key == "authority_hash_chain" else _boundary_profile(child, dispatch, task) for key, child in value.items()}
    if isinstance(value, list):
        return [_boundary_profile(child, dispatch, task) for child in value]
    if isinstance(value, str):
        return value.replace(dispatch, "<DISPATCH>").replace(task, "<TASK>")
    return value


def _validate_dispatch(repository_root, relative, task_id, mode, enforce_process_cwd=False):
    if not isinstance(task_id, str) or TASK_PATTERN.fullmatch(task_id) is None:
        raise ValueError("TASK_ID_INVALID")
    expected_relative = DISPATCH_ROOT + f"GEN_ENC_CAD_1_PHASE_B_TASK_{task_id}.dispatch_authorization.json"
    if relative != expected_relative:
        raise ValueError("AUTHORIZATION_SCOPE_MISMATCH")
    paths = _WindowsExtendedPathAdapter(pathlib.Path(repository_root).resolve())
    raw = paths.read_bytes(relative)
    schema_raw = paths.read_bytes(DISPATCH_SCHEMA)
    if hashlib.sha256(schema_raw).hexdigest() != DISPATCH_SCHEMA_SHA256:
        raise ValueError("DISPATCH_SCHEMA_HASH_MISMATCH")
    try:
        schema = json.loads(schema_raw)
        record = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("DISPATCH_JSON_INVALID") from exc
    if canonical_json_bytes(record) != raw:
        raise ValueError("DISPATCH_CANONICAL_BYTES_INVALID")
    _schema_validate(record, schema)
    if set(record) != set(schema["required"]):
        raise ValueError("DISPATCH_PROPERTY_SET_INVALID")
    if (
        record["schema_version"] != "gen_enc_cad_1_dispatch_authorization_v1"
        or record["record_type"] != "GEN_ENC_CAD_1_IMPLEMENTATION_DISPATCH_AUTHORIZATION"
        or record["record_id"] != f"GEN_ENC_CAD_1_PHASE_B_TASK_{task_id}"
        or record["issuer_role"] != "GEN_ENC_INTERMEDIATE_CONTROLLER"
        or record["issuer_thread_id"] != "01a0452b-ee9f-7ce0-a671-78d80cb069fe"
        or record["allowed_task_id"] != task_id
        or record["allowed_modes"] != ["preflight", "compile", "verify", "package-results"]
        or mode not in record["allowed_modes"]
    ):
        raise ValueError("AUTHORIZATION_SCOPE_MISMATCH")
    now = datetime.datetime.now(datetime.timezone.utc)
    if not (_utc(record["issued_at_utc"]) <= now < _utc(record["expires_at_utc"])) or record["revoked"] is not False:
        raise ValueError("AUTHORIZATION_STATE_INVALID")
    if record["guardian_decision"] not in {"GUARDIAN_APPROVE", "GUARDIAN_APPROVE_WITH_REQUIRED_DISCLOSURES"} or record["guardian_implementation_execution_authorized"] is not True:
        raise ValueError("GUARDIAN_AUTHORIZATION_INVALID")
    for key, expected in CORRECTED_REVISED_PATHS.items():
        if record[key] != expected:
            raise ValueError("CORRECTED_AUTHORITY_PATH_MISMATCH")
    chain = record["exact_boundaries"].get("authority_hash_chain")
    if not isinstance(chain, list) or len(chain) < 4:
        raise ValueError("AUTHORITY_CHAIN_INCOMPLETE")
    seen_roles, seen_paths, bound = set(), set(), set()
    for entry in chain:
        if not isinstance(entry, dict) or not {"role", "path", "sha256"}.issubset(entry) or not all(isinstance(entry[key], str) for key in ("role", "path", "sha256")):
            raise ValueError("AUTHORITY_CHAIN_ENTRY_INVALID")
        if not entry["role"] or entry["role"] in seen_roles or entry["path"] in seen_paths or re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is None:
            raise ValueError("AUTHORITY_CHAIN_ENTRY_INVALID")
        seen_roles.add(entry["role"]); seen_paths.add(entry["path"])
        if paths.sha256(entry["path"]) != entry["sha256"]:
            raise ValueError("AUTHORITY_HASH_MISMATCH")
        bound.add((entry["path"], entry["sha256"]))
    for path_key, hash_key in (("guardian_review_path", "guardian_review_sha256"), ("revised_contract_path", "revised_contract_sha256"), ("revised_progress_path", "revised_progress_sha256"), ("revised_manifest_path", "revised_manifest_sha256")):
        if (record[path_key], record[hash_key]) not in bound:
            raise ValueError("AUTHORITY_CHAIN_BINDING_MISSING")
    boundaries = record["exact_boundaries"]
    if boundaries.get("dispatch_record_path") != relative:
        raise ValueError("AUTHORIZATION_SCOPE_MISMATCH")
    if hashlib.sha256(canonical_json_bytes(_boundary_profile(boundaries, relative, task_id))).hexdigest() != BOUNDARY_PROFILE_SHA256:
        raise ValueError("EXACT_BOUNDARIES_MISMATCH")
    root_text = str(pathlib.Path(repository_root).resolve())
    if record["working_directory"] != root_text or (enforce_process_cwd and str(pathlib.Path.cwd().resolve()) != root_text):
        raise ValueError("WORKING_DIRECTORY_MISMATCH")
    runtime = record["runtime_binding"]
    if runtime != {"float": "IEEE754_BINARY64_ROUND_TO_NEAREST_TIES_TO_EVEN", "implementation": "CPython", "machine": ["AMD64", "x86_64"], "observed_match_required": True, "os": "Windows", "sys_platform": "win32", "version": "3.12.4"}:
        raise ValueError("RUNTIME_BINDING_INVALID")
    if platform.python_implementation() != "CPython" or platform.python_version() != "3.12.4" or sys.platform != "win32" or platform.machine() not in runtime["machine"]:
        raise ValueError("FAIL_RUNTIME_BINDING")
    expected_top = {
        "implementation_source_creation_authorized": True, "executable_schema_creation_authorized": True,
        "literal_fixture_creation_authorized": True, "literal_fixture_execution_authorized": True,
        "implementation_execution_authorized": True, "technical_conformance_preflight_authorized": True,
        "timing_preflight_authorized": False,
    }
    if any(record[key] is not value for key, value in expected_top.items()):
        raise ValueError("AUTHORIZATION_MATRIX_INVALID")
    expected_formal = {
        "cad_kernel_authorized": False, "comsol_authorized": False, "development_validation_final_test_access_authorized": False,
        "evidence_level_ceiling": "E1_TECHNICAL_CONFORMANCE_ONLY", "final_test_read": False, "formal_generator_authorized": False,
        "formal_geometry_authorized": False, "formal_identity_authorized": False, "formal_row_authorized": False, "formal_seed_authorized": False,
        "full_wave_authorized": False, "gen_enc_2_authorized": False, "physical_experiment_authorized": False, "science_data_access_authorized": False,
        "scientific_hypothesis_status": "NOT_TESTED", "scientific_identity_generation_authorized": False, "static_eligibility_authorized": False,
        "technical_phase_b_authorized": True, "timing_or_performance_evaluation_authorized": False,
    }
    if record["formal_authorizations"] != expected_formal or not isinstance(boundaries.get("required_disclosures"), list) or not boundaries["required_disclosures"]:
        raise ValueError("AUTHORIZATION_MATRIX_INVALID")
    return record, raw


def fail(reason):
    print(reason, file=sys.stderr)
    raise SystemExit(2)


def read_json(path):
    return json.loads(PATHS.read_bytes(path))


def run_id_for(auth_raw, task, manifest_raw):
    a = hashlib.sha256(auth_raw).hexdigest()
    f = hashlib.sha256(manifest_raw).hexdigest()
    return hashlib.sha256(f"GEN_ENC_CAD_1_RUN_ID_V1\n{a}\n{task}\n{f}".encode("ascii")).hexdigest()


def _validate_manifest_envelope(boundaries, relative, raw):
    expected = {
        "canonical_bytes": SEALED_MANIFEST_DESCRIPTOR,
        "order": "EXACT_REV01_FIXTURE_ARRAY_ORDER_ORDINAL_1_TO_42",
        "path": SEALED_MANIFEST_PATH,
        "record_count": 42,
        "schema": "schemas/gen_enc/gen_enc_cad_1/complete_fixture_manifest.schema.json",
    }
    declarations = [
        entry for entry in boundaries.get("authority_hash_chain", [])
        if entry.get("path") == SEALED_MANIFEST_PATH and entry.get("role") == "COMPLETE_FIXTURE_MANIFEST_42"
    ]
    if boundaries.get("complete_fixture_manifest") != expected or relative != SEALED_MANIFEST_PATH:
        raise ValueError("COMPLETE_FIXTURE_MANIFEST_ENVELOPE_INVALID")
    if len(declarations) != 1 or declarations[0].get("sha256") != SEALED_MANIFEST_SHA256:
        raise ValueError("COMPLETE_FIXTURE_MANIFEST_DECLARED_HASH_INVALID")
    if len(raw) != SEALED_MANIFEST_BYTE_LENGTH or hashlib.sha256(raw).hexdigest() != SEALED_MANIFEST_SHA256:
        raise ValueError("COMPLETE_FIXTURE_MANIFEST_ACTUAL_HASH_OR_LENGTH_INVALID")
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise ValueError("COMPLETE_FIXTURE_MANIFEST_TERMINAL_LF_INVALID")
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("COMPLETE_FIXTURE_MANIFEST_JSON_INVALID") from exc
    if canonical_json_bytes(manifest) + b"\n" != raw:
        raise ValueError("COMPLETE_FIXTURE_MANIFEST_CANONICAL_PAYLOAD_INVALID")
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 42 or [item.get("ordinal") for item in records] != list(range(1, 43)):
        raise ValueError("COMPLETE_FIXTURE_MANIFEST_ORDER_INVALID")
    return manifest


def _validate_manifest_then_run_id(auth_raw, task, boundaries, relative, manifest_raw):
    manifest = _validate_manifest_envelope(boundaries, relative, manifest_raw)
    return manifest, run_id_for(auth_raw, task, manifest_raw)


def stage_path(run_id, name):
    return f"outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/phase_b/.staging/{run_id}/{name}.stage.{run_id}.tmp"


def stage_root(run_id):
    return f"outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/phase_b/.staging/{run_id}"


def validate_common(args):
    try:
        record, raw = _validate_dispatch(REPO, args.authorization_record, args.task_id, args.mode, enforce_process_cwd=True)
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        fail(str(exc))
    manifest_raw = PATHS.read_bytes(args.fixture_manifest)
    try:
        manifest, derived = _validate_manifest_then_run_id(raw, args.task_id, record["exact_boundaries"], args.fixture_manifest, manifest_raw)
    except (KeyError, TypeError, ValueError) as exc:
        fail(str(exc))
    if args.run_id != derived:
        fail("RUN_ID_MISMATCH")
    for item in manifest["records"]:
        data = PATHS.read_bytes(item["fixture_path"])
        if hashlib.sha256(data).hexdigest() != item["fixture_sha256"]:
            fail("FIXTURE_HASH_MISMATCH")
        fixture = json.loads(data)
        expected = fixture["expected"]
        if expected["observed_subject_status"] != item["expected_observed_subject_status"] or expected["ordered_reason_codes"] != item["expected_ordered_reason_codes"]:
            fail("FIXTURE_EXPECTATION_BINDING_MISMATCH")
    return record, manifest


def exact_files(root, expected):
    if not PATHS.exists(root):
        return expected == set()
    return PATHS.list_files(root) == expected


def gate_b(record, manifest):
    expected_sources = set(record["exact_boundaries"]["source_paths_exact"])
    expected_schemas = set(record["exact_boundaries"]["executable_schema_paths_exact"])
    expected_fixtures = set(record["exact_boundaries"]["literal_fixture_paths_exact"] + [record["exact_boundaries"]["complete_fixture_manifest"]["path"]])
    for path in expected_sources | expected_schemas | expected_fixtures | {record["exact_boundaries"]["test_path_exact"]}:
        if not PATHS.is_file(path):
            fail("GATE_B_EXPECTED_PATH_MISSING")
    if not exact_files("src/acoustic_encoder/gen_enc/cad_mapping", {p for p in expected_sources if p.startswith("src/")}):
        fail("GATE_B_UNLISTED_SOURCE")
    if not exact_files("schemas/gen_enc/gen_enc_cad_1", expected_schemas):
        fail("GATE_B_UNLISTED_SCHEMA")
    if not exact_files("tests/fixtures/gen_enc_cad_1", expected_fixtures):
        fail("GATE_B_UNLISTED_FIXTURE")
    for path in expected_schemas:
        schema = read_json(path)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or schema.get("type") not in ("object", "array"):
            fail("SCHEMA_META_INVALID")
    verifier = PATHS.read_text("scripts/gen_enc_cad_1_verify_fixture.py")
    permitted = set(record["exact_boundaries"]["independent_verifier"]["permitted_imports_exact"])
    for node in ast.walk(ast.parse(verifier)):
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        else:
            continue
        if any(name not in permitted for name in names):
            fail("VERIFIER_IMPORT_FORBIDDEN")
    forbidden = ["subprocess", "socket", "requests", "ctypes", "importlib", "eval(", "exec(", "cad_mapping", "gen_enc_2c"]
    if any(token in verifier for token in forbidden):
        fail("VERIFIER_CAPABILITY_FORBIDDEN")
    return True


def write_exclusive(path, value):
    raw = canonical_json_bytes(value)
    PATHS.write_exclusive(path, raw)


def compile_all(args, record, manifest):
    root = stage_root(args.run_id)
    if PATHS.exists(root):
        fail("OUTPUT_COLLISION")
    PATHS.mkdir(root, parents=True, exist_ok=False)
    compiled_records, audit_records = [], []
    try:
        for item in manifest["records"]:
            fixture = read_json(item["fixture_path"])
            subject = None if item["fixture_id"] in NULL_SUBJECTS else compile_mapping(fixture)
            static_subject = None if subject is None else audit_static(subject)
            compiled_records.append({"ordinal": item["ordinal"], "fixture_id": item["fixture_id"], "compiled_mapping_subject": subject})
            audit_records.append({"ordinal": item["ordinal"], "fixture_id": item["fixture_id"], "static_audit_subject": static_subject})
        envelope = {"evidence_level": "E1_TECHNICAL_CONFORMANCE_ONLY", "scientific_hypothesis_status": "NOT_TESTED", "formal_instance_count": 0, "final_test_read": False}
        write_exclusive(stage_path(args.run_id, "compiled_mapping.json"), {**envelope, "records": compiled_records})
        write_exclusive(stage_path(args.run_id, "static_audit.json"), {**envelope, "records": audit_records})
    except Exception:
        for name in ("compiled_mapping.json", "static_audit.json"):
            candidate = stage_path(args.run_id, name)
            if PATHS.exists(candidate):
                PATHS.unlink(candidate, require_owned=True)
        if PATHS.exists(root):
            PATHS.rmdir(root, require_owned=True)
        raise


def package(args, record):
    authority_root = record["exact_boundaries"]["success_root_exact"]
    if (
        not isinstance(authority_root, str)
        or authority_root != SUCCESS_ROOT_AUTHORITY_EXACT
        or not authority_root.endswith("/")
        or authority_root.endswith("//")
    ):
        fail("PACKAGE_RESULTS_SUCCESS_ROOT_AUTHORITY_MISMATCH")
    target = authority_root[:-1]
    children = [target + "/" + name for name in SUCCESS]
    expected = stage_path(args.run_id, "complete_run_manifest.json")
    if args.complete_run_manifest != expected:
        fail("COMPLETE_RUN_MANIFEST_PATH_MISMATCH")
    run = json.loads(PATHS.read_bytes(expected))
    if len(run["records"]) != 42 or any(r["fixture_run_status"] != "PASS_EXPECTATION_MATCH" for r in run["records"]):
        fail("INCOMPLETE_OR_FAILED_RUN")
    if PATHS.exists(target):
        fail("OUTPUT_COLLISION")
    PATHS.mkdir(target, parents=True, exist_ok=False)
    for name, child in zip(SUCCESS, children, strict=True):
        PATHS.replace(stage_path(args.run_id, name), child)
    PATHS.rmdir(stage_root(args.run_id))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "compile", "package-results"))
    parser.add_argument("--authorization-record", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--fixture-manifest", default="tests/fixtures/gen_enc_cad_1/complete_fixture_manifest.json")
    parser.add_argument("--complete-run-manifest")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    record, manifest = validate_common(args)
    gate_b(record, manifest)
    if args.mode == "compile":
        compile_all(args, record, manifest)
    elif args.mode == "package-results":
        package(args, record)
    else:
        print("GATE_A_PASS GATE_B_PASS")


if __name__ == "__main__":
    main()
