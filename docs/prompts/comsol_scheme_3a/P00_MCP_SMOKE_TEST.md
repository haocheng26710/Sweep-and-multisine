# Copy-paste prompt — P00 COMSOL MCP smoke test

You are working in a fresh Codex project. The workspace root is:

`D:\Bristol course\dissertation\program work`

This task is only P00, a disposable COMSOL MCP end-to-end smoke test. Do not start any V2.5 model.

## Required context

1. Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely.
2. Inspect `git status --short --branch` and preserve all unrelated user changes.
3. Discover the actually callable COMSOL MCP tools in this task. Do not assume that installation alone means the server, COMSOL process or license is working.

## Exact task

Verify the complete loop:

1. Query COMSOL MCP/session status.
2. Start or connect to a local COMSOL session using the installed version. Do not guess a remote host/port.
3. Record COMSOL version and licensed products/interfaces relevant to Pressure Acoustics and Eigenfrequency studies.
4. Create a new disposable 3D model named `COMSOL_3A_P00_RIGID_TUBE`.
5. Build an air-filled rectangular tube/cavity:
   - length along x: `0.1 m`;
   - cross-section: `0.02 m × 0.02 m`;
   - rigid/sound-hard walls;
   - air at a documented temperature, with the actual speed of sound recorded.
6. Add Pressure Acoustics and an Eigenfrequency study.
7. Search for the first non-zero longitudinal mode around `c/(2L)`, approximately `1715 Hz` when `c=343 m/s`.
8. Create at least two mesh levels and check frequency convergence.
9. Solve and retrieve the numerical eigenfrequency through MCP, not only from a screenshot.
10. Export:
    - `.mph` model;
    - CSV or JSON containing analytic and computed values;
    - pressure-mode PNG;
    - mesh/statistics text or JSON;
    - session/tool/license log;
    - SHA-256 manifest.

Use the output directory:

`outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE/`

Create the report:

`docs/progress/COMSOL_3A_P00_MCP_SMOKE.md`

## Acceptance gate

P00 passes only if all are true:

- COMSOL can be started or connected through MCP;
- the required acoustics and eigenfrequency capability is licensed;
- create → geometry → physics → mesh → solve → numeric result → image/data export → save all work;
- the computed non-zero longitudinal frequency differs from the analytic value by no more than 2%;
- the accepted mesh result changes by no more than 1% relative to the previous mesh;
- the `.mph` can be saved and inspected/reloaded;
- all artifacts exist and are hashed.

If any item fails, do not improvise a V2.5 model. Diagnose the exact layer: MCP visibility, COMSOL process, license, model API, solver, export or filesystem. Preserve logs and stop.

## Prohibited actions

- Do not inspect or model V2.5 geometry.
- Do not read final-test.
- Do not modify experimental data or existing reports.
- Do not install software, edit MCP configuration or restart the Codex app without explicit user authorization.
- Do not push, tag, release or automatically commit.
- Do not begin P01.

## Final response format

Lead with `P00 PASS` or `P00 FAIL`. Then provide:

- COMSOL/MCP/session/license status;
- analytic and computed frequencies and errors;
- mesh comparison;
- exact artifact paths and hashes;
- any limitation or failure diagnosis;
- confirmation that P01 was not started.

Stop and wait for user acceptance.

