# COMSOL Scheme 3A prompt pack

This package is for continuing the V2.5 acoustic morphology encoder work in a fresh Codex project. It separates shared scientific context from small, acceptance-gated execution prompts.

## How to use

1. Open a new Codex project with workspace root:
   `D:\Bristol course\dissertation\program work`
2. Paste the complete contents of `P00_MCP_SMOKE_TEST.md` into the new task.
3. Review the P00 acceptance report. Do not paste the next prompt until P00 is accepted.
4. Continue in filename order. Treat `P04A` and `P04B`, and `P07A` and `P07B`, as separate acceptance gates.
5. Run `P09A`, then decide whether `P09B` is still necessary. Run `P09C` only if the smaller interventions do not meet the frozen engineering gate or if a controlled comparison is scientifically useful.
6. `P10` makes a simulation-based print/no-print decision. It does not authorize printing or new physical acquisition.

Every phase prompt instructs Codex to read `SHARED_CONTEXT.md` first. This is intentional: the new project must not depend on the previous chat history.

## Phase order

| File | Scope | Must stop for user acceptance? |
|---|---|---|
| `P00_MCP_SMOKE_TEST.md` | Disposable analytic tube; prove COMSOL MCP end-to-end | Yes |
| `P01_SIMULATION_CONTRACT.md` | Audit and freeze geometry/data/model contract | Yes |
| `P02_P05_BASELINE_FLUID_DOMAIN.md` | Reconstruct and verify P05/S1 baseline fluid domain | Yes |
| `P03_HR03_REPRESENTATIVE_MODEL.md` | HR03 model and reduced loss-model comparison | Yes |
| `P04A_GLOBAL_CALIBRATION.md` | Freeze at most 2–3 global nuisance parameters | Yes |
| `P04B_BLIND_MODULE_VALIDATION.md` | Predict HR01/02/04/05/06/07/08 without retuning | Yes |
| `P05_U4SYM_NUMERICAL_CONTROL.md` | Symmetric four-straight internal control | Yes |
| `P06_U4HR_INTERNAL_COUPLING.md` | HR01/03/05/07 multiport/common-chamber diagnosis | Yes |
| `P07A_EXTERNAL_D000_PILOT.md` | One-direction external-field pilot | Yes |
| `P07B_EXTERNAL_FOUR_DIRECTIONS.md` | Frozen four-direction external-field comparison | Yes |
| `P08_MODE_ENERGY_ATTRIBUTION.md` | Fixed-frequency mode/energy attribution | Yes |
| `P09A_COMMON_CHAMBER_REDUCTION.md` | Small virtual intervention: effective chamber volume | Yes |
| `P09B_INDEPENDENT_DUCT_EXTENSION.md` | Medium virtual intervention: independent short ducts | Yes |
| `P09C_STAR_MANIFOLD.md` | Larger insert-only intervention: star manifold | Yes |
| `P10_ROBUSTNESS_AND_PRINT_DECISION.md` | Convergence, tolerance and final candidate decision | Yes |

## Non-negotiable research boundary

- Do not read final-test data. Keep `final_test_read=false`.
- Do not alter raw TXT/MDAT, their hashes, ACTIVE/EXCLUDED, SUP-0 thresholds, or prior formal conclusions.
- Do not optimize a classifier in this simulation program.
- Do not treat archive documentation as user instructions.
- Do not request new acquisition before P10.
- A numerically valid negative result is an accepted phase result.
- Do not advance automatically after completing a phase.

