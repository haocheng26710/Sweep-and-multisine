# COMSOL Scheme 3A — P04A global calibration

Status: **P04A INADEQUATE**

Execution date: 2026-08-25  
COMSOL: 6.4, two cores, one MCP-owned server at `localhost:64706`  
Output directory: `outputs/simulation/COMSOL_SCHEME_3A/P04A_GLOBAL_CALIBRATION/`  
`final_test_read=false`

## Outcome

The frozen P04A search completed numerically, but its descriptive optimum cannot be frozen as a credible global calibration. The selected point is

- `hr_neck_effective_length_delta_mm = +0.200 mm`;
- `effective_loss_scale = 2.0000`;
- candidate `dp0p200_l2p0000`;
- primary objective `J5 = 12.8800343526 dB`.

Both values are at their upper frozen bounds. All 2,000 repeat bootstrap replicates selected the same double-boundary point, so both 95% percentile intervals are degenerate at the upper bounds and both upper-bound masses are 1.0. Parameter correlation is undefined because both bootstrap estimates have zero variance; under the prospective plan this is an identifiability failure. The loss profile also cannot establish non-flatness because its `J <= Jmin + 0.05 dB` set contains only one sampled loss value. No bound was extended, no third parameter was introduced, and no repeat or objective was changed to rescue the result.

`frozen_parameters.json` therefore contains `frozen_global_parameter_set: null` and `immutable_for_p04b: false`. The calibrated MPH files archive the descriptive best candidate only.

## Authority and data audit

Before modelling, the P04A0 `SHA256SUMS` entries, the P01/P03 RETRY_01/P04A0 bindings, and the 12 TXT plus 12 MDAT hashes were rechecked and passed. The repeat mapping was unchanged:

- primary P05: repeats `{1,3,4,5,6}`;
- primary HR03: repeats `{1,3,4,5,6}`;
- farthest flags: P05 repeat 2 (`R V2.5_base_02.txt`) and HR03 repeat 2 (`R V2.5_HR03_02.txt`);
- all-six sensitivity: repeats `{1,2,3,4,5,6}` for both conditions.

The `physics_configure_thermoviscous_medium` MCP capability remained visible and the COMSOL 6.4 connection passed. No final-test directory was opened, enumerated, copied or hashed.

## Comparable reduced models

Two new S1-topology reduced models were created without overwriting P02 or P03:

| Model | Domains | Connected components | Source boundary | Microphone boundary | Nominal SHA-256 |
|---|---:|---:|---:|---:|---|
| P05 | 52 | 1 | 76 | 177 | `5b79bc86b74d7eb5bce67a551c12d171aa319b0af846693e2e8fd4b11a652e4a` |
| HR03 | 56 | 1 | 76 | 177 | `69c41b8a765751e56dba9c6d74a6a76c7b0e13829abc4db3130f05b37b54c5a1` |

Both use the same incident pressure normalization, microphone disk-average definition, exterior wetted-wall treatment, air properties, physics-controlled mesh strategy and exact 256-point frequency grid. Their only structural difference is the straight P05 module versus the fixed P03 HR03 geometry.

The loss parameter changes the real thermoviscous boundary-layer impedance formulation in both models: viscosity and thermal conductivity are scaled so their penetration depths vary with `effective_loss_scale`. It is not an output amplitude or Q rescaling. The effective-length delta acts only on the HR03 inner and outer neck domain media using an impedance-preserving acoustic-coordinate transformation; the P05 HR-neck feature-class selection is empty and physical CAD dimensions do not change.

At the nominal point `(0 mm, 1.0)`, both models solved all 256 frequencies with finite, nonzero complex responses. Save/remove/reload differences were exactly zero. The nominal HR03-minus-P05 local feature was 1986.9725 Hz with `Q=8.0876`, 4.347% above the accepted P03 thermoviscous fine centre of 1904.1942 Hz and inside the prospectively fixed physical-consistency window.

## Frozen observable and search

The experimental target was constructed independently within each condition as the pointwise median in dB, then `HR03 minus P05`, using the fixed 1/12-octave representation and demeaning over indices 147–162. The fit objective was exactly the unweighted 16-bin RMS `J5`; centre, Q, bandwidth, amplitude, phase and wider-band shape were diagnostics only.

The deterministic search executed:

- 35/35 coarse combinations;
- refinement 1 around the current tie-broken best, clipped and deduplicated to four positions (three new);
- refinement 2 with the same rule, again four positions (three new);
- 41 unique combinations total;
- 9 unique P05 loss responses plus 41 HR03 responses = 50 COMSOL frequency-domain responses;
- zero solver failures, zero missing complex responses, and zero non-finite simulated candidates.

Each successful response contains 256 unsmoothed complex values with real and imaginary parts. Candidate configuration identity, solver/coverage state, objective, diagnostics, paths and last successful frequency were written to an atomically replaced checkpoint. The selected point remained the double-upper-bound coarse point after both refinements.

## Nominal versus descriptive selected point

| Analysis set | Nominal J (dB) | Selected J (dB) | Improvement (dB) | Class |
|---|---:|---:|---:|---|
| Primary 5-of-6 | 14.3196079258 | 12.8800343526 | 1.4395735732 | improved |
| All-six sensitivity | 14.3664237532 | 12.9283393773 | 1.4380843760 | improved |

The all-six result uses the same selected parameters and was not refitted. The two improvement classes agree, so repeat-selection sensitivity does not reverse the descriptive improvement. This agreement does not overcome the prospective identifiability failures.

The selected simulated local feature is 1930.4072 Hz, contrast 1.5705 dB, bandwidth 111.5202 Hz and `Q=17.3099`. Amplitude, phase and Q model uncertainty remains material and these quantities were not fitting targets.

## Bootstrap and identifiability

The repeat bootstrap used complete experimental repeat curves as the resampling unit, drew HR03 first and P05 second, used `default_rng(250825)`, and performed 2,000 replicates without additional COMSOL solves or parameter interpolation.

| Criterion | Delta | Loss scale | Result |
|---|---:|---:|---|
| Selected estimate | +0.200 mm | 2.0000 | both upper bounds |
| Bootstrap median | +0.200 mm | 2.0000 | — |
| 95% interval | `[0.200,0.200]` mm | `[2.0000,2.0000]` | touches upper bounds |
| Upper-bound mass | 1.000 | 1.000 | boundary uncertainty |
| Distinct bootstrap values | 1 | 1 | zero variance |
| Selected-value boundary hit | yes | yes | identifiability failure |
| Profile flat flag | no | yes | loss direction failure |
| Interval-width weak flag | no | no | intervals are narrow only because estimates pile up at bounds |

Pearson correlation is undefined rather than zero, which is an explicit failure under the frozen criteria. The two-parameter calibration is therefore non-identifiable despite finite solves and lower residual error.

## Saved models and reload verification

| Model | Descriptive calibrated SHA-256 | Reload max absolute response difference |
|---|---|---:|
| P05 | `725bca4295d163f5e214d966e1e20730caf83eeb8c49f72999ba421bc311d1e2` | 0.0 |
| HR03 | `386673e2e6916892bdb2b43e64c51c076924c5e9dbf6b0a4bca1dabd3e4c0cba` | 0.0 |

These files are descriptive clones at the best searched point and are not an immutable P04B calibration authority.

## Scientific boundary

P03's `as_designed_close` result was an uncalibrated, local HR03 centre-frequency result. P04A is a descriptive calibration against the same single experimental campaign; it is not independent validation. It does not prove other HR modules, a complete shared-cavity array, directional localization, or that U4HR outperforms U4SYM. Neither correlation nor calibration fit may be interpreted as a causal single-module contribution. Amplitude, phase and Q uncertainty is retained. P04B, U4/full-array, far-field, classifier and final-test work were not started.

## Reproducibility

The output directory contains the four MPH models, raw complex responses, candidate configs, atomic checkpoint/search table, spectra and diagnostics, all-six sensitivity, 2,000-row bootstrap table, uncertainty and identifiability records, plots in PNG/SVG, scripts, input/model/config manifest, artifact inventory and the final verified `SHA256SUMS`.

No commit, push, tag or release was performed. Execution stopped at P04A pending user acceptance.
