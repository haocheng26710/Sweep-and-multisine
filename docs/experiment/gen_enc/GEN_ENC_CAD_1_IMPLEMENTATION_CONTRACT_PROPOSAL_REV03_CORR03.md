# GEN-ENC-CAD-1 implementation-contract proposal REV03-CORR03

Version: `GEN-ENC-CAD-1-PHASE-A-PROPOSAL-REV03-CORR03-v1`

Date: 2026-08-28

Terminal state: `READY_FOR_GUARDIAN_CORR03_CONTRACT_REVIEW`

Evidence label: `E0_LF_DESCRIPTOR_AND_VALIDATOR_BOUNDARY_PROFILE_CONTRACT_ONLY`

Current state: `corr03_task_reservation_authorized=false`; `corr03_authorization_record_creation_authorized=false`; `corr03_patch_authorized=false`; `corr03_static_checks_authorized=false`; `corr03_ordinary_tests_authorized=false`; `execution_task_reservation_authorized=false`; `new_execution_dispatch_authorized=false`; `new_run_id_derivation_authorized=false`; `technical_conformance_preflight_authorized=false`; `timing_preflight_authorized=false`; `gate_a_authorized=false`; `gate_b_authorized=false`; `literal_fixture_execution_authorized=false`; `independent_verifier_authorized=false`; `phase_b_retry_authorized=false`; every formal/scientific authorization is false; `formal_instance_count=0`; `final_test_read=false`.

## Increment metadata

- **New content:** forward-only bounded LF descriptor and validator boundary-profile correction required by `GEN_ENC_CAD_1_E1_RETRY_ATTEMPT_02_PRE_GATE_RESULT_REVIEW.json`.
- **Relates to:** sealed Attempt02 pre-Gate result, immutable CORR02 bytes/evidence, exact 42-record manifest, prior contracts and CAD-0 authority.
- **Unchanged:** manifest bytes and every record; current implementation/test/dispatch bytes; fixture paths/hashes/statuses; parsers, CAD algorithms, classification, thresholds, run-id algorithm, output roots and scientific/formal prohibitions.
- **Evidence:** E0 contract/governance only; no corrected executable bytes, ordinary-test result or E1 evidence.
- **Override:** `overrides=false`; prior reports and evidence remain byte-authoritative provenance.

## 1. Attempt02 classification and seal

Attempt02 task `01a047a9-b299-7460-b37d-638e8e5691e2` and dispatch `outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/dispatch/GEN_ENC_CAD_1/GEN_ENC_CAD_1_PHASE_B_TASK_01a047a9-b299-7460-b37d-638e8e5691e2.dispatch_authorization.json`, SHA-256 `020e926bec9589d5c952652e4432d16ea302c1e134db01a732c989e615dcded2`, are consumed and may not be edited, retried or reused. Attempt02 stopped before run-id derivation and before Gate A. It generated no E1 pass/fail, static result, scientific result, success file or failure record.

The blocking defect is only serialization-descriptor provenance: the dispatch boundary profile stated `NO_TRAILING_NEWLINE`, while the already sealed manifest has one final LF. It is not a payload, order, fixture, endpoint, classification or science defect.

## 2. Immutable manifest and rejection of Option B

The following is indivisible authority:

- path: `tests/fixtures/gen_enc_cad_1/complete_fixture_manifest.json`;
- byte length: `21334`;
- last byte: decimal `10` / hexadecimal `0A`;
- SHA-256 of actual exact bytes: `0c5944324535ae082c1246765e10a63d3c8035906476ccc175133a2102cfc521`;
- records: exactly 42, ordinal 1 through 42 in the frozen order;
- all fixture IDs, paths, fixture hashes, expected `fixture_run_status`, `observed_subject_status`, reason codes and subject-presence classifications unchanged;
- exactly one terminal LF: raw bytes equal canonical no-trailing-newline payload bytes followed by one `0A`, with neither zero nor two terminal LF bytes.

Option B—rewriting the manifest without its final LF—is prohibited. The no-LF prospective SHA `da958738ce59a7bbd2320d02b326cc661816a3cc3d70a4aa4ab8c2d175545714` is a negative-control identity only and may not replace the sealed hash or enter an authority chain as the manifest identity.

## 3. Corrected descriptor and non-spillover boundary

The sole corrected descriptor is exactly:

`UTF8_NO_BOM_RECURSIVE_UNICODE_KEY_SORT_ARRAYS_PRESERVED_SHORTEST_ROUNDTRIP_FINITE_BINARY64_NO_WHITESPACE_WITH_EXACTLY_ONE_TRAILING_LF_EXCEPTION_FOR_THIS_SEALED_MANIFEST`

The exception applies only when all predicates are true simultaneously: exact manifest path; exact SHA-256 `0c5944...c521`; exact 21,334-byte length; exact 42-record cardinality; exact frozen ordinal/order, IDs, paths, hashes and statuses; parsed payload canonicalization equal to raw bytes excluding exactly one final `0A`; and no second terminal LF. Any mismatch fails closed before run-id derivation.

This descriptor does not alter the generic canonical JSON rule. Every dispatch, schema, source manifest, report, result, inventory and other JSON artifact continues to require its previously frozen canonical bytes and newline rule. No alias, suffix-based exemption, directory-wide exception, compatible hash or parsed-payload-only acceptance is allowed.

## 4. Validator profile binding and exact future edit boundary

The current normalized execution boundary profile SHA-256 is `9b41240ef0f29a7895f5a5fe5e99990a9ae9f86ce2bd085172d6f73363547303`. Replacing only the manifest descriptor with the exact corrected string produces the unique corrected normalized profile SHA-256:

`4b30217bc150d8d47fb5dfb4203a67f5286246d1d9f3e118a52c532592bcc258`

The future correction may change only:

1. `scripts/gen_enc_cad_1_compile_fixture.py`, current SHA-256 `50672fb40b10cfe38673fc79c9b1d54fabed41bc6a489d5ee3dfcb63404cc1df`, 26,409 bytes;
2. `scripts/gen_enc_cad_1_verify_fixture.py`, current SHA-256 `0e8b83c9609010034221fef5bf4747d7f967f83b1f42ab115e91ce0c54802115`, 31,959 bytes;
3. `tests/test_gen_enc_cad_1_contract_conformance.py`, current SHA-256 `7bc9ce69e8938b6cd4544a191fc4e7b9cf1558d1ca6cf4e852de2023df1ff590`, 13,474 bytes.

Within each validator, changes are limited to its own exact manifest boundary-envelope predicate, descriptor binding and `BOUNDARY_PROFILE_SHA256` replacement from the old value to `4b3021...c258`. Compiler and verifier must independently require the exact path/hash/length/42/order/one-LF conjunction before deriving a run ID. No shared helper or cross-import is allowed. The verifier remains stdlib-only with the existing exact 16-import allowlist.

The test path may change only to add the bounded ordinary falsifiers in section 6. No fourth path may change. The generic JSON parser, canonical serializer, fixture parser, fixture files, CAD/root/ownership/graph/clearance algorithms, classifications, thresholds, status machines, run-id function, staging formula and output package are outside the edit boundary.

## 5. Run-id preservation

The run-id formula remains exactly `GEN_ENC_CAD_1_RUN_ID_V1\n{A}\n{T}\n{F}` with no final newline, followed by lowercase SHA-256 of those ASCII bytes. `A` remains the hash of exact canonical newly validated dispatch bytes; `T` remains the exact newly validated task ID; `F` remains the SHA-256 of actual exact sealed manifest bytes:

`0c5944324535ae082c1246765e10a63d3c8035906476ccc175133a2102cfc521`

No canonicalized-payload hash, no-LF hash or descriptor hash may substitute for `F`. The two validators continue to derive independently and cross-check explicit `--run-id`. This contract derives no run ID.

## 6. Ordinary falsifiers

The existing ordinary test source must add exactly five CORR03 cases; they are not members of the 42-fixture manifest:

1. exact LF-bearing sealed bytes, descriptor, path, hash, length, cardinality and order pass both validators;
2. the same canonical payload with zero terminal LF fails the exact descriptor/hash binding;
3. the same canonical payload with two terminal LF bytes fails the exact descriptor/hash binding;
4. any payload, record order or declared/actual hash change fails closed;
5. compiler and verifier independently produce the same corrected boundary-profile SHA and accept/reject the same envelope.

Tests use isolated copies or in-memory bytes and never rewrite the sealed manifest. Expected negative rejection is a passing expectation match. No case emits fixture/member/static/scientific results or exercises Gate A/B.

## 7. Future correction authorization and incremental evidence

This contract creates no task or authorization. Only after guardian approval may the controller reserve one distinct idle CORR03 correction task and issue one canonical task-bound record at:

`outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/GEN_ENC_CAD_1_CORR03/GEN_ENC_CAD_1_REV03_CORR03_TASK_<task-id>.authorization.json`

Future schema path: `schemas/governance/gen_enc_cad_1_rev03_corr03_authorization.schema.json`. Issuer: `GEN_ENC_INTERMEDIATE_CONTROLLER`. The record must bind the approving review and this contract/progress/manifest, Attempt02 review hash, consumed task/dispatch, exact current three hashes, immutable manifest envelope, old/new profile hashes, exact three-path change boundary, exact evidence root/files, modes, runtime, expiry and revocation. Only bounded patch/static/ordinary-test/evidence fields may be true; all execution and scientific fields stay false.

The sole future evidence root is:

`outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/recovery_rev03/corr03_incremental_evidence/`

It contains exactly eight files, no subdirectories and zero unlisted paths:

1. `corr03_three_file_before_after_manifest.json`;
2. `corr03_unchanged_67_hash_verification.json`;
3. `corr03_retained_70_and_manifest_verification.json`;
4. `corr03_boundary_profile_verification.json`;
5. `corr03_static_check_report.json`;
6. `corr03_ordinary_test_report.json`;
7. `artifact_inventory.json`;
8. `SHA256SUMS.txt` with seven non-self entries; self excluded.

Evidence freezes three new hashes/lengths, 67 unchanged hashes, exact retained-70 cardinality, the unchanged 21,334-byte LF-bearing manifest, old/new profile reproduction and equality across validators, bounded static checks and exact ordinary outcomes. Any collision or pre-existing root causes zero writes and a stop.

## 8. Strict sequence and current stop

Exact future sequence: seal Attempt02 identities as consumed; guardian approves this contract; reserve a distinct idle correction task; issue/validate the CORR03 correction authorization before writes; patch only the three paths; run only bounded static checks and ordinary falsifiers; freeze the eight-file evidence package; stop without run-id, Gate A/B, 42 fixtures or verifier main; guardian reviews corrected bytes and evidence; only after that approval and required administrative confirmation reserve a new idle execution task; issue a new dispatch carrying the corrected descriptor/profile; derive a new run ID using actual sealed manifest bytes.

This phase modifies no manifest, implementation, test, dispatch or prior evidence. It executes no checks except read-only provenance/hash verification. Do not contact guardian or commit/push/tag/release. Stop at `READY_FOR_GUARDIAN_CORR03_CONTRACT_REVIEW`.
