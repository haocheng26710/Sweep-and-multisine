from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from scripts.gen_enc_2c_s2_corr02 import driver_corr02 as D
from scripts.gen_enc_2c_s2_corr02 import independent_verifier_corr02 as V

REPO = Path(__file__).resolve().parents[1]
FORMAL_SCHEMAS = REPO / "schemas/gen_enc/gen_enc_2c_rev03"
CORR02_SCHEMAS = REPO / "schemas/gen_enc/gen_enc_2c_s2_corr02"
ALLOWLIST = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/s1_implementation_freeze/path_allowlist_manifest.json"
AUTH_SCHEMA = CORR02_SCHEMAS / "authorization.schema.json"
ATT_SCHEMA = CORR02_SCHEMAS / "guardian_attestation.schema.json"
REVIEW_REL = "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2C_S2_CORR01_RESULT_SEAL_REVIEW.json"


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO.resolve()).as_posix()


def make_release(tmp: Path) -> dict:
    tmp.mkdir(parents=True, exist_ok=True)
    manifest_paths = {}
    manifest_hashes = {}
    for name in D.MANIFEST_ORDER:
        path = tmp / f"{name}.manifest.json"
        D.atomic_json(path, {"identity_class": "TECHNICAL_SUBSTITUTE_ONLY", "name": name})
        manifest_paths[name] = rel(path)
        manifest_hashes[name] = D.sha_file(path)
    token = hashlib.sha256(str(tmp).encode()).hexdigest()[:10]
    bases = {name: f".tmp/c2r_{token}/{name}" for name in ("staging", "success", "failure", "temp", "journal")}
    att_path = tmp / "guardian_release_attestation.json"
    contract_path = tmp / "contract.json"
    contract = {
        "schema_version": "gen_enc_2c_s2_corr02_technical_contract_v1",
        "manifest_paths": manifest_paths,
        "terminal_roots": bases,
        "attestation_path": rel(att_path),
        "attestation_schema_path": rel(ATT_SCHEMA),
        "attestation_schema_sha256": D.sha_file(ATT_SCHEMA),
        "technical_substitute_only": True,
        "final_test_read": False,
    }
    D.atomic_json(contract_path, contract)
    fake_authorities = {}
    for family in D.FAMILIES:
        fake_authorities[family] = {"path": rel(tmp / f"DO_NOT_READ_{family}.json"), "sha256": "a" * 64, "pointer": "/DO_NOT_READ"}
    permissions = {D.FORMAL_PERMISSION: True, **{name: False for name in D.FORBIDDEN_PERMISSIONS}}
    payload = {
        "schema_version": "gen_enc_2c_s2_corr02_authorization_v2", "record_kind": "RELEASE",
        "task_id": D.TASK_ID, "dispatch_id": "GEN-ENC-2C-S2-CORR02-RELEASE-TECHNICAL-SUBSTITUTE-001",
        "attempt": 1, "issued_at": "2026-08-28T00:00:00Z", "expires_at": "2099-08-31T00:00:00Z",
        "revoked": False, "consumed": False, "reusable": False, "draft_promoted": False,
        "prior_draft_dispatch_id": "GEN-ENC-2C-S2-CORR02-DRAFT-EXPIRED-001",
        "guardian_review_path": REVIEW_REL, "guardian_review_sha256": D.GUARDIAN_REVIEW_SHA256,
        "contract_path": rel(contract_path), "contract_sha256": D.sha_file(contract_path),
        "attestation_path": rel(att_path), "attestation_schema_path": rel(ATT_SCHEMA), "attestation_schema_sha256": D.sha_file(ATT_SCHEMA),
        "manifest_sha256": manifest_hashes, "runtime": {"python": platform.python_version(), "jsonschema": importlib.metadata.version("jsonschema")},
        "commands": ["formal", "independent-verify"], "modes": ["S2_GENERATE_STATIC", "TECHNICAL_SUBSTITUTE", "formal"],
        "terminal_roots": bases, "permissions": permissions,
        "requested_scope": {"authoritative": True, "scope": "S2_FORMAL_GENERATION_STATIC_AUDIT_AND_INDEPENDENT_VERIFICATION_ONLY"},
        "formal_authorities": fake_authorities, "final_test_state": "SEALED", "final_test_read": False, "run_id": None,
    }
    release = {"payload": payload, "payload_sha256": D.sha_bytes(D.canonical(payload))}
    release_path = tmp / "release.json"; D.atomic_json(release_path, release)
    release_sha = D.sha_file(release_path); run_id = D.derive_run_id(release_sha, D.TASK_ID, manifest_hashes)
    roots = {name: f"{base}/{run_id}" for name, base in bases.items()}
    kinds = ("HAND_ROWS", "NEAR_ROWS", "RANDOM_SEEDS", "PHYSICS_SEEDS")
    bindings = [{"authority_kind": kind, "path": fake_authorities[f]["path"], "sha256": "a" * 64,
                 "json_pointer": "/DO_NOT_READ", "bound_before_read": True}
                for f, kind in zip(D.FAMILIES, kinds)]
    attestation = {
        "schema_version": "gen_enc_2c_s2_corr02_guardian_attestation_v1", "record_kind": "NEW_CANONICAL_RELEASE_ATTESTATION",
        "canonical_attestation_path": rel(att_path), "attestation_schema_path": rel(ATT_SCHEMA),
        "attestation_schema_sha256": D.sha_file(ATT_SCHEMA), "task_id": D.TASK_ID, "dispatch_id": payload["dispatch_id"],
        "attempt": 1, "run_id": run_id, "terminal_roots": roots, "release_path": rel(release_path),
        "release_full_sha256": release_sha, "guardian_review_path": REVIEW_REL,
        "guardian_review_sha256": D.GUARDIAN_REVIEW_SHA256, "guardian_review_bytes_verified": True,
        "one_way_full_file_attestation": True, "draft_promotion": False, "manifest_sha256": manifest_hashes,
        "formal_authority_bindings": bindings, "final_test_read": False,
    }
    D.atomic_json(att_path, attestation)
    return {"release": release_path, "attestation": att_path, "contract": contract_path, "run_id": run_id,
            "roots": roots, "payload": payload, "bundle": tmp / "bundle.json"}


def make_draft(path: Path) -> Path:
    false_permissions = {D.FORMAL_PERMISSION: False, **{name: False for name in D.FORBIDDEN_PERMISSIONS}}
    payload = {"schema_version":"gen_enc_2c_s2_corr02_authorization_v2","record_kind":"DRAFT","task_id":D.TASK_ID,
        "dispatch_id":"GEN-ENC-2C-S2-CORR02-DRAFT-EXPIRED-001","attempt":0,"issued_at":"2026-08-27T00:00:00Z","expires_at":"2026-08-27T00:00:01Z",
        "revoked":False,"consumed":False,"reusable":False,"draft_promoted":False,"prior_draft_dispatch_id":None,
        "guardian_review_path":None,"guardian_review_sha256":None,"contract_path":None,"contract_sha256":None,
        "attestation_path":None,"attestation_schema_path":None,"attestation_schema_sha256":None,
        "manifest_sha256":{"source":None,"schema":None,"fixture":None,"authority":None,"allowlist":None},"runtime":None,"commands":[],"modes":[],
        "terminal_roots":{"staging":None,"success":None,"failure":None,"temp":None,"journal":None},"permissions":false_permissions,
        "requested_scope":{"authoritative":False,"scope":"S2_FORMAL_GENERATION_STATIC_AUDIT_AND_INDEPENDENT_VERIFICATION_ONLY"},
        "formal_authorities":None,"final_test_state":"SEALED","final_test_read":False,"run_id":None}
    D.atomic_json(path,{"payload":payload,"payload_sha256":D.sha_bytes(D.canonical(payload))}); return path


@pytest.fixture
def tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "direct-tree"
    fake = {f:{"path":"SYNTHETIC_SUBSTITUTE_AUTHORITY","sha256":D.ZERO_HASH,"pointer":"/"} for f in D.FAMILIES}
    result = D.build_tree(root, FORMAL_SCHEMAS, ALLOWLIST, D.synthetic_bundle(), fake)
    assert result == {"artifacts":92,"members":80,"direct_schema":True,"formal_input_read_count":0,"final_test_read":False}
    bundle = tmp_path / "synthetic-authorities.json"; D.atomic_json(bundle, D.synthetic_bundle())
    return root, bundle


def test_direct_schema_92_tree_no_wrappers(tree: tuple[Path, Path]) -> None:
    root, _ = tree; files = [p for p in root.rglob("*") if p.is_file()]
    assert len(files) == 92
    for path in files:
        if path.suffix == ".json":
            obj = json.loads(path.read_text())
            assert "identity_class" not in obj and "artifact" not in obj
            assert "TECHNICAL_FIXTURE" not in path.read_text()
    assert not any(Path(p).exists() for p in json.loads(ALLOWLIST.read_text())["paths"])


def test_release_gated_independent_verifier_success(tree: tuple[Path, Path], tmp_path: Path) -> None:
    _, _ = tree; gate = make_release(tmp_path / "gate"); root=REPO/gate["roots"]["staging"]; control=REPO/gate["roots"]["success"]
    fake={f:{"path":"SYNTHETIC_SUBSTITUTE_AUTHORITY","sha256":D.ZERO_HASH,"pointer":"/"} for f in D.FAMILIES}; D.build_tree(root,FORMAL_SCHEMAS,ALLOWLIST,D.synthetic_bundle(),fake)
    bundle=tmp_path/"gate"/"synthetic-authorities.json"; D.atomic_json(bundle,D.synthetic_bundle())
    args = V.parser().parse_args(["technical-substitute","--repo-root",str(REPO),"--tree-root",str(root),"--control-root",str(control),
        "--schema-root",str(FORMAL_SCHEMAS),"--allowlist",str(ALLOWLIST),"--release",str(gate["release"]),"--attestation",str(gate["attestation"]),
        "--contract",str(gate["contract"]),"--authorization-schema",str(AUTH_SCHEMA),"--attestation-schema",str(ATT_SCHEMA),"--technical-authority",str(bundle)])
    result = V.execute(args)
    assert result["status"] == "VERIFIED_SUCCESS" and (control / "VERIFIED_SUCCESS.json").is_file()


def test_draft_rejected_before_any_authority_read(tree: tuple[Path, Path], tmp_path: Path) -> None:
    root, bundle = tree; draft = make_draft(tmp_path / "draft.json")
    with pytest.raises(Exception, match="DRAFT"):
        V.authorize(draft, AUTH_SCHEMA, tmp_path/"missing-attestation", ATT_SCHEMA, tmp_path/"missing-contract", "x", "technical-substitute", REPO)
    assert not any((tmp_path / f"DO_NOT_READ_{f}.json").exists() for f in D.FAMILIES)


def test_driver_formal_cli_rejects_draft_before_inputs(tmp_path: Path) -> None:
    draft=make_draft(tmp_path/"draft.json"); sentinel=tmp_path/"DO_NOT_READ.json"; control=tmp_path/"control"
    cmd=[sys.executable,str(REPO/"scripts/gen_enc_2c_s2_corr02/driver_corr02.py"),"formal","--repo-root",str(REPO),
         "--release",str(draft),"--attestation",str(tmp_path/"missing-attestation"),"--contract",str(tmp_path/"missing-contract"),
         "--authorization-schema",str(AUTH_SCHEMA),"--schema-root",str(FORMAL_SCHEMAS),"--allowlist",str(ALLOWLIST),"--control-root",str(control)]
    for name in ("hand","near","random","physics"):
        cmd += [f"--{name}-path",str(sentinel),f"--{name}-sha256","0"*64,f"--{name}-pointer","/DO_NOT_READ"]
    result=subprocess.run(cmd,capture_output=True,text=True)
    assert result.returncode==2 and "RELEASE_IDENTITY" in result.stderr and not sentinel.exists()
    marker=control/"FAIL_CLOSED.json"; assert marker.is_file()
    jsonschema.validate(json.loads(marker.read_text()),json.loads((FORMAL_SCHEMAS/"fail_closed_record.schema.json").read_text()))


def test_formal_authority_cli_substitution_rejected_before_read(tmp_path: Path) -> None:
    gate=make_release(tmp_path/"gate"); control=REPO/gate["roots"]["failure"]; sentinel=tmp_path/"DO_NOT_READ_SUBSTITUTE.json"
    cmd=[sys.executable,str(REPO/"scripts/gen_enc_2c_s2_corr02/driver_corr02.py"),"formal","--repo-root",str(REPO),
         "--release",str(gate["release"]),"--attestation",str(gate["attestation"]),"--contract",str(gate["contract"]),
         "--authorization-schema",str(AUTH_SCHEMA),"--schema-root",str(FORMAL_SCHEMAS),"--allowlist",str(ALLOWLIST),"--control-root",str(control)]
    for name in ("hand","near","random","physics"):
        cmd += [f"--{name}-path",str(sentinel),f"--{name}-sha256","0"*64,f"--{name}-pointer","/WRONG"]
    result=subprocess.run(cmd,capture_output=True,text=True)
    assert result.returncode==2 and "FORMAL_AUTHORITY_SUBSTITUTION_FORBIDDEN" in result.stderr and not sentinel.exists()


@pytest.mark.parametrize("mutation", ["missing", "false_static", "hash"])
def test_verifier_disagreement_is_fail_closed(tree: tuple[Path, Path], tmp_path: Path, mutation: str) -> None:
    _, _ = tree; gate = make_release(tmp_path / "gate"); root=REPO/gate["roots"]["staging"]; control=REPO/gate["roots"]["failure"]
    fake={f:{"path":"SYNTHETIC_SUBSTITUTE_AUTHORITY","sha256":D.ZERO_HASH,"pointer":"/"} for f in D.FAMILIES}; D.build_tree(root,FORMAL_SCHEMAS,ALLOWLIST,D.synthetic_bundle(),fake)
    bundle=tmp_path/"gate"/"synthetic-authorities.json"; D.atomic_json(bundle,D.synthetic_bundle())
    member = next(root.rglob("HAND_01.identity.json")); obj = json.loads(member.read_text())
    if mutation == "missing": del obj["cad_static_audit"]["volume_m3"]
    elif mutation == "false_static": obj["cad_static_audit"]["volume_m3"] *= 0.9
    else: obj["member_sha256"] = "f" * 64
    D.atomic_json(member, obj)
    args = V.parser().parse_args(["technical-substitute","--repo-root",str(REPO),"--tree-root",str(root),"--control-root",str(control),
        "--schema-root",str(FORMAL_SCHEMAS),"--allowlist",str(ALLOWLIST),"--release",str(gate["release"]),"--attestation",str(gate["attestation"]),
        "--contract",str(gate["contract"]),"--authorization-schema",str(AUTH_SCHEMA),"--attestation-schema",str(ATT_SCHEMA),"--technical-authority",str(bundle)])
    result = V.execute(args)
    assert result["status"] == "FAIL_CLOSED" and (control / "FAIL_CLOSED.json").is_file()


@pytest.mark.parametrize("field", ["release_full_sha256","guardian_review_sha256","run_id","terminal_roots"])
def test_attestation_mutations_rejected(tree: tuple[Path, Path], tmp_path: Path, field: str) -> None:
    _, _ = tree; gate = make_release(tmp_path / "gate"); att = json.loads(gate["attestation"].read_text())
    att[field] = ({"staging":"bad","success":"bad","failure":"bad","temp":"bad","journal":"bad"} if field=="terminal_roots" else "0"*64)
    D.atomic_json(gate["attestation"], att)
    with pytest.raises(Exception):
        D.validate_release(REPO,gate["release"],gate["attestation"],gate["contract"],AUTH_SCHEMA,"formal","S2_GENERATE_STATIC")


def test_actual_guardian_review_bytes_hash_mutation_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    gate = make_release(tmp_path / "gate")
    monkeypatch.setattr(D, "GUARDIAN_REVIEW_SHA256", "0"*64)
    with pytest.raises(Exception, match="GUARDIAN"):
        D.validate_release(REPO,gate["release"],gate["attestation"],gate["contract"],AUTH_SCHEMA,"formal","S2_GENERATE_STATIC")


def test_run_id_exact_bytes_and_literal_5c6e() -> None:
    hashes = {name: hashlib.sha256(name.encode()).hexdigest() for name in D.MANIFEST_ORDER}; release = "a"*64
    preimage = b"\x0a".join([D.DOMAIN,release.encode(),D.TASK_ID.encode()]+[hashes[k].encode() for k in D.MANIFEST_ORDER])
    assert not preimage.endswith(b"\x0a") and b"\\n" not in preimage
    assert D.LITERAL_BACKSLASH_N.hex()=="5c6e" and D.derive_run_id(release,D.TASK_ID,hashes)==V.derive_run_id(release,hashes)


@pytest.mark.parametrize("inject", ["copy","fsync","replace","journal","progress"])
def test_publication_faults_rollback_to_zero(tree: tuple[Path, Path], tmp_path: Path, inject: str) -> None:
    root,_=tree; repo=tmp_path/"publication"; journal=tmp_path/"journal.json"; run="b"*64
    with pytest.raises(Exception): D.transaction_publish(root,repo,ALLOWLIST,journal,run,inject=inject,inject_index=1)
    assert not any((repo/p).exists() for p in json.loads(ALLOWLIST.read_text())["paths"])
    state=json.loads(journal.read_text()); assert state["state"]=="ROLLED_BACK" and state["published"]==[] and state["transaction_owned_temps"]==[]


def test_publication_success_uses_exact_s1_allowlist(tree: tuple[Path, Path], tmp_path: Path) -> None:
    root,_=tree; repo=tmp_path/"publication"; journal=tmp_path/"journal.json"; run="d"*64
    result=D.transaction_publish(root,repo,ALLOWLIST,journal,run)
    paths=json.loads(ALLOWLIST.read_text())["paths"]
    assert result["published"]==92 and all((repo/p).is_file() for p in paths)
    assert (repo/"docs/progress/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION_RESULTS.md").is_file()
    assert json.loads(journal.read_text())["state"]=="COMMITTED"


@pytest.mark.parametrize("state", ["PREPARED","PUBLISHING"])
def test_startup_recovery_only_owned_temps(tmp_path: Path, state: str) -> None:
    run="c"*64; owned=tmp_path/f"owned.{run}.c2tmp"; unrelated=tmp_path/"unrelated.tmp"; published=tmp_path/"published.json"
    owned.write_text("x"); unrelated.write_text("keep"); published.write_text("x"); journal=tmp_path/"journal.json"
    D.atomic_json(journal,{"schema_version":"gen_enc_2c_s2_corr02_publication_journal_v1","run_id":run,"state":state,"published":[str(published)],"transaction_owned_temps":[str(owned)]})
    result=D.startup_recovery(journal,run)
    assert result["recovered"] and not owned.exists() and not published.exists() and unrelated.exists()


def test_stale_cross_attempt_root_rejected(tmp_path: Path) -> None:
    gate=make_release(tmp_path/"gate"); stale=REPO/gate["roots"]["staging"]; stale.mkdir(parents=True)
    try:
        with pytest.raises(Exception,match="STALE"):
            D.validate_release(REPO,gate["release"],gate["attestation"],gate["contract"],AUTH_SCHEMA,"formal","S2_GENERATE_STATIC")
    finally:
        stale.rmdir()


def test_package_results_requires_exactly_one_terminal(tmp_path: Path) -> None:
    run="e"*64; success=tmp_path/"success"/run; failure=tmp_path/"failure"/run
    with pytest.raises(Exception,match="EXACTLY_ONE"): D.package_results(success,failure,run)
    success.mkdir(parents=True); D.atomic_json(success/"VERIFIED_SUCCESS.json",{"run_id":run,"terminal_state":"VERIFIED_SUCCESS"})
    assert D.package_results(success,failure,run)["terminal"]=="VERIFIED_SUCCESS"
    failure.mkdir(parents=True); D.atomic_json(failure/"FAIL_CLOSED.json",{"run_id":run,"terminal_state":"FAIL_CLOSED"})
    with pytest.raises(Exception,match="EXACTLY_ONE"): D.package_results(success,failure,run)


def test_original_bf_review_lineage_exact() -> None:
    review=json.loads((REPO/"outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2C_S2_PREEXECUTION_FREEZE_REVIEW.json").read_text())
    assert [x["id"] for x in review["blocking_findings"]]==[f"S2-BF-{i:02d}" for i in range(1,12)]
    assert hashlib.sha256((REPO/REVIEW_REL).read_bytes()).hexdigest()=="e50c05875fb26116f71e2e4142ce2f13f415f1c4c8095377a4be3878374c6e1d"


def test_cli_help_and_forbidden_imports() -> None:
    for script in ("driver_corr02.py","independent_verifier_corr02.py"):
        assert subprocess.run([sys.executable,str(REPO/"scripts/gen_enc_2c_s2_corr02"/script),"--help"],capture_output=True).returncode==0
    source=(REPO/"scripts/gen_enc_2c_s2_corr02/independent_verifier_corr02.py").read_text()
    assert all(token not in source for token in ("import driver","import generator","import orchestrator","import cad_mapper"))
