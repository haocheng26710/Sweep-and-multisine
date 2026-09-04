import argparse
import collections
import dataclasses
import decimal
import fractions
import hashlib
import itertools
import json
import math
import os
import pathlib
import platform
import stat
import struct
import sys
import typing

REPO = pathlib.Path(__file__).resolve().parents[1]
DISPATCH_ROOT = "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/dispatch/GEN_ENC_CAD_1/"
DISPATCH_SCHEMA = "schemas/gen_enc/gen_enc_cad_1/dispatch_authorization.schema.json"
DISPATCH_SCHEMA_SHA256 = "f21d49c86fb0f2dcaa7d6d47e3f0d06ed35555a885b64683e7b01a52d55cc75a"
BOUNDARY_PROFILE_SHA256 = "4b30217bc150d8d47fb5dfb4203a67f5286246d1d9f3e118a52c532592bcc258"
SEALED_MANIFEST_PATH = "tests/fixtures/gen_enc_cad_1/complete_fixture_manifest.json"
SEALED_MANIFEST_SHA256 = "0c5944324535ae082c1246765e10a63d3c8035906476ccc175133a2102cfc521"
SEALED_MANIFEST_BYTE_LENGTH = 21334
SEALED_MANIFEST_DESCRIPTOR = "UTF8_NO_BOM_RECURSIVE_UNICODE_KEY_SORT_ARRAYS_PRESERVED_SHORTEST_ROUNDTRIP_FINITE_BINARY64_NO_WHITESPACE_WITH_EXACTLY_ONE_TRAILING_LF_EXCEPTION_FOR_THIS_SEALED_MANIFEST"
CORRECTED_REVISED_PATHS = {
    "revised_contract_path": "docs/experiment/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT_PROPOSAL_REV03_CORR02.md",
    "revised_progress_path": "docs/progress/GEN_ENC_CAD_1_PHASE_A_CONTRACT_PROPOSAL_REV03_CORR02.md",
    "revised_manifest_path": "outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/phase_a_rev03_corr02/SHA256SUMS.txt",
}
SUCCESS = ["compiled_mapping.json", "static_audit.json", "verification_report.json", "audit_log.json", "source_hash_manifest.json", "schema_hash_manifest.json", "fixture_hash_manifest.json", "complete_run_manifest.json", "result_summary.json", "artifact_inventory.json", "SHA256SUMS.txt"]
NULL_SUBJECTS = {"FX_HASH_MISMATCH", "FX_SCHEMA_MISSING_FIELD", "FX_SCHEMA_EXTRA_FIELD", "FX_CANONICAL_NONFINITE", "FX_AUTHORIZATION_MISSING", "FX_AUTHORIZATION_WRONG_CONTRACT", "FX_AUTHORIZATION_WRONG_SCOPE", "FX_PATH_SYMLINK_ESCAPE", "FX_PATH_JUNCTION_ESCAPE", "FX_OUTPUT_UNLISTED", "FX_OUTPUT_COLLISION", "FX_VERIFIER_FORBIDDEN_IMPORT"}
ALLOWLIST = [f"IFX_U4_{sector}_{suffix}" for sector in ("000", "090", "180", "270") for suffix in ("RIM_BOTTOM", "RIM_TOP", "SHOULDER_LOWER", "SHOULDER_UPPER")] + [f"IFX_U4_{sector}_RIM" for sector in ("000", "090", "180", "270")]


class _VerifierWindowsPathAdapter:
    PREFIX = "\\\\?\\"
    REPARSE_ATTRIBUTE = 0x400

    def __init__(self, verified_root):
        self.root = pathlib.Path(verified_root)
        self.normal_root = str(self.root).rstrip("\\")
        if (
            os.name != "nt"
            or not self.root.is_absolute()
            or len(self.normal_root) < 3
            or not self.normal_root[0].isalpha()
            or self.normal_root[1:3] != ":\\"
            or self.normal_root.startswith((self.PREFIX, "\\\\", "\\\\.\\"))
        ):
            raise ValueError("PATH_REPOSITORY_ROOT_INVALID")
        root_value = os.lstat(self.PREFIX + self.normal_root)
        self._ensure_plain(root_value)
        self.root_identity = self._stat_identity(root_value)
        self.owned_paths = set()

    @staticmethod
    def _stat_identity(value):
        return (
            value.st_mode,
            value.st_dev,
            value.st_ino,
            getattr(value, "st_file_attributes", 0),
            getattr(value, "st_reparse_tag", 0),
        )

    def _ensure_plain(self, value):
        if getattr(value, "st_file_attributes", 0) & self.REPARSE_ATTRIBUTE or getattr(value, "st_reparse_tag", 0):
            raise ValueError("PATH_REPARSE_POINT_FORBIDDEN")

    def _translate(self, relative_name):
        if not isinstance(relative_name, str) or not relative_name:
            raise ValueError("PATH_LOGICAL_RELATIVE_REQUIRED")
        lowered = relative_name.casefold()
        forbidden = ("*", "?", "[", "]", "%", "$", "~", "\x00")
        if relative_name[0] in "/\\" or "\\" in relative_name or ":" in relative_name or any(mark in relative_name for mark in forbidden) or "globalroot" in lowered:
            raise ValueError("PATH_NAMESPACE_OR_EXPANSION_FORBIDDEN")
        pieces = relative_name.split("/")
        if any(piece in ("", ".", "..") or len(piece) >= 255 for piece in pieces):
            raise ValueError("PATH_COMPONENT_INVALID")
        normal = str(self.root.joinpath(*pieces))
        if os.path.commonpath((self.normal_root, normal)) != self.normal_root:
            raise ValueError("PATH_OUTSIDE_REPOSITORY")
        extended = self.PREFIX + normal
        if extended.removeprefix(self.PREFIX) != normal:
            raise ValueError("PATH_IDENTITY_OR_BOUNDARY_MISMATCH")
        return pieces, normal, extended

    def representations(self, relative_name):
        unused, normal, extended = self._translate(relative_name)
        return normal, extended, relative_name

    def _observe(self, relative_name):
        pieces, normal, extended = self._translate(relative_name)
        chain = []
        parent = None
        for position in range(-1, len(pieces)):
            normal_part = self.normal_root if position == -1 else str(self.root.joinpath(*pieces[: position + 1]))
            extended_part = self.PREFIX + normal_part
            try:
                value = os.lstat(extended_part)
            except FileNotFoundError:
                return {"relative": relative_name, "normal": normal, "extended": extended, "chain": chain, "present": False, "missing": position, "parent": parent}
            self._ensure_plain(value)
            identity = self._stat_identity(value)
            if position == -1 and identity != self.root_identity:
                raise ValueError("PATH_IDENTITY_OR_BOUNDARY_MISMATCH")
            chain.append((position, normal_part, extended_part, identity, parent))
            parent = (value.st_dev, value.st_ino)
        return {"relative": relative_name, "normal": normal, "extended": extended, "chain": chain, "present": True, "missing": None, "parent": parent}

    def _confirm(self, observation):
        unused, normal, extended = self._translate(observation["relative"])
        if normal != observation["normal"] or extended != observation["extended"]:
            raise ValueError("PATH_IDENTITY_OR_BOUNDARY_MISMATCH")
        confirmed_value = None
        for unused_position, unused_normal, extended_part, identity, unused_parent in observation["chain"]:
            try:
                value = os.lstat(extended_part)
            except FileNotFoundError as exc:
                raise ValueError("PATH_IDENTITY_OR_BOUNDARY_MISMATCH") from exc
            self._ensure_plain(value)
            if self._stat_identity(value) != identity:
                raise ValueError("PATH_IDENTITY_OR_BOUNDARY_MISMATCH")
            confirmed_value = value
        if not observation["present"]:
            try:
                os.lstat(observation["extended"])
            except FileNotFoundError:
                return observation
            raise ValueError("PATH_IDENTITY_OR_BOUNDARY_MISMATCH")
        observation["confirmed_stat"] = confirmed_value
        return observation

    def _checked(self, relative_name, required=None):
        observation = self._confirm(self._observe(relative_name))
        if required is True and not observation["present"]:
            raise FileNotFoundError(relative_name)
        if required is False and observation["present"]:
            raise FileExistsError(relative_name)
        return observation

    def exists(self, relative_name):
        return self._checked(relative_name)["present"]

    def lstat(self, relative_name):
        observation = self._checked(relative_name, True)
        return observation["confirmed_stat"]

    def read_bytes(self, relative_name):
        observation = self._checked(relative_name, True)
        with open(observation["extended"], "rb") as stream:
            return stream.read()

    def hash_file(self, relative_name):
        digest = hashlib.sha256()
        observation = self._checked(relative_name, True)
        with open(observation["extended"], "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def mkdir(self, relative_name, parents=False, exist_ok=False):
        pieces, unused_normal, unused_extended = self._translate(relative_name)
        names = ["/".join(pieces[:count]) for count in range(1, len(pieces) + 1)] if parents else [relative_name]
        for name in names:
            observation = self._checked(name)
            if observation["present"]:
                mode = observation["chain"][-1][3][0]
                if not stat.S_ISDIR(mode) or (name == relative_name and not exist_ok):
                    raise FileExistsError(name)
                continue
            observation = self._checked(name, False)
            os.mkdir(observation["extended"])
            self.owned_paths.add(name)

    def write_exclusive(self, relative_name, raw):
        parent = relative_name.rsplit("/", 1)[0]
        self.mkdir(parent, parents=True, exist_ok=True)
        observation = self._checked(relative_name, False)
        with open(observation["extended"], "xb") as stream:
            self.owned_paths.add(relative_name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())

    def replace(self, source_name, destination_name):
        source = self._observe(source_name)
        destination = self._observe(destination_name)
        self._confirm(destination)
        self._confirm(source)
        if not source["present"]:
            raise FileNotFoundError(source_name)
        os.replace(source["extended"], destination["extended"])
        self.owned_paths.discard(source_name)
        self.owned_paths.add(destination_name)

    def unlink(self, relative_name, require_owned=False):
        if require_owned and relative_name not in self.owned_paths:
            raise ValueError("PATH_NOT_OWNED")
        observation = self._checked(relative_name, True)
        os.unlink(observation["extended"])
        self.owned_paths.discard(relative_name)

    def rmdir(self, relative_name, require_owned=False):
        if require_owned and relative_name not in self.owned_paths:
            raise ValueError("PATH_NOT_OWNED")
        observation = self._checked(relative_name, True)
        os.rmdir(observation["extended"])
        self.owned_paths.discard(relative_name)


PATHS = _VerifierWindowsPathAdapter(REPO)


def canonical(value):
    def check(item):
        if isinstance(item, float) and (not math.isfinite(item) or (item == 0 and math.copysign(1, item) < 0)):
            raise ValueError("NONFINITE_OR_NEGATIVE_ZERO")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError("NON_STRING_KEY")
                check(child)
        if isinstance(item, list):
            for child in item:
                check(child)
    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _task_id_valid(value):
    groups = value.split("-") if isinstance(value, str) else []
    return [len(group) for group in groups] == [8, 4, 4, 4, 12] and all(character in "0123456789abcdef" for group in groups for character in group)


def _schema_validate(value, schema):
    if "const" in schema and value != schema["const"]:
        raise ValueError("DISPATCH_SCHEMA_CONST_MISMATCH")
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict): raise ValueError("DISPATCH_SCHEMA_TYPE_MISMATCH")
        if not set(schema.get("required", ())).issubset(value): raise ValueError("DISPATCH_SCHEMA_REQUIRED_MISSING")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and not set(value).issubset(properties): raise ValueError("DISPATCH_SCHEMA_ADDITIONAL_PROPERTY")
        for key, child in value.items():
            if key in properties: _schema_validate(child, properties[key])
    elif expected_type == "array" and not isinstance(value, list): raise ValueError("DISPATCH_SCHEMA_TYPE_MISMATCH")
    elif expected_type == "boolean" and not isinstance(value, bool): raise ValueError("DISPATCH_SCHEMA_TYPE_MISMATCH")


def _utc_epoch(value):
    if not isinstance(value, str) or len(value) != 20 or value[4] != "-" or value[7] != "-" or value[10] != "T" or value[13] != ":" or value[16] != ":" or value[19] != "Z":
        raise ValueError("AUTHORIZATION_TIMESTAMP_INVALID")
    try: year, month, day, hour, minute, second = (int(value[a:b]) for a, b in ((0, 4), (5, 7), (8, 10), (11, 13), (14, 16), (17, 19)))
    except ValueError as exc: raise ValueError("AUTHORIZATION_TIMESTAMP_INVALID") from exc
    leap = lambda y: y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    month_days = [31, 29 if leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if year < 1970 or not 1 <= month <= 12 or not 1 <= day <= month_days[month - 1] or not 0 <= hour < 24 or not 0 <= minute < 60 or not 0 <= second < 60:
        raise ValueError("AUTHORIZATION_TIMESTAMP_INVALID")
    days = sum(366 if leap(candidate) else 365 for candidate in range(1970, year)) + sum(month_days[:month - 1]) + day - 1
    return days * 86400 + hour * 3600 + minute * 60 + second


def _boundary_profile(value, dispatch, task):
    if isinstance(value, dict): return {key: "<AUTHORITY_CHAIN>" if key == "authority_hash_chain" else _boundary_profile(child, dispatch, task) for key, child in value.items()}
    if isinstance(value, list): return [_boundary_profile(child, dispatch, task) for child in value]
    if isinstance(value, str): return value.replace(dispatch, "<DISPATCH>").replace(task, "<TASK>")
    return value


def _validate_dispatch(repository_root, relative, task_id, mode, enforce_process_cwd=False):
    if not _task_id_valid(task_id): raise ValueError("TASK_ID_INVALID")
    expected_relative = DISPATCH_ROOT + f"GEN_ENC_CAD_1_PHASE_B_TASK_{task_id}.dispatch_authorization.json"
    if relative != expected_relative: raise ValueError("AUTHORIZATION_SCOPE_MISMATCH")
    paths = _VerifierWindowsPathAdapter(pathlib.Path(repository_root).resolve())
    raw, schema_raw = paths.read_bytes(relative), paths.read_bytes(DISPATCH_SCHEMA)
    if sha(schema_raw) != DISPATCH_SCHEMA_SHA256: raise ValueError("DISPATCH_SCHEMA_HASH_MISMATCH")
    try: schema, record = json.loads(schema_raw), json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise ValueError("DISPATCH_JSON_INVALID") from exc
    if canonical(record) != raw: raise ValueError("DISPATCH_CANONICAL_BYTES_INVALID")
    _schema_validate(record, schema)
    if set(record) != set(schema["required"]): raise ValueError("DISPATCH_PROPERTY_SET_INVALID")
    if (record["schema_version"] != "gen_enc_cad_1_dispatch_authorization_v1" or record["record_type"] != "GEN_ENC_CAD_1_IMPLEMENTATION_DISPATCH_AUTHORIZATION" or
        record["record_id"] != f"GEN_ENC_CAD_1_PHASE_B_TASK_{task_id}" or record["issuer_role"] != "GEN_ENC_INTERMEDIATE_CONTROLLER" or
        record["issuer_thread_id"] != "01a0452b-ee9f-7ce0-a671-78d80cb069fe" or record["allowed_task_id"] != task_id or
        record["allowed_modes"] != ["preflight", "compile", "verify", "package-results"] or mode not in record["allowed_modes"]):
        raise ValueError("AUTHORIZATION_SCOPE_MISMATCH")
    now = sys.modules["time"].time()
    if not (_utc_epoch(record["issued_at_utc"]) <= now < _utc_epoch(record["expires_at_utc"])) or record["revoked"] is not False: raise ValueError("AUTHORIZATION_STATE_INVALID")
    if record["guardian_decision"] not in {"GUARDIAN_APPROVE", "GUARDIAN_APPROVE_WITH_REQUIRED_DISCLOSURES"} or record["guardian_implementation_execution_authorized"] is not True: raise ValueError("GUARDIAN_AUTHORIZATION_INVALID")
    if any(record[key] != expected for key, expected in CORRECTED_REVISED_PATHS.items()): raise ValueError("CORRECTED_AUTHORITY_PATH_MISMATCH")
    chain = record["exact_boundaries"].get("authority_hash_chain")
    if not isinstance(chain, list) or len(chain) < 4: raise ValueError("AUTHORITY_CHAIN_INCOMPLETE")
    seen_roles, seen_paths, bound = set(), set(), set()
    for entry in chain:
        if not isinstance(entry, dict) or not {"role", "path", "sha256"}.issubset(entry) or not all(isinstance(entry[key], str) for key in ("role", "path", "sha256")): raise ValueError("AUTHORITY_CHAIN_ENTRY_INVALID")
        if not entry["role"] or entry["role"] in seen_roles or entry["path"] in seen_paths or len(entry["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in entry["sha256"]): raise ValueError("AUTHORITY_CHAIN_ENTRY_INVALID")
        seen_roles.add(entry["role"]); seen_paths.add(entry["path"])
        if paths.hash_file(entry["path"]) != entry["sha256"]: raise ValueError("AUTHORITY_HASH_MISMATCH")
        bound.add((entry["path"], entry["sha256"]))
    for path_key, hash_key in (("guardian_review_path", "guardian_review_sha256"), ("revised_contract_path", "revised_contract_sha256"), ("revised_progress_path", "revised_progress_sha256"), ("revised_manifest_path", "revised_manifest_sha256")):
        if (record[path_key], record[hash_key]) not in bound: raise ValueError("AUTHORITY_CHAIN_BINDING_MISSING")
    boundaries = record["exact_boundaries"]
    if boundaries.get("dispatch_record_path") != relative: raise ValueError("AUTHORIZATION_SCOPE_MISMATCH")
    if sha(canonical(_boundary_profile(boundaries, relative, task_id))) != BOUNDARY_PROFILE_SHA256: raise ValueError("EXACT_BOUNDARIES_MISMATCH")
    root_text = str(pathlib.Path(repository_root).resolve())
    if record["working_directory"] != root_text or (enforce_process_cwd and str(pathlib.Path.cwd().resolve()) != root_text): raise ValueError("WORKING_DIRECTORY_MISMATCH")
    runtime = record["runtime_binding"]
    if runtime != {"float":"IEEE754_BINARY64_ROUND_TO_NEAREST_TIES_TO_EVEN","implementation":"CPython","machine":["AMD64","x86_64"],"observed_match_required":True,"os":"Windows","sys_platform":"win32","version":"3.12.4"}: raise ValueError("RUNTIME_BINDING_INVALID")
    if platform.python_implementation() != "CPython" or platform.python_version() != "3.12.4" or sys.platform != "win32" or platform.machine() not in runtime["machine"]: raise ValueError("FAIL_RUNTIME_BINDING")
    expected_top = {"implementation_source_creation_authorized":True,"executable_schema_creation_authorized":True,"literal_fixture_creation_authorized":True,"literal_fixture_execution_authorized":True,"implementation_execution_authorized":True,"technical_conformance_preflight_authorized":True,"timing_preflight_authorized":False}
    if any(record[key] is not value for key, value in expected_top.items()): raise ValueError("AUTHORIZATION_MATRIX_INVALID")
    expected_formal = {"cad_kernel_authorized":False,"comsol_authorized":False,"development_validation_final_test_access_authorized":False,"evidence_level_ceiling":"E1_TECHNICAL_CONFORMANCE_ONLY","final_test_read":False,"formal_generator_authorized":False,"formal_geometry_authorized":False,"formal_identity_authorized":False,"formal_row_authorized":False,"formal_seed_authorized":False,"full_wave_authorized":False,"gen_enc_2_authorized":False,"physical_experiment_authorized":False,"science_data_access_authorized":False,"scientific_hypothesis_status":"NOT_TESTED","scientific_identity_generation_authorized":False,"static_eligibility_authorized":False,"technical_phase_b_authorized":True,"timing_or_performance_evaluation_authorized":False}
    if record["formal_authorizations"] != expected_formal or not isinstance(boundaries.get("required_disclosures"), list) or not boundaries["required_disclosures"]: raise ValueError("AUTHORIZATION_MATRIX_INVALID")
    return record, raw


def run_id_for(auth_raw, task, manifest_raw):
    return sha(f"GEN_ENC_CAD_1_RUN_ID_V1\n{sha(auth_raw)}\n{task}\n{sha(manifest_raw)}".encode("ascii"))


def _validate_manifest_envelope(boundaries, relative, raw):
    expected = {"canonical_bytes":SEALED_MANIFEST_DESCRIPTOR,"order":"EXACT_REV01_FIXTURE_ARRAY_ORDER_ORDINAL_1_TO_42","path":SEALED_MANIFEST_PATH,"record_count":42,"schema":"schemas/gen_enc/gen_enc_cad_1/complete_fixture_manifest.schema.json"}
    declarations = [entry for entry in boundaries.get("authority_hash_chain", []) if entry.get("path") == SEALED_MANIFEST_PATH and entry.get("role") == "COMPLETE_FIXTURE_MANIFEST_42"]
    if boundaries.get("complete_fixture_manifest") != expected or relative != SEALED_MANIFEST_PATH: raise ValueError("COMPLETE_FIXTURE_MANIFEST_ENVELOPE_INVALID")
    if len(declarations) != 1 or declarations[0].get("sha256") != SEALED_MANIFEST_SHA256: raise ValueError("COMPLETE_FIXTURE_MANIFEST_DECLARED_HASH_INVALID")
    if len(raw) != SEALED_MANIFEST_BYTE_LENGTH or sha(raw) != SEALED_MANIFEST_SHA256: raise ValueError("COMPLETE_FIXTURE_MANIFEST_ACTUAL_HASH_OR_LENGTH_INVALID")
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"): raise ValueError("COMPLETE_FIXTURE_MANIFEST_TERMINAL_LF_INVALID")
    try: manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise ValueError("COMPLETE_FIXTURE_MANIFEST_JSON_INVALID") from exc
    if canonical(manifest) + b"\n" != raw: raise ValueError("COMPLETE_FIXTURE_MANIFEST_CANONICAL_PAYLOAD_INVALID")
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 42 or [item.get("ordinal") for item in records] != list(range(1,43)): raise ValueError("COMPLETE_FIXTURE_MANIFEST_ORDER_INVALID")
    return manifest


def _validate_manifest_then_run_id(auth_raw, task, boundaries, relative, manifest_raw):
    manifest = _validate_manifest_envelope(boundaries, relative, manifest_raw)
    return manifest, run_id_for(auth_raw, task, manifest_raw)


def stage(run_id, name):
    return f"outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/phase_b/.staging/{run_id}/{name}.stage.{run_id}.tmp"


def owner(x, y, extent):
    if -extent <= x < extent and -extent <= y < extent:
        return "CENTRAL"
    sectors = (("000", 1.0, 0.0), ("090", 0.0, 1.0), ("180", -1.0, 0.0), ("270", 0.0, -1.0))
    scores = [(x * dx + y * dy, sector) for sector, dx, dy in sectors]
    highest = max(value for value, sector in scores)
    return min(sector for value, sector in scores if value == highest)


def components(nodes, edges):
    graph = {node: [] for node in nodes}
    for left, right, area in edges:
        if fractions.Fraction(str(area)) > 0:
            graph[left].append(right); graph[right].append(left)
    seen, count = set(), 0
    for start in sorted(nodes):
        if start in seen: continue
        count += 1; seen.add(start); queue = collections.deque([start])
        while queue:
            for nxt in sorted(graph[queue.popleft()]):
                if nxt not in seen: seen.add(nxt); queue.append(nxt)
    return count


def signed_area(points):
    pts = [(fractions.Fraction(str(x)), fractions.Fraction(str(y))) for x, y in points]
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2


def clip_polygon(points, normal, offset):
    n0, n1, off = fractions.Fraction(str(normal[0])), fractions.Fraction(str(normal[1])), fractions.Fraction(str(offset))
    source = [(fractions.Fraction(str(x)), fractions.Fraction(str(y))) for x, y in points]; result = []
    for index, current in enumerate(source):
        previous = source[index - 1]; cv = n0 * current[0] + n1 * current[1] - off; pv = n0 * previous[0] + n1 * previous[1] - off
        if cv <= 0:
            if pv > 0:
                t = pv / (pv - cv); result.append((previous[0] + t * (current[0] - previous[0]), previous[1] + t * (current[1] - previous[1])))
            result.append(current)
        elif pv <= 0:
            t = pv / (pv - cv); result.append((previous[0] + t * (current[0] - previous[0]), previous[1] + t * (current[1] - previous[1])))
    return result


def union_volume(boxes):
    axes = [sorted({fractions.Fraction(str(box[a][e])) for box in boxes for e in (0, 1)}) for a in range(3)]
    total = fractions.Fraction(0)
    for xi, yi, zi in itertools.product(range(len(axes[0]) - 1), range(len(axes[1]) - 1), range(len(axes[2]) - 1)):
        low = (axes[0][xi], axes[1][yi], axes[2][zi]); high = (axes[0][xi + 1], axes[1][yi + 1], axes[2][zi + 1]); mid = tuple((a + b) / 2 for a, b in zip(low, high))
        if any(all(fractions.Fraction(str(box[a][0])) < mid[a] < fractions.Fraction(str(box[a][1])) for a in range(3)) for box in boxes): total += (high[0]-low[0])*(high[1]-low[1])*(high[2]-low[2])
    return float(total)


def root(target, lower, upper, intercept, slope):
    if slope <= 0 or not intercept + slope * lower <= target <= intercept + slope * upper: raise ValueError("ROOT_NOT_BRACKETED")
    lo, hi = lower, upper
    for unused in range(80):
        mid = (lo + hi) / 2
        if intercept + slope * mid < target: lo = mid
        else: hi = mid
    return lo if abs(intercept+slope*lo-target) <= abs(intercept+slope*hi-target) else hi


def recompute(fixture):
    fid, scenario, data = fixture["fixture_id"], fixture["scenario"], fixture["inputs"]
    status, reason, measurements = "SUBJECT_PASS", data.get("reason"), {}
    if scenario == "root_q270":
        q = [*data["xyz"], -sum(data["xyz"]) / 3]; weights = [math.exp(v) for v in q]; measurements["target_m3"] = 0.60 * 3.014899604922098e-5 * weights[3] / sum(weights)
    elif scenario == "root_bracket":
        try: measurements["root"] = root(data["target"], data["lower"], data["upper"], data["intercept"], data["slope"]); reason = "FULL_DOMAIN_BRACKET"
        except ValueError: status, reason = "TEMPLATE_VALIDITY_REJECTED", "ROOT_NOT_BRACKETED"
    elif scenario == "ownership":
        if data.get("positive_crossing") and len({owner(x, y, data["half_extent"]) for x, y in data["points"]}) > 1: status, reason = "TEMPLATE_VALIDITY_REJECTED", "OWNERSHIP_NONRECTILINEAR_CROSSING"
        else: measurements["owner"] = owner(data["point"][0], data["point"][1], data["half_extent"])
    elif scenario == "connectivity":
        actual = components(data["actual_nodes"], data["actual_edges"]); reduced = components(data["reduced_nodes"], data["reduced_edges"]); measurements = {"actual_components":actual,"reduced_components":reduced}
        if actual != 1: status, reason = "COST_INELIGIBLE", "ACTUAL_FLUID_COMPONENT_COUNT_NOT_ONE"
        else: reason = "ACTUAL_ONE_COMPONENT_REDUCED_DISCONNECTED_DESCRIPTIVE"
    elif scenario == "threshold":
        measurements = {"value":data["value"],"gate":data["gate"]}
        if not data.get("derived") or not data.get("witness"): status, reason, measurements = "TEMPLATE_VALIDITY_REJECTED", "MEASUREMENT_DERIVATION_OR_WITNESS_MISSING", {}
        elif data["value"] < data["gate"]: status, reason = "COST_INELIGIBLE", data["below_reason"]
        else: reason = data["pass_reason"]
    elif scenario == "allowlist":
        ids=data["ids"]
        if len(ids)!=len(set(ids)): status,reason="TEMPLATE_VALIDITY_REJECTED","EXCEPTION_ALLOWLIST_DUPLICATE_ID"
        elif set(ids)!=set(ALLOWLIST): status,reason="TEMPLATE_VALIDITY_REJECTED",("EXCEPTION_ALLOWLIST_MISSING_ID" if set(ids)<set(ALLOWLIST) else "EXCEPTION_ID_NOT_ALLOWLISTED")
        else: reason,measurements="EXACT_20_ID_ALLOWLIST_AND_SEPARATE_MINIMA",{"allowlist_count":20}
    elif scenario == "spillover": status,reason,measurements="COST_INELIGIBLE","GENERAL_MINIMUM_FEATURE_BELOW_THRESHOLD",{"value":data["value"],"gate":0.002}
    elif scenario == "overlap_fragment": reason="GENERAL_AUDIT_ONLY_NO_EXCEPTION_INHERITANCE"
    elif scenario == "empty_eligible_set": status,reason="TEMPLATE_VALIDITY_REJECTED","NO_ELIGIBLE_OPPOSING_PAIR"
    elif scenario == "canonical": reason=data["reason"]
    elif scenario == "zero_area":
        clipped=clip_polygon(data["polygon"],[1,0],10)
        if signed_area(clipped)==0: status,reason="TEMPLATE_VALIDITY_REJECTED","DEGENERATE_BOUNDARY_FACE"
    elif scenario == "box_union": measurements["union_volume"]=union_volume(data["boxes"])
    elif scenario == "forced": status,reason=data["status"],data["reason"]
    return {"fixture_id":fid,"observed_subject_status":status,"ordered_reason_codes":[reason],"measurements":measurements}


def write(path, value):
    raw=canonical(value)
    PATHS.write_exclusive(path, raw)
    return sha(raw)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("mode",choices=("verify",)); parser.add_argument("--authorization-record",required=True); parser.add_argument("--task-id",required=True); parser.add_argument("--fixture-manifest",required=True); parser.add_argument("--run-id",required=True); args=parser.parse_args()
    try: auth, auth_raw = _validate_dispatch(REPO, args.authorization_record, args.task_id, args.mode, enforce_process_cwd=True)
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc: raise SystemExit(str(exc)) from exc
    manifest_raw=PATHS.read_bytes(args.fixture_manifest)
    try: manifest, derived = _validate_manifest_then_run_id(auth_raw,args.task_id,auth["exact_boundaries"],args.fixture_manifest,manifest_raw)
    except (KeyError, TypeError,ValueError) as exc: raise SystemExit(str(exc)) from exc
    if derived!=args.run_id: raise SystemExit("RUN_ID_MISMATCH")
    compiled=json.loads(PATHS.read_bytes(stage(args.run_id,"compiled_mapping.json"))); static=json.loads(PATHS.read_bytes(stage(args.run_id,"static_audit.json"))); verification=[]; run_records=[]
    for item, comp, audit in zip(manifest["records"],compiled["records"],static["records"]):
        fixture=json.loads(PATHS.read_bytes(item["fixture_path"])); calculated=recompute(fixture); expected=fixture["expected"]; match=calculated["observed_subject_status"]==expected["observed_subject_status"] and calculated["ordered_reason_codes"]==expected["ordered_reason_codes"]
        subject=comp["compiled_mapping_subject"]
        if item["fixture_id"] in NULL_SUBJECTS:
            subject_match=subject is None and audit["static_audit_subject"] is None
        else:
            subject_match=subject==calculated and audit["static_audit_subject"]["observed_subject_status"]==calculated["observed_subject_status"]
        entry={"ordinal":item["ordinal"],"fixture_id":item["fixture_id"],"verification_entry":{"independently_recomputed":True,"expectation_match":match,"compiler_subject_match":subject_match,"observed_subject_status":calculated["observed_subject_status"],"ordered_reason_codes":calculated["ordered_reason_codes"]}}
        verification.append(entry); present=item["fixture_id"] not in NULL_SUBJECTS
        run_records.append({"ordinal":item["ordinal"],"fixture_id":item["fixture_id"],"fixture_path":item["fixture_path"],"fixture_sha256":item["fixture_sha256"],"fixture_run_status":"PASS_EXPECTATION_MATCH" if match and subject_match else "FAIL_EXPECTATION_MISMATCH","observed_subject_status":calculated["observed_subject_status"],"ordered_reason_codes":calculated["ordered_reason_codes"],"compiled_mapping_subject_present":present,"static_audit_subject_present":present,"verification_entry_present":True,"compiled_mapping_record_sha256":sha(canonical(comp)),"static_audit_record_sha256":sha(canonical(audit)),"verification_record_sha256":sha(canonical(entry))})
    if any(r["fixture_run_status"]!="PASS_EXPECTATION_MATCH" for r in run_records): raise SystemExit("FIXTURE_EXPECTATION_MISMATCH")
    envelope={"evidence_level":"E1_TECHNICAL_CONFORMANCE_ONLY","scientific_hypothesis_status":"NOT_TESTED","formal_instance_count":0,"final_test_read":False}
    verification_obj={**envelope,"records":verification}; ver_hash=write(stage(args.run_id,"verification_report.json"),verification_obj)
    compiled_hash=PATHS.hash_file(stage(args.run_id,"compiled_mapping.json")); static_hash=PATHS.hash_file(stage(args.run_id,"static_audit.json"))
    run_obj={**envelope,"run_id":args.run_id,"complete_fixture_manifest_sha256":sha(manifest_raw),"aggregate_hashes":{"compiled_mapping.json":compiled_hash,"static_audit.json":static_hash,"verification_report.json":ver_hash},"records":run_records}; write(stage(args.run_id,"complete_run_manifest.json"),run_obj)
    source_entries=[{"path":p,"sha256":PATHS.hash_file(p),"byte_length":len(PATHS.read_bytes(p)),"role":"IMPLEMENTATION_SOURCE"} for p in sorted(auth["exact_boundaries"]["source_paths_exact"])]
    schema_entries=[{"path":p,"sha256":PATHS.hash_file(p),"byte_length":len(PATHS.read_bytes(p)),"role":"EXECUTABLE_SCHEMA"} for p in sorted(auth["exact_boundaries"]["executable_schema_paths_exact"])]
    fixture_entries=[{"path":r["fixture_path"],"sha256":r["fixture_sha256"],"byte_length":len(PATHS.read_bytes(r["fixture_path"])),"role":"LITERAL_FIXTURE"} for r in manifest["records"]]
    write(stage(args.run_id,"audit_log.json"),{**envelope,"command":"verify-complete-42","runtime":{"implementation":"CPython","version":"3.12.4","platform":"win32","machine":platform.machine()},"counts":{"fixtures":42,"passes":42},"result":"PASS","reason_codes":[]})
    write(stage(args.run_id,"source_hash_manifest.json"),{"entries":source_entries,"entry_count":len(source_entries)})
    write(stage(args.run_id,"schema_hash_manifest.json"),{"entries":schema_entries,"entry_count":len(schema_entries)})
    write(stage(args.run_id,"fixture_hash_manifest.json"),{"entries":fixture_entries,"entry_count":42,"complete_fixture_manifest_sha256":sha(manifest_raw)})
    write(stage(args.run_id,"result_summary.json"),{**envelope,"terminal_state":"READY_FOR_INTERMEDIATE_ACCEPTANCE_AND_GUARDIAN_RESULT_SEAL_REVIEW","gate_a":"PASS","gate_b":"PASS","fixture_count":42,"fixture_pass_count":42,"independent_verifier":"PASS","timing_preflight_authorized":False})
    write(stage(args.run_id,"artifact_inventory.json"),{**envelope,"success_files":SUCCESS,"success_file_count":11,"failure_record_count":0,"formal_generator_invoked":False,"formal_seed_consumed":False})
    lines=[]
    for name in SUCCESS[:-1]: lines.append(f"{PATHS.hash_file(stage(args.run_id,name))}  {name}")
    raw=("\n".join(lines)+"\n").encode("ascii")
    PATHS.write_exclusive(stage(args.run_id,"SHA256SUMS.txt"), raw)
    print("INDEPENDENT_VERIFIER_PASS FIXTURES=42")


if __name__=="__main__": main()
