# GEN-ENC-2 E2 PREEXECUTION CONTRACT FREEZE-02

## Additive scope

This is the single bounded RC completion requested after Guardian review SHA-256 `c69015d6bbe9fba1c70146365963eb2adcb36c1f0855f28a6a94fa31c78a4f49`. It is additive to the immutable Freeze-01, authority addendum 01, and Freeze-01 CORR01 packages. It closes only RC01–RC04. Accepted scientific authority GAP01–GAP05, exact80 identities and order, full workload, metrics, thresholds, family rules, and evidence ceiling are unchanged.

No formal development or validation unit ran. No response root was read or written, no execution control or formal run ID was created, and `final_test_read=false`.

## RC closure

RC01 is closed by `scripts/gen_enc_2_e2_formal_driver_freeze02.py` and the exact argv arrays in the Freeze02 command manifest. The development and single-use-validation modes have separate exact roots. The first formal operation reads only the externally supplied authorization record and fails closed before any scientific input or output-root access when authorization is absent, invalid, consumed, final-test-enabled, hash-mismatched, or root-mismatched. This package creates no authorization record.

RC02 is closed by `scripts/gen_enc_2_e2_independent_verifier_freeze02.py`. The verifier accepts frozen identity, nuisance, seed, partition, angle, frequency and shared-core inputs and independently recomputes the chunk. It does not import the formal driver and does not accept a caller-produced second array as verifier evidence. Its synthetic fixture recomputes a one-cell chunk from frozen inputs and detects an injected driver-value perturbation.

RC03 is closed by fully constrained Draft 2020-12 schemas for receipts, compact-stat manifests, checkpoints, audit manifests, quarantine records and partition terminals. Formal arrays use NPY 1.0 with frozen dtype, shape, order and SHA-256 receipts; no per-complex JSON representation is allowed. The exact merge key is partition, stage, family ordinal, member ordinal, chunk index and array role. Common-W accumulators use sequential binary64 addition. Finest member/cell/repeat/angle/frequency-derived payloads preserve reconstruction of common W, shared/differential quantities, `E_primary`, `r_stable`, matched-cost status, 256-frequency throughput, bridge and held-out results, candidate/family/global terminals, bootstrap, permutation and uncertainty.

The conservative retained-storage ledger totals 44,213,173,248 bytes (about 41.176 GiB), including 320 audit chunks, receipts, stats, checkpoint, one largest validation failure chunk, inventory and 4 GiB filesystem safety overhead. It is below the 48 GiB managed cap. Startup free space remains at least 80 GiB and the reserve floor remains at least 32 GiB. The 20 core-hour, 10 wall-hour and 8 GiB aggregate-peak limits include driver, verifier, I/O, hashing, merging, checkpointing and deletion.

RC04 is closed in formal bytes as: driver raw temporary write; independent input recomputation; tolerance comparison; durable PASS receipt and compact statistics; checkpoint plus resource/storage check; then audit retention or non-audit raw deletion. Verification failure quarantines the unique chunk, stops the partition, forbids later merge and same-run retry, and does not delete the failed raw chunk. Development must complete 80/80, pass independent verification, seal W and all development decisions before validation can open once; validation cannot feed back into development.

## Evidence level and unchanged conclusions

This remains a preexecution E0 contract/implementation freeze with synthetic technical fixtures only. It does not establish reduced-model response findings, COMSOL/full-wave facts, physical facts, or scientific improvement. It does not authorize E2, E3, E4, inverse design, printing, external services, parameter search, additional members/families, or final-test access. Older reports, failures and terminal conclusions are not overwritten.

