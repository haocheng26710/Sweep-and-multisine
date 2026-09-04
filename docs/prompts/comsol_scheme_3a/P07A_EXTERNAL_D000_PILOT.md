# Copy-paste prompt — P07A one-direction external-field pilot

Execute only P07A after the user accepts P06 and its scientific branch decision.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely, then read the P01 contract and all accepted P05/P06 internal reports/models. Read the frozen acquisition geometry/orientation definition from P01. Inspect git status and preserve unrelated work.

## Exact task

Add the smallest defensible free-field exterior model for D000 only, for both accepted configurations:

- U4SYM;
- U4HR.

The physical source distance is `0.8 m`. Do not silently approximate it as a plane wave. First use official COMSOL documentation and a bounded analytic check to choose a compact representation, preferably an analytic background spherical wave or equivalent source/boundary formulation that avoids meshing the entire 0.8 m path. If the available MCP/license cannot implement a defensible compact formulation, stop and report the exact limitation.

1. Freeze D000 source/device orientation from P01; do not infer it from filenames alone.
2. Add an exterior air domain with a documented radiation boundary/PML treatment.
3. Keep the already accepted internal geometries, physics parameters, losses and microphone evaluation unchanged.
4. Use a small predeclared pilot frequency set containing the designed HR centres and the fixed exploratory frequencies. Do not select frequencies after viewing fields.
5. Check exterior-domain/PML thickness and mesh sensitivity.
6. Export microphone transfer relative to the incident/reference field for U4SYM and U4HR.
7. Compare simulated U4HR−U4SYM with the measured D000 S3−S2 relative/demeaned spectrum only as a bounded pilot. Do not fit the exterior model to the D000 result.
8. Identify whether the exterior formulation is numerically stable enough for four directions.

The real room, support and loudspeaker directivity are not modelled in this phase. State this limitation prominently.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P07A_EXTERNAL_D000/`

Create:

- U4SYM and U4HR D000 pilot `.mph` models or auditable clones;
- source/background-field derivation and validation note;
- exterior-domain, PML and mesh sensitivity CSV;
- pilot transfer and HET−HOM comparison CSV;
- field and geometry PNG/SVG;
- solver log and SHA-256 manifest;
- `docs/progress/COMSOL_3A_P07A_EXTERNAL_D000_PILOT.md`.

## Execution acceptance gate

- Source orientation and 0.8 m representation are explicit and justified.
- Incident-field normalization is validated independently of the device.
- PML/radiation and mesh sensitivity satisfy P01-frozen criteria.
- Both configurations solve at every pilot frequency.
- Microphone and reference-field expressions return finite, labelled values.
- No model fitting is performed against D000.

Scientific agreement with the experiment may be weak and is not required for execution acceptance. Classify it as consistent, partially consistent, inconsistent or unidentifiable under the missing-room/source-directivity limitations.

## Prohibited actions

- No D090/D180/D270 solve.
- No room model.
- No geometry redesign, classifier, final-test, print or acquisition.
- No push/tag/release or automatic commit.
- Do not begin P07B.

## Final response format

Lead with `P07A READY FOR FOUR DIRECTIONS`, `P07A EXTERIOR MODEL NOT READY`, or `P07A BLOCKED`. Report formulation, convergence, pilot agreement classification, artifacts/hashes and confirmation that P07B was not started. Stop for user acceptance.
