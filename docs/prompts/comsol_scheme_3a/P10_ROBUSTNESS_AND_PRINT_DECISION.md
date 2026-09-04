# Copy-paste prompt — P10 robustness confirmation and print/no-print decision

Execute only P10 after the user has accepted the intervention-screening results and explicitly identified which candidates, if any, may advance.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely, then read the P01 contract and every accepted baseline/external/mechanism/intervention report. Verify all frozen hashes. Inspect git status and preserve unrelated work.

## Exact task

Use the pre-frozen multi-objective criteria to select at most one intervention candidate. If none meets the gate, retain `no candidate`; do not choose the least bad design and call it successful.

For the original U4HR baseline and at most one candidate:

1. Run the accepted fine-mesh convergence check.
2. Run only the P01-frozen tolerance/sensitivity cases, including documented dimensional perturbations such as ±0.2 mm and the frozen seal-gap/material/air-property cases.
3. Confirm the full four-direction external response using the accepted P07 formulation.
4. Recompute all fixed metrics:
   - top-1/top-2 mapping;
   - diagonal advantage;
   - normalized off-diagonal energy;
   - resonance drift;
   - insertion loss;
   - direction-pattern correspondence;
   - chamber/module energy participation.
5. Compare baseline and candidate using identical grids, meshes and normalization.
6. Decide one outcome:
   - `NO_PRINT_no_stable_improvement`;
   - `PRINT_ONE_REMOVABLE_INSERT_for_minimal_validation`;
   - `SCHEME_3A_INSUFFICIENT_consider_3B`;
   - `MECHANISM_RESULT_SUFFICIENT_physical_validation_future_work`.
7. If printing is recommended, produce a dimensional design requirement and minimal validation rationale only. Do not generate production STL, send a print job or schedule measurements without a new user request.
8. Write a thesis-facing synthesis that distinguishes:
   - existing real experimental evidence;
   - calibrated simulation evidence;
   - virtual design prediction;
   - remaining unvalidated claims.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P10_ROBUSTNESS_DECISION/`

Create:

- final baseline/candidate models;
- mesh/tolerance/external-direction comparison tables;
- final metric dashboard CSV/JSON;
- figures suitable for later thesis review;
- candidate dimensional requirements if applicable;
- complete SHA-256 manifest;
- `docs/progress/COMSOL_3A_P10_ROBUSTNESS_AND_PRINT_DECISION.md`;
- `docs/progress/COMSOL_3A_FINAL_SYNTHESIS.md`.

## Acceptance gate

- At most one candidate advances.
- The candidate is selected only by P01-frozen criteria.
- Mesh changes key centres by less than 1% and key contrast by less than 0.5 dB, or the candidate fails.
- Robust code-preservation targets are evaluated without relaxation: expected top-1 4/4, diagonal advantage at least 3 dB, drift less than 1/12 octave, normalized off-diagonal energy no more than 0.5, plus frozen tolerance requirements.
- External four-direction confirmation uses the accepted P07 formulation without retuning.
- A no-candidate result remains an allowed final result.
- No causal module-percentage, reliable localization or H1-confirmed claim is made.

## Prohibited actions

- No new optimization grid, classifier, room fit, final-test, production STL, print, acquisition, push, tag or release.
- Do not change legacy experimental conclusions or metadata.
- Do not start a physical-validation phase.

## Final response format

Lead with the exact decision label. Then provide baseline-vs-candidate metrics, robustness findings, publication-safe mechanism conclusion, remaining limits, exact report/model/table/figure paths and hashes, and confirmation that no printing or new acquisition was started. Stop for user decision.
