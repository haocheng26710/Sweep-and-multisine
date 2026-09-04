# Copy-paste prompt — P05 U4SYM internal numerical control

Execute only P05 after the user accepts P04B as credible for U4 modelling.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely, then read the simulation contract and all accepted P02–P04B reports/configs. Verify frozen parameter hashes. Read the P01/P05/P09 geometry sources and the S2 provenance addendum. Inspect git status and preserve unrelated changes.

## Exact task

Build the full internal U4SYM control:

- P05 straight modules open at 0°, 90°, 180°, 270°;
- P09 solid dummies at 45°, 135°, 225°, 315°;
- the complete connected fixed passages, central chamber and accepted microphone sampling region;
- no external air domain in this phase.

1. Reuse the accepted calibrated physics and global parameters without retuning.
2. Create stable named selections for all four active exterior ports, four dummy positions, fixed passages, central chamber and microphone region.
3. Excite one active port at a time using a documented port formulation.
4. Export:
   - four port-to-microphone transfers;
   - full 4×4 port scattering/coupling matrix if supported by the accepted formulation;
   - central-chamber and passage energy measures;
   - pressure fields at pre-frozen diagnostic frequencies.
5. Align rotationally equivalent responses by coordinate mapping and quantify numerical symmetry.
6. Run the frozen mesh-convergence check.

Do not try to reproduce the measured S2 four-direction differences in an internal symmetric-port model. This phase is a numerical symmetry/control test, not an external-direction simulation.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P05_U4SYM_CONTROL/`

Create:

- `COMSOL_3A_P05_U4SYM_INTERNAL.mph`;
- port-to-mic transfer CSV;
- 4×4 coupling/scattering CSV;
- symmetry and mesh-convergence CSV;
- field/mesh/selection figures;
- solver log and SHA-256 manifest;
- `docs/progress/COMSOL_3A_P05_U4SYM_NUMERICAL_CONTROL.md`.

## Acceptance gate

- Physical identity is exactly four open P05 modules plus four diagonal P09 dummies.
- No dummy port leaks into the acoustic domain.
- Four rotationally equivalent port responses agree within the P01-frozen numerical symmetry tolerance, approximately 0.2 dB after alignment.
- Key centres shift less than 1% and key contrasts less than 0.5 dB between accepted meshes.
- The transfer and coupling matrices are numerically retrievable and fully labelled.
- Any asymmetry is diagnosed before proceeding.

## Prohibited actions

- No HR modules.
- No external field or room.
- No comparison that rebrands internal port excitation as a measured direction.
- No classifier, final-test, print or acquisition.
- No push/tag/release or automatic commit.
- Do not begin P06.

## Final response format

Lead with `P05 CONTROL PASS`, `P05 CONTROL FAIL`, or `P05 BLOCKED`. Report physical identity, numerical symmetry, convergence, matrix outputs, artifacts/hashes and confirmation that P06 was not started. Stop for acceptance.
