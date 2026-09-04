# Copy-paste prompt — P01 simulation contract and provenance freeze

Execute only P01. P00 must already have an accepted PASS report.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

1. Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely.
2. Read the accepted report `docs/progress/COMSOL_3A_P00_MCP_SMOKE_RETRY_02.md`, verify its `P00 PASS` disposition, and inspect/hash-check the artifacts under `outputs/simulation/COMSOL_SCHEME_3A/P00_MCP_SMOKE_RETRY_02/`. The original P00 and `RETRY_01` reports are preserved failure provenance and must not be mistaken for the accepted model or overwritten.
3. Read all repository sources listed in section 8 of the shared context completely.
4. Run `git status --short --branch`, inspect the current branch and working tree, and preserve unrelated modifications.

## Exact task

This phase is an audit/freeze phase. Do not solve a V2.5 acoustic model.

1. Verify the source ZIP hashes against `reference_assets/physical_design/model_packages/README.md`.
2. Inspect the V2 and V2.5 parameter JSON and generator source inside the archives as read-only design provenance.
3. Produce a geometry identity table covering P01, P03 microphone insert, P05, P09, the central chamber, fixed inner/outer passages, and HR01–HR08.
4. Record coordinate systems and the physical mapping:
   - U4SYM: P05 open at 0/90/180/270°, P09 at diagonals;
   - U4HR: HR01/03/05/07 at 0/90/180/270°, P09 at diagonals.
5. Record the user’s latest authoritative provenance clarification: S2 physically used four open P05 modules; the one-open-channel TXT notes are stale. Do not edit raw TXT notes.
6. Create a separate provenance addendum and update only human-readable derived documentation that still describes S2 assembly as awaiting confirmation. Do not rewrite original measurement metadata, frozen analysis JSON, artifact manifests or existing SHA-256 records; cross-reference the addendum instead.
7. Freeze the modelling hierarchy, allowed calibration parameters, experiment–simulation comparison grid, mesh convergence rules, named selections, result expressions and artifact schema.
8. Freeze exact definitions for:
   - port-to-microphone transfer;
   - 4×4 port scattering/coupling matrix;
   - diagonal advantage;
   - normalized off-diagonal energy;
   - resonance centre and drift;
   - module/chamber energy participation;
   - mesh convergence;
   - candidate tolerance success.
9. Distinguish execution acceptance from scientific success so that a valid negative result cannot be discarded.
10. List every geometry or physical fact that remains unverified. If any fact blocks P02, say so precisely.

## Outputs

Create:

- `docs/progress/COMSOL_3A_P01_SIMULATION_CONTRACT.md`
- `docs/progress/V25_S2_OPEN_CHANNEL_PROVENANCE_ADDENDUM.md`
- `outputs/simulation/COMSOL_SCHEME_3A/P01_CONTRACT/simulation_contract.json`
- `outputs/simulation/COMSOL_SCHEME_3A/P01_CONTRACT/input_manifest.csv`
- `outputs/simulation/COMSOL_SCHEME_3A/P01_CONTRACT/SHA256SUMS`

If a minimal helper script is required to inspect archive parameters or generate manifests, write a small test first. Do not create an acoustics solver script in this phase.

## Acceptance gate

- All source identities and hashes are traceable.
- S1 single-campaign 5-of-6 and S2/S3 3-of-4 rules are recorded correctly.
- S2 physical four-open identity is no longer described as unconfirmed in newly authoritative derived documentation.
- Raw notes remain byte-identical.
- Fluid-domain reconstruction is separated from plastic solid geometry.
- Exact metric formulas and numerical gates are frozen prospectively.
- No final-test or unrelated data are read.
- The contract states whether P02 is ready or blocked.

## Prohibited actions

- No V2.5 acoustic solve.
- No classifier.
- No threshold tuning from simulation output.
- No new acquisition or print design.
- No raw-data edits.
- No push/tag/release and no automatic commit.
- Do not begin P02.

## Final response format

Lead with `P01 READY FOR ACCEPTANCE` or `P01 BLOCKED`. Summarize verified identities, S2 provenance correction, frozen metric definitions, remaining unknowns, exact artifacts, and confirm P02 was not started. Stop for user review.
