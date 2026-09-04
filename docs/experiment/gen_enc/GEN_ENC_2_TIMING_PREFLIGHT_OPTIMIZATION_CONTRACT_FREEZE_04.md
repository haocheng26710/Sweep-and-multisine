# GEN-ENC-2 timing-preflight bounded optimization — CONTRACT-FREEZE-04

Status: `READY_FOR_ADVISOR_AND_GUARDIAN_OPTIMIZATION_FREEZE_REVIEW`.

This additive freeze binds the single bounded optimization pass allowed after the accepted Attempt02 `RESOURCE_BLOCKED` terminal. It neither modifies nor supersedes the Attempt02 result, checkpoint, controller provenance, or seal. It authorizes no fresh formal timing preflight and no GEN-ENC-2 E2 execution.

## Frozen scientific semantics

The model remains `PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1`: five nodes, four branches, the same family/CAD mappings, `C=V/(rho*c^2)`, `Z=R+jωM`, HAND_01 global-first representative, frequency grid, nuisance values, seeds, canonical order, numerical thresholds, workload, and checkpoint/resume semantics. The full future obligation remains four families x 20 members, 28 angles, 3,675 cells x two repeats, four states, four ports, and 256 frequencies. No response, pressure, matrix, endpoint, score, performance, or ranking artifact may be persisted.

## Only permitted implementation changes

The scalar frequency loop is replaced by chunked NumPy batched 5x5 complex solves. Member, nuisance-row, state, and frequency invariants are precomputed or reused, repeated nuisance parsing is removed, and deterministic SplitMix64 draws are vectorized without changing keys or ordering. No JIT, GPU, external service, new hardware, lower precision, skipped solve, approximation, formal-response cache, or workload reduction is permitted.

The frozen scalar implementation remains available only as a development equivalence reference. The optimized implementation is the production timing/E2 common core. The equivalence fixture compares all four family mappings in memory, requires identical finite/status outcomes, and applies `rtol=1e-12, atol=1e-12` to complex outputs. Formal responses are never written.

## Development benchmark and execution boundary

The development-only single-process fixture recorded CPU speedup 11.75x and wall speedup 12.593802107319604x, exceeding the frozen targets 2.73x and 5.54x. Dividing the accepted Attempt02 projections by those measured factors gives estimate-only projections of 4.639775413711583 core-hours and 4.398928774568679 serial wall-hours. These are not formal-preflight evidence and do not establish FEASIBLE.

No parallel worker was used. A future, separately guardian-authorized fresh preflight may consider at most eight local workers only if the single-process projected CPU remains at or below 20 core-hours; every worker must set `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, and `OPENBLAS_NUM_THREADS=1`, while preserving canonical key, seed, checkpoint, and reduction order. The frozen future command remains single-process unless a later additive authority explicitly freezes otherwise.

Hard stops remain 20 core-hours, 10 wall-hours, and 8 GiB aggregate peak memory. This freeze generated no formal run ID, executed zero formal units, read no final-test data, and did not start E2.
