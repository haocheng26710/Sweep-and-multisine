# COMSOL Scheme 3A — P04B-N nominal cross-module validation

## Status

`P04B-N MODEL NOT CREDIBLE FOR U4`

All required nominal models executed successfully, but the frozen centre-level credibility gates failed. Scheme 3A P05/P06 and full U4 must not proceed.

This is not a blocked run and not a P04A calibration validation. No fitted P04A parameter or descriptive calibrated MPH was used. `final_test_read=false`.

## Protocol and authority

Before any new HR modeling, the non-overwriting protocol branch and nominal authority were written and hashed:

- `protocol_deviation_addendum.json`: `526332d7ba0968e86c8fba80f8f9db40f7dbee03c0f3c06094908d142d9da723`
- `nominal_parameter_authority.json`: `8ae7018acfe37d4a576633b093b5ca4557b3c098ebc94d768f3a1c029214667d`
- pre-solve hash record: `PRE_SOLVE_AUTHORITY_SHA256SUMS`

The frozen model uses `hr_neck_effective_length_delta_mm=0.0`, `effective_loss_scale=1.0`, P03/P04A nominal air (`c=343 m/s`, `rho=1.2041 kg/m³`, `mu=1.814e-5 Pa·s`, `k=0.0257 W/(m·K)`, `Cp=1005 J/(kg·K)`, `gamma=1.4`), and the P03-verified Pressure Acoustics plus Thermoviscous Boundary Layer Impedance formulation. The P04A descriptive candidate (`delta=+0.2 mm`, `loss_scale=2.0`) was prohibited and never loaded.

The V2.5 source generator shows that the cavity plan is a rounded rectangle with `r=min(1.2 mm, cavity_width/4)`. This source-defined rule was recorded and hashed in `geometry_implementation_clarification.json` before the rounded rebuild. It preserves the design-table centre, bounding dimensions, volume, height and neck interfaces; it is not experimental tuning. Superseded rectangular pre-gate attempts remain under `superseded_rectangular_attempts/` and are excluded from scientific summaries.

## Execution acceptance

Real COMSOL 6.4 ran headlessly with two cores and 27 licensed products visible. Eight production models and the HR04/HR07 verification meshes completed on the exact 256-bin grid. Every production model had:

- 56 domains in one connected active air component;
- non-empty source, microphone, inner-neck, cavity, outer-neck and whole-module selections;
- zero inner/outer interface gap;
- maximum recorded geometry error between 0.0014% and 0.0122%, below 1%;
- finite, non-zero complex microphone transfer and positive integrated energy;
- exact save/reload response stability.

Production meshes contained 45,728–48,814 elements. HR04 and HR07 second meshes contained 60,972 and 67,230 elements. All models used the same 25 kHz physics-controlled rule; production used automatic size 6 and verification used size 5. The actual mesh statistics are in `mesh_statistics.csv/json`.

## Primary result: internal module energy

The primary response is the module-region integral of

`|p|²/(4ρc²) + ρ(|ux|²+|uy|²+|uz|²)/4`.

Within each CAD target ±1/6 octave, an interior sampled maximum was refined by a quadratic in log frequency and log energy. Boundary maxima were rejected exactly as frozen.

| Module | Measured centre (Hz) | Simulated result (Hz) | Identifiable | Signed / absolute error | Bandwidth / Q |
|---|---:|---:|---|---:|---:|
| HR01 | 1216.08 | 1109.03 | yes | −107.05 Hz / 8.80% | 46.87 Hz / 23.66 |
| HR02 | 1510.20 | boundary maximum at 1345.43 | no | not valid | not valid |
| HR03 | 1848.56 | boundary maximum at 1670.84 | no | not valid | not valid |
| HR04 | 2198.33 | boundary maximum at 2015.87 | no | not valid | not valid |
| HR05 | 2652.29 | boundary maximum at 2432.16 | no | not valid | not valid |
| HR06 | 3200.00 | 3341.90 | yes | +141.90 Hz / 4.43% | 79.73 Hz / 41.92 |
| HR07 | 3916.97 | 4075.21 | yes | +158.24 Hz / 4.04% | 82.67 Hz / 49.29 |
| HR08 | 4396.65 | 4806.42 | yes | +409.77 Hz / 9.32% | 83.13 Hz / 57.82 |

The diagnostic sampled maxima are monotonically ordered HR01→HR08, but HR02–HR05 do not have valid centres. Therefore the formal predicted-centre ordering gate is not satisfied: boundary points cannot be promoted to centres.

For the stable experimental modules, HR07 is interior and within 5%, but HR03 and HR04 are non-identifiable boundary maxima. The required stable-module gate therefore fails.

HR04 remained a boundary maximum on both meshes, so a numerical centre-change percentage cannot be defined and its necessary mesh gate fails. HR07 changed by only 0.0187%, passing the <1% gate. Existing P03 bounded-local evidence remains valid (reduced 0.0224%, full thermoviscous 0.1246%), but that local topology is not identity-equivalent to the S1 shared-topology model re-extracted here; it cannot overwrite the S1 HR03 boundary result.

Selected 5-of-6 and all-six measured centres are identical for all eight modules. Both analyses therefore give the same negative centre-level conclusion.

## Secondary result: microphone relative transfer

The comparison used the nominal disk-average microphone, incident-pressure normalization, and HR-minus-P05 relative transfer. Simulation was retained unsmoothed in the per-module complex CSV files; only comparison curves used frozen 1/12-octave dB smoothing.

| Module | Relative RMSE (dB) | Pearson | Spearman | Cosine | Window direction |
|---|---:|---:|---:|---:|---|
| HR01 | 19.07 | 0.081 | 0.110 | 0.081 | agree |
| HR02 | 14.37 | 0.126 | 0.121 | 0.126 | agree |
| HR03 | 11.72 | 0.136 | 0.084 | 0.136 | agree |
| HR04 | 6.25 | 0.687 | 0.579 | 0.687 | agree |
| HR05 | 4.95 | 0.589 | 0.442 | 0.589 | agree |
| HR06 | 7.00 | −0.144 | −0.044 | −0.144 | disagree |
| HR07 | 8.78 | −0.208 | −0.081 | −0.208 | agree |
| HR08 | 8.70 | −0.260 | −0.230 | −0.260 | disagree |

These are selected-5-of-6 metrics over 800–5000 Hz; all-six results are substantively unchanged. HR04 and HR05 have the best relative shape correspondence, but HR05 is a weak experimental signature and neither result validates absolute amplitude, Q or full transfer. HR03 and HR07 illustrate the hierarchy clearly: their local window polarity agrees, while their full shapes remain poor. HR06 and HR08 even reverse the local window direction.

Internal-energy and microphone-transfer features separate materially. Examples include HR03 (energy boundary maximum 1670.84 Hz versus simulated microphone feature 1986.97 Hz), HR04 (2015.87 versus 2135.74 Hz), and HR07 (internal 4075.21 versus microphone 3860.81 Hz). A microphone feature therefore cannot substitute for the primary internal centre.

## Answers to the eight required questions

1. **Did nominal geometry predict HR01–HR08 centre ordering?** The diagnostic sampled maxima are strictly ordered, but four are boundary maxima. Formal centre ordering is not established and the frozen gate fails.
2. **Are HR03/HR04/HR07 centre errors all ≤5%?** No. HR07 is identifiable at 4.04%; HR03 and HR04 are non-identifiable, so no valid error can be claimed.
3. **How do weak HR01/HR05 signatures affect interpretation?** They limit experiment-facing claims. HR01's 8.80% centre miss is not strengthened by its weak signature, and HR05's boundary result is still a model failure to identify a centre; neither module was tuned or excluded.
4. **Do internal-energy and microphone features separate?** Yes, strongly, including HR03, HR04 and HR07. This confirms that the secondary microphone layer cannot replace the primary energy metric.
5. **Which transfer shapes correspond relatively better?** HR04 and HR05 rank highest by Pearson and RMSE. This is relative ranking only, not full-spectrum validation.
6. **Which modules show centre/local correspondence without full-shape correspondence?** HR07 has an interior centre within 5% and correct window polarity, but negative full-shape correlation. HR06 also has an interior centre within 5%, but its local polarity and full shape disagree. HR03 has correct microphone-window polarity but no valid S1 internal centre.
7. **Is the nominal internal model sufficient to enter U4 common-chamber mechanism analysis?** No. Stable-module interior-centre and required mesh gates fail, so P05/P06/full U4 must stop.
8. **What limitation follows from P04A's unidentifiable calibration?** This phase can only test the frozen as-designed nominal model. It cannot attribute errors to identifiable loss or length corrections, claim calibrated validation, rescue transfer shape, or justify new bounds/parameters.

## Gate table and stopping rule

| Frozen gate | Result |
|---|---|
| All geometry, selection and solver execution pass | pass |
| Valid predicted centre order | fail: four boundary maxima |
| HR03/HR04/HR07 all interior | fail |
| HR03/HR04/HR07 all ≤5% | fail |
| HR04/HR07 second-mesh centre change <1% | fail: HR04 centre undefined; HR07 passes |
| Selected/all-six centre conclusion unchanged | pass: both negative |

Final status: `P04B-N MODEL NOT CREDIBLE FOR U4`.

No P05, U4, full array, external field, classifier, commit, push, tag or release was started. Work stops here pending user acceptance.
