# Copy-paste prompt — P04A bounded global calibration

Execute only P04A after the user accepts P03.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read completely:

- `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md`;
- accepted P01–P03 reports and contracts;
- P05 baseline and HR03 accepted COMSOL models;
- S1 inventory, repeat selection and HR03/P05 preprocessed outputs used by the accepted experimental analysis.

Inspect current git status. Raw TXT/MDAT and frozen analysis outputs are read-only.

## Exact task

Calibrate at most 2–3 global nuisance parameters using only the P05 baseline and HR03 single-entry comparison. The purpose is to account for bounded common modelling uncertainty, not to make every curve look perfect.

1. Use the exact metric, parameter bounds, objective and frequency ranges frozen in P01.
2. Candidate global parameters may include only contract-approved quantities such as one common effective end correction, one common wall/seal loss parameter, and one microphone-coupling volume/impedance parameter.
3. Do not change CAD cavity volumes, HR-specific neck widths/lengths or target frequencies.
4. Fit the demeaned HR03-minus-P05 response or other P01-frozen relative quantity so that unknown source amplitude and broadband room gain are not treated as module physics.
5. Respect repeat structure: obtain uncertainty from measurement repeats and/or bounded parameter bootstrap; do not treat frequency bins as independent observations.
6. Compare selected 5-of-6 representative results with all-six sensitivity results.
7. Record identifiability: parameter correlations, flat objective directions and boundary-hitting estimates.
8. Freeze one calibrated parameter set before inspecting the other HR-module agreement in P04B.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P04A_GLOBAL_CALIBRATION/`

Create:

- frozen parameter JSON with units, bounds and provenance;
- calibration search table CSV;
- measured-vs-simulated HR03-minus-P05 spectra and fixed-window effects;
- repeat-aware uncertainty table;
- identifiability/sensitivity plots;
- updated but non-overwriting calibrated `.mph` clone;
- SHA-256 manifest;
- `docs/progress/COMSOL_3A_P04A_GLOBAL_CALIBRATION.md`.

## Acceptance gate

- No more than three global nuisance parameters are fitted.
- No HR-specific geometry is altered.
- The same parameter values apply to P05 and HR03.
- The objective and bounds are exactly those frozen in P01.
- Selected-repeat and all-repeat conclusions are shown.
- The frozen parameter file is immutable input for P04B.
- A poor or non-identifiable calibration is reported as such and is not rescued by adding parameters.

## Prohibited actions

- Do not inspect P04B simulation predictions before freezing parameters.
- Do not retune windows or experimental preprocessing.
- No U4/external model, classifier, final-test, print or acquisition.
- No push/tag/release or automatic commit.
- Do not begin P04B.

## Final response format

Lead with `P04A CALIBRATION FROZEN`, `P04A INADEQUATE`, or `P04A BLOCKED`. List fitted parameters, bounds, identifiability, selected/all-repeat agreement, artifacts/hashes and confirmation that P04B was not started. Stop for acceptance.

