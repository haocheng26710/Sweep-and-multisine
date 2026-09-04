# P01 READY FOR ACCEPTANCE — simulation contract and provenance freeze

Date: 2026-08-25  
Scope: P01 audit/freeze only; no V2.5 model was built or solved

## 1. P00 identity and working-tree boundary

The accepted prerequisite is exclusively `docs/progress/COMSOL_3A_P00_MCP_SMOKE_RETRY_02.md` with disposition `P00 PASS`, backed by `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE_RETRY_02/`. All eight entries in its stored SHA-256 manifest were recomputed and matched. Original P00 and RETRY_01 remain failure provenance and were neither changed nor treated as accepted models.

The starting branch was `feature/v2-dual-input` tracking `origin/feature/v2-dual-input`. The working tree already contained numerous modified/untracked user files. They were treated as baseline; no reset, checkout, clean, stash, delete, commit, push, tag, or release operation was used.

## 2. Verified source identities

| Source | Bytes | SHA-256 | Status |
|---|---:|---|---|
| V2.0.1 print package | 2,601,550 | `2f3bdbf791f77fc276b6f7b7bc0790e101c082e0191b5af3d5c24d83a162d29f` | Matches registry |
| V2.5 patch | 710,509 | `849566111d121bdcf581018a31ec1759ad39646001a258e367732c21a85b401f` | Matches registry |

The parameter JSON and generator source inside both archives were inspected read-only. Archive documentation was treated as design provenance, not as execution instructions.

## 3. Geometry identity freeze

| Identity | Frozen nominal design facts | Acoustic-domain interpretation |
|---|---|---|
| P01 | Regular octagon; apothem 105 mm; air height 9.2 mm from z=3.0 to 12.2 mm; module radii 32–88 mm | Reconstruct the connected air cavity; P01 plastic STL is not the fluid domain |
| P03 | iMM-6C front Ø8.8 mm; recommended bore Ø9.0 mm; socket Ø20.4 mm; insert neck Ø20.0 mm; flange Ø30×3 mm; nominal tip z≈7 mm | Physical diaphragm plane/area remains unverified; use explicitly nominal point and disk-average probes |
| P05 | 56 mm radial body; 17/36 mm inner/outer body widths; tray 7.6 mm; bottom 1.2 mm; air height 6.4 mm; straight channel width 9.4 mm | Nominal P02 baseline module; use corrected V2.0.1 lid interface |
| P09 | Solid dummy with inner and outer filling tongues; distinct from P10 | Removes inactive diagonal sectors from the connected U4 fluid domain; it is not an open or closed side branch |
| Central chamber | Radius 18 mm; height 9.2 mm | Circular nominal chamber joined to all active inner passages |
| Fixed inner passage | r≈17–32 mm; width 8 mm; height 9.2 mm | Begins 1 mm inside chamber radius to ensure a geometric union |
| Fixed outer passage | r=88–105 mm; 17 mm long; width tapers 8→16 mm; height 9.2 mm | Outer truncation/port cross-section must receive a stable named selection |

All HR01–HR08 targets, cavity centres/plan dimensions/volumes, neck widths, and physical neck lengths are frozen in `simulation_contract.json`. Package estimates are design provenance, not FEM or measurement truth.

Coordinate system: head centre `(0,0)`, `+Y=0°/N`, `+X=90°/E`, base bottom `z=0`; module local x is inward negative/outward positive, y tangential, z upward.

## 4. Physical assembly mapping and S2 correction

- U4SYM/S2: P05 open at 0°/90°/180°/270°; P09 solid dummies at 45°/135°/225°/315°.
- U4HR/S3: HR01/HR03/HR05/HR07 at 0°/90°/180°/270°; P09 at diagonals.

The user’s 2026-08-25 confirmation makes S2’s four-open-P05 identity authoritative. All 16 S2 `1 acoustic channels open` notes are stale template metadata. A separate addendum was created, and the only human-readable derived report that still said “awaiting confirmation” now cross-references it. Raw TXT/MDAT, frozen analysis JSON, artifact manifests, and existing hashes were not changed.

The frozen `analysis_summary.json` still contains its historical `physical_four_open_assembly_requires_user_confirmation=true` flag. It is preserved unchanged and must be interpreted together with the addendum.

## 5. Experimental and calibration freeze

- S1: one six-repeat campaign; flag the unique farthest curve and use 5-of-6 for primary analysis; retain all six for sensitivity.
- S2/S3: four repeats per direction; flag the unique farthest and use 3-of-4; retain all four for sensitivity.
- Exact comparison grid: `f[n]=200×2^(n/48) Hz`, `n=0…255`, 256 points, last point 7947.8899972702975 Hz.
- Comparison processing: preserve unsmoothed complex simulation results; resample to the exact grid, then apply the frozen 1/12-octave dB smoothing for experiment-comparison results only.
- Primary/secondary bands remain 200–4000/4000–8000 Hz.

Only effective neck-length corrections, predeclared feature-class loss/Q scales, a tolerance-bounded global cavity-compliance scale, one reduced-network chamber-coupling parameter, and measured-air-property changes are calibratable. Per-direction gains, post-result window movement, assembled-direction frequency shifts, and S2/S3 fitting are prohibited.

Because the current V2.5 data contain no independent assembly/reposition block, calibration agreement is descriptive and cannot be called independent validation.

## 6. Frozen modelling hierarchy

1. Accepted analytic tube smoke test.
2. Parameterized P05 nominal fluid-domain baseline.
3. Isolated HR03 local model.
4. Bounded local thermoviscous comparison.
5. Full internal U4SYM numerical control.
6. Full internal U4HR multiport/common-chamber model.
7. Compact free-field external model, one direction then four.
8. Fixed-frequency field/energy attribution.
9. One-variable-at-a-time virtual interventions.
10. Fine-mesh and tolerance confirmation for one best candidate.

Bulk physics is Pressure Acoustics, Frequency Domain. Narrow Region/effective losses require level-4 justification. Full thermoviscous physics remains local unless evidence requires expansion. The external pilot must validate a compact spherical/background source representation; it may not silently replace the 0.8 m source with a plane wave or add a room.

## 7. Frozen metrics

Let cardinal port order be `[000,090,180,270]`, channel order `[HR01,HR03,HR05,HR07]`, and `p=acpr.p_t`.

- Port→microphone transfer: `T_mi(f)=p̄_mic(f)/p_i+(f)`, using complex area-average nominal microphone pressure and incident plane-wave pressure at driven port i. Drive one port; anechoically terminate the other active ports.
- Power-wave scattering matrix: with `Zc_k=ρc/A_k`, `a_k=(p̄_k+Zc_k U_k)/(2√Zc_k)`, `b_k=(p̄_k−Zc_k U_k)/(2√Zc_k)`, define `S_ji=b_j/a_i`. `U_k` is positive outward from the internal domain.
- Channel energy: `E_ik=mean_{f∈W_k}|T_mi(f)|²`; `C_ik=10log10(E_ik)`; `W_k` is ±1/12 octave around a centre frozen before the assembled run.
- Diagonal advantage: `DA=mean_i(C_ii)−mean_{i≠k}(C_ik)`. Gate: ≥3 dB and 4/4 unique row-wise diagonal top-1; ties fail.
- Normalized off-diagonal energy: `R_off=mean_i{[(Σ_{k≠i}E_ik)/3]/E_ii}`. Gate: ≤0.5.
- Resonance centre: log-frequency quadratic refinement of the module-region integrated-energy maximum within ±1/6 octave of the frozen reference. A boundary maximum fails identification.
- Resonance drift: `|log2(f_assembled/f_isolated)|`; gate <1/12 octave.
- Energy participation: `P_r=∫_r w dV/∫_all w dV`, with `w=|p|²/(4ρc²)+ρ|u|²/4`; mutually exclusive region participation plus labelled remainder must close to 1 within 1e-6.

These definitions, exact formulas, zero/non-finite handling, and reference centres are machine-frozen in the JSON contract.

## 8. Mesh, selections, tolerance, and artifact gates

Bulk `hmax≤c/(6fmax)`; critical necks require at least four elements across on coarse and six on fine. Fine local hmax must be ≤0.75 of coarse. Two consecutive accepted meshes must give resonance change <1% and diagonal-advantage change <0.5 dB. U4SYM coordinate-aligned rotational equivalents must differ by no more than 0.2 dB.

Named selections use stable geometry-derived tags, never entity numbers alone. Required families cover the full fluid, chamber, nominal microphone surface, walls, every port/fixed passage/module, and each HR cavity/neck. Tags, counts, and geometric measures must survive rebuild.

Candidate tolerance success requires every scientific gate in nominal geometry and every applicable ±0.2 mm critical-dimension, 0.5×/1×/2× loss, and seal case. Seal cases are frozen at airtight, 0.05 mm, and 0.10 mm gaps, but cannot be claimed until a defensible gap-impedance model exists.

Every later simulation phase must export config, input manifest, named selections, mesh statistics, unsmoothed complex results, summary metrics, solver/session/license log, non-empty PNG, saved/reloaded MPH, report, and final SHA-256 manifest in a phase-specific directory.

## 9. Execution acceptance versus scientific success

Execution acceptance requires valid geometry/connectivity, stable selections, successful physics/mesh/solve/export, mesh convergence, MPH reload, and verified hashes. Scientific success separately requires the frozen hypothesis gates.

A valid model that yields no code preservation is an accepted negative scientific result. Thresholds may not be changed to rescue it, and it may not be discarded as an execution failure.

## 10. Unverified facts and P02 effect

| Unverified fact | Evidence boundary | Blocks P02? | Required handling |
|---|---|:---:|---|
| Actual printed dimensions, warpage, roughness, gasket compression and leak paths | Digital design only | No | P02 is nominal-design only |
| Actual iMM-6C diaphragm sampling plane/area | Only front Ø8.8 mm, shoulder length 10 mm and nominal z≈7 mm known | No | Export nominal point and disk average; no physical-response claim |
| Seal-gap impedance and printed-surface loss | No measurement | No | Sound-hard nominal P02; blocks later candidate tolerance claim |
| V2.5 old lid overhang 0.8 mm versus V2.0.1 corrected 0.10 mm inset | Both archive generators | No for P02 | Use V2.0.1 P05; reconcile before later HR solid/gasket compatibility claims |
| Narrow Region/Thermoviscous feature licence | P00 proved bulk Pressure Acoustics/Eigenfrequency only | No | Verify before hierarchy level 4 |
| Faithful compact 0.8 m loudspeaker model | Not validated | No | Blocks external level 7, not P02 |
| Cross-assembly/reposition generalisation | Not measured | No | No generalisation claim |

No user question is required before nominal P02. P02 is ready only as a parameterized P05 nominal fluid-domain baseline; it must not claim physical calibration or begin HR/common-chamber scientific selection.

## 11. Acceptance table

| P01 gate | Result |
|---|---|
| Source identities and hashes traceable | PASS |
| RETRY_02 accepted identity and SHA verified | PASS |
| S1 5-of-6 and S2/S3 3-of-4 recorded | PASS |
| S2 four-open identity corrected in derived documentation | PASS |
| Raw notes and frozen machine artifacts unchanged | PASS |
| Plastic and acoustic fluid domains separated | PASS |
| Metrics and numerical/scientific gates frozen | PASS |
| P02 readiness stated | PASS — nominal P05 baseline only |

P01 disposition: **READY FOR ACCEPTANCE**.

Artifacts:

- `docs/progress/COMSOL_3A_P01_SIMULATION_CONTRACT.md`
- `docs/progress/V25_S2_OPEN_CHANNEL_PROVENANCE_ADDENDUM.md`
- `outputs/simulation/COMSOL_SCHEME_3A/P01_CONTRACT/simulation_contract.json`
- `outputs/simulation/COMSOL_SCHEME_3A/P01_CONTRACT/input_manifest.csv`
- `outputs/simulation/COMSOL_SCHEME_3A/P01_CONTRACT/SHA256SUMS`

No later phase was started. P02 was not started, no V2.5 acoustic model was created or solved, and final-test was not read.
