# GEN-ENC-CAD-0 Phase A contract proposal

Date: 2026-08-28

Terminal state: `READY_FOR_GUARDIAN_AND_USER_REVIEW`

This strictly incremental phase produced an `E0_CAD_MAPPING_CONTRACT_PROPOSAL` only. It did not freeze final geometry, execute a formal seed, generate an identity, emit static eligibility, run CAD/solver/COMSOL/full-wave work, inspect responses/timing/endpoints, or read development/validation/final-test data.

The recommended finite profile is `D1-T1 / D2-A / D3-A / D4-A`: an exact-volume square central plenum and fixed cardinal sectors; separate reduced RANDOM graph from actual shared-plenum fluid connectivity; equal disclosed connector-slot capacity; and fail-closed member retention as `COST_INELIGIBLE` when geometry and volume conflict.

Static algebra recorded without geometry execution:

- central volume is exactly `0.40V*` by `A=sqrt(0.40V*/(4H))`;
- local softmax shares sum to `0.60V*` by construction;
- proposed fixed per-sector passage volume is `2.4656e-6 m3`;
- proposed root span is `0.0598973350360816 m` and cavity area is `1.088e-4 m2`;
- the root function is strictly increasing whenever `A_cav>(A_in+A_out)/2`, otherwise it fails closed;
- a conservative sealed-bound algebra check gives derivative lower bound `9.88e-5 m2`, maximum lower-end volume `3.35817335036082e-6 m3` including the maximum proposed extra-window bound, and minimum upper-end volume `5.42998934014433e-6 m3`, versus the sealed-q local-target range `[3.7578617934992004e-6,5.383935836344015e-6] m3`; hence T1 brackets the full parameter-bound box algebraically, with no formal identity execution;
- derived candidate envelope is `0.210/0.210/0.0092 m`, compared only after derivation with sealed caps;
- exact union accounting uses ownership clipping plus coordinate-compressed elementary cells, so every positive-volume overlap is deducted once.

Four user decisions remain explicit in `user_decision_matrix.json`. No existing file was modified. All authorization fields are false, all execution/generation/read counts are zero, all identity hashes are null, no RQ is closed, and final-test remains sealed/read false.

Authoritative proposal package: `outputs/gen_enc/GEN_ENC_CAD_0_FIXED_SECTOR_MAPPING_CONTRACT/phase_a/`.
