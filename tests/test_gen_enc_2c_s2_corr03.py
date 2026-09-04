from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path

import jsonschema
import pytest

from scripts.gen_enc_2c_s2_corr03 import driver_corr03 as D
from scripts.gen_enc_2c_s2_corr03 import independent_verifier_corr03 as V

REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "tests/fixtures/gen_enc_2c_s2_corr03"
SCHEMAS = REPO / "schemas/gen_enc/gen_enc_2c_s2_corr03"
FORMAL_SCHEMAS = REPO / "schemas/gen_enc/gen_enc_2c_rev03"
ALLOWLIST = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/s1_implementation_freeze/path_allowlist_manifest.json"
REJECTION = REPO / "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2C_S2_CORR02_PREEXECUTION_IMPLEMENTATION_FREEZE_REVIEW.json"
REJECTION_SHA = "d33792bd5d81ae7bdc3c3e4059f86ad211e12679042f8ac79d6632401e3ad2ac"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fixture(name: str) -> dict:
    return load(FIX / name)


def exact_runtime_bundle() -> dict:
    hand = copy.deepcopy(fixture("hand_rows_exact_shape.json")["rows"])
    near = copy.deepcopy(fixture("near_rows_exact_shape.json")["rows"])
    # Values stay synthetic; these two schedules satisfy the frozen adapter bounds.
    for row in hand:
        row["central_mix_aperture_fraction"] = 0.2
    for index, row in enumerate(near):
        row["shared_coupling_alpha"] = 0.03 + index * 0.04 / 19
    random_authority = {"seeds": fixture("random_seed_split_exact_shape.json"), "family_specification": fixture("random_family_spec_exact_shape.json")}
    physics = fixture("physics_master_spec_exact_shape.json")
    return {
        "hand_rows": hand,
        "near_rows": near,
        "random_authority": random_authority,
        "physics_authority": physics,
        "cad0_mapping": fixture("cad0_technical_facts.json"),
    }


def bindings() -> dict[str, dict[str, str]]:
    one = lambda name: {"path": f"TECHNICAL_SUBSTITUTE_ONLY/{name}", "sha256": "0" * 64, "pointer": "/"}
    return {
        D.FAMILIES[0]: one(D.FAMILIES[0]),
        D.FAMILIES[1]: one(D.FAMILIES[1]),
        D.FAMILIES[2]: {"spec": one("RANDOM_SPEC"), "seed_split": one("RANDOM_SEED_SPLIT")},
        D.FAMILIES[3]: one(D.FAMILIES[3]),
        "CAD0_MAPPING": one("CAD0_MAPPING"),
    }


def logical_paths() -> list[str]:
    paths = load(ALLOWLIST)["paths"]
    marker = "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/"
    return [p[len(marker):] if p.startswith(marker) else p for p in paths]


def write_canonical(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(D.canonical(value))


def technical_release_mirror(repo: Path) -> dict:
    """Build a future-approval-shaped mirror using only synthetic bytes under basetemp."""
    schema_rel = "schemas/gen_enc/gen_enc_2c_s2_corr03/guardian_attestation.schema.json"
    auth_schema_rel = "schemas/gen_enc/gen_enc_2c_s2_corr03/authorization.schema.json"
    write_canonical(repo / schema_rel, load(SCHEMAS / "guardian_attestation.schema.json"))
    write_canonical(repo / auth_schema_rel, load(SCHEMAS / "authorization.schema.json"))
    guardian_rel = "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2C_S2_CORR03_TECHNICAL_SUBSTITUTE_ONLY_REVIEW.json"
    write_canonical(repo / guardian_rel, {"identity_class": "TECHNICAL_SUBSTITUTE_ONLY", "stage": "GEN-ENC-2C-S2-CORR03", "verdict": "APPROVE", "decision": "APPROVE TECHNICAL MIRROR ONLY"})
    manifest_paths = {key: f"technical_mirror/manifests/{key}.json" for key in D.MANIFEST_ORDER}
    manifests = {}
    for key, rel in manifest_paths.items():
        write_canonical(repo / rel, {"identity_class": "TECHNICAL_SUBSTITUTE_ONLY", "manifest_kind": key})
        manifests[key] = D.sha_file(repo / rel)
    authority_docs = {
        "hand": fixture("hand_rows_exact_shape.json"), "near": fixture("near_rows_exact_shape.json"),
        "random_spec": fixture("random_family_spec_exact_shape.json"), "random_seed": fixture("random_seed_split_exact_shape.json"),
        "physics": fixture("physics_master_spec_exact_shape.json"), "cad0": fixture("cad0_technical_facts.json"),
    }
    flat = {}
    for key, value in authority_docs.items():
        rel = f"technical_mirror/authorities/{key}.json"
        write_canonical(repo / rel, value)
        flat[key] = {"path": rel, "sha256": D.sha_file(repo / rel), "pointer": "/"}
    authorities = {D.FAMILIES[0]: flat["hand"], D.FAMILIES[1]: flat["near"], D.FAMILIES[2]: {"spec": flat["random_spec"], "seed_split": flat["random_seed"]}, D.FAMILIES[3]: flat["physics"], "CAD0_MAPPING": flat["cad0"]}
    bases = {key: f"technical_mirror/{key}" for key in ("staging", "success", "failure", "temp", "journal")}
    commands = ["generate-staging", "independent-verify-reseal", "publish", "recover", "package-results"]
    modes = ["S2_FORMAL_GENERATION", "S2_INDEPENDENT_VERIFICATION_RESEAL", "S2_VERIFIED_PUBLICATION", "S2_SAFE_RECOVERY"]
    contract_rel = "technical_mirror/contracts/corr03.json"
    contract = {"identity_class": "TECHNICAL_SUBSTITUTE_ONLY", "runtime": {"python": platform.python_version(), "jsonschema": importlib.metadata.version("jsonschema")}, "commands": commands, "modes": modes, "manifest_paths": manifest_paths, "terminal_root_bases": bases}
    write_canonical(repo / contract_rel, contract)
    release_rel = "technical_mirror/authorization/release.json"
    att_rel = "technical_mirror/attestation/guardian.json"
    permissions = {name: name == D.FORMAL_PERMISSION for name in [D.FORMAL_PERMISSION, *D.FORBIDDEN_PERMISSIONS]}
    payload = {"schema_version": "gen_enc_2c_s2_corr03_authorization_v1", "record_kind": "RELEASE", "task_id": D.TASK_ID,
        "dispatch_id": "GEN-ENC-2C-S2-CORR03-RELEASE-TECHNICAL-SUBSTITUTE-001", "attempt": 1, "issued_at": "2026-08-28T00:00:00Z", "expires_at": "2099-12-31T23:59:59Z",
        "expired": False, "revoked": False, "consumed": False, "reusable": False, "draft_promoted": False,
        "guardian_approval_path": guardian_rel, "guardian_approval_sha256": D.sha_file(repo / guardian_rel), "contract_path": contract_rel, "contract_sha256": D.sha_file(repo / contract_rel),
        "attestation_path": att_rel, "attestation_schema_path": schema_rel, "attestation_schema_sha256": D.sha_file(repo / schema_rel), "manifest_sha256": manifests,
        "terminal_root_bases": bases, "formal_authorities": authorities, "permissions": permissions,
        "requested_scope": {"authoritative": True, "scope": "S2_GENERATE_VERIFY_RESEAL_PUBLISH_ONLY"}, "commands": commands, "modes": modes,
        "run_id": None, "final_test_state": "SEALED", "final_test_read": False}
    release = {"payload": payload, "payload_sha256": D.sha_bytes(D.canonical(payload))}
    write_canonical(repo / release_rel, release)
    release_sha = D.sha_file(repo / release_rel)
    run_id = D.derive_run_id(release_sha, D.TASK_ID, manifests)
    def attested(binding: dict) -> dict:
        return {**binding, "bound_before_read": True}
    att_authorities = {D.FAMILIES[0]: attested(authorities[D.FAMILIES[0]]), D.FAMILIES[1]: attested(authorities[D.FAMILIES[1]]),
        D.FAMILIES[2]: {"spec": attested(authorities[D.FAMILIES[2]]["spec"]), "seed_split": attested(authorities[D.FAMILIES[2]]["seed_split"])},
        D.FAMILIES[3]: attested(authorities[D.FAMILIES[3]]), "CAD0_MAPPING": attested(authorities["CAD0_MAPPING"])}
    roots = {key: f"{base}/{run_id}" for key, base in bases.items()}
    attestation = {"schema_version": "gen_enc_2c_s2_corr03_guardian_attestation_v2", "record_kind": "NEW_CANONICAL_RELEASE_ATTESTATION", "task_id": D.TASK_ID,
        "dispatch_id": payload["dispatch_id"], "attempt": 1, "run_id": run_id, "release_path": release_rel, "release_full_sha256": release_sha,
        "guardian_approval_path": guardian_rel, "guardian_approval_sha256": payload["guardian_approval_sha256"], "guardian_approval_bytes_verified": True,
        "approval_is_eventual_corr03_review": True, "one_way_full_file_attestation": True, "draft_promotion": False, "manifest_sha256": manifests,
        "terminal_roots": roots, "formal_authority_bindings": att_authorities, "final_test_read": False}
    write_canonical(repo / att_rel, attestation)
    return {"release": repo / release_rel, "auth_schema": repo / auth_schema_rel, "attestation": repo / att_rel, "att_schema": repo / schema_rel, "contract": repo / contract_rel, "roots": roots, "run_id": run_id}


def test_corr03_schema_meta_and_all_fixtures() -> None:
    schemas = {p.name: load(p) for p in SCHEMAS.glob("*.json")}
    for schema in schemas.values():
        jsonschema.Draft202012Validator.check_schema(schema)
    authority = jsonschema.Draft202012Validator(schemas["technical_authority_shape.schema.json"])
    for name in ("hand_rows_exact_shape.json", "near_rows_exact_shape.json", "random_family_spec_exact_shape.json", "random_seed_split_exact_shape.json", "physics_master_spec_exact_shape.json"):
        authority.validate(fixture(name))
    jsonschema.validate(fixture("cad0_technical_facts.json"), schemas["cad0_technical_facts.schema.json"])
    jsonschema.validate(fixture("bf_ledger.json"), schemas["bf_ledger.schema.json"])


def test_technical_future_release_and_one_way_attestation_pass_both_independent_gates(tmp_path_factory: pytest.TempPathFactory) -> None:
    repo = tmp_path_factory.getbasetemp() / "technical_mirror_gate"
    mirror = technical_release_mirror(repo)
    driver_gate = D.validate_release(repo, mirror["release"], mirror["attestation"], mirror["contract"], mirror["auth_schema"], "generate-staging", "S2_FORMAL_GENERATION")
    assert driver_gate["run_id"] == mirror["run_id"]
    (repo / mirror["roots"]["staging"]).mkdir(parents=True)
    verifier_gate = V.gate(repo, mirror["release"], mirror["auth_schema"], mirror["attestation"], mirror["att_schema"], mirror["contract"])
    assert verifier_gate["run_id"] == mirror["run_id"] == driver_gate["run_id"]


def test_expired_all_false_draft_is_rejected_by_both_gates_before_any_authority_read(tmp_path: Path) -> None:
    repo = tmp_path / "TECHNICAL_SUBSTITUTE_ONLY_DRAFT_MIRROR"
    schema_path = repo / "authorization.schema.json"
    write_canonical(schema_path, load(SCHEMAS / "authorization.schema.json"))
    false_permissions = {name: False for name in [D.FORMAL_PERMISSION, *D.FORBIDDEN_PERMISSIONS]}
    payload = {"schema_version": "gen_enc_2c_s2_corr03_authorization_v1", "record_kind": "DRAFT", "task_id": D.TASK_ID,
        "dispatch_id": "GEN-ENC-2C-S2-CORR03-DRAFT-TECHNICAL-SUBSTITUTE-001", "attempt": 0, "issued_at": "2026-08-28T00:00:00Z", "expires_at": "2026-08-28T00:00:01Z",
        "expired": True, "revoked": False, "consumed": False, "reusable": False, "draft_promoted": False,
        "guardian_approval_path": None, "guardian_approval_sha256": None, "contract_path": None, "contract_sha256": None, "attestation_path": None,
        "attestation_schema_path": None, "attestation_schema_sha256": None, "manifest_sha256": {key: None for key in D.MANIFEST_ORDER},
        "terminal_root_bases": {key: None for key in ("staging", "success", "failure", "temp", "journal")}, "formal_authorities": None,
        "permissions": false_permissions, "requested_scope": {"authoritative": False, "scope": "S2_GENERATE_VERIFY_RESEAL_PUBLISH_ONLY"},
        "commands": [], "modes": [], "run_id": None, "final_test_state": "SEALED", "final_test_read": False}
    draft = {"payload": payload, "payload_sha256": D.sha_bytes(D.canonical(payload))}
    draft_path = repo / "TECHNICAL_SUBSTITUTE_ONLY_DRAFT.json"
    write_canonical(draft_path, draft)
    sentinel = repo / "MUST_NOT_BE_READ.authority"
    with pytest.raises(Exception, match="RELEASE|DRAFT"):
        D.validate_release(repo, draft_path, sentinel, sentinel, schema_path, "generate-staging", "S2_FORMAL_GENERATION")
    with pytest.raises(Exception, match="DRAFT"):
        V.gate(repo, draft_path, schema_path, sentinel, sentinel, sentinel)
    assert not sentinel.exists()


@pytest.mark.parametrize("mutation", ["task", "approval_hash", "expiry", "revocation", "consumed", "reusable", "draft_promotion", "commands", "modes", "manifest", "root", "run", "authority_binding"])
def test_release_and_attestation_mutations_fail_both_gates(tmp_path_factory: pytest.TempPathFactory, mutation: str) -> None:
    repo = tmp_path_factory.getbasetemp() / f"mutation_{mutation}"
    mirror = technical_release_mirror(repo)
    release = load(mirror["release"])
    attestation = load(mirror["attestation"])
    p = release["payload"]
    if mutation == "task": p["task_id"] = "0" * 36
    elif mutation == "approval_hash": p["guardian_approval_sha256"] = "0" * 64
    elif mutation == "expiry": p["expires_at"] = "2020-01-01T00:00:00Z"
    elif mutation == "revocation": p["revoked"] = True
    elif mutation == "consumed": p["consumed"] = True
    elif mutation == "reusable": p["reusable"] = True
    elif mutation == "draft_promotion": p["draft_promoted"] = True
    elif mutation == "commands": p["commands"] = list(reversed(p["commands"]))
    elif mutation == "modes": p["modes"] = list(reversed(p["modes"]))
    elif mutation == "manifest": p["manifest_sha256"]["source"] = "0" * 64
    elif mutation == "root": attestation["terminal_roots"]["staging"] = f"technical_mirror/staging/{'0' * 64}"
    elif mutation == "run": attestation["run_id"] = "0" * 64
    elif mutation == "authority_binding": attestation["formal_authority_bindings"][D.FAMILIES[0]]["sha256"] = "0" * 64
    if mutation in {"task", "approval_hash", "expiry", "revocation", "consumed", "reusable", "draft_promotion", "commands", "modes", "manifest"}:
        release["payload_sha256"] = D.sha_bytes(D.canonical(p))
        write_canonical(mirror["release"], release)
    else:
        write_canonical(mirror["attestation"], attestation)
    with pytest.raises(Exception):
        D.validate_release(repo, mirror["release"], mirror["attestation"], mirror["contract"], mirror["auth_schema"], "generate-staging", "S2_FORMAL_GENERATION")
    (repo / mirror["roots"]["staging"]).mkdir(parents=True, exist_ok=True)
    with pytest.raises(Exception):
        V.gate(repo, mirror["release"], mirror["auth_schema"], mirror["attestation"], mirror["att_schema"], mirror["contract"])


def test_authoritative_task_id_has_no_aa4f_typo() -> None:
    scoped = list(SCHEMAS.rglob("*")) + list(FIX.rglob("*")) + [Path(__file__)]
    text = "".join(path.read_text(encoding="utf-8") for path in scoped if path.is_file())
    forbidden = "01a048bd-dc5e-7e93-87e6-72d299eb" + "aa4f"
    assert forbidden not in text.replace('"' + forbidden[:36] + '" + "' + forbidden[36:] + '"', "")
    assert D.TASK_ID == V.TASK_ID == "01a048bd-dc5e-7e93-87e6-72d299ebaa4d"


@pytest.mark.parametrize("name", ["random_family_spec_exact_shape.json", "physics_master_spec_exact_shape.json"])
def test_parameter_order_is_ordered_not_a_set(name: str) -> None:
    schema = load(SCHEMAS / "technical_authority_shape.schema.json")
    value = fixture(name)
    value["parameter_order"][0], value["parameter_order"][1] = value["parameter_order"][1], value["parameter_order"][0]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(value)


def test_random_contract_has_20_seeds_13_draws_and_exact_half_atom() -> None:
    spec = fixture("random_family_spec_exact_shape.json")
    seeds = fixture("random_seed_split_exact_shape.json")["random"]
    assert len(seeds) == len(set(seeds)) == 20
    assert len(spec["parameter_order"]) == spec["inverse_cdf"]["draw_count"] == 13
    assert spec["inverse_cdf"]["edge"] == {
        "zero_atom_probability": 0.5,
        "zero_when": "u<0.5",
        "positive_branch": "0.2+0.6*(2*u-1)",
        "same_uniform_for_atom_and_positive_branch": True,
    }
    assert spec["draw_addressing"]["golden_gamma_hex"] == "9e3779b97f4a7c15"


def test_physics_fisher_yates_contract_and_independent_vectors() -> None:
    spec = fixture("physics_master_spec_exact_shape.json")
    assert len(spec["parameter_order"]) == len(spec["bounds"]) == 15
    assert spec["permutation_algorithm"] == {
        "golden_gamma_hex": "9e3779b97f4a7c15",
        "parameter_index_origin": 0,
        "generator": "SPLITMIX64",
        "loop": "i=19..1",
        "x_expression": "(master_seed+GOLDEN_GAMMA*(1+32*parameter_index+(19-i))) mod 2^64",
        "j_expression": "splitmix64(x)%(i+1)",
    }
    for parameter_index in range(15):
        left = D.fisher_yates(spec["master_seed"], parameter_index)
        right = V.fisher_yates(spec["master_seed"], parameter_index)
        assert left == right and sorted(left) == list(range(20))


def test_exact_adapter_has_no_base_parameters_fallback() -> None:
    driver_source = (REPO / "scripts/gen_enc_2c_s2_corr03/driver_corr03.py").read_text(encoding="utf-8")
    verifier_source = (REPO / "scripts/gen_enc_2c_s2_corr03/independent_verifier_corr03.py").read_text(encoding="utf-8")
    assert "def base_parameters" not in driver_source
    assert "base_parameters(" not in verifier_source
    bundle = exact_runtime_bundle()
    adapted = D.adapt_authority_bundle(bundle["hand_rows"], bundle["near_rows"], bundle["random_authority"], bundle["physics_authority"])
    assert len(adapted["canonical_rows"]) == 80
    broken = copy.deepcopy(bundle["hand_rows"])
    del broken[0]["volume_logit_0"]
    with pytest.raises(Exception, match="SHAPE|ROW"):
        D.adapt_authority_bundle(broken, bundle["near_rows"], bundle["random_authority"], bundle["physics_authority"])


@pytest.fixture
def staged(tmp_path: Path) -> tuple[Path, dict]:
    bundle = exact_runtime_bundle()
    root = tmp_path / "staging"
    result = D.generate_staging(root, FORMAL_SCHEMAS, ALLOWLIST, bundle, bindings(), cad_contract=bundle["cad0_mapping"]["facts"])
    assert result["status"] == "GENERATION_STAGED" and result["artifacts"] == 92
    assert not any(p.name in {"VERIFIED_SUCCESS.json", "PUBLISHED_SUCCESS.json"} for p in root.rglob("*"))
    return root, bundle


def test_complete_direct_schema_tree_has_nonnull_member_selfhashes(staged: tuple[Path, dict]) -> None:
    root, _ = staged
    files = [p for p in root.rglob("*") if p.is_file()]
    assert len(files) == 92
    for rel in logical_paths()[:80]:
        member = load(root / rel)
        assert member["member_sha256"] not in (None, "0" * 64)
        assert member["member_sha256"] == D.self_hash(member, "member_sha256")


def test_verifier_reseals_before_publication(staged: tuple[Path, dict], tmp_path: Path) -> None:
    root, bundle = staged
    attestation = tmp_path / "verifier-terminal.json"
    run_id = "a" * 64
    release_binding = {
        "dispatch_id": "GEN-ENC-2C-S2-CORR03-RELEASE-SYNTHETIC-001",
        "release_full_sha256": "b" * 64,
        "run_id": run_id,
        "generation_terminal_sha256": "c" * 64,
        "verifier_terminal_schema": load(SCHEMAS / "verifier_terminal.schema.json"),
    }
    before = load(root / logical_paths()[88])
    assert before["status"] != "PASS_STATIC_IDENTITY_RECOMPUTATION"
    result = V.verify_and_reseal(root, FORMAL_SCHEMAS, ALLOWLIST, bundle, attestation, release_binding)
    assert result["status"] == "VERIFIED_STAGING_RESEALED_NOT_PUBLISHED"
    terminal = load(attestation)
    jsonschema.validate(terminal, load(SCHEMAS / "verifier_terminal.schema.json"))
    assert terminal["member_self_hash_null_count"] == 0 and terminal["success_written"] is False
    assert load(root / logical_paths()[88])["status"] == "PASS_STATIC_IDENTITY_RECOMPUTATION"


def test_verified_staging_publishes_complete_tree_and_one_terminal(tmp_path_factory: pytest.TempPathFactory) -> None:
    tmp_path = tmp_path_factory.getbasetemp() / "publish_e2e"
    bundle = exact_runtime_bundle()
    root = tmp_path / "staging"
    generated = D.generate_staging(root, FORMAL_SCHEMAS, ALLOWLIST, bundle, bindings(), cad_contract=bundle["cad0_mapping"]["facts"])
    assert generated["status"] == "GENERATION_STAGED" and generated["artifacts"] == 92
    run_id = "9" * 64
    release_sha256 = "8" * 64
    attestation_path = tmp_path / "verifier-terminal.json"
    release_binding = {
        "dispatch_id": "GEN-ENC-2C-S2-CORR03-RELEASE-SYNTHETIC-E2E-001",
        "release_full_sha256": release_sha256,
        "run_id": run_id,
        "generation_terminal_sha256": "7" * 64,
        "verifier_terminal_schema": load(SCHEMAS / "verifier_terminal.schema.json"),
    }
    V.verify_and_reseal(root, FORMAL_SCHEMAS, ALLOWLIST, bundle, attestation_path, release_binding)
    verifier_terminal = load(attestation_path)
    repo = tmp_path / "publication"
    journal = repo / "journal" / run_id / "publication.json"
    terminal_root = repo / "success" / run_id
    release_context = {
        "task_id": D.TASK_ID,
        "dispatch_id": release_binding["dispatch_id"],
        "run_id": run_id,
        "authorization_sha256": release_sha256,
        "roots": {"journal": f"journal/{run_id}"},
    }
    result = D.publish_verified(root, repo, FORMAL_SCHEMAS, ALLOWLIST, journal, terminal_root, release_context, verifier_terminal)
    assert result["status"] == "PUBLISHED_SUCCESS" and result["artifacts"] == 92
    assert all((repo / rel).is_file() for rel in load(ALLOWLIST)["paths"])
    terminal_files = list(terminal_root.glob("*.json"))
    assert [p.name for p in terminal_files] == ["VERIFIED_SUCCESS.json"]
    terminal = load(terminal_files[0])
    jsonschema.validate(terminal, load(SCHEMAS / "publication_terminal.schema.json"))
    assert terminal["partial_publication_count"] == 0 and terminal["package_terminal_count"] == 1


def test_publication_rejects_unverified_staging(staged: tuple[Path, dict], tmp_path: Path) -> None:
    root, _ = staged
    run_id = "d" * 64
    release = {"task_id": D.TASK_ID, "run_id": run_id, "authorization_sha256": "e" * 64, "roots": {"journal": f"journal/{run_id}"}}
    with pytest.raises(Exception, match="VERIFIER|ATTESTATION"):
        D.publish_verified(root, tmp_path / "publication", FORMAL_SCHEMAS, ALLOWLIST, tmp_path / "journal.json", tmp_path / "success" / run_id, release, {})


@pytest.mark.parametrize("inject", ["copy", "fsync", "replace", "journal", "progress"])
def test_publication_faults_leave_zero_targets_and_unrelated_temp(staged: tuple[Path, dict], tmp_path: Path, inject: str) -> None:
    root, _ = staged
    repo = tmp_path / "publication"
    unrelated = tmp_path / "unrelated.tmp"
    unrelated.write_text("keep", encoding="utf-8")
    journal = tmp_path / f"{inject}.journal.json"
    context = {"task_id": D.TASK_ID, "authorization_sha256": "f" * 64, "run_id": "1" * 64, "roots": {"journal": "unused"}}
    with pytest.raises(Exception):
        D.transaction_publish(root, repo, ALLOWLIST, journal, context["run_id"], inject=inject, inject_index=1, release_context=context)
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert not any((repo / rel).exists() for rel in load(ALLOWLIST)["paths"])
    state = load(journal)
    assert state["state"] == "ROLLED_BACK" and state["published"] == [] and state["transaction_owned_temps"] == []


def test_safe_recovery_rejects_non_allowlist_deletion(staged: tuple[Path, dict], tmp_path: Path) -> None:
    _, _ = staged
    repo = tmp_path / "recovery"
    run_id = "2" * 64
    journal = repo / "journal" / run_id / "publication.json"
    unrelated = repo / "unrelated.json"
    unrelated.parent.mkdir(parents=True, exist_ok=True)
    unrelated.write_text("keep", encoding="utf-8")
    context = {"task_id": D.TASK_ID, "authorization_sha256": "3" * 64, "run_id": run_id, "roots": {"journal": f"journal/{run_id}"}}
    D.atomic_json(journal, {"schema_version": "gen_enc_2c_s2_corr03_publication_journal_v1", "task_id": D.TASK_ID, "release_sha256": context["authorization_sha256"], "allowlist_sha256": D.sha_file(ALLOWLIST), "run_id": run_id, "state": "PUBLISHING", "published": [str(unrelated)], "transaction_owned_temps": []})
    with pytest.raises(Exception, match="NON_ALLOWLIST"):
        D.safe_startup_recovery(journal, context, repo, ALLOWLIST)
    assert unrelated.read_text(encoding="utf-8") == "keep"


def test_guardian_binding_is_eventual_corr03_not_corr01() -> None:
    schema_text = (SCHEMAS / "authorization.schema.json").read_text(encoding="utf-8")
    driver_text = (REPO / "scripts/gen_enc_2c_s2_corr03/driver_corr03.py").read_text(encoding="utf-8")
    verifier_text = (REPO / "scripts/gen_enc_2c_s2_corr03/independent_verifier_corr03.py").read_text(encoding="utf-8")
    assert "CORR01" not in schema_text + driver_text + verifier_text
    assert "GEN_ENC_2C_S2_CORR03" in schema_text
    assert REJECTION_SHA == hashlib.sha256(REJECTION.read_bytes()).hexdigest()


def test_bf_ledger_preserves_rejection_hashes_and_honest_status() -> None:
    review = load(REJECTION)
    ledger = fixture("bf_ledger.json")
    expected = {item["id"]: (item["guardian_status"], hashlib.sha256(item["finding"].encode("utf-8")).hexdigest()) for item in review["blocker_determinations"]}
    assert [(x["id"], x["guardian_status"], x["guardian_finding_sha256"]) for x in ledger["entries"]] == [(f"S2-BF-{i:02d}", *expected[f"S2-BF-{i:02d}"]) for i in range(1, 12)]
    assert all(hashlib.sha256(x["finding"].encode("utf-8")).hexdigest() == x["original_finding_utf8_sha256"] for x in ledger["entries"])
    assert [x["id"] for x in ledger["entries"] if x["guardian_status"] == "CLOSED"] == ["S2-BF-09"]
    assert ledger["claimed_closed_count"] == 1 and ledger["formal_execution_authorized"] is False


def test_verifier_forbidden_imports_and_cli_help() -> None:
    source = (REPO / "scripts/gen_enc_2c_s2_corr03/independent_verifier_corr03.py").read_text(encoding="utf-8")
    assert all(token not in source for token in ("import driver", "import generator", "import orchestrator", "import cad_mapper"))
    assert D.parser().parse_args(["synthetic", "--output-root", "x", "--schema-root", "y", "--allowlist", "z"]).command == "synthetic"
    parsed = V.parser().parse_args(["synthetic", "--tree-root", "x", "--schema-root", "y", "--allowlist", "z", "--authority-bundle", "a", "--generation-terminal", "g", "--generation-terminal-schema", "gs", "--verifier-terminal-schema", "vs", "--attestation-out", "b"])
    assert parsed.mode == "synthetic"
