# GEN-ENC FAST B1 R11 shape input-format correction 01

This additive science-first repair preserves the failed run `65e80d0b…c254` and all earlier packages. It changes only the treatment of historical authority JSON encoding.

For each of the exact 13 manifest entries, the driver and independent verifier first hash the untouched raw bytes and compare that SHA-256 with the frozen manifest. They then decode and parse standard JSON without requiring the historical bytes to equal a newly serialized canonical representation. Basic manifest schema and selector type checks remain mandatory. All newly written mapping, provenance, verification, and failure records remain canonical JSON.

No authority is rewritten. Scalar values and scalar-value hashes are excluded from mappings. `OWNERSHIP_CELLS` and `OWNERSHIP_RULE` remain future outputs rather than authority selectors. A future real inspection requires a new controller-supplied run ID and result directory.

This correction used only synthetic, non-formal fixtures. Formal authority reads and formal runs during the correction are zero; `final_test_read=false`.
