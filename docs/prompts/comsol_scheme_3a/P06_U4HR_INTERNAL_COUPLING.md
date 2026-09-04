# Copy-paste prompt — P06 U4HR internal coupling baseline

Execute only P06 after the user accepts P05.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely and read the accepted P01–P05 reports/models/configs. Verify frozen parameter/model hashes. Read the physical mapping and V2.5 geometry source. Inspect git status and preserve unrelated work.

## Exact task

Clone the accepted U4SYM internal model and replace only the four active modules:

- 0° P05 → HR01;
- 90° P05 → HR03;
- 180° P05 → HR05;
- 270° P05 → HR07;
- retain P09 dummies at 45°, 135°, 225°, 315°.

Do not change common physics, losses, source normalization, microphone definition, mesh rule or global parameters.

1. Verify every HR module orientation, fluid volume, neck identity and interface.
2. Excite each active port separately.
3. Export four port-to-microphone transfers and the full labelled 4×4 port coupling/scattering matrix.
4. Compute P01-frozen quantities:
   - diagonal advantage;
   - normalized off-diagonal energy;
   - resonance centre drift relative to accepted single-entry centres;
   - target-window top-1 and top-2 correspondence;
   - module and central-chamber energy participation;
   - U4HR minus U4SYM internal transfer differences.
5. Evaluate both the designed centres and the fixed exploratory frequencies `1623.27`, `2198.33`, `3973.94`, `6493.09 Hz` without selecting new “best” bins.
6. Run the frozen mesh-convergence check.
7. State whether the internal model supports common-chamber code destruction, substantial code preservation, or an unresolved mixed case.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P06_U4HR_INTERNAL/`

Create:

- `COMSOL_3A_P06_U4HR_INTERNAL.mph`;
- port-to-microphone transfer table;
- 4×4 coupling/scattering table;
- code-preservation and resonance-drift table;
- module/chamber energy table;
- U4HR-vs-U4SYM internal comparison table;
- pressure/phase/energy figures;
- convergence log and SHA-256 manifest;
- `docs/progress/COMSOL_3A_P06_U4HR_INTERNAL_COUPLING.md`.

## Execution acceptance gate

- Geometry and mapping are exact and fully labelled.
- All four excitations solve under the frozen model.
- Convergence criteria pass or failures are quantified.
- Every code metric is computed from pre-frozen definitions.
- No threshold or frequency selection changes after seeing results.

## Scientific branch decision

Use only P01-frozen criteria:

- `internal_code_destroyed_or_mixed`: proceed toward P08/P09 Scheme 3A diagnosis, with P07 external comparison still useful;
- `internal_code_substantially_preserved`: P07 becomes decisive; do not presume an internal redesign and consider Scheme 3B if external angular gating is weak;
- `model_inconclusive`: stop and identify whether geometry, loss, convergence or source definition is responsible.

## Prohibited actions

- No geometry intervention yet.
- No external field, room, classifier, final-test, print or acquisition.
- No individual causal contribution percentages.
- No push/tag/release or automatic commit.
- Do not begin P07A or P08.

## Final response format

Lead with execution status and scientific branch decision. Report code-preservation metrics, coupling/energy findings, fixed-frequency observations, artifacts/hashes and confirmation that no later phase was started. Stop for user acceptance.
