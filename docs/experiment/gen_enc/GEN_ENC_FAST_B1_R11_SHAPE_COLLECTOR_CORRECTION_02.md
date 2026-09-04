# GEN-ENC FAST B1 R11 shape collector correction 02

This is the final science-first bounded shape repair. It preserves both earlier failed runs and changes no CAD semantics.

The collector and independent verifier each read the exact 13 historical authority files once. Each file's untouched raw bytes must match its frozen SHA-256 and parse as standard JSON. The output inventories every JSON pointer and node type, object key names and child counts, and array lengths and element types. It never writes scalar values or scalar-value hashes.

All 31 selectors receive a diagnostic status. Required selectors are `PRESENT_MATCH`, `PRESENT_TYPE_MISMATCH`, or `MISSING`; the two future-output selectors are `FUTURE_OUTPUT_PRESENT` or `FUTURE_OUTPUT_ABSENT`. Missing and type mismatch do not stop structural collection. Raw hash and JSON parse failures remain fail-closed.

All derived files are canonical JSON. A successful versioned directory contains only `shape_mapping.json`, `provenance.json`, and `independent_verification.json`; a failed directory contains `FAILURE.json`.

The freeze used synthetic fixtures only. Formal authority reads and formal runs are zero; `final_test_read=false`.
