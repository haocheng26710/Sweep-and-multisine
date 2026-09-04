# GEN-ENC-CAD-1 implementation-contract proposal REV03-CORR01

Version: `GEN-ENC-CAD-1-PHASE-A-PROPOSAL-REV03-CORR01-v1`

Date: 2026-08-28

Terminal state: `READY_FOR_GUARDIAN_REV03_CORR01_PREEXECUTION_REVIEW`

Evidence label: `E0_WINDOWS_LONG_PATH_TECHNICAL_RECOVERY_CONTRACT_CORRECTION`

Current state: `recovery_task_reservation_authorized=false`; `recovery_authorization_record_creation_authorized=false`; `recovery_task_action_authorized=false`; `recovery_implementation_authorized=false`; `test_modification_authorized=false`; `ordinary_local_recovery_tests_authorized=false`; `post_correction_static_checks_authorized=false`; `technical_conformance_preflight_authorized=false`; `timing_preflight_authorized=false`; `gate_a_authorized=false`; `gate_b_authorized=false`; `literal_fixture_execution_authorized=false`; `independent_verifier_authorized=false`; `phase_b_retry_authorized=false`; every formal/scientific authorization is false; `formal_instance_count=0`; `final_test_read=false`.

## Increment metadata

- **New content:** closed preexecution correction for the exact recovery authorization carrier, post-correction evidence package, recovery-only sequence, colon scope and per-operation Windows identity snapshots required by `GEN_ENC_CAD_1_PHASE_A_REV03_CONTRACT_PREEXECUTION_REVIEW.json`.
- **Relates to:** unchanged REV03 and its guardian review; Attempt 01 result seal and retained baseline; unchanged initial/REV01/REV02 packages.
- **Unchanged:** every prior byte and hash; Attempt 01 70 artifacts, failure record and consumed dispatch; three-file change allowlist; 42-fixture manifest; Windows adapter scope; logical paths, run formula, CAD/scientific semantics and zero counts.
- **Evidence:** proposal-only E0 recovery governance; no recovery implementation or execution evidence.
- **Override:** `overrides=false`; forward-only correction.

## 1. Recovery authorization carrier

Recovery authorization is a new governance object and is not the REV02 execution dispatch. Its sole future root is:

`outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/GEN_ENC_CAD_1_RECOVERY/`

Its sole filename pattern is:

`GEN_ENC_CAD_1_REV03_RECOVERY_TASK_<task-id>.authorization.json`

where `<task-id>` is the exact canonical UUID of the already reserved idle recovery task. The future schema path is `schemas/governance/gen_enc_cad_1_rev03_recovery_authorization.schema.json`; this correction defines it but creates neither schema nor record.

Issuer is exactly `GEN_ENC_INTERMEDIATE_CONTROLLER`. The canonical record binds issuer/thread, one idle recovery task ID, the REV03 guardian review path/hash `c752a9eaca6400cc5b55b975f26945665aadacac3ca7277dec1dcd6526e6d21a`, official decision and required disclosures, REV03 contract/progress/manifest paths and hashes, Attempt 01 70-file seal `90777d...6b63`, complete fixture manifest hash, exact three change paths with before hashes, exact evidence root/files, permitted recovery modes, runtime, expiry/revocation and all authorization booleans.

Only the recovery fields may be true: `recovery_task_action_authorized`, `recovery_implementation_authorized`, `test_modification_authorized`, `ordinary_local_recovery_tests_authorized`, and `post_correction_static_checks_authorized`. The record must keep technical-conformance execution, Gate A/B, 42 fixtures, independent verifier, 11-file package, retry, timing, formal/scientific/static/CAD/data/GEN-ENC-2 authorizations false. It derives no run ID and cannot authorize later execution.

Record JSON uses the existing canonical JSON rules; its identity is lowercase SHA-256 of exact canonical bytes. Validate path, schema, canonical round-trip, issuer, task equality, complete hash chain, mode and boundaries before any write. Any byte/hash/task/path/mode/runtime/boundary change, expiry or revocation invalidates it. Opaque secrets, environment substitution, old dispatch reuse or silent schema expansion are forbidden.

## 2. Exact post-correction evidence package

The sole future persistent evidence root is:

`outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/recovery_rev03/post_correction_evidence/`

It must be absent before authorized recovery and contain exactly seven files with no subdirectories or unlisted paths:

1. `three_file_before_after_manifest.json`
2. `unchanged_67_hash_verification.json`
3. `retained_70_path_set_verification.json`
4. `static_check_report.json`
5. `ordinary_recovery_test_report.json`
6. `artifact_inventory.json`
7. `SHA256SUMS.txt`

The first file records the exact three paths with before/after SHA-256 and byte lengths plus diff-scope classification. The second records all 67 unchanged paths/hashes and zero mismatches. The third proves the exact 70-path set/cardinality, three changed plus 67 unchanged, inventory seal relationship and unchanged complete fixture manifest. Static and ordinary-test reports use fixed required fields and zero scientific/formal counts. Inventory lists exactly the six non-self evidence files plus `SHA256SUMS.txt`.

`SHA256SUMS.txt` has exactly six entries—every evidence artifact except itself—ordered by Unicode-code-point path, using lowercase SHA-256, two spaces and LF; self is excluded to avoid recursion. Any collision or pre-existing root/file causes zero writes and preserves the existing object. These seven governance/result artifacts do not count as new implementation source, executable schema, test source or literal fixture.

## 3. Recovery-only sequence

The exact sequence is:

1. Validate the separately issued recovery authorization and all 70 baseline hashes before writes.
2. Patch only the three allowlisted files.
3. Run syntax/AST, exact import allowlist, negative-capability, no-shared-helper/no-third-party, executable-schema hash/meta-validation, exact path/cardinality, 42-manifest byte/hash/order and zero-unlisted static checks.
4. Run only deterministic ordinary-local recovery tests from the existing test source.
5. Freeze the exact seven-file evidence package.
6. Stop. Do not run Gate A, Gate B, any of the 42 fixtures, independent verifier, package-results or Phase B retry.
7. Submit the corrected three bytes and exact evidence package for another guardian `CONTRACT_PRE_EXECUTION_REVIEW`.

Ordinary recovery tests therefore run after the three-file patch and static checks, but before final hashes/evidence sealing. They are not members of the 42-fixture manifest and cannot change it.

## 4. Colon and path-input clarification

`ANY_COLON` rejection applies only to logical/user-supplied exact-relative input. Such input may contain no colon, drive designator, ADS or namespace prefix. Independently validate the configured repository root as a normal absolute local drive path matching `^[A-Za-z]:\\`; the single drive-designator colon at index 1 is permitted only in that internal verified root and in the normal absolute path derived from it. It is never accepted from the relative input.

Already extended-prefixed paths, UNC, `\\.\` device paths, `GLOBALROOT`, rooted paths, drive-relative paths and ADS remain rejected. The internal `\\?\D:\...` representation is derived only after these checks and never changes the logical identity.

## 5. Per-operation identity and reparse snapshot

Immediately before each path-based OS operation, `lstat` every existing ancestor and the existing target, recording internally: logical component index; normalized absolute component; `st_mode`; `st_dev`; `st_ino`; Windows `st_file_attributes`; `FILE_ATTRIBUTE_REPARSE_POINT` bit; `st_reparse_tag` when exposed; and parent identity `(st_dev,st_ino)`. Any reparse bit/tag, missing expected ancestor, parent/object identity change, root/drive/boundary change or strip-prefix round-trip mismatch fails closed before the operation.

For a nonexistent target, bind and recheck the existing parent identity. For `os.replace`, independently snapshot/recheck source, destination parent and existing destination. For unlink/rmdir, recheck the exact owned object and parent immediately before mutation.

`FLUSH` and `FSYNC` are handle-only operations: they inherit the identity and access mode of the file handle opened exclusively through the validated extended path. They do not perform a new path lookup. Any later path operation must nevertheless repeat the complete lstat/reparse/identity checks; handle inheritance never relaxes later checks.

## 6. Current stop

This correction creates no recovery task, authorization record, evidence package or schema, and modifies none of the Attempt 01 70 artifacts. No test, static recovery check, Gate, fixture, verifier or implementation command ran. Current hashes and zero counts remain unchanged. Do not contact guardian or commit/push/tag/release. Stop at `READY_FOR_GUARDIAN_REV03_CORR01_PREEXECUTION_REVIEW`.
