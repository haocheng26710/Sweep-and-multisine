import datetime
import hashlib
import json
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acoustic_encoder.gen_enc.cad_mapping import canonical_json_bytes, compile_mapping
from acoustic_encoder.gen_enc.cad_mapping.compiler import ALLOWLIST
import scripts.gen_enc_cad_1_compile_fixture as compiler_module
import scripts.gen_enc_cad_1_verify_fixture as verifier_module
from scripts.gen_enc_cad_1_compile_fixture import _WindowsExtendedPathAdapter, _validate_dispatch as compiler_validate_dispatch, run_id_for as compiler_run_id_for
from scripts.gen_enc_cad_1_verify_fixture import _VerifierWindowsPathAdapter, _validate_dispatch as verifier_validate_dispatch, run_id_for as verifier_run_id_for


def test_manifest_is_complete_and_ordered():
    manifest = json.loads((ROOT / "tests/fixtures/gen_enc_cad_1/complete_fixture_manifest.json").read_bytes())
    assert manifest["record_count"] == 42
    assert [record["ordinal"] for record in manifest["records"]] == list(range(1, 43))
    assert len({record["fixture_id"] for record in manifest["records"]}) == 42


def test_literal_expectations_are_matched_without_formal_inputs():
    manifest = json.loads((ROOT / "tests/fixtures/gen_enc_cad_1/complete_fixture_manifest.json").read_bytes())
    null_ids = {record["fixture_id"] for record in manifest["records"] if not record["compiled_mapping_subject_expected"]}
    for record in manifest["records"]:
        fixture = json.loads((ROOT / record["fixture_path"]).read_bytes())
        if record["fixture_id"] in null_ids:
            continue
        observed = compile_mapping(fixture)
        assert observed["observed_subject_status"] == fixture["expected"]["observed_subject_status"]
        assert observed["ordered_reason_codes"] == fixture["expected"]["ordered_reason_codes"]


def test_allowlist_and_canonical_bytes_are_frozen():
    assert len(ALLOWLIST) == len(set(ALLOWLIST)) == 20
    assert canonical_json_bytes({"z": 2, "a": 1}) == b'{"a":1,"z":2}'


def _recovery_adapters(tmp_path):
    return (_WindowsExtendedPathAdapter(tmp_path.resolve()), _VerifierWindowsPathAdapter(tmp_path.resolve()))


def _long_directory():
    return "/".join(("a" * 80, "b" * 80, "c" * 80))


def _remove_long_tree(adapter, directory):
    pieces = directory.split("/")
    for count in range(len(pieces), 0, -1):
        adapter.rmdir("/".join(pieces[:count]), require_owned=True)


def test_windows_adapters_derive_long_extended_identity_without_logical_mutation(tmp_path):
    logical = _long_directory() + "/identity.bin"
    for adapter in _recovery_adapters(tmp_path):
        normal, extended, retained = adapter.representations(logical)
        assert len(normal) > 260
        assert max(len(component) for component in logical.split("/")) < 255
        assert extended == "\\\\?\\" + normal
        assert retained == logical
        assert extended.removeprefix("\\\\?\\") == normal


def test_windows_adapters_exclusive_create_read_hash_replace_unlink_and_cleanup(tmp_path):
    directory = _long_directory()
    for index, adapter in enumerate(_recovery_adapters(tmp_path)):
        owned_directory = directory + f"/adapter-{index}"
        source = owned_directory + "/source.bin"
        replacement = owned_directory + "/replacement.bin"
        payload = b"long-path-payload"
        adapter.write_exclusive(source, payload)
        assert adapter.read_bytes(source) == payload
        observed_hash = adapter.hash_file(source) if hasattr(adapter, "hash_file") else adapter.sha256(source)
        assert observed_hash == hashlib.sha256(payload).hexdigest()
        assert adapter.lstat(source).st_size == len(payload)
        adapter.write_exclusive(replacement, b"replacement")
        adapter.replace(replacement, source)
        assert adapter.read_bytes(source) == b"replacement"
        adapter.unlink(source, require_owned=True)
        _remove_long_tree(adapter, owned_directory)


def test_windows_adapters_preserve_collision_bytes(tmp_path):
    for index, adapter in enumerate(_recovery_adapters(tmp_path)):
        directory = f"collision-{index}"
        logical = directory + "/held.bin"
        adapter.write_exclusive(logical, b"original")
        try:
            adapter.write_exclusive(logical, b"overwrite")
        except FileExistsError:
            pass
        else:
            raise AssertionError("exclusive collision did not fail closed")
        assert adapter.read_bytes(logical) == b"original"
        adapter.unlink(logical, require_owned=True)
        adapter.rmdir(directory, require_owned=True)


def test_windows_adapters_reject_invalid_namespace_inputs(tmp_path):
    invalid = (
        r"\\?\D:\prefixed",
        r"D:\absolute",
        r"\\server\share\file",
        r"\\.\device",
        r"C:drive-relative",
        "name:stream",
        "/rooted",
        "../escape",
        "dir/./alias",
        "dir/$EXPANDED",
        "GLOBALROOT/device",
    )
    for adapter in _recovery_adapters(tmp_path):
        for logical in invalid:
            try:
                adapter.representations(logical)
            except ValueError:
                pass
            else:
                raise AssertionError(f"invalid logical path accepted: {logical!r}")


def test_windows_adapters_reject_injected_reparse_observation(tmp_path, monkeypatch):
    adapters = _recovery_adapters(tmp_path)
    adapters[0].mkdir("reparse-probe")
    real_lstat = pathlib.os.lstat

    class ReparseObservation:
        def __init__(self, value):
            self.st_mode = value.st_mode
            self.st_dev = value.st_dev
            self.st_ino = value.st_ino
            self.st_file_attributes = getattr(value, "st_file_attributes", 0) | 0x400
            self.st_reparse_tag = 1

    def injected(path):
        value = real_lstat(path)
        return ReparseObservation(value) if str(path).endswith("reparse-probe") else value

    monkeypatch.setattr(pathlib.os, "lstat", injected)
    for adapter in adapters:
        try:
            adapter.exists("reparse-probe")
        except ValueError as exc:
            assert str(exc) == "PATH_REPARSE_POINT_FORBIDDEN"
        else:
            raise AssertionError("reparse observation did not fail closed")
    monkeypatch.undo()
    adapters[0].rmdir("reparse-probe", require_owned=True)


def test_windows_adapters_reject_parent_identity_change(tmp_path, monkeypatch):
    adapters = _recovery_adapters(tmp_path)
    adapters[0].mkdir("identity-probe")
    real_lstat = pathlib.os.lstat

    class ChangedIdentity:
        def __init__(self, value):
            self.st_mode = value.st_mode
            self.st_dev = value.st_dev
            self.st_ino = value.st_ino + 1
            self.st_file_attributes = getattr(value, "st_file_attributes", 0)
            self.st_reparse_tag = getattr(value, "st_reparse_tag", 0)

    for adapter in adapters:
        calls = {"target": 0}

        def injected(path):
            value = real_lstat(path)
            if str(path).endswith("identity-probe"):
                calls["target"] += 1
                if calls["target"] == 2:
                    return ChangedIdentity(value)
            return value

        monkeypatch.setattr(pathlib.os, "lstat", injected)
        try:
            adapter.exists("identity-probe")
        except ValueError as exc:
            assert str(exc) == "PATH_IDENTITY_OR_BOUNDARY_MISMATCH"
        else:
            raise AssertionError("identity change did not fail closed")
        monkeypatch.undo()
    adapters[0].rmdir("identity-probe", require_owned=True)


CORR02_TEST_TASK = "11111111-2222-3333-4444-555555555555"
ATTEMPT01_TASK = "01a04695-2076-72f1-a118-2f9e4a402f90"
ATTEMPT01_DISPATCH = f"outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/dispatch/GEN_ENC_CAD_1/GEN_ENC_CAD_1_PHASE_B_TASK_{ATTEMPT01_TASK}.dispatch_authorization.json"
ATTEMPT02_DISPATCH = "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/dispatch/GEN_ENC_CAD_1/GEN_ENC_CAD_1_PHASE_B_TASK_01a047a9-b299-7460-b37d-638e8e5691e2.dispatch_authorization.json"
CORR03_DESCRIPTOR = "UTF8_NO_BOM_RECURSIVE_UNICODE_KEY_SORT_ARRAYS_PRESERVED_SHORTEST_ROUNDTRIP_FINITE_BINARY64_NO_WHITESPACE_WITH_EXACTLY_ONE_TRAILING_LF_EXCEPTION_FOR_THIS_SEALED_MANIFEST"
SEALED_MANIFEST = "tests/fixtures/gen_enc_cad_1/complete_fixture_manifest.json"


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _replace_task(value, old_dispatch, new_dispatch, old_task, new_task):
    if isinstance(value, dict):
        return {key: _replace_task(child, old_dispatch, new_dispatch, old_task, new_task) for key, child in value.items()}
    if isinstance(value, list):
        return [_replace_task(child, old_dispatch, new_dispatch, old_task, new_task) for child in value]
    if isinstance(value, str):
        return value.replace(old_dispatch, new_dispatch).replace(old_task, new_task)
    return value


def _write_temp(root, relative, raw):
    adapter = _WindowsExtendedPathAdapter(root.resolve())
    if adapter.exists(relative):
        adapter.unlink(relative)
    adapter.write_exclusive(relative, raw)


def _corr02_dispatch_pair(tmp_path):
    new_dispatch = f"outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/dispatch/GEN_ENC_CAD_1/GEN_ENC_CAD_1_PHASE_B_TASK_{CORR02_TEST_TASK}.dispatch_authorization.json"
    schema_path = "schemas/gen_enc/gen_enc_cad_1/dispatch_authorization.schema.json"
    _write_temp(tmp_path, schema_path, (ROOT / schema_path).read_bytes())
    template = json.loads((ROOT / ATTEMPT01_DISPATCH).read_bytes())
    record = _replace_task(template, ATTEMPT01_DISPATCH, new_dispatch, ATTEMPT01_TASK, CORR02_TEST_TASK)
    record["exact_boundaries"]["complete_fixture_manifest"]["canonical_bytes"] = CORR03_DESCRIPTOR
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    record["issued_at_utc"] = (now - datetime.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    record["expires_at_utc"] = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    record["working_directory"] = str(tmp_path.resolve())
    bindings = (
        ("GUARDIAN_REVIEW", "guardian_review_path", "guardian_review_sha256", "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_CAD_1_PHASE_A_REV03_CORR02_CONTRACT_REVIEW.json"),
        ("REV03_CORR02_CONTRACT", "revised_contract_path", "revised_contract_sha256", "docs/experiment/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT_PROPOSAL_REV03_CORR02.md"),
        ("REV03_CORR02_PROGRESS", "revised_progress_path", "revised_progress_sha256", "docs/progress/GEN_ENC_CAD_1_PHASE_A_CONTRACT_PROPOSAL_REV03_CORR02.md"),
        ("REV03_CORR02_MANIFEST", "revised_manifest_path", "revised_manifest_sha256", "outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/phase_a_rev03_corr02/SHA256SUMS.txt"),
    )
    chain = []
    for ordinal, (role, path_key, hash_key, path) in enumerate(bindings, 1):
        raw = f"corr02-authority-{ordinal}".encode("ascii")
        _write_temp(tmp_path, path, raw)
        digest = hashlib.sha256(raw).hexdigest()
        record[path_key], record[hash_key] = path, digest
        chain.append({"path": path, "role": role, "sha256": digest})
    manifest_raw = (ROOT / SEALED_MANIFEST).read_bytes()
    _write_temp(tmp_path, SEALED_MANIFEST, manifest_raw)
    chain.append({"path": SEALED_MANIFEST, "role": "COMPLETE_FIXTURE_MANIFEST_42", "sha256": hashlib.sha256(manifest_raw).hexdigest()})
    record["exact_boundaries"]["authority_hash_chain"] = chain
    raw = _canonical(record)
    _write_temp(tmp_path, new_dispatch, raw)
    return new_dispatch, record, raw


def _assert_rejected(callable_):
    try:
        callable_()
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        return
    raise AssertionError("rollover authorization was not rejected")


def test_corr02_new_task_dispatch_pair_accept(tmp_path):
    dispatch, expected, raw = _corr02_dispatch_pair(tmp_path)
    compiler_record, compiler_raw = compiler_validate_dispatch(tmp_path, dispatch, CORR02_TEST_TASK, "preflight")
    verifier_record, verifier_raw = verifier_validate_dispatch(tmp_path, dispatch, CORR02_TEST_TASK, "verify")
    assert compiler_record == verifier_record == expected
    assert compiler_raw == verifier_raw == raw


def test_corr02_filename_path_task_mismatch(tmp_path):
    dispatch, unused_record, unused_raw = _corr02_dispatch_pair(tmp_path)
    wrong_task = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    _assert_rejected(lambda: compiler_validate_dispatch(tmp_path, dispatch, wrong_task, "preflight"))
    _assert_rejected(lambda: verifier_validate_dispatch(tmp_path, dispatch, wrong_task, "verify"))


def test_corr02_stale_attempt01_pair(tmp_path):
    schema_path = "schemas/gen_enc/gen_enc_cad_1/dispatch_authorization.schema.json"
    _write_temp(tmp_path, schema_path, (ROOT / schema_path).read_bytes())
    _write_temp(tmp_path, ATTEMPT01_DISPATCH, (ROOT / ATTEMPT01_DISPATCH).read_bytes())
    _assert_rejected(lambda: compiler_validate_dispatch(tmp_path, ATTEMPT01_DISPATCH, ATTEMPT01_TASK, "preflight"))
    _assert_rejected(lambda: verifier_validate_dispatch(tmp_path, ATTEMPT01_DISPATCH, ATTEMPT01_TASK, "verify"))


def test_corr02_changed_authority_hash(tmp_path):
    dispatch, record, unused_raw = _corr02_dispatch_pair(tmp_path)
    record["exact_boundaries"]["authority_hash_chain"][0]["sha256"] = "0" * 64
    _write_temp(tmp_path, dispatch, _canonical(record))
    _assert_rejected(lambda: compiler_validate_dispatch(tmp_path, dispatch, CORR02_TEST_TASK, "preflight"))
    _assert_rejected(lambda: verifier_validate_dispatch(tmp_path, dispatch, CORR02_TEST_TASK, "verify"))


def test_corr02_compiler_verifier_run_id_equal(tmp_path):
    dispatch, unused_record, raw = _corr02_dispatch_pair(tmp_path)
    compiler_record, compiler_raw = compiler_validate_dispatch(tmp_path, dispatch, CORR02_TEST_TASK, "preflight")
    verifier_record, verifier_raw = verifier_validate_dispatch(tmp_path, dispatch, CORR02_TEST_TASK, "verify")
    manifest_raw = (ROOT / "tests/fixtures/gen_enc_cad_1/complete_fixture_manifest.json").read_bytes()
    assert compiler_record == verifier_record
    assert compiler_run_id_for(compiler_raw, CORR02_TEST_TASK, manifest_raw) == verifier_run_id_for(verifier_raw, CORR02_TEST_TASK, manifest_raw)


def _corr03_boundaries():
    record = json.loads((ROOT / ATTEMPT02_DISPATCH).read_bytes())
    record["exact_boundaries"]["complete_fixture_manifest"]["canonical_bytes"] = CORR03_DESCRIPTOR
    return record["exact_boundaries"]


def _assert_corr03_rejected_before_run_id(module, boundaries, raw):
    original = module.run_id_for
    calls = []
    module.run_id_for = lambda *args: calls.append(args)
    try:
        _assert_rejected(lambda: module._validate_manifest_then_run_id(b"authorization", CORR02_TEST_TASK, boundaries, SEALED_MANIFEST, raw))
    finally:
        module.run_id_for = original
    assert calls == []


def test_corr03_exact_sealed_one_lf_pass():
    boundaries = _corr03_boundaries()
    raw = (ROOT / SEALED_MANIFEST).read_bytes()
    assert compiler_module._validate_manifest_envelope(boundaries, SEALED_MANIFEST, raw)["record_count"] == 42
    assert verifier_module._validate_manifest_envelope(boundaries, SEALED_MANIFEST, raw)["record_count"] == 42


def test_corr03_zero_terminal_lf_fail():
    boundaries = _corr03_boundaries()
    raw = (ROOT / SEALED_MANIFEST).read_bytes()[:-1]
    for module in (compiler_module, verifier_module):
        _assert_corr03_rejected_before_run_id(module, boundaries, raw)


def test_corr03_two_terminal_lf_fail():
    boundaries = _corr03_boundaries()
    raw = (ROOT / SEALED_MANIFEST).read_bytes() + b"\n"
    for module in (compiler_module, verifier_module):
        _assert_corr03_rejected_before_run_id(module, boundaries, raw)


def test_corr03_payload_order_or_hash_change_fail():
    exact_raw = (ROOT / SEALED_MANIFEST).read_bytes()
    payload = json.loads(exact_raw)
    payload["records"][0]["fixture_id"] += "_MUTATED"
    payload_mutation = _canonical(payload) + b"\n"
    reordered = json.loads(exact_raw)
    reordered["records"][0], reordered["records"][1] = reordered["records"][1], reordered["records"][0]
    record_order_mutation = _canonical(reordered) + b"\n"
    declared_hash_mutation = _corr03_boundaries()
    for entry in declared_hash_mutation["authority_hash_chain"]:
        if entry.get("role") == "COMPLETE_FIXTURE_MANIFEST_42":
            entry["sha256"] = "0" * 64
    subcases = {
        "PAYLOAD_MUTATION": (_corr03_boundaries(), payload_mutation),
        "RECORD_ORDER_MUTATION": (_corr03_boundaries(), record_order_mutation),
        "DECLARED_OR_ACTUAL_HASH_MUTATION": (declared_hash_mutation, exact_raw),
    }
    recorded = {}
    for subcase, (boundaries, raw) in subcases.items():
        for module in (compiler_module, verifier_module):
            _assert_corr03_rejected_before_run_id(module, boundaries, raw)
        recorded[subcase] = "FAIL_CLOSED_BEFORE_RUN_ID"
    assert recorded == {subcase: "FAIL_CLOSED_BEFORE_RUN_ID" for subcase in subcases}


def test_corr03_compiler_verifier_profile_agreement():
    boundaries = _corr03_boundaries()
    raw = (ROOT / SEALED_MANIFEST).read_bytes()
    compiler_profile = hashlib.sha256(canonical_json_bytes(compiler_module._boundary_profile(boundaries, ATTEMPT02_DISPATCH, "01a047a9-b299-7460-b37d-638e8e5691e2"))).hexdigest()
    verifier_profile = verifier_module.sha(verifier_module.canonical(verifier_module._boundary_profile(boundaries, ATTEMPT02_DISPATCH, "01a047a9-b299-7460-b37d-638e8e5691e2")))
    assert compiler_profile == verifier_profile == compiler_module.BOUNDARY_PROFILE_SHA256 == verifier_module.BOUNDARY_PROFILE_SHA256
    assert compiler_module._validate_manifest_envelope(boundaries, SEALED_MANIFEST, raw) == verifier_module._validate_manifest_envelope(boundaries, SEALED_MANIFEST, raw)


CORR04_AUTHORITY_ROOT = "outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/phase_b/technical/"
CORR04_INTERNAL_ROOT = CORR04_AUTHORITY_ROOT[:-1]
CORR04_RUN_ID = "f" * 64


class _Corr04TracingAuthority(str):
    def __new__(cls, value, events):
        instance = super().__new__(cls, value)
        instance.events = events
        return instance

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if key == slice(None, -1, None):
            self.events.append(("normalize", value))
        return value


class _Corr04SyntheticPackageAdapter:
    def __init__(self, events=None, root_collision=False):
        self.events = [] if events is None else events
        self.root_collision = root_collision
        self.existing_bytes = b"pre-existing-root-bytes" if root_collision else None
        self.root_created = False
        self.final_files = set()
        self.final_subdirectories = set()
        self.destination_absence = []
        self.staging_removed = False

    def read_bytes(self, logical):
        self.events.append(("adapter.read_bytes", logical))
        return json.dumps({"records": [{"fixture_run_status": "PASS_EXPECTATION_MATCH"} for _ in range(42)]}).encode("utf-8")

    def exists(self, logical):
        self.events.append(("adapter.exists", logical))
        return self.root_collision and logical == CORR04_INTERNAL_ROOT

    def mkdir(self, logical, parents=False, exist_ok=False):
        self.events.append(("adapter.mkdir", logical, parents, exist_ok))
        assert logical == CORR04_INTERNAL_ROOT
        self.root_created = True

    def replace(self, source, destination):
        self.events.append(("adapter.replace", source, destination))
        assert self.root_created
        was_absent = destination not in self.final_files
        self.destination_absence.append(was_absent)
        assert was_absent
        self.final_files.add(destination)

    def rmdir(self, logical):
        self.events.append(("adapter.rmdir", logical))
        assert logical == compiler_module.stage_root(CORR04_RUN_ID)
        self.staging_removed = True


def _corr04_args():
    return types.SimpleNamespace(
        run_id=CORR04_RUN_ID,
        complete_run_manifest=compiler_module.stage_path(CORR04_RUN_ID, "complete_run_manifest.json"),
    )


def _corr04_record(authority_root=CORR04_AUTHORITY_ROOT):
    return {"exact_boundaries": {"success_root_exact": authority_root}}


def _corr04_run_synthetic_package(monkeypatch, authority_root=CORR04_AUTHORITY_ROOT, root_collision=False, events=None):
    adapter = _Corr04SyntheticPackageAdapter(events=events, root_collision=root_collision)
    monkeypatch.setattr(compiler_module, "PATHS", adapter)
    compiler_module.package(_corr04_args(), _corr04_record(authority_root))
    return adapter


def _corr04_assert_rejected_before_adapter(monkeypatch, authority_root):
    adapter = _Corr04SyntheticPackageAdapter()
    monkeypatch.setattr(compiler_module, "PATHS", adapter)
    try:
        compiler_module.package(_corr04_args(), _corr04_record(authority_root))
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("invalid CORR04 authority root did not fail closed")
    assert adapter.events == []
    assert not adapter.root_created
    assert adapter.final_files == set()


def test_corr04_f01_exact_one_terminal_slash_authority_pass(monkeypatch):
    events = []
    authority = _Corr04TracingAuthority(CORR04_AUTHORITY_ROOT, events)
    adapter = _corr04_run_synthetic_package(monkeypatch, authority_root=authority, events=events)
    assert events[0] == ("normalize", CORR04_INTERNAL_ROOT)
    assert events[1][0] == "adapter.read_bytes"
    assert all("technical//" not in str(event) for event in adapter.events)


def test_corr04_f02_zero_or_two_terminal_slash_mismatch_reject(monkeypatch):
    _corr04_assert_rejected_before_adapter(monkeypatch, CORR04_INTERNAL_ROOT)
    _corr04_assert_rejected_before_adapter(monkeypatch, CORR04_AUTHORITY_ROOT + "/")


def test_corr04_f03_interior_doubled_separator_reject(monkeypatch):
    malformed = CORR04_AUTHORITY_ROOT.replace("phase_b/technical/", "phase_b//technical/")
    _corr04_assert_rejected_before_adapter(monkeypatch, malformed)


def test_corr04_f04_eleven_child_path_identity(monkeypatch):
    adapter = _corr04_run_synthetic_package(monkeypatch)
    expected = [CORR04_INTERNAL_ROOT + "/" + name for name in compiler_module.SUCCESS]
    observed = [event[2] for event in adapter.events if event[0] == "adapter.replace"]
    assert observed == expected
    assert len(observed) == len(set(observed)) == 11


def test_corr04_f05_preexisting_normalized_success_root_collision(monkeypatch):
    adapter = _Corr04SyntheticPackageAdapter(root_collision=True)
    before = adapter.existing_bytes
    monkeypatch.setattr(compiler_module, "PATHS", adapter)
    try:
        compiler_module.package(_corr04_args(), _corr04_record())
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("pre-existing normalized success root did not fail closed")
    assert adapter.existing_bytes == before
    assert not adapter.root_created
    assert adapter.final_files == set()
    assert not any(event[0] == "adapter.replace" for event in adapter.events)


def test_corr04_f06_windows_long_path_representation(tmp_path):
    adapter = _WindowsExtendedPathAdapter(tmp_path.resolve())
    logical = _long_directory() + "/" + CORR04_INTERNAL_ROOT + "/" + compiler_module.SUCCESS[0]
    normal, extended, retained = adapter.representations(logical)
    assert len(normal) > 260
    assert extended == "\\\\?\\" + normal
    assert extended.removeprefix("\\\\?\\") == normal
    assert retained == logical
    assert retained.endswith(CORR04_INTERNAL_ROOT + "/" + compiler_module.SUCCESS[0])


def test_corr04_f07_atomic_move_absent_destination_only(monkeypatch):
    adapter = _corr04_run_synthetic_package(monkeypatch)
    moves = [event[1:] for event in adapter.events if event[0] == "adapter.replace"]
    expected = [
        (compiler_module.stage_path(CORR04_RUN_ID, name), CORR04_INTERNAL_ROOT + "/" + name)
        for name in compiler_module.SUCCESS
    ]
    assert moves == expected
    assert adapter.destination_absence == [True] * 11
    assert not any("fallback" in str(event).casefold() for event in adapter.events)


def test_corr04_f08_zero_unlisted_eleven_file_package(monkeypatch):
    adapter = _corr04_run_synthetic_package(monkeypatch)
    expected = {CORR04_INTERNAL_ROOT + "/" + name for name in compiler_module.SUCCESS}
    assert adapter.final_files == expected
    assert len(adapter.final_files) == 11
    assert adapter.final_subdirectories == set()
    assert adapter.staging_removed
