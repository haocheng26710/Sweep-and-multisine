# Copy-paste prompt — P02 P05 baseline fluid-domain model

Execute only P02 after the user accepts P01.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read completely:

- `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md`
- `docs/progress/COMSOL_3A_P01_SIMULATION_CONTRACT.md`
- `outputs/simulation/COMSOL_SCHEME_3A/P01_CONTRACT/simulation_contract.json`
- the P01 provenance addendum and manifest.

Inspect git status and preserve unrelated changes.

## Exact task

Build and verify only the P05/S1 baseline connected fluid domain. Do not build an HR module or full U4 array.

1. Determine the exact S1 baseline physical state from authoritative acquisition/design records. Do not guess which unused ports are sealed by P09, P10 or another blocker.
2. Reconstruct the connected air domain parametrically from source dimensions. Do not treat the exterior plastic STL surface as an already valid fluid domain.
3. Include only the fluid regions required by the frozen P01 contract, including the relevant P05 passage, fixed inner/outer passage, central chamber portion and microphone sampling region.
4. Use stable named selections for inlet, all rigid walls, interfaces, chamber subdomain and microphone evaluation region.
5. Verify units, connected components, volumes, cross-sections, interface alignment and absence of sliver domains.
6. Create coarse and normal meshes suitable for a preliminary Pressure Acoustics check.
7. Run only a sparse non-calibrating frequency-domain diagnostic sufficient to show that sources, boundaries, datasets and microphone evaluation work. Do not fit experimental curves.
8. Save geometry and mesh inspection images, volume/entity tables, sparse transfer output and the `.mph` model.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P02_P05_BASELINE/`

Create:

- `COMSOL_3A_P02_P05_BASELINE.mph`
- geometry/selection/volume JSON or CSV;
- sparse diagnostic transfer CSV;
- geometry and mesh PNGs;
- solver log and SHA-256 manifest;
- `docs/progress/COMSOL_3A_P02_P05_BASELINE.md`.

## Acceptance gate

- Exactly one intended connected acoustic domain, unless the contract explicitly requires multiple coupled domains.
- No unintended opening at a blocked port.
- Module/fixed-passage interfaces align without gaps or overlaps beyond the frozen tolerance.
- Analytic source dimensions and COMSOL volumes/cross-sections agree within 1% where an analytic value exists.
- Named selections survive a geometry rebuild.
- Sparse solve completes and returns finite microphone pressure/transfer values.
- The report clearly identifies simplifications and does not claim experiment agreement.

If the S1 baseline assembly cannot be established, or the fluid domain cannot be made watertight without guessing, stop with an exact blocker and do not proceed.

## Prohibited actions

- No HR geometry.
- No parameter fitting.
- No full 200–8000 Hz production sweep.
- No external air/room model.
- No final-test, classifier, new print or acquisition.
- No push/tag/release and no automatic commit.
- Do not begin P03.

## Final response format

Lead with `P02 PASS`, `P02 PASS WITH LIMITATIONS`, or `P02 BLOCKED`. Report geometry identity, volume/dimension checks, selection stability, sparse-solve status, artifact paths/hashes and confirmation that P03 was not started. Stop for user acceptance.

