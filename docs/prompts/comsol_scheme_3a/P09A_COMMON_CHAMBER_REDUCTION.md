# Copy-paste prompt — P09A virtual intervention: reduced effective common chamber

Execute only P09A after the user accepts P08 and agrees that Scheme 3A intervention remains justified.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely and read the accepted P01/P06/P08 artifacts. Verify baseline model/config hashes. Inspect git status and preserve unrelated work.

## Exact task

Test only one design-variable family: reducing the effective shared central-chamber air volume with a geometrically plausible removable insert while preserving the head, HR modules, microphone nominal position and exterior ports.

1. Before solving, define a deterministic parameterization that produces approximately:
   - 100% baseline chamber volume;
   - 75% chamber volume;
   - 50% chamber volume.
2. Record the exact achieved volumes and any unavoidable secondary geometric effects.
3. Do not change module cavities/necks, global loss parameters, source normalization, target windows or success metrics.
4. Run the frozen internal U4HR excitations on the predeclared screening grid.
5. Compute code preservation, diagonal advantage, normalized off-diagonal energy, resonance drift, insertion loss and chamber/module energy participation.
6. Compare every variant directly with the original P06 baseline, not with a stacked P09B/P09C design.
7. Do not run full four-direction external validation in this screening phase.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P09A_CHAMBER_REDUCTION/`

Create:

- parametric intervention model;
- achieved geometry/volume table;
- fixed metric comparison CSV;
- field/energy comparison figures;
- convergence and solver log;
- SHA-256 manifest;
- `docs/progress/COMSOL_3A_P09A_CHAMBER_REDUCTION.md`.

## Acceptance gate

- Exactly the frozen three volume levels are evaluated.
- Geometry remains watertight and microphone/module identities unchanged.
- All metrics use P01 definitions.
- Numerical convergence passes at the screening level.
- Scientific success/failure is reported without adding intermediate volume levels after seeing results.

Classify: `candidate_meets_gate`, `promising_but_below_gate`, `no_useful_improvement`, or `invalid_geometry/model`.

## Prohibited actions

- No duct extension, star manifold, damping, module retuning or external four-direction solve.
- No adaptive parameter levels, classifier, final-test, print or acquisition.
- No push/tag/release or automatic commit.
- Do not begin P09B.

## Final response format

Lead with the P09A classification. Report exact geometry levels, frozen metrics, tradeoffs, artifacts/hashes and confirmation that P09B was not started. Stop for user decision; P09B is not automatic if P09A already meets the gate.
