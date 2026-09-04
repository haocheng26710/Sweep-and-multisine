# Copy-paste prompt — P09C virtual intervention: removable star manifold

Execute P09C only after explicit user authorization following P09B or a documented decision to skip P09B.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely and read all accepted baseline/P08/P09 intervention reports. Use the original P06 U4HR model as the default baseline; do not silently stack prior modifications. Inspect git status and preserve unrelated work.

## Exact task

Test a removable central star-manifold/partial-isolation insert that keeps the existing P01 head, HR modules and microphone position.

1. Before solving, define one physical isolation parameter, preferably radial divider extension or equivalent, with exactly three predeclared states:
   - no divider/original chamber;
   - partial isolation;
   - high isolation short of completely sealing the microphone from any channel.
2. Document exact dimensions, remaining mixing volume, minimum clearances and printability assumptions. Do not use a vague percentage without a physical dimension.
3. Keep HR geometry, outer ports, global loss parameters, target windows and metrics frozen.
4. Verify that all four channels still couple to the microphone and that no divider creates an unintended sealed cavity.
5. Run the frozen internal screening excitations/grid.
6. Compute code preservation, diagonal advantage, normalized off-diagonal energy, resonance drift, insertion loss and energy participation.
7. Compare each state with the original P06 baseline and with P09A/P09B only in the final table, not by stacking geometries.
8. Do not generate STL or authorize printing in this phase.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P09C_STAR_MANIFOLD/`

Create:

- parametric star-manifold model;
- exact geometry/clearance table;
- frozen metric comparison CSV;
- field/energy figures;
- solver/convergence log;
- SHA-256 manifest;
- `docs/progress/COMSOL_3A_P09C_STAR_MANIFOLD.md`.

## Acceptance gate

- Three physically defined states only.
- Watertight valid fluid domains with four channels still coupled to the microphone.
- Frozen numerical and scientific metrics complete.
- Printability is discussed but not claimed validated.
- No parameter grid is expanded after viewing results.

Classify: `candidate_meets_gate`, `promising_but_below_gate`, `no_useful_improvement`, or `invalid_geometry/model`.

## Prohibited actions

- No hidden combination with P09A/P09B.
- No new HR tuning, external four-direction solve, classifier, final-test, STL generation, print or acquisition.
- No push/tag/release or automatic commit.
- Do not begin P10.

## Final response format

Lead with the classification. Report dimensions, frozen metrics/tradeoffs, artifacts/hashes and confirmation that P10 was not started. Stop for user acceptance.
