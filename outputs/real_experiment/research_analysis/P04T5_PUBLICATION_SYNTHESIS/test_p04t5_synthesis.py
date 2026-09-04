from p04t5_synthesis import decide_terminal_state, validate_evidence_chain


def test_current_authority_closes_scheme_3a() -> None:
    assert decide_terminal_state(
        inputs_ok=True,
        p04b_credible_for_u4=False,
        new_verifiable_model_repair=False,
    ) == "P04T5 CLOSE_SCHEME_3A_WITH_PUBLISHABLE_MECHANISM_RESULT"


def test_rebuilt_contract_requires_new_repair_basis() -> None:
    assert decide_terminal_state(
        inputs_ok=True,
        p04b_credible_for_u4=False,
        new_verifiable_model_repair=True,
    ) == "P04T5 AUTHORIZE_REBUILT_MODEL_CONTRACT_BEFORE_P05"


def test_integrity_failure_precedes_scientific_decision() -> None:
    assert decide_terminal_state(
        inputs_ok=False,
        p04b_credible_for_u4=False,
        new_verifiable_model_repair=False,
    ) == "P04T5 BLOCKED_INPUT_INTEGRITY"


def test_evidence_chain_requires_all_frozen_stages_and_boundaries() -> None:
    rows = [
        {"stage": stage, "supports": "bounded claim", "does_not_support": "overclaim"}
        for stage in ("P04T1V", "P04T2", "P04T3", "P04T4_REV01")
    ]
    validate_evidence_chain(rows)
