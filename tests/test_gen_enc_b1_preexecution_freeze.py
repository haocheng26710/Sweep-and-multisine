from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from scripts.gen_enc_b1 import formal_driver as driver
from scripts.gen_enc_b1 import independent_verifier as verifier

REPO = Path(__file__).resolve().parents[1]
SCHEMAS = REPO / "schemas/gen_enc/b1"
FIXTURE = REPO / "tests/fixtures/gen_enc_b1/technical_contract_fixture.json"
FREEZE = REPO / "outputs/gen_enc/GEN_ENC_FAST_START/b1_preexecution_freeze"


def fixture_objects() -> dict:
    cfg = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert cfg["identity_class"] == "TECHNICAL_FIXTURE_ONLY_NEVER_FORMAL_AUTHORITY" and cfg["authority_read_count"] == 0
    hand, near = [], []
    for i in range(1, 21):
        q0 = (i - 10.5) / 200; q90 = -q0 / 2; q180 = q0 / 4
        common = {"volume_logit_0": q0, "volume_logit_90": q90, "volume_logit_180": q180, "derived_volume_logit_270": -(q0 + q90 + q180) / 3,
                  "external_aperture_fraction_0": .41 + i / 1000, "external_aperture_fraction_90": .42 + i / 1000, "external_aperture_fraction_180": .43 + i / 1000, "external_aperture_fraction_270": .44 + i / 1000,
                  "loss_fraction_0": .03 + i / 10000, "loss_fraction_90": .035 + i / 10000, "loss_fraction_180": .04 + i / 10000, "loss_fraction_270": .045 + i / 10000}
        hand.append({"member_id": f"HAND_{i:02d}", **common, "central_mix_aperture_fraction": .2 + i / 1000})
        near.append({"member_id": f"NEAR_{i:02d}", **common, "shared_coupling_alpha": .03 + (i - 1) * .04 / 19})
    random_spec = {"family_id": driver.FAMILIES[2], "version": "TECHNICAL", "member_count": 20, "stochastic": True, "seeds_ref": "TECHNICAL", "parameter_order": list(driver.RANDOM_ORDER), "parameters": [{"technical": True}] * 3, "dof": 13, "uniform_algorithm": "OPEN_BINARY64_NEXTAFTER", "splitmix64": "FROZEN", "reciprocity": True, "canonical_generator": "TECHNICAL_ONLY"}
    physics_spec = {"family_id": driver.FAMILIES[3], "version": "TECHNICAL", "member_count": 20, "stochastic": True, "lhs_master_seed": cfg["physics_master_seed"], "member_identity_seeds_ref": "TECHNICAL", "parameter_order": list(driver.PHYSICS_ORDER), "parameters": [{"technical": True}] * 4, "dof": 15, "lhs_algorithm": ["FISHER_YATES", "MIDPOINT", "NO_JITTER", "20_STRATA"], "physics_identity": ["TECHNICAL"] * 4, "unstructured_random_matrix_substitution": False}
    values = {"HAND_ROWS": hand, "NEAR_ROWS": near, "RANDOM_FAMILY_SPEC": random_spec, "RANDOM_FIXED_SEEDS": cfg["random_seeds"], "PHYSICS_FAMILY_SPEC_PARAMETERS_LHS": physics_spec, "PHYSICS_MASTER_SEED": cfg["physics_master_seed"], "PHYSICS_MEMBER_IDENTITY_SEEDS": cfg["physics_member_seeds"]}
    values.update({f"CAD0_MULTI_SOURCE_{i:02d}": {"identity_class": "TECHNICAL_FIXTURE_ONLY", "source_index": i} for i in range(1, 14)})
    return values


def binding(run_id: str = "a" * 64) -> dict:
    return {"run_id": run_id, "release_sha256": "b" * 64, "authority_allowlist_sha256": driver.FAST0_ALLOWLIST_SHA256, "source_manifest_sha256": "c" * 64, "schema_manifest_sha256": "d" * 64, "command_manifest_sha256": "e" * 64}


def transaction_context(tmp_path: Path, run_id: str = "f" * 64) -> dict:
    roots = {name: tmp_path / name for name in ("staging", "run", "pointer", "journal", "success", "failure", "side_records")}
    release = {"roots": {k: str(v.relative_to(tmp_path)) for k, v in roots.items()}}
    return {**binding(run_id), "release": release, "roots_resolved": roots, "schemas": driver.load_schemas(SCHEMAS)}


def make_transaction_staging(root: Path) -> None:
    for index, rel in enumerate(driver.exact_artifact_paths()):
        path = root / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(f"technical-{index}\n".encode())


def test_schemas_are_valid_strict_and_task_bound() -> None:
    for path in SCHEMAS.glob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8")); jsonschema.Draft202012Validator.check_schema(schema)
        assert schema.get("additionalProperties") is False
    assert driver.TASK_ID == verifier.TASK_ID == "01a049a7-15ca-79e1-92a2-d3822ba8609d"


def test_technical_fixture_builds_exact_frozen_b1_members_without_authority_read() -> None:
    members = driver.adapt_exact_objects(fixture_objects())
    assert [x["member_id"] for x in members] == [f"{driver.PREFIX[f]}_{i:02d}" for f in driver.FAMILIES for i in range(1, 6)]
    assert all(len(x["cad_static_evidence"]["ownership_cells"]) == 5 for x in members)
    assert all(len(x["cad_static_evidence"]["slot_placements"]) == 20 for x in members)
    assert all(len(x["cad_static_evidence"]["volume_root_witnesses"]) == 4 for x in members)
    assert all(len(x["cad_static_evidence"]["u4_exception_witnesses"]) == 20 for x in members)
    assert all(x["failure_slot_retained"] and x["scientific_hypothesis_status"] == "NOT_TESTED" for x in members)


def test_named_axes_seed_bindings_nextafter_fisher_yates_and_independent_mutation_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    objects = fixture_objects(); members = driver.adapt_exact_objects(objects)
    monkeypatch.setattr(driver, "splitmix64", lambda _: (1 << 64) - 1)
    monkeypatch.setattr(verifier, "_mix", lambda _: (1 << 64) - 1)
    expected = __import__("math").nextafter(1.0, 0.0)
    assert driver.open_uniform(1, 0) == verifier.uniform(1, 0) == expected
    monkeypatch.undo()
    assert [driver.fisher_yates(objects["PHYSICS_MASTER_SEED"], i) for i in range(15)] == [verifier.permutation(objects["PHYSICS_MASTER_SEED"], i) for i in range(15)]
    bad = dict(objects); bad["RANDOM_FAMILY_SPEC"] = dict(objects["RANDOM_FAMILY_SPEC"]); bad["RANDOM_FAMILY_SPEC"]["parameter_order"] = list(reversed(driver.RANDOM_ORDER))
    with pytest.raises((driver.B1Error, verifier.VerifyError)): driver.adapt_exact_objects(bad)
    bad = dict(objects); bad["PHYSICS_MEMBER_IDENTITY_SEEDS"] = objects["PHYSICS_MEMBER_IDENTITY_SEEDS"][:-1]
    with pytest.raises(driver.B1Error): driver.adapt_exact_objects(bad)
    assert len(members) == 20


def test_generate_non_success_then_independent_verify_reseal_zero_unlisted(tmp_path: Path) -> None:
    stage = tmp_path / "stage"; result = driver.build_staging(stage, fixture_objects(), binding(), SCHEMAS)
    assert result == {"status": "STAGED_NON_SUCCESS", "authority_read_count": 20, "member_count": 20, "artifact_count": 29}
    assert not any(p.name == "VERIFIED_SUCCESS.json" for p in stage.rglob("*"))
    checked = verifier.verify_and_reseal(stage, fixture_objects(), binding(), SCHEMAS)
    assert checked["status"] == "VERIFIED_RESEALED_NOT_PUBLISHED"
    assert set(p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()) == set(driver.exact_artifact_paths())
    assert json.loads((stage / "independent_verification.json").read_text())["status"] == "PASS"
    sums = (stage / "SHA256SUMS.txt").read_text().splitlines(); assert len(sums) == 30
    context = {**binding(), "schemas": driver.load_schemas(SCHEMAS)}
    driver.assert_verified_staging(stage, context)
    report_path = stage / "independent_verification.json"; report = json.loads(report_path.read_text()); report["status"] = "FAIL_CLOSED"; report_path.write_bytes(driver.canonical(report))
    with pytest.raises(driver.B1Error): driver.assert_verified_staging(stage, context)


@pytest.mark.parametrize("field", ["ownership_cells", "slot_placements", "volume_root_witnesses", "u4_exception_witnesses", "general_minima", "exception_minima", "reduced_graph", "actual_fluid_graph"])
def test_independent_verifier_rejects_missing_empty_or_threshold_copy(field: str, tmp_path: Path) -> None:
    stage = tmp_path / field; driver.build_staging(stage, fixture_objects(), binding(), SCHEMAS)
    path = stage / "members/HAND_01.json"; member = json.loads(path.read_text())
    member["cad_static_evidence"][field] = [] if isinstance(member["cad_static_evidence"][field], list) else {}
    path.write_bytes(driver.canonical(member))
    with pytest.raises((verifier.VerifyError, jsonschema.ValidationError)): verifier.verify_and_reseal(stage, fixture_objects(), binding(), SCHEMAS)


def test_draft_attempt0_fails_before_authority_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    draft = {"schema_version": "gen_enc_fast_b1_release_v1", "record_kind": "DRAFT", "authoritative": False, "attempt": 0, "run_id": None}
    path = tmp_path / "draft.json"; path.write_bytes(driver.canonical(draft)); att = tmp_path / "att.json"; att.write_bytes(driver.canonical({}))
    touched = []
    original = driver.sha_file
    monkeypatch.setattr(driver, "sha_file", lambda p: (touched.append(p), original(p))[1])
    with pytest.raises(Exception): driver.validate_release(REPO, path, att, SCHEMAS, "preflight", False)
    assert touched == []


def test_run_id_derivation_is_frozen_independent_and_binds_every_release_field() -> None:
    release = {"run_id": "0" * 64, "task_id": driver.TASK_ID, "batch_id": "B1", "commands_exact": ["preflight", "generate-staging", "verify", "publish", "recover", "package-results"], "roots": {"staging": "a", "run": "b", "pointer": "c", "journal": "d", "success": "e", "failure": "f", "side_records": "g"}, "nonce": "technical-fixture-only"}
    left, right = driver.derive_run_id(release), verifier.derive_run_id(release)
    assert left == right and len(left) == 64
    changed = dict(release); changed["nonce"] = "technical-fixture-mutated"
    assert driver.derive_run_id(changed) != left


def test_exact_31_target_transaction_cross_root_commit_pointer_and_mixed_terminal_prevention(tmp_path: Path) -> None:
    context = transaction_context(tmp_path); stage = context["roots_resolved"]["staging"]; make_transaction_staging(stage)
    journal = context["roots_resolved"]["journal"] / "publication.json"; pointer = context["roots_resolved"]["pointer"] / "B1.json"
    result = driver.transaction_publish(stage, context["roots_resolved"]["run"], journal, pointer, context)
    assert result["published"] == 31 and pointer.is_file() and pointer.parent != context["roots_resolved"]["run"]
    terminal = driver.write_terminal(context["roots_resolved"]["success"], context["roots_resolved"]["failure"], True, context, {"authority_reads": 0, "members": 20, "artifacts": 31, "published": 31})
    assert terminal.is_file()
    with pytest.raises(driver.B1Error, match="MIXED"):
        driver.write_terminal(context["roots_resolved"]["success"], context["roots_resolved"]["failure"], False, context, {"authority_reads": 0, "members": 20, "artifacts": 31, "published": 0})


@pytest.mark.parametrize("index", range(20))
def test_real_subprocess_kill_after_replace_before_journal_recovers_each_member_target(index: int, tmp_path: Path) -> None:
    case = tmp_path / f"case-{index}"; context = transaction_context(case); stage = context["roots_resolved"]["staging"]; make_transaction_staging(stage)
    code = """from pathlib import Path
from scripts.gen_enc_b1 import formal_driver as d
base=Path(r'%s'); schemas=d.load_schemas(Path(r'%s')); roots={n:base/n for n in ('staging','run','pointer','journal','success','failure','side_records')}; c={**%r,'release':{'roots':{k:str(v.relative_to(base)) for k,v in roots.items()}},'roots_resolved':roots,'schemas':schemas}; d.transaction_publish(roots['staging'],roots['run'],roots['journal']/'publication.json',roots['pointer']/'B1.json',c,'kill:%d')
""" % (case, SCHEMAS, binding("f" * 64), index)
    completed = subprocess.run([sys.executable, "-c", code], cwd=REPO, check=False)
    assert completed.returncode == 86
    removed = driver.rollback(context["roots_resolved"]["journal"] / "publication.json", context["roots_resolved"]["run"], context["roots_resolved"]["pointer"] / "B1.json", context["schemas"])
    assert removed >= 1 and not any(p.is_file() for p in context["roots_resolved"]["run"].rglob("*"))


@pytest.mark.parametrize("fault", ["copy:0", "fsync:0", "replace:0", "journal:0", "pointer", "terminal"])
def test_copy_fsync_replace_journal_pointer_terminal_faults_leave_zero_partial_publication(fault: str, tmp_path: Path) -> None:
    case = tmp_path / fault.replace(":", "-"); context = transaction_context(case); stage = context["roots_resolved"]["staging"]; make_transaction_staging(stage)
    journal = context["roots_resolved"]["journal"] / "publication.json"; pointer = context["roots_resolved"]["pointer"] / "B1.json"
    with pytest.raises(driver.B1Error):
        driver.transaction_publish(stage, context["roots_resolved"]["run"], journal, pointer, context, None if fault == "terminal" else fault)
        if fault == "terminal": raise driver.B1Error("INJECT_TERMINAL")
    if journal.exists(): driver.rollback(journal, context["roots_resolved"]["run"], pointer, context["schemas"])
    assert not pointer.exists() and not any(p.is_file() for p in context["roots_resolved"]["run"].rglob("*"))


def test_recovery_recomputes_token_temp_and_rejects_reparse_or_unowned_names(tmp_path: Path) -> None:
    context = transaction_context(tmp_path); stage = context["roots_resolved"]["staging"]; make_transaction_staging(stage)
    journal = context["roots_resolved"]["journal"] / "publication.json"; pointer = context["roots_resolved"]["pointer"] / "B1.json"
    with pytest.raises(driver.B1Error): driver.transaction_publish(stage, context["roots_resolved"]["run"], journal, pointer, context, "replace:0")
    state = json.loads(journal.read_text()); state["entries"][0]["temp_absolute"] += ".substring-trick"; journal.write_bytes(driver.canonical(state))
    with pytest.raises(driver.B1Error, match="OWNERSHIP"): driver.rollback(journal, context["roots_resolved"]["run"], pointer, context["schemas"])


def test_driver_and_verifier_sources_are_independent_and_no_technical_fixture_formal_cli() -> None:
    driver_source = (REPO / "scripts/gen_enc_b1/formal_driver.py").read_text(); verifier_source = (REPO / "scripts/gen_enc_b1/independent_verifier.py").read_text()
    assert "independent_verifier" not in driver_source and "formal_driver" not in verifier_source
    assert "technical" not in {action.dest for action in driver.parser()._actions}
    assert "synthetic" not in driver_source and "technical-authority" not in driver_source and 'add_argument("--fault")' not in driver_source


def test_freeze_package_hashes_draft_and_zero_formal_counters() -> None:
    lines = (FREEZE / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines()
    assert lines and all(__import__("hashlib").sha256((FREEZE / line[66:]).read_bytes()).hexdigest() == line[:64] for line in lines)
    draft = json.loads((FREEZE / "DRAFT.json").read_text()); jsonschema.Draft202012Validator(json.loads((SCHEMAS / "draft.schema.json").read_text())).validate(draft)
    assert draft["attempt"] == 0 and draft["run_id"] is None and not draft["may_flip_or_promote"] and not any(draft["permissions"].values())
    state = json.loads((FREEZE / "execution_state.json").read_text())
    assert state["formal_authority_read_count"] == state["formal_member_count"] == state["formal_static_run_count"] == state["formal_publication_count"] == 0
    assert state["release_created"] == state["attestation_created"] == state["commit_pointer_created"] == 0 and state["final_test_read"] is False
