# GEN-ENC-CAD-1 implementation-contract proposal REV03

Version: `GEN-ENC-CAD-1-PHASE-A-PROPOSAL-REV03-v1`

Date: 2026-08-28

Terminal state: `READY_FOR_GUARDIAN_CONTRACT_PREEXECUTION_REVIEW_REV03`

Evidence label: `E0_WINDOWS_LONG_PATH_TECHNICAL_RECOVERY_CONTRACT_PROPOSAL`

Current state: `recovery_implementation_authorized=false`; `implementation_task_creation_authorized=false`; `dispatch_authorization_record_creation_authorized=false`; `implementation_source_creation_authorized=false`; `test_modification_authorized=false`; `executable_schema_creation_authorized=false`; `literal_fixture_creation_authorized=false`; `literal_fixture_execution_authorized=false`; `independent_verifier_authorized=false`; `technical_conformance_preflight_authorized=false`; `timing_preflight_authorized=false`; `phase_b_retry_authorized=false`; `formal_generator_authorized=false`; `formal_seed_authorized=false`; `formal_row_authorized=false`; `scientific_identity_generation_authorized=false`; `formal_instance_count=0`; `static_eligibility_authorized=false`; `gen_enc_2_authorized=false`; `final_test_read=false`.

## Increment metadata and Attempt 01 disposition

- **New content:** Windows extended-length path-addressing recovery contract implementing every `required_REV03_preexecution_corrections` item from the Attempt 01 result-seal review.
- **Relates to:** unchanged initial/REV01/REV02 CAD-1 packages; `GEN_ENC_CAD_1_PHASE_B_RESULT_SEAL_REVIEW_ATTEMPT_01.json`; the retained Attempt 01 artifact inventory, complete fixture manifest, failure record and consumed dispatch.
- **Unchanged:** all prior contract bytes; all 70 Attempt 01 artifacts in this authoring turn; immutable failure record and old dispatch; logical paths, canonical bytes/hashes/manifests, stable IDs, run-id/staging formulas, 42-fixture order/cardinality, success/failure roots, CAD-0 U1/U2/U3 and every scientific/formal boundary.
- **Evidence:** E0 recovery proposal only. Attempt 01 remains `E1_IMPLEMENTATION_ATTEMPT_TECHNICAL_FAILURE_ONLY`, with no E1 conformance, static eligibility, manufacturability or scientific authority.
- **Override:** `overrides=false`; this is a forward-only technical addendum.

Before this proposal was written, the 70 retained artifacts were rehashed individually with zero mismatch. Their guardian inventory seal is `90777da5bf2ed51f8d1726143fb74041c271a0cc5236e1987cf5142907d16b63`. The byte-identical complete fixture manifest is `0c5944324535ae082c1246765e10a63d3c8035906476ccc175133a2102cfc521`; the immutable failure record is `ff83589406e2e9e68f18ad3bfdf6db8a9f3cec3ca6a85d3e3a0407eed8fdee38`.

## 1. Exact recovery byte-change boundary

After separate guardian preexecution approval and a new dispatch, only these three existing files may change:

1. `scripts/gen_enc_cad_1_compile_fixture.py`
2. `scripts/gen_enc_cad_1_verify_fixture.py`
3. `tests/test_gen_enc_cad_1_contract_conformance.py`

The first two may change only to embed their own stdlib-only Windows path adapter and route the frozen filesystem operations through it. The test file may change only by adding deterministic ordinary-local adapter tests. No other source, schema, test, literal fixture, complete fixture manifest, contract or Attempt 01 artifact may change. A fourth changed file, unlisted creation, or scope expansion stops recovery and requires a new reviewed proposal.

## 2. Duplicated isolated adapters and import boundary

The compiler script and verifier script must each contain a complete, separately implemented adapter. There is no shared helper, import between adapters, generated copy, third-party package or new module. The verifier's permitted stdlib import list remains exactly REV01's: `argparse`, `collections`, `dataclasses`, `decimal`, `fractions`, `hashlib`, `itertools`, `json`, `math`, `os`, `pathlib`, `platform`, `stat`, `struct`, `sys`, `typing`. No import expansion is allowed.

Each adapter accepts only an already lexically validated logical exact-relative path plus the already validated resolved repository root. It derives a normal absolute drive path beneath that root and then, internally, derives the Windows extended-length OS-call representation `\\?\D:\...`. That prefix is only an alternate address for the same object. It never appears in user input, CLI fields, canonical JSON, manifests, hashes, stable IDs, run ID inputs, logs or reported logical paths.

Reject before conversion: user-supplied absolute or prefixed input; `\\?\`, `\\.\`, UNC/network/device/GLOBALROOT namespaces; rooted or drive-relative forms; colon/alternate-data-stream syntax; glob, alias, environment expansion, `.`/`..`; any logical mutation; a resolved object outside the repository/assigned root; or an ancestor identity mismatch.

## 3. Same-object and repeated safety rules

For every operation, reconstruct the extended representation solely from the verified root plus unchanged logical components. Strip-prefix normalization must round-trip exactly to the frozen normal absolute path. Existing parent/object identity, drive, case-normalized components and boundary membership must match; otherwise fail closed.

Immediately before **each** OS call, repeat containment and every-existing-ancestor symlink/junction/reparse-point inspection. The adapter must cover, consistently and without fallback paths: absence/collision checks; directory creation; exclusive file creation/open; ordinary read; stat/lstat; hashing reads; flush and `fsync`; `os.replace`; unlink; and `rmdir`. A check-to-use identity/boundary change fails `PATH_IDENTITY_OR_BOUNDARY_MISMATCH`. No operation may silently retry through an unprefixed, shortened, relocated or less-validated path.

Logical paths and canonical identities remain unchanged. The run ID preimage and SHA-256 formula remain REV02-exact. Staging names remain `<final-filename>.stage.<run_id>.tmp`; the 11-file success root and clean-owned-run failure root remain unchanged. Attempt 01's run ID is not reusable.

## 4. Existing-test-source recovery tests

Only `tests/test_gen_enc_cad_1_contract_conformance.py` may receive new tests. No 43rd fixture or fixture-manifest change is allowed. Deterministic ordinary-local tests must cover:

- a derived absolute path longer than 260 characters while every component is shorter than 255;
- logical normal/extended representation identity and exact logical-path preservation;
- exclusive create, read, SHA-256, flush/`fsync`, atomic replace, unlink and directory cleanup through the adapter;
- collision preservation with zero deletion/overwrite;
- rejection of user-supplied extended prefixes, absolute paths, UNC, device namespace, drive-relative and ADS inputs;
- rejection of a symlink/junction/reparse escape or, if the local account cannot create such an object, a deterministic injected `stat`/reparse observation that exercises the identical fail-closed branch without weakening the assertion.

Tests may use only owned temporary directories beneath the approved ordinary-local test root and must remove only exact owned paths. Their addition is technical conformance coverage, not a new literal fixture or scientific object.

## 5. Recovery freeze and gates

After separately authorized recovery implementation, rehash all 70 retained paths. Exactly the three allowlisted paths may differ; the other 67 must match Attempt 01 hashes. Freeze old/new/diff hashes for the three, verify the 70-entry path set is unchanged, and require the complete fixture manifest hash to remain exactly `0c5944...c521`.

Before any retry, rerun only the static post-correction checks: Python syntax/AST, exact import allowlists, no shared helper/third-party dependency, negative capabilities, executable-schema hashes/meta-validation, exact path/cardinality, 42-fixture manifest bytes/order and zero unlisted files. The resulting three-file hashes and static-check record require a new guardian `CONTRACT_PRE_EXECUTION_REVIEW`. Recovery implementation approval does not itself authorize fixture execution.

## 6. New task, dispatch and run provenance

Old task `01a04695-2076-72f1-a118-2f9e4a402f90`, old dispatch SHA-256 `963174135167f125391f27109d5519636dd46345d202997772b1ffe059a40fc9`, and old run ID `ae70d9d6c84c2fb9b9723ee9833f266601a9e89c38ef18aa3652bf719a87febe` are consumed/revoked and must never be reused. Their bytes and failure provenance remain immutable.

Strict sequence: guardian approves this exact REV03 for recovery implementation; intermediate controller reserves a new idle lowest-level task ID; that task takes no action; the three-file recovery is made only under the specifically authorized recovery task boundary; updated hashes/static checks are sealed; guardian performs another preexecution review of those exact bytes; intermediate controller reserves a new idle execution task and issues a new exact-path immutable dispatch bound to it; the task derives a new run ID and validates Gate A before action. No old identity may shortcut this sequence.

This REV03 creates no task or dispatch and authorizes no implementation. No Attempt 01 source/schema/test/fixture was modified, no command or test was executed, and no formal/scientific data was accessed. Do not contact guardian or commit/push/tag/release. Stop at `READY_FOR_GUARDIAN_CONTRACT_PREEXECUTION_REVIEW_REV03`.
