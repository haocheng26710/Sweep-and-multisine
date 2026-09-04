from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from scripts.gen_enc_fast_0 import adapter_independent as independent
from scripts.gen_enc_fast_0 import adapter_primary as primary
from scripts.gen_enc_fast_0 import authority_gate as gate
from scripts.gen_enc_fast_0 import technical_transaction as txn

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs/gen_enc/GEN_ENC_FAST_START/fast_0_authority_batch_contract_freeze"
TABLES = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/family_design_tables_rev01.json"
MANIFEST = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/family_identity_manifest_rev01.json"
SEEDS = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_exact_sealed_objects_read_only_and_independent_adapters_agree() -> None:
    before = {p: gate.sha256(p) for p in (TABLES, MANIFEST, SEEDS)}
    docs = [load(TABLES), load(MANIFEST), load(SEEDS)]
    left = primary.adapt(*docs)
    right = independent.consume(*docs)
    assert left == right
    assert len(left["hand_rows"]) == len(left["near_rows"]) == len(left["random_seeds"]) == 20
    assert len(left["random_uniforms"]) == 20 and all(len(x) == 13 for x in left["random_uniforms"])
    assert len(left["physics_permutations"]) == 15 and all(sorted(x) == list(range(20)) for x in left["physics_permutations"])
    assert before == {p: gate.sha256(p) for p in before}


def test_random_binary64_nextafter_special_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(primary, "splitmix64", lambda _: (1 << 64) - 1)
    monkeypatch.setattr(independent, "_mix", lambda _: (1 << 64) - 1)
    expected = __import__("math").nextafter(1.0, 0.0)
    assert primary.open_uniform(1, 0) == expected
    assert independent._u(1, 0) == expected


def test_authority_allowlist_is_exact_and_rejects_any_arbitrary_triple() -> None:
    allowlist = gate.load_allowlist(OUT / "authority_allowlist.json")
    gate.require_exact_triples(allowlist, allowlist["entries"])
    assert all(not x["technical_fixture"] and "fixtures" not in x["path"].casefold() for x in allowlist["entries"])
    for field, bad in (("path", "technical/fixture.json"), ("sha256", "0" * 64), ("pointer", "/wrong")):
        mutated = [dict(x) for x in allowlist["entries"]]
        mutated[0][field] = bad
        with pytest.raises(ValueError, match="TRIPLE"):
            gate.require_exact_triples(allowlist, mutated)


def test_allowlisted_bytes_hashes_pointers_and_shapes() -> None:
    allowlist = load(OUT / "authority_allowlist.json")
    for item in allowlist["entries"]:
        path = REPO / item["path"]
        assert gate.sha256(path) == item["sha256"]
        value = load(path)
        if item["pointer"]:
            for token in item["pointer"].lstrip("/").split("/"):
                value = value[int(token)] if isinstance(value, list) else value[token]
        shape = item["object_shape"]
        assert shape["type"] == ("object" if isinstance(value, dict) else "array" if isinstance(value, list) else type(value).__name__)
        if isinstance(value, list):
            assert len(value) == shape["count"]
        if isinstance(value, dict):
            assert list(value) == shape["field_names"]


def test_four_batches_are_disjoint_complete_80_and_failure_preserving() -> None:
    ledger = load(OUT / "four_batch_ledger.json")
    slots = [(m["family_id"], m["slot_ordinal"]) for b in ledger["batches"] for m in b["members"]]
    assert len(slots) == len(set(slots)) == 80
    assert all(m["failure_slot_retained"] for b in ledger["batches"] for m in b["members"])
    assert [b["family_ordinals"] for b in ledger["batches"]] == [list(range(x, x + 5)) for x in (1, 6, 11, 16)]


def test_draft_attempt0_rejected_before_authority_read(tmp_path: Path) -> None:
    draft = load(REPO / "tests/fixtures/gen_enc_fast_0/draft_attempt0.json")
    sentinel = tmp_path / "authority-must-not-be-read.json"
    with pytest.raises(ValueError, match="BEFORE_READ"):
        gate.pre_read_authorization(draft)
    assert not sentinel.exists()


def test_single_terminal_no_mixed_state(tmp_path: Path) -> None:
    root = tmp_path / "terminal"
    txn.write_terminal(root, "SUCCESS", {"identity_class": "TECHNICAL_FIXTURE_ONLY"})
    with pytest.raises(ValueError, match="ALREADY"):
        txn.write_terminal(root, "FAIL_CLOSED", {"identity_class": "TECHNICAL_FIXTURE_ONLY"})
    assert [x.name for x in root.glob("*.json")] == ["VERIFIED_SUCCESS.json"]


def test_real_subprocess_termination_after_replace_is_recovered_exactly(tmp_path: Path) -> None:
    source = REPO / "tests/fixtures/gen_enc_fast_0/technical_payload.json"
    root = tmp_path / "exclusive-target-root"
    target = root / "payload.json"
    journal = tmp_path / "journal.json"
    unrelated = root / "unrelated.txt"
    root.mkdir()
    unrelated.write_text("preserve", encoding="utf-8")
    run_id = "a" * 64
    code = "from pathlib import Path; from scripts.gen_enc_fast_0.technical_transaction import publish_one; publish_one(Path(r'%s'),Path(r'%s'),Path(r'%s'),'%s',True)" % (source, target, journal, run_id)
    completed = subprocess.run([sys.executable, "-c", code], cwd=REPO, check=False)
    assert completed.returncode == 73 and target.exists() and journal.exists()
    result = txn.recover(journal, run_id, root)
    assert result["state"] == "ROLLED_BACK" and not target.exists()
    assert unrelated.read_text(encoding="utf-8") == "preserve"


def test_final_test_is_sealed_and_never_allowlisted() -> None:
    with pytest.raises(ValueError, match="FINAL_TEST"):
        gate.assert_no_final_test("data/final_test/member.json")
    allowlist = load(OUT / "authority_allowlist.json")
    assert all("final_test" not in x["path"].casefold() for x in allowlist["entries"])
    assert load(OUT / "execution_state.json")["final_test_read"] is False


def test_schemas_are_valid_and_package_draft_remains_false() -> None:
    for path in (REPO / "schemas/gen_enc/fast_0").glob("*.json"):
        jsonschema.Draft202012Validator.check_schema(load(path))
    state = load(OUT / "draft_authorization_state.json")
    assert state["record_kind"] == "DRAFT" and state["attempt"] == 0 and state["run_id"] is None and not state["may_flip_or_promote"]
    assert not any(state["permissions"].values())


def test_adapter_sources_are_independent_of_each_other_and_legacy() -> None:
    sources = [(REPO / "scripts/gen_enc_fast_0/adapter_primary.py").read_text(encoding="utf-8"), (REPO / "scripts/gen_enc_fast_0/adapter_independent.py").read_text(encoding="utf-8")]
    forbidden = ("adapter_primary", "adapter_independent", "gen_enc_2c", "driver", "generator", "cad_mapper")
    assert all(all(token not in source for token in forbidden) for source in sources)
