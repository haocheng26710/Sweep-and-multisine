# COMSOL Scheme 3A — P04A0 calibration preflight

Date: 2026-08-25  
Status: **P04A0 CONTRACT FROZEN**  
Scope: prospective calibration contract only; no calibration search and no formal COMSOL solve

## Outcome and contract gap

P04A requires exact parameter bounds, objective and frequency ranges “frozen in P01”. The accepted P01 contract actually freezes allowed/prohibited parameter classes, repeat processing, the 256-point grid and the 200–4000/4000–8000 Hz bands, but it does not contain a complete executable numerical optimization contract. This phase therefore adds a non-overwriting prospective contract. P01 remains unchanged and is not represented as if it already contained these values.

The accepted P03 `+3.009%` HR03 residual establishes motivation only. It was not used to widen bounds, choose the HR03 window, add objective terms or set stopping rules.

## Input identity audit

The authority chain is complete. P01 machine contract SHA-256 is `b1aedab671bc659eaccf6ac3a6948667abe2ddafc40f27d58cbe8d924429d780`; accepted P03 RETRY_01 report is `d9e2fa9ae4583a477cef886da2535e9f0806094ab7b7de5c6eafbbfc44975dfa`; frozen repeat selection is `6a174a156919adbcd6fb67f018bf74667c1317905a8c7411a327765edff8d9dd`; joint preprocessed spectra are `e5454dbe149e2d3a17a0a0539905af6d828ce7c75f72f51d126934f8f5a8c4ed`.

All 12 TXT and 12 paired MDAT files were rehashed read-only and matched the S1 inventory. The old B01/B02 labels are retained only for identity; the current authority treats repeats 1–6 as one campaign.

| Condition | Campaign repeat | Exact TXT | TXT SHA-256 | Exact MDAT | Primary |
|---|---:|---|---|---|---|
| P05 base | 1 | `R V2.5_base_01.txt` | `2b7a0de5c265a7e91513c48f95cd46830c3ed38e55c7b4e5a517e137262a5297` | `R V2.5_base_01.mdat` | keep |
| P05 base | 2 | `R V2.5_base_02.txt` | `1dfb9ad16af11ef96badc285f4687e0eed926a36bcc99a44ffdbc64fc84d5e58` | `R V2.5_base_02.mdat` | **farthest flag** |
| P05 base | 3 | `R V2.5_base_03.txt` | `11f9c9a7750c6ef224d32b1ca576a32d34a97f2469401f9f1ea6ff1a60923ff9` | `R V2.5_base_03.mdat` | keep |
| P05 base | 4 | `R V2.5_base_04.txt` | `1f4b5b9601a826b01eb2d9977f45e220d7b3821e67f17c6d79d8b320a44e4f65` | `R V2.5_base_04.mdat` | keep |
| P05 base | 5 | `R V2.5_base_05.txt` | `9b94c9f13c805c2227bef2b9c56eea6de1f3be233c6ff292884ad7b9b624d591` | `R V2.5_base_05.mdat` | keep |
| P05 base | 6 | `R V2.5_base_06.txt` | `440f3553442cae83a89e8c3c49e7cfba72e05ad4373447f2d0015bf81efb37f1` | `R V2.5_base_06.mdat` | keep |
| HR03 | 1 | `R V2.5_HR03_01.txt` | `f20ff6de4aac5d642cef70d9bb6deab226a0f9da8162801cca976f3b0288e344` | `R V2.5_HR03_01.mdat` | keep |
| HR03 | 2 | `R V2.5_HR03_02.txt` | `549b27e13666118030703804ac422cd1ee98aebaab5fe2f619deda77afae5fa6` | `R V2.5_HR03_02.mdat` | **farthest flag** |
| HR03 | 3 | `R V2.5_HR03_03.txt` | `cca0b3d7f6f0dad54196f72bab74ffb152fece477f4f0ea0b98c141c004d5c72` | `R V2.5_HR03_03.mdat` | keep |
| HR03 | 4 | `R V2.5_HR03_04.txt` | `a5b8aeeb6acbede26ed2074ff008f2d1097cc6a084ec04c4c3897237dd23886d` | `R V2.5_HR03_04.mdat` | keep |
| HR03 | 5 | `R V2.5_HR03_05.txt` | `c2f56f7971eedb5b069f76eb9120bca92c38d19c3d12085a955f8d072ddf28ba` | `R V2.5_HR03_05.mdat` | keep |
| HR03 | 6 | `R V2.5_HR03_06.txt` | `73aeb3a8ed574851429ae683cf53edc2c738acd748282c51b655c9b641db4756` | `R V2.5_HR03_06.mdat` | keep |

Full MDAT SHA-256 values and per-repeat preprocessing/output hashes are in `calibration_input_manifest.csv`. Primary is P05 `{1,3,4,5,6}` and HR03 `{1,3,4,5,6}`; all-six sensitivity is `{1,2,3,4,5,6}` for each. Raw curves remain undeleted.

## Frozen observable and processing

For each condition, form the pointwise median-in-dB representative across the frozen repeat set, then calculate `HR03 - P05`. Primary uses 5-of-6; sensitivity uses all six. Conditions are aggregated independently and are not paired by repeat number.

The exact preprocessing remains 200–8000 Hz, `f[n]=200*2^(n/48)`, `n=0..255`, 256 points, and frozen `formal_log_grid_v1` 1/12-octave dB smoothing. The primary/secondary diagnostic bands remain 200–4000/4000–8000 Hz.

The calibration range is the pre-existing HR03 CAD target window, `1850 Hz ±1/6 octave`: continuous bounds `1648.1626285596276–2076.55478937234 Hz`; exact grid indices 147–162, 16 bins, `1670.838051883862–2074.943287441615 Hz`. Experimental and simulated relative curves are demeaned over those same 16 bins.

Future P04A must construct comparable S1-topology P05 and HR03 reduced models with the same incident-port normalization and nominal microphone disk-average transfer. Existing P02 microphone output and P03 local cavity-average output are not directly subtractable. Unsmoothed complex transfers must be saved first; real/imaginary parts are placed on the exact grid before magnitude ratio and comparison-only dB smoothing. Unknown source amplitude and a constant local broadband offset are removed by the relative/de-meaned observable, not fitted as physics.

## Frozen parameters and bounds

| Parameter | Nominal | Exact bounds | Auditable source and application |
|---|---:|---:|---|
| `hr_neck_effective_length_delta_mm` | 0 mm | `[-0.2, +0.2] mm` | P01 already freezes critical-neck length tolerance magnitude ±0.2 mm. One feature-class effective correction applies to both HR03 necks and later every HR neck; nominal CAD is unchanged. P05 has no HR-neck selection, so the operator is empty there rather than becoming a P05-specific substitute. |
| `effective_loss_scale` | 1.0 | `[0.5, 2.0]` | P01 already freezes 0.5×/1×/2× effective-loss cases. The same reduced-model loss formulation and scalar apply to the declared wetted-wall classes in both P05 and HR03. |

No third parameter is justified. Air temperature lacks a bound acquisition record; seal-gap impedance and microphone coupling are unverified; chamber coupling is not a full-3D parameter. No HR03-specific shift, physical neck/cavity/target change, per-module loss, per-direction gain/phase or arbitrary frequency-axis shift is allowed.

## Frozen objective

Let `Y_exp,5[n]` be the demeaned, smoothed experimental relative curve and `Y_sim[n;p]` the identically processed simulated relative curve. The only fitted objective is

`J5(p) = sqrt((1/16) * Σ[n=147..162] (Y_sim[n;p] - Y_exp,5[n])²) dB`.

Weights are equal because the grid is uniform in log frequency. Frequency bins define a curve norm, not 16 experimental repeats. Centre, local contrast, peak amplitude, bandwidth, Q, simulation phase and full-band shape errors are diagnostic only. All-six `J6(p*)` uses the same primary-fitted parameters; there is no second fit. Missing/nonfinite complex values, zero magnitude, extrapolation, solver failure, or no interior fixed-window feature makes a candidate infeasible (`+Infinity`). Bounds are never expanded. Values within `0.01 dB` of `Jmin` use the frozen nominal-distance/lexicographic tie-break.

## Repeat-aware uncertainty and identifiability

The future bootstrap uses complete repeat curves: independently sample five HR03 and five P05 curves with replacement, take pointwise medians, and repeat 2000 times with NumPy `default_rng(250825)`. Bootstrap optima are selected only from the already-solved search table, with no surrogate or additional solve. Report percentile 2.5/97.5% parameter intervals.

Identifiability is flagged if any condition holds:

- bootstrap parameter `|Pearson r| >= 0.90`, or undefined correlation from zero variance;
- a `J <= Jmin + 0.05 dB` profile set spans at least 50% of a bound;
- optimum lies within the final step of a bound (`0.025 mm` or `0.0625`);
- a 95% parameter interval spans at least 50% of its bound;
- selected/all-six improvement classes (`improved`, `indistinguishable`, `worsened`, tolerance `0.01 dB`) differ.

Any such result is reported; it cannot trigger a third parameter, changed flag, new range or separate all-six fit.

## Frozen search budget

Coarse grid: effective length `{-0.2,-0.1,0,0.1,0.2} mm` × loss `{0.5,0.75,1,1.25,1.5,1.75,2}` = 35 combinations. Two and only two clipped/deduplicated 3×3 refinements use steps `(0.05 mm,0.125)` then `(0.025 mm,0.0625)`. Hard ceiling: 53 unique parameter combinations and 106 P05/HR03 frequency-domain solves. Solver failures are logged and assigned `+Infinity`; neither bounds nor budget may be extended. Only complex frequency-axis interpolation is allowed, never parameter-space interpolation.

## Acceptance and scope boundary

| P04A0 gate | Result |
|---|---|
| P01/P03/input hash bindings complete | PASS |
| Exact P05/HR03 six-repeat mapping verified | PASS |
| Unique farthest flags and 5-of-6/all-six sets frozen | PASS |
| Two auditable parameter bounds frozen | PASS |
| Objective, ranges, failures and tie-break frozen | PASS |
| Repeat bootstrap and identifiability rules frozen | PASS |
| Search method and hard solve ceiling frozen | PASS |
| P01/raw/analysis artifacts unchanged | PASS |
| Calibration or formal COMSOL solve performed | NO — required for this phase |

Disposition: **P04A0 CONTRACT FROZEN**.

Artifacts are under `outputs/simulation/COMSOL_SCHEME_3A/P04A0_CALIBRATION_PREFLIGHT/`; `SHA256SUMS` is the final authority. No P04A fit, formal COMSOL solve, P04B prediction, other-HR inspection, U4/array/external model, classifier, print decision, commit, push, tag or release was performed. `final_test_read=false`. P04A and P04B were not started.
