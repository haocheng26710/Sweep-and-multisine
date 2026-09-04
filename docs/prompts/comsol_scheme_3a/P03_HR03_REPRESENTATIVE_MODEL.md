# Copy-paste prompt — P03 HR03 representative model and loss-model check

Execute only P03 after the user accepts P02.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely, then read the accepted P01 contract and P02 report and inspect the accepted P02 `.mph` and named selections. Read the V2.5 parameter JSON/generator sections defining HR03. Inspect git status and preserve unrelated work.

## Exact task

Use the accepted P02 baseline geometry and replace only the P05 module air passage with the HR03 fluid geometry. HR03 is the representative module because its single-campaign signature is stable and its measured centre is `1848.6 Hz`.

1. Reconstruct HR03 parametrically from the authoritative source values, including both necks and the cavity. Verify the local-to-global transform and inward/outward orientation.
2. Re-run all P02 connectivity, cross-section, volume, interface and named-selection checks.
3. Build a bulk Pressure Acoustics, Frequency Domain model with an effective narrow-channel loss treatment justified by official COMSOL documentation and the local geometry.
4. Build a bounded local reference model using Thermoviscous Acoustics or another documented higher-fidelity boundary-layer treatment. Keep this reference small enough to solve reliably; do not apply full thermoviscous physics to the complete head.
5. Compare the reduced and reference loss treatments at prospectively specified frequencies around the HR03 resonance. Record pressure transfer, phase, peak centre and width/Q where identifiable.
6. Run at least two accepted mesh levels. Explicitly check resolution of any thermoviscous boundary layers in the reference model.
7. Do not tune separate HR03-only parameters to force the result to 1848.6 Hz. This phase evaluates the as-designed geometry and modelling hierarchy.

If the COMSOL license or MCP lacks a required thermoviscous/narrow-region feature, retrieve the exact available physics/interfaces and stop with a bounded alternative proposal. Do not silently replace the reference with an unvalidated damping constant.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P03_HR03/`

Create:

- bulk/effective-loss `.mph`;
- bounded reference `.mph`;
- geometry and mesh checks;
- reduced-vs-reference transfer/phase CSV;
- peak/Q comparison CSV or JSON;
- pressure-field and comparison PNG/SVG;
- solver/license log and SHA-256 manifest;
- `docs/progress/COMSOL_3A_P03_HR03_LOSS_MODEL.md`.

## Execution acceptance gate

- HR03 fluid volume and neck dimensions agree with the source within 1%.
- Connected-domain and named-selection checks pass.
- Both accepted models solve, or an exact licensed-feature blocker is documented.
- Accepted mesh changes the main resonance centre by less than 1%.
- Reduced-vs-reference peak-centre difference is less than 1%; amplitude and phase differences are quantified rather than hidden.
- The report distinguishes numerical validity from experiment agreement.

## Scientific outcome classification

Classify, without changing the gate:

- `as_designed_close`: uncalibrated centre within 5% of 1848.6 Hz;
- `systematic_offset`: valid model, larger centre offset that may justify a global nuisance parameter in P04A;
- `model_inadequate`: loss or geometry hierarchy cannot reproduce a physically interpretable HR03 mode;
- `blocked`: software/license/geometry fact prevents a valid comparison.

## Prohibited actions

- No module-specific fitted correction.
- No HR01/02/04/05/06/07/08 model.
- No U4 model, external field, classifier, final-test, print or acquisition.
- No push/tag/release or automatic commit.
- Do not begin P04A.

## Final response format

Lead with P03 execution status and scientific outcome classification. Report geometry checks, physics hierarchy, resonance/mesh/loss comparison, exact artifacts and hashes, and confirm P04A was not started. Stop for user acceptance.
