# GEN-ENC FAST B1 R11 minimal shape freeze

This additive sidecar implements the science-first minimum gate accepted on 2026-08-29. It preserves the earlier R11 and CORR01 packages as immutable history and does not claim that their adversarial governance blockers were closed.

The inspector reads exactly 13 manifest-listed JSON objects once, checks the SHA-256 of the original bytes, requires canonical JSON and basic schema conformance, and emits structural paths, node types, object/array shape, selector status, and source provenance. It emits no scalar values or hashes of scalar values. `OWNERSHIP_CELLS` and `OWNERSHIP_RULE` are classified as future derived outputs, not authority selectors.

The verifier is a separate implementation which reopens the same 13 objects once and independently recomputes the mapping. Runs are sequential and use a new versioned result directory. Successful directories contain only the driver mapping, provenance, and independent report; failures retain `FAILURE.json`.

The freeze is implementation-only. Formal authority reads, formal shape runs, controls, identity/static work, publication, Phase B, and final-test reads are all zero. A real shape inspection requires a later controller dispatch.
