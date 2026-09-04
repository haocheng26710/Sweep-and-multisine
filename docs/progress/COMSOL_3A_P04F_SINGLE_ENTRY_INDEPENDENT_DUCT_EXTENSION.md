# P04F RETRY_01 — single-entry independent duct extension

## Scientific classification

`NO_USEFUL_IMPROVEMENT`

The earlier aborted state is corrected to `P04F PRESTART BLOCKED_BY_MCP`; it was pre-start, non-scientific, and consumed no formal P04F attempt. RETRY_01 used a fresh accepted COMSOL 6.4 server, loaded the saved P04E 100% MPH by verified SHA-256, reused its 0 mm solution, and performed exactly one formal solve for each of 5 and 10 mm.

## Tracked result

| Extension | Refined peak (Hz) | Shift vs 0 (oct) | Target distance (oct) | Chamber/fluid | Cavity/module | Mic peak-to-peak (dB) | Q |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1651.415285 | 0.000000 | 0.205478 | 0.064232 | 0.593729 | 0.000 | 38.204 |
| 5 | 1651.221629 | -0.000169 | 0.205647 | 0.071767 | 0.593917 | 0.206 | 37.639 |
| 10 | 1652.658144 | 0.001085 | 0.204392 | 0.080409 | 0.593024 | 0.304 | 35.069 |

The 10 mm state does not move away from the 1904.194 Hz isolated full-TV target, but the sequence is not monotonic because 5 mm first moves slightly away. The 10 mm shift is far below 1/12 octave, and chamber participation rises rather than falling to 80% or less of baseline. The branch is unique under the frozen continuity-cost margin rule. Geometry, mesh, solve, save, and reload gates all passed.

## Engineering audit

- 5 mm: 41,092 elements; minimum quality 0.1376; analytic minimum clearance 8.149 mm or greater by relevant pair.
- 10 mm: 41,621 elements; minimum quality 0.1376; analytic minimum clearance 2.546 mm.
- Both: one connected air system, independent ducts before the prescribed mixing plane, common chamber after it, no domain below 1e-12 m³, and all required selections non-empty.
- `final_test_read=false`; P05/P06/U4/STL were not started; no commit, push, tag, or release was performed.
