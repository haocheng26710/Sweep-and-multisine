# Copy-paste prompt — P08 fixed-frequency mode and energy attribution

Execute only P08 after the user accepts P07B. If P07B is blocked but P06 is valid, ask the user before performing an internal-only P08; do not assume authorization.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely, then read the simulation contract and accepted P03/P05/P06/P07 reports/models. Verify hashes. Inspect git status and preserve unrelated work.

## Exact task

Attribute the accepted baseline responses at a fixed, predeclared frequency set:

- accepted single-entry centres for HR01/03/05/07;
- `1623.27 Hz`;
- `2198.33 Hz`;
- `3973.94 Hz`;
- `6493.09 Hz`;
- any additional exact frequencies already frozen in P01, and no others.

For U4SYM and U4HR:

1. Export pressure magnitude and phase fields for each active-port excitation and, where accepted, each external direction.
2. Compute volume-integrated acoustic energy or the P01-frozen proxy separately for:
   - each active module cavity/neck region;
   - fixed radial passages;
   - central shared chamber;
   - microphone coupling region;
   - exterior domain only when meaningful.
3. Compute normalized simulated energy participation and port-to-port transfer at every fixed frequency.
4. Use eigenfrequency/mode analysis only as a supplementary attribution tool if damping and boundary conditions make the relation defensible. Do not force a one-to-one eigenmode label onto a broad driven response.
5. Classify each feature as predominantly localized, shared/common-chamber, mixed or numerically unresolved using P01-frozen definitions.
6. Compare the classifications with the measured clues: HR-specific 1.62/6.49 kHz and shared 2.20/3.97 kHz.
7. Clearly state that simulated energy participation is not an experimental causal contribution percentage.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P08_MODE_ENERGY/`

Create:

- fixed-frequency energy-participation CSV;
- feature attribution table CSV;
- port/direction field manifest;
- pressure/phase/energy PNG/SVG figures;
- any supplementary eigenmode table with explicit limitations;
- solver and expression audit log;
- SHA-256 manifest;
- `docs/progress/COMSOL_3A_P08_MODE_ENERGY_ATTRIBUTION.md`.

## Acceptance gate

- Every result uses the fixed frequency set.
- Domain integrals are fully labelled and reproducible.
- Energy normalization and units are explicit.
- Field maps and numeric integrals agree qualitatively.
- No frequency bins are treated as independent statistical samples.
- Attributions include an unresolved category and are not forced.
- The report gives a bounded answer to whether the common chamber reorganizes the isolated code.

## Prohibited actions

- No new frequency search, classifier, causal percentage claim, geometry modification, final-test, print or acquisition.
- No push/tag/release or automatic commit.
- Do not begin P09A.

## Final response format

Lead with the strongest supported mechanism statement and its confidence boundary. List feature classifications, numeric energy evidence, experiment correspondence, artifacts/hashes and confirmation that P09A was not started. Stop for acceptance.
