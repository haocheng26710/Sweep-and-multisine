# COMSOL Scheme 3A — P00 MCP smoke test

## Outcome

**P00 FAIL**

P00 reached a local COMSOL 6.4 session through MCP and could create, parameterize, save, reload, and inspect an otherwise empty disposable model. It could not create the required 3D component because the MCP component wrapper invoked an API overload that COMSOL 6.4 does not provide. Per the P00 stop rule, no V2.5 model or later phase was attempted.

## Session and capability status

| Item | Result | Evidence |
|---|---|---|
| MCP visibility | PASS | 93 COMSOL MCP tools were callable/discoverable |
| Local COMSOL session | PASS | COMSOL 6.4 started on localhost with a dynamically assigned port and 16 cores |
| Pressure Acoustics interface advertised | YES | `physics_get_available` listed `Pressure Acoustics (acpr)` |
| Acoustics documentation installed | YES | PDF inventory listed `Acoustics_Module` |
| Acoustics license checkout verified | NOT VERIFIED | Actual physics creation could not reach license checkout because `comp1` was absent |
| Eigenfrequency capability verified | NOT VERIFIED | Study creation returned an error and no solution was possible |

## Model definition and analytic target

The disposable model was assigned parameters for a `0.1 m × 0.02 m × 0.02 m` air cavity at `293.15 K`, with recorded sound speed `c = 343.2 m/s`. The analytic first non-zero longitudinal mode is:

`f = c/(2L) = 343.2/(2 × 0.1) = 1716.0 Hz`.

No computed eigenfrequency exists, so numerical error and convergence cannot be evaluated.

## Exact failure diagnosis

Failure layer: **MCP model API compatibility**.

The MCP `model_create_component` operation called `ModelNodeListClient.create(str,bool,int)`. COMSOL 6.4 reported that only `create(str,str)`, `create(str)`, and `create(str,bool)` were available. Inspection confirmed that the component list remained empty. All later geometry and Pressure Acoustics probes consequently failed on missing tag `comp1`.

This is upstream of geometry, meshing, solver, results export, and a conclusive Acoustics license checkout. It is not evidence that those downstream layers themselves are defective.

## Mesh comparison

| Mesh | Elements | Eigenfrequency | Change |
|---|---:|---:|---:|
| Coarse | Not created | Not solved | N/A |
| Fine | Not created | Not solved | N/A |

The required two-level convergence criterion was not testable.

## Acceptance gate

| Requirement | Status |
|---|---|
| Start/connect through MCP | PASS |
| Required license and interfaces verified | FAIL — interface advertised, license checkout unverified |
| Create → geometry → physics → mesh → solve → result → exports → save | FAIL — stopped at component creation |
| Computed frequency within 2% of analytic | NOT TESTED |
| Accepted mesh changes by no more than 1% | NOT TESTED |
| `.mph` saved and reloaded/inspected | PARTIAL PASS — diagnostic empty model saved and reloaded |
| All required successful-run artifacts exist and are hashed | FAIL — no pressure PNG or numerical solution export can exist |

## Artifacts

- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE/COMSOL_3A_P00_RIGID_TUBE_FAILED_COMPONENT_API.mph`
- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE/p00_results.json`
- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE/mesh_statistics.json`
- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE/session_tool_license_log.md`
- `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE/SHA256SUMS.txt`

The manifest records every artifact that exists. A pressure-mode PNG was not fabricated because no geometry or solution existed.

## Scope confirmation

P01 was not started. No V2.5 geometry was inspected, modeled, or solved. Final-test data was not read. Existing experimental data and reports were not modified.
