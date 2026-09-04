# Copy-paste prompt — P04B cross-module blind validation

Execute only P04B after the user accepts P04A and its parameter file is frozen.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely and read the accepted P01–P04A reports. Verify the hash of the frozen P04A parameter JSON before solving. Read authoritative HR geometry values and the experimental S1 analysis outputs. Inspect git status and preserve unrelated work.

## Exact task

Without changing any P04A calibrated parameter, construct and predict HR01, HR02, HR04, HR05, HR06, HR07 and HR08 in the accepted single-entry geometry. Here “blind” means these modules were excluded from parameter calibration; it does not claim that the analyst had never seen their experimental data.

1. Parameterize module geometry directly from authoritative source values.
2. Apply the identical bulk physics, loss treatment, mesh rule, boundary conditions and microphone definition used for HR03.
3. Run the P01-frozen simulation grid and export experiment-compatible representative spectra.
4. Compare predictions with S1 using:
   - centre frequency and signed centre error;
   - peak/notch polarity;
   - fixed target-window effects;
   - bandwidth/Q where reliably identifiable;
   - Pearson, Spearman and cosine similarity of demeaned spectra;
   - centre ordering and adjacent separation;
   - selected-repeat and all-repeat sensitivity.
5. Respect repeats as uncertainty units. Do not obtain confidence intervals by resampling frequency bins.
6. Report HR01 and HR05 weakness honestly. Do not add per-module losses or end corrections.
7. Produce a clear decision: whether the frozen physical model is credible enough to predict the internal U4 control and HR array.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P04B_BLIND_MODULE_VALIDATION/`

Create:

- parameterized module models or a single auditable parametric model;
- per-module prediction/measurement CSV;
- centre/order/window/similarity summary CSV;
- selected/all-repeat uncertainty table;
- comparison figures;
- solver log and SHA-256 manifest;
- `docs/progress/COMSOL_3A_P04B_BLIND_MODULE_VALIDATION.md`.

## Acceptance gate

Execution passes when all seven modules use the frozen model and auditable geometry without retuning, solves converge, artifacts are complete and uncertainty is repeat-aware.

Classify scientific validity prospectively:

- centre ordering preserved or not;
- stable-module centre error for HR04/HR07 and any other stable module;
- fixed-window effect-direction agreement;
- whether mismatch is global, module-specific or concentrated in weak experimental signatures.

Do not invent a single pass percentage after seeing results. Apply only P01-frozen criteria. If the model is inadequate, stop Scheme 3A before P05 and explain exactly why.

## Prohibited actions

- No recalibration or module-specific fitting.
- No reselecting four modules to improve the current experimental claim.
- No U4 solve if the phase concludes the model is not credible.
- No classifier, final-test, print or acquisition.
- No push/tag/release or automatic commit.
- Do not begin P05.

## Final response format

Lead with `P04B MODEL CREDIBLE FOR U4`, `P04B MODEL NOT CREDIBLE FOR U4`, or `P04B BLOCKED`. Give per-module headline results, mismatch diagnosis, artifacts/hashes and confirmation that P05 was not started. Stop for user acceptance.
