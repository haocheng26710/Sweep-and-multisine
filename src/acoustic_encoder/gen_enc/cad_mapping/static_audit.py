FEATURE_GATE = 0.002
LOAD_GATE = 0.0016


def audit_static(compiled):
    return {
        "classification": "TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY",
        "fixture_id": compiled["fixture_id"],
        "observed_subject_status": compiled["observed_subject_status"],
        "ordered_reason_codes": compiled["ordered_reason_codes"],
        "measurements": compiled.get("measurements", {}),
        "scientific_hypothesis_status": "NOT_TESTED",
        "formal_instance_count": 0,
        "final_test_read": False,
    }
