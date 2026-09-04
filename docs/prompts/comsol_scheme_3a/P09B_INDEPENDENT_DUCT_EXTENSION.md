# Copy-paste prompt — P09B virtual intervention: independent short duct extensions

Execute P09B only after explicit user acceptance of P09A and authorization to continue.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely and read the accepted baseline/P08/P09A reports. Use the original P06 U4HR model as the comparison baseline unless the user explicitly authorizes a stacked design. Inspect git status and preserve unrelated work.

## Exact task

Test only one design-variable family: four independent short passages extending each HR outlet closer to the microphone before mixing.

1. Before solving, define one mechanically interpretable extension parameter with exactly:
   - 0 mm baseline;
   - 5 mm;
   - 10 mm.
2. Keep passage cross-section, HR geometry, microphone nominal position, outer ports, global losses, targets and metrics fixed unless the physical geometry makes this impossible. Record unavoidable changes rather than compensating with hidden parameters.
3. Verify that each extension remains independent up to its documented mixing plane.
4. Run the frozen internal screening excitations/grid.
5. Compute the same code, crosstalk, drift, insertion-loss and energy metrics as P09A.
6. Compare each level directly with the original P06 baseline.
7. Do not run full external four-direction validation.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P09B_DUCT_EXTENSION/`

Create the parametric model, geometry table, frozen metric table, figures, solver/convergence log, SHA-256 manifest and:

`docs/progress/COMSOL_3A_P09B_INDEPENDENT_DUCT_EXTENSION.md`

## Acceptance gate

- Only 0/5/10 mm levels are tested.
- All four ducts are geometrically equivalent except for their attached HR modules.
- Named selections and fluid connectivity are correct.
- No module-specific tuning occurs.
- Frozen numerical and scientific metrics are complete.

Classify: `candidate_meets_gate`, `promising_but_below_gate`, `no_useful_improvement`, or `invalid_geometry/model`.

## Prohibited actions

- No chamber-volume stacking from P09A unless explicitly authorized.
- No star manifold, damping or module retuning.
- No external four-direction solve, classifier, final-test, print or acquisition.
- No push/tag/release or automatic commit.
- Do not begin P09C.

## Final response format

Lead with the classification, then give frozen metrics/tradeoffs, artifacts/hashes and confirmation that P09C was not started. Stop for user decision.
