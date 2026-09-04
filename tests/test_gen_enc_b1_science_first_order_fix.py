from scripts.gen_enc_b1_science_first.independent_verifier import EXPECTED_MEMBER_IDS,_ordered_member_paths

def test_explicit_frozen_order_ignores_lexical_physics_before_random(tmp_path):
    root=tmp_path/"members";root.mkdir()
    for member_id in reversed(EXPECTED_MEMBER_IDS):(root/(member_id+".json")).write_text("{}",encoding="utf-8")
    assert [path.stem for path in sorted(root.glob("*.json"))].index("PHYSICS_01") < [path.stem for path in sorted(root.glob("*.json"))].index("RANDOM_01")
    assert [path.stem for path in _ordered_member_paths(root)]==list(EXPECTED_MEMBER_IDS)
