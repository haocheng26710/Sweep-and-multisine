# P00 PASS — COMSOL MCP smoke test RETRY_02

## Scope and isolation

This run executed P00 only. It began by disconnecting/clearing the prior COMSOL state, starting a new local COMSOL 6.4 session, and verifying an empty model list. No previous failed MPH was loaded or inherited. Original P00 and RETRY_01 artifacts/reports were not overwritten. P01 and the V2.5 formal model were not started.

Output directory: `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE_RETRY_02/`

## Session and capability result

- COMSOL MCP: connected and operational.
- COMSOL: 6.4, local session, 16 cores.
- Pressure Acoustics: available as stable physics tag `acpr`; live creation, meshing, and solution succeeded.
- Eigenfrequency: created and solved with stable Java tags `std_eig/step1`; shift `1715[Hz]`; requested eigenfrequency count 8; solve method reported `java_tag`.
- License evidence: the required capabilities checked out and executed successfully. The MCP status API does not expose a complete license-product checkout list; this limitation is recorded in the session log.

## Model definition and explicit readback

- Air domain: rectangular 3D cavity, `0.1 m × 0.02 m × 0.02 m`, length along x.
- Sound-hard walls: explicitly applied to boundaries 1–6.
- Medium tag: `fpam1`, not a blank Common Air material node.
- Speed of sound readback: `c_mat=userdef`, `c=343[m/s]`.
- Density readback: `rho_mat=userdef`, `rho=1.2041[kg/m^3]`.
- Physics-controlled mesh readback at both levels: `size_control_parameter=Frequency`, `maximum_frequency=2000[Hz]`.

The analytic first longitudinal frequency is `c/(2L) = 1715.0 Hz`.

Numerical values were retrieved through MCP using `real(freq)`. The exclusion rule was frozen as: exclude every mode with `abs(real(freq)) < 1 Hz`, then select the first remaining mode near `c/(2L)`. Thus the coarse `0.012155 Hz` and fine `0.046043 Hz` constant-pressure zero modes were excluded. The analytic value was not substituted for either computed value.

## Mesh and frequency comparison

| Level | autoMeshSize | Elements | Vertices | Minimum quality | Mean quality | First non-zero longitudinal mode (Hz) | Relative analytic error |
|---|---:|---:|---:|---:|---:|---:|---:|
| Coarse | 6 | 196 | 78 | 0.4574 | 0.6859 | 1715.0177452361083 | 0.0010347076% |
| Fine | 4 | 1131 | 305 | 0.3697 | 0.7242 | 1715.0014015554377 | 0.0000817233% |

Coarse-to-fine frequency change: `0.0009529744%`.

## End-to-end and reload checks

- Created and ran a 3D `PlotGroup3D/Surface` with expression `acpr.p_t`.
- COMSOL exported `pressure_mode_acpr_p_t.png`; size `14,839 bytes`; the file decoded successfully and is non-empty.
- Saved `COMSOL_3A_P00_RIGID_TUBE_RETRY_02.mph`; size `1,922,098 bytes`.
- Removed the model from memory and verified model count 0.
- Reloaded the saved MPH and checked component, Block/Finalize geometry, Pressure Acoustics and SoundHard features, fine mesh, Eigenfrequency study, solution, dataset, 3D plot, and image export.
- Re-read `real(freq)` after reload and recovered the same fine-mesh spectrum, including `1715.0014015554377 Hz`.

Two localized wrapper defects encountered during inspection are preserved in the tool log: the component-list helper has a COMSOL 6.4 overload mismatch, and two label-oriented helpers require localized display labels. These did not affect construction, stable-tag study execution, save/reload, or the independent full-model inspection.

## Acceptance gate

| Gate | Result | Evidence |
|---|---|---|
| Fresh COMSOL session and empty model list | PASS | Disconnect/clear, local start, model count 0 |
| Pressure Acoustics and Eigenfrequency operational | PASS | Physics creation and two successful eigenfrequency solves |
| Complete create-to-export chain | PASS | Geometry, physics, meshes, solutions, numerical readout, plot, PNG, JSON/CSV, MPH |
| Fine frequency error ≤2% | PASS | 0.0000817233% |
| Coarse-to-fine change ≤1% | PASS | 0.0009529744% |
| PNG non-empty | PASS | 14,839 bytes and decoded successfully |
| MPH save, removal, reload, and node inspection | PASS | All required node classes present after reload |
| Artifacts hashed | PASS | `SHA256SUMS.txt` contains all deliverables except itself |

Overall result: **P00 PASS**.

## Artifacts

- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE_RETRY_02/COMSOL_3A_P00_RIGID_TUBE_RETRY_02.mph`
- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE_RETRY_02/numerical_results.json`
- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE_RETRY_02/numerical_results.csv`
- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE_RETRY_02/mesh_statistics.json`
- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE_RETRY_02/pressure_mode_acpr_p_t.png`
- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE_RETRY_02/session_tool_license_log.md`
- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE_RETRY_02/reload_inspection.json`
- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE_RETRY_02/SHA256SUMS.txt`
- `docs/progress/COMSOL_3A_P00_MCP_SMOKE_RETRY_02.md`

No later phase was started.
