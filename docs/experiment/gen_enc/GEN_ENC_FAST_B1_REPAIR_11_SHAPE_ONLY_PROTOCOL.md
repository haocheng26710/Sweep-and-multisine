# GEN-ENC FAST B1 Repair-11 authority-shape-only protocol

Repair-11 is an additive, non-scientific conformance lane bound to task `01a049a7-15ca-79e1-92a2-d3822ba8609d`. It does not modify Repair-10, reinterpret CAD, change an authority pointer, generate a member, assess static eligibility, publish an artifact, access the final test, or authorize Phase B.

The only future command sequence is:

1. `shape-preflight`
2. `extract-shape`
3. `verify-shape`
4. `package-shape`

Fresh task/run-bound one-use release, one-way guardian attestation, and dispatch bytes are required before that sequence may run. The implementation freeze creates none of those bytes and does not execute the sequence against formal authority.

The driver and independent verifier each open the exact 13 allowlisted CAD semantic objects once, in separate processes without a shared parsed object or cache. Each open is durably receipted. A completed shape run therefore has exactly 13 driver reads, 13 verifier reads, and 26 cumulative receipts.

Persisted structural evidence is limited to source path/hash/pointer bindings, canonical JSON pointer sets, node JSON types, array arity and element-type sets, object child counts and key-name sets, selector classifications, and value-independent structural digests. Scalar values, scalar hashes, scalar lengths, members, static evidence, scientific artifacts, performance claims, and publication are forbidden.

`OWNERSHIP_CELLS` and `OWNERSHIP_RULE` are frozen as `FIXTURE_ONLY_FUTURE_OUTPUT`. Their absence is classified as `ABSENT_FIXTURE_ONLY_OR_FUTURE_OUTPUT`; their presence in a technical mirror is rejected. Every other Repair-10 selector retains its exact purpose, pointer, and expected JSON type. Missing or mismatched selectors fail closed without substitution.

Exactly one run terminal is allowed. A successful package contains only the driver snapshot, independent report, and verifier terminal bindings and stops at `SUCCESS_SHAPE_ONLY_AWAITING_GUARDIAN_RESULT_SEAL`.

