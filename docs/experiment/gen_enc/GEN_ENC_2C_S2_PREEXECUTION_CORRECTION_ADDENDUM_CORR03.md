# GEN-ENC-2C S2 preexecution correction addendum — CORR03

## Scope and authority

This addendum records a bounded technical preexecution correction on task `01a048bd-dc5e-7e93-87e6-72d299ebaa4d`. Its sole direct authority is the immutable CORR02 guardian rejection:

- path: `outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_2C_S2_CORR02_PREEXECUTION_IMPLEMENTATION_FREEZE_REVIEW.json`
- SHA-256: `d33792bd5d81ae7bdc3c3e4059f86ad211e12679042f8ac79d6632401e3ad2ac`
- verdict: `REJECT`
- scientific interpretation: `NOT_TESTED`

CORR03 did not read formal HAND or NEAR rows, formal RANDOM seeds, or formal PHYSICS values. It did not create a RELEASE or guardian approval, did not create formal identities, did not run formal CAD/static eligibility, and did not publish any of the 92 formal targets. The only exercised authorities were explicitly labelled technical substitutes with exact future-input shapes.

Evidence remains `E1_TECHNICAL_PREEXECUTION_CORRECTION_ONLY`. This addendum does not claim scientific evidence, formal execution, or guardian closure.

## Exact authority adapter

The CORR03 driver and independent verifier implement the same frozen input contract through separate code paths.

- HAND accepts exactly 20 ordered stored rows, exact `HAND_01` through `HAND_20` member IDs, and the stored `volume_logit_*`, derived 270-degree logit, four external-aperture, `central_mix_aperture_fraction`, and four loss fields. Exact keysets, order, finite values, bounds, and derived-logit tolerance are enforced.
- NEAR accepts the corresponding 20 ordered rows and exact IDs, replacing central mix with the frozen `shared_coupling_alpha` schedule `0.03 + (i-1)*0.04/19`.
- RANDOM binds the family specification and 20-value seed split as two distinct path/hash/JSON-pointer authorities before either file is read. Each of the 13 coordinates is addressed independently with SplitMix64. The same open-interval uniform is used for the 50-percent zero atom and positive inverse-CDF branch. The fourth volume logit is derived rather than drawn.
- PHYSICS binds the frozen master seed, ordered 15 bounds pairs, parameter order, and parameter-specific Fisher–Yates midpoint-LHS algorithm. The exact SplitMix64 address and binary64 operation order are independently regenerated for all 20 rows.
- CAD-0 is a sixth binding. The exact HAND, NEAR, RANDOM specification, RANDOM seed split, PHYSICS specification, and CAD-0 mapping triples must all match the RELEASE and one-way attestation before formal authority content reads become reachable.

There is no `base_parameters` fallback and no formal-path substitution by synthetic field names. Formal schema objects are direct objects without a technical wrapper. Technical substitutes remain non-formal.

## Independent CAD-0 reconstruction

The independent verifier does not import the driver, generator, orchestrator, or a CAD mapper. It reconstructs and checks:

- the four exact-volume root solves and residuals;
- frozen cell ownership and slot placement;
- all 20 fixed U4 exception witnesses;
- family-dependent reduced graphs and the actual positive-area fluid graph;
- component counts, weighted degrees, and algebraic-connectivity evidence;
- measured feature candidates from cover/spine thickness, steps, cavity height, root lengths, and active slot widths;
- measured eligible solid-load candidates from top/bottom general covers and slot/collector gaps;
- explicit exclusion of the intentional 1.5 mm U4 collar-rim exception;
- separate comparisons with the 2.0 mm minimum-feature and 1.6 mm minimum-load thresholds.

Threshold constants are not substituted for measurements. The final dual-implementation check agreed on all 80 parameter records, all 80 CAD audit objects, and all 80 eligibility statuses.

## Verification, reseal, and publication boundary

Generation writes only a run-specific staging tree and a non-success generation record. It cannot write `VERIFIED_SUCCESS`.

The independent verifier requires exactly 92 staged paths from the S1 allowlist and validates all 80 non-null member self-hashes, four family manifests, the identity index, scientific manifest, inventory, six result artifacts, SHA256SUMS, and the exact progress path. After successful independent recomputation it atomically replaces:

- allowlist index 88: final independent-verification report;
- index 89: verifier-authored successful execution record;
- index 91: progress record;
- index 90: complete SHA256SUMS.

It then revalidates the complete dependency chain and emits a schema-valid `VERIFIED_STAGING` attestation. The attestation binds the RELEASE full SHA, task, dispatch, bare 64-hex run ID, actual staging root, generation-terminal hash, final report hash, final scientific-manifest hash, counts, and the ordered 92-entry staging aggregate. It does not write a publication success marker.

The publication command accepts that exact terminal schema, independently recomputes the ordered 92-entry aggregate and final hashes, and invokes the exact-path transaction. Only a committed 92-path publication can write the single `PUBLISHED_SUCCESS`/`VERIFIED_SUCCESS.json` package terminal.

## Release, attestation, run identity, and DRAFT

The formal gates dynamically bind an eventual CORR03 guardian approval path and actual file SHA-256. CORR01 and the rejecting CORR02 review are not hard-coded as future approval. A future RELEASE must be a new canonical record with a new dispatch ID. Its one-way attestation binds the already immutable full RELEASE bytes; a DRAFT cannot be flipped or promoted.

The RELEASE carries `run_id=null` and base terminal roots. The run ID is the bare lowercase SHA-256 of the frozen domain-separated, `0x0A`-separated preimage containing the full RELEASE SHA, task ID, and source/schema/fixture/authority/allowlist hashes in exact order. It has no final newline, and the two-byte literal `5c6e` is not a separator. The later canonical attestation contains the derived run ID and expanded staging/success/failure/temp/journal roots.

The expired DRAFT remains attempt 0, non-authoritative, non-reusable, non-promotable, and non-executable, with every execution permission false and all release/authority bindings null. Formal gates reject DRAFT before authority content reads.

## Publication recovery and failure containment

Publication uses a canonical run-specific journal and transaction-owned, same-directory temporary files for Windows same-volume replacement. Startup recovery accepts only `PREPARED` or `PUBLISHING` work that matches the task, immutable RELEASE SHA, run ID, exact allowlist hash, repository containment, declared run-specific journal root, published targets, and the owned temporary suffix. A journal pathname alone is not deletion authority.

Fault tests cover copy, fsync, replace, journal-write, and cross-root progress failures. Rollback leaves zero published targets, deletes only transaction-owned temporary files, preserves unrelated files, and records a rolled-back journal. Stale attempts, cross-attempt roots, mismatched retry pairs, non-allowlist deletion targets, and unauthenticated recovery are rejected.

## Immutable BF ledger

The CORR03 ledger preserves every original ID and finding hash. Guardian status is not rewritten by implementation evidence and can change only through a later guardian review.

| ID | Guardian status retained | CORR03 technical status | Finding SHA-256 |
| --- | --- | --- | --- |
| S2-BF-01 | OPEN | IMPLEMENTED_UNREVIEWED | `f927e2e1852ce39d735946b259822ef66c328847ccd48fc6ecaba1ed421bf921` |
| S2-BF-02 | PARTIAL_NOT_CLOSED | IMPLEMENTED_UNREVIEWED | `3fd1d2362213894e6864a5404ac091c222772d0a3d0fa5d7a7d9c2a7b4843f2e` |
| S2-BF-03 | OPEN | IMPLEMENTED_UNREVIEWED | `8853bfcae39d73060d58f2a624e2f4ab8cd3ed6a6c6e86379ec303e27c651bd5` |
| S2-BF-04 | OPEN | PARTIAL_UNREVIEWED | `17a8280b717f618465e5eae71d7900266768a4c09482f3828e0f2e388e0fac86` |
| S2-BF-05 | PARTIAL_NOT_CLOSED | IMPLEMENTED_UNREVIEWED | `d505b09faae1907078feccc77ce4284bb75138de78702b9b0422137e1e06e440` |
| S2-BF-06 | OPEN | IMPLEMENTED_UNREVIEWED | `a6c8d7baec0ba6ae6c8ddf175e8e224318cda25d2730544e5fc31c0c41591228` |
| S2-BF-07 | OPEN | IMPLEMENTED_UNREVIEWED | `5a3722a67eb474610eb20133429977ab8a97806f7ec40bd40fd61a933084f752` |
| S2-BF-08 | OPEN | IMPLEMENTED_UNREVIEWED | `8135b83a835e6cbcc017d97af19ebe4bb34be968e66f666d9ddd0e4d1e6a9159` |
| S2-BF-09 | CLOSED | UNCHANGED_CLOSED | `a79d1288576bef7a54743be3f7056b54139da5a0931a3ec11f4fab50a98f357f` |
| S2-BF-10 | OPEN_CRITICAL_TECHNICAL_SAFETY | IMPLEMENTED_UNREVIEWED | `74c1f4ce6bcdfa8573a3cd5ac6bc440bd2547b197e0b9d72c55e6ff5246a1675` |
| S2-BF-11 | PARTIAL_NOT_CLOSED | IMPLEMENTED_UNREVIEWED | `96fb3ddae2c9332107ac2e2cdf230a9ed05a7953c30120c8816468a40c06d2f2` |

The guardian-closed count therefore remains exactly `1/11`. CORR03 does not claim `11/11` closure. BF-04 remains explicitly `PARTIAL_UNREVIEWED` pending guardian assessment of the independent CAD evidence.

## Validation and retained iterations

The final ordinary suite result is `35 passed, 0 failed, 0 errors`.

The preserved progression is:

- schema-agent run05: 18 passed and one CAD mismatch from staging generated by an earlier driver revision;
- verifier-agent run06: 18 passed and one verifier-terminal staging-root schema mismatch;
- run07: 19 passed;
- run08: 19 passed and one positive publication test failure caused by obsolete publisher terminal field names;
- run09: 34 passed and one intentional cross-root journal rejection exposed by an incorrectly located positive-test journal;
- run10: 35 passed.

Additional direct checks passed: Python compilation, JSON-schema meta-validation, forbidden-import AST inspection, sealed-algorithm equivalence for RANDOM 20×13 and PHYSICS 20×15, DRAFT rejection before authority reads, and 80/80/80 dual-implementation parameter/CAD/status agreement.

No test iteration or task-owned temporary root was removed. Retained verifier iterations include `.tmp/gen_enc_2c_s2_corr03_verifier_agent_run06` through `run10`, the previously disclosed schema-agent roots including run05, and Python bytecode caches.

## Formal zero state and terminal interpretation

- current attempt: `0`
- current run ID: `null`
- formal RELEASE/attestation: absent
- formal HAND/NEAR rows read: `0`
- formal RANDOM/PHYSICS values read: `0`
- formal identities: `0`
- static eligibility runs: `0`
- formal target writes: `0`
- existing formal 92-path targets: `0`
- formal member/family/index hashes: `null`
- timing/response/simulation/data/final-test work: `0`
- `final_test_read`: `false`
- science: `NOT_TESTED`

The technical candidate state is `READY_FOR_INTERMEDIATE_ACCEPTANCE_AND_GUARDIAN_S2_CORR03_PREEXECUTION_REVIEW_FORMAL_EXECUTION_BLOCKED`. This is a request for a new guardian preexecution review, not approval. Formal execution remains fail-closed until an eventual guardian approval, a new canonical RELEASE, and its one-way attestation exist and validate.
