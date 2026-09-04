# COMSOL Scheme 3A — P03 HR03 loss-model check RETRY_01

Status: **P03 RETRY_01 PASS**  
Scientific result classification: **`as_designed_close`**  
Date: 2026-08-25

The first P03 attempt remains permanently recorded as **BLOCKED** because the old MCP interface could create `ThermoacousticsSinglePhysics` but could not populate its air-material model. The dedicated Thermoviscous Acoustics material path has now been fixed and verified against a real COMSOL 6.4 solve. `P03_HR03_RETRY_01` is the first valid formal HR03 modeling and scientific-analysis attempt. The MCP repair itself is not a scientific finding.

## Provenance and scope

The P02 report and SHA-256 manifest selected `outputs/simulation/COMSOL_SCHEME_3A/P02_P05_BASELINE/COMSOL_3A_P02_P05_BASELINE.mph` as authority. All 25 P02 manifest entries were recomputed successfully. P02 was loaded read-only to establish the representative P05 span, local/global transform, and named-geometry rules; it was not solved, overwritten, or modified.

The formal models are the hierarchy-prescribed bounded representative HR03 branch rather than a complete head. The +X/90° branch keeps local x negative inward and positive outward. In global x, the inner neck spans 31.4–55.0 mm, cavity 55.0–81.0 mm, and outer neck 81.0–88.6 mm. This replaces the P05 air passage over the frozen module span without creating another HR module or array.

## Geometry and connectivity

| Check | Result |
|---|---:|
| Inner neck width / length | 2.8 / 23.6 mm; 0% error |
| Outer neck width / length | 4.4 / 7.6 mm; 0% error |
| Air height | 6.4 mm; 0% error |
| Cavity volume | 2496.0 vs 2488.045 mm³; 0.3197% error |
| Total HR03 fluid volume | 3132.928 vs 3124.973 mm³; 0.2546% error |
| Connected components | 1 |
| Real air domains | `[1,2,3]` |
| Named selections | 7/7 nonempty; save/reload stable |

Both interfaces have zero gap and zero centerline offset. Shared inner/outer areas are 17.92 and 28.16 mm². The unchanged geometry gate (≤1%) passes.

## Physics and new-tool verification

The reduced model uses Pressure Acoustics (`acpr`) with a `ThermoviscousBoundaryLayerImpedance` effective-loss boundary. Its Pressure-Acoustics material settings use explicit `c=343 m/s` and `rho=1.2041 kg/m³`.

The reference model uses full `ThermoacousticsSinglePhysics` (`ta`). The new `physics_configure_thermoviscous_medium` tool was called on nonempty domains `[1,2,3]` and targeted `tam1/ThermoviscousAcousticsModel`. It wrote and read back:

- `rho0=1.2041 kg/m³`, `c=343 m/s`;
- `mu=1.814e-5 Pa·s`, `muB=1.09e-5 Pa·s`;
- `kcond=0.0257 W/(m·K)`, `Cp=1005 J/(kg·K)`, `gamma=1.4`;
- equilibrium `T=293.15 K`, `p=101325 Pa`;
- every corresponding source selector as `userdef`.

No blank Common Air material was created. The thermoviscous model did not use Pressure Acoustics `fpam1`, `rho_mat`, or `rho`. Thermoviscous inlet/outlet constraints use COMSOL 6.4 `PressureAdiabatic`, not the Pressure-Acoustics-only `Pressure` feature.

## Solver, license, meshes, and boundary layers

Both physics layers completed real COMSOL 6.4 frequency-domain solves on the frozen 1500–2200 Hz, 25 Hz grid. Full Thermoviscous Acoustics coarse/fine solves completed in 7.553/12.462 s, proving the Acoustics Module feature checkout on demand; this is no longer merely a feature-creation probe.

| Model | Mesh | Elements | Vertices | Minimum / mean quality | Centre Hz |
|---|---|---:|---:|---:|---:|
| Reduced | coarse | 162154 | 29574 | 0.2197 / 0.6838 | 1891.041 |
| Reduced | fine | 554664 | 97767 | 0.2067 / 0.6795 | 1890.617 |
| Full TV | coarse | 877 | 381 | 0.006865 / 0.2381 | 1901.822 |
| Full TV | fine | 1284 | 550 | 0.01102 / 0.2926 | 1904.194 |

Reduced hmax fine/coarse is 0.667, giving approximately 4.90/7.35 elements across the 2.8 mm inner neck. TV physics-controlled meshes contain a dedicated `BndLayer` on both levels with three layers and stretch 1.2. At 1848.564 Hz the calculated viscous and thermal penetration depths are approximately 0.0509 and 0.0604 mm. They are far below the 1.4 mm minimum half-width and do not overlap. The boundary layers are explicitly represented rather than replaced by BLI in the reference.

Reduced and TV resonance-centre mesh changes are 0.0224% and 0.1246%, both below 1%.

## Reduced/reference comparison

| Metric | Reduced fine | Full TV fine | Difference |
|---|---:|---:|---:|
| Resonance centre Hz | 1890.617 | 1904.194 | 0.7130% |
| Peak magnitude Pa/Pa | 27.247 | 34.379 | −2.020 dB |
| Peak phase deg | −91.27 | −82.84 | −8.43° |
| Bandwidth Hz | 57.865 | 46.430 | +11.436 Hz |
| Q | 32.673 | 41.013 | −8.340 |

Across the common 1775–2025 Hz fine grid, the magnitude-difference RMS/max-absolute values are 2.065/3.941 dB; phase-difference RMS/max-absolute values are 14.90°/37.41°. The centre gate passes, but amplitude and phase differences are scientifically material and are not hidden.

## Experiment comparison and classification

The full thermoviscous fine centre is 1904.194 Hz. Relative to the measured HR03 centre 1848.564 Hz, the uncalibrated signed difference is **+3.009%**. No geometry, damping, or HR03-specific correction was fitted to obtain this result.

The numerical model is valid; reduced/reference peak centres agree within 1%; and the full uncalibrated centre is within the frozen 5% experiment gate. The scientific classification is therefore **`as_designed_close`**. This is a bounded local HR03 conclusion, not validation of the complete head, U4 array, or direction code.

## Acceptance

| Gate | Result |
|---|---|
| Geometry/neck error ≤1% | PASS |
| Connected air and named selections | PASS |
| Reduced and full Thermoviscous solve | PASS |
| Two-mesh centre changes <1% | PASS |
| Reduced/reference centre difference <1% | PASS — 0.7130% |
| Amplitude and phase quantified | PASS |
| No HR03-specific tuning | PASS |
| Save/remove/reload/result equality | PASS — max 0 Pa |

All artifacts are under `outputs/simulation/COMSOL_SCHEME_3A/P03_HR03_RETRY_01/`; `SHA256SUMS` is the final authority.

The original `docs/progress/COMSOL_3A_P03_HR03_LOSS_MODEL.md` and `outputs/simulation/COMSOL_SCHEME_3A/P03_HR03/` BLOCKED provenance remain unchanged. P02 was not redone. P04A was not started. No other HR module, complete V2.5 head, U4/S1/S2/S3/S4 array, external field, classifier, or print decision was created. `final_test_read=false`. No commit, push, tag, or release occurred.
