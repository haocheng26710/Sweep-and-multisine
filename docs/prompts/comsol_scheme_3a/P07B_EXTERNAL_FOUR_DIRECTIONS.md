# Copy-paste prompt — P07B frozen four-direction external comparison

Execute only P07B after the user accepts P07A as ready.

Workspace root:

`D:\Bristol course\dissertation\program work`

## Required context

Read `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md` completely and read all accepted P01, P06 and P07A artifacts. Verify frozen model/config hashes. Inspect git status and preserve unrelated changes.

## Exact task

Using the accepted P07A formulation without retuning, compute U4SYM and U4HR for:

- D000;
- D090;
- D180;
- D270.

1. Change only the source direction/device rotation parameter defined in the contract.
2. Preserve the 0.8 m source representation, exterior domain, PML, mesh rule, internal physics and normalization.
3. Run the P01-frozen frequency grid. Development may use the already frozen sparse/pilot grid, but final tables for experiment comparison must use the contract’s compatible output grid or an explicitly documented interpolation that does not create extra FEM information.
4. Export per direction/configuration:
   - incident-normalized microphone transfer;
   - demeaned spectrum;
   - fixed target-window effects;
   - fixed exploratory-frequency values;
   - U4HR−U4SYM differences.
5. Compare simulated and measured direction patterns using fixed-window sign consistency, Pearson, Spearman and cosine similarity.
6. Use directions and experimental repeats as uncertainty/replication units where applicable. Do not treat frequency bins as independent samples.
7. Do not optimize or report a new classifier.
8. Decide whether existing data/model support:
   - internal code loss;
   - external angular-gating weakness;
   - both;
   - or an unidentifiable mixture.

## Outputs

Use:

`outputs/simulation/COMSOL_SCHEME_3A/P07B_EXTERNAL_4DIR/`

Create:

- parametric four-direction models/configs;
- direction/configuration spectra CSV;
- fixed-window comparison CSV;
- simulated-vs-measured correspondence CSV;
- direction figures and HET−HOM figures;
- numerical sensitivity/solver log;
- SHA-256 manifest;
- `docs/progress/COMSOL_3A_P07B_EXTERNAL_FOUR_DIRECTIONS.md`.

## Acceptance gate

- Only the frozen direction parameter changes across directions.
- All eight configuration×direction cases solve with accepted convergence.
- Direction labels and module mappings are correct and auditable.
- Comparisons use only predeclared grids/windows/frequencies.
- Simulation agreement and missing-room/source limitations are separated.
- Results do not claim cross-day or cross-assembly classifier generalization.

## Prohibited actions

- No room fitting or empirical direction-specific correction.
- No adaptive frequency selection.
- No classifier, final-test, geometry redesign, print or acquisition.
- No push/tag/release or automatic commit.
- Do not begin P08 or P09.

## Final response format

Lead with the execution status and one of the four mechanism classifications. Give the most important fixed-window/direction correspondences, exact limitations, artifacts/hashes and confirmation that no later phase was started. Stop for user acceptance.
