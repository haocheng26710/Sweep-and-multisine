# COMSOL 3A P04E — HR03 single-entry chamber ablation

## Terminal classification

`P04E PARTIAL RESTORATION`

The tracked cavity branch moves monotonically from `1651.415285 Hz` through `1684.694190 Hz` to `1749.399436 Hz` as the retained central-chamber fraction decreases from 100% to 75% to 50%. The total shift is `0.083156771 octave`, just below the frozen `1/12 = 0.083333333 octave` restoration gate by `0.000176563 octave`. This is partial restoration, not full restoration-trend support.

## Frozen geometry and provenance

- Achieved fractions are exactly `100.000000%`, `75.000000%`, and `50.000000%` under the deterministic analytic geometry definition.
- Corridor widths are `36.0 mm` for the unmodified-cylinder representation, `13.4233374414 mm`, and `8.0316557506 mm`; the central well is `Ø9.0 mm`.
- Every fixed-channel opening remains `8.0 × 9.2 = 73.6 mm²`.
- P04B HR03 authority SHA-256 is `33bf573dddc0c0b163e7f0a5e177fc227d16aa541479606e971cb4a3a9398db7`.
- Frozen P04E contract SHA-256 is `2a4f9744319fea6378ab1247d7a885983eff0ed7b40ce7bbd1af46cb941c2a12`.
- P04B-N and P04C SHA manifests passed completely. `final_test_read=false`.

## Geometry, mesh, and solver gates

All states retained one connected 56-domain air component, all four fixed-channel paths to the central well, the HR03-to-microphone path, stable nonempty named selections, unchanged HR03 leaf-region measures, one source boundary, one microphone boundary, no isolated air component, and no domain below the frozen `1e-12 m³` sliver threshold. Geometry, selections, and mesh were saved, removed, and reloaded before any P04E acoustic study. Solved results were also equal after save/remove/reload.

One Pressure Acoustics + nominal BLI screening mesh was used per state, automatic level 6 with 2100 Hz control:

- 100%: `31,381` elements, `8,058` vertices, minimum/mean quality `0.1376 / 0.5968`.
- 75%: `31,457` elements, `8,122` vertices, minimum/mean quality `0.1376 / 0.5995`.
- 50%: `731,519` elements, `148,452` vertices, minimum/mean quality `0.01826 / 0.6134`.

No second mesh was run and no mesh-convergence claim is made. All three frozen 31-point studies completed in real COMSOL 6.4.

## Peak and branch evidence

Every strict cavity-energy interior peak on the regular 1400–2100 Hz grid is recorded in `peak_inventory.csv`; landmarks were excluded. The P04C ~1650.40 Hz branch was tracked by log-frequency, cavity/module participation, kinetic fraction, and cavity–chamber phase, never by nearest-to-1904 selection. Assignment was unique with no mode split or branch ambiguity.

Signed octave offsets versus the P04C `1650.401492 Hz` reference are `+0.000886`, `+0.029670`, and `+0.084043`. Offsets versus isolated full-TV `1904.194227 Hz` are `-0.205478`, `-0.176694`, and `-0.122321`.

Cavity/module participation at the sampled tracked peaks decreases `0.593729 → 0.577896 → 0.556837`, while the cavity remains the largest of the three HR03 leaf regions. Cavity–chamber phase changes `174.318° → 172.191° → 171.712°`; it remains near antiphase rather than showing complete decoupling. Chamber/whole-fluid participation at those points increases `0.064232 → 0.094929 → 0.105034`, so the phase/participation evidence does not support complete removal of the shared mode.

Microphone transfer magnitude at the sampled tracked peaks is `5.07188`, `5.97686`, and `6.67137`, finite and nonzero. Relative insertion-loss change at the same sampled frequencies is `0.000`, `-5.858`, and `-18.737 dB`. At the old `1646.8836 Hz` landmark, the 50% state incurs `+7.539 dB` because the branch has moved; at `1986.9725 Hz` it changes by `-7.582 dB`. This is frequency redistribution, not broadband microphone collapse.

## Decision boundary

The intervention gives a clear monotonic design direction but narrowly misses the complete restoration threshold. It is an exploratory design clue only. Per the frozen gate, no printable insert is designed now. No fourth volume, P05, P06, U4, full-TV S1, PA–TV repair, external-field work, classifier, final-test read, or STL generation was started. Stop and wait for user acceptance.
