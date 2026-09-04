# COMSOL Scheme 3A P02 — P05 nominal connected fluid-domain baseline

Date: 2026-08-25  
Disposition: **P02 PASS**  
Scope: nominal S1/P05 internal fluid-domain and sparse toolchain baseline only

The authoritative S1 state was established without using stale note metadata: 0° P05-S01 open; 90°/180°/270° P05-S02/S03/S04 terminated by nominal airtight P10 plugs at 12 mm insertion depth; and the four diagonal slots filled by P09 solid dummies and therefore excluded from the connected fluid domain.

COMSOL 6.4 reconstructed the nominal connected air volume from parameter values rather than importing a plastic STL. The model contains an 18 mm-radius × 9.2 mm central chamber, four r=17–32 mm fixed inner passages, four 56×9.4×6.4 mm P05 air channels, one full 17 mm open outer transition and three 5 mm retained P10-side outer segments. The constructed union volume is 30148.9960 mm³. All analytic/constructed volume and cross-section comparisons have 0% error; all module/fixed interfaces have zero centreline offset and zero gap, with 51.2 mm² shared openings.

The geometry is one acoustic connected component split into 52 deliberate COMSOL domains for stable region and microphone selections. The 28 coordinate-derived named selections were nonempty. Rebuild checks retained 52 full-fluid entities, mic boundary 177 and source boundary 76; the saved model reloaded with the same working operators. `bnd_wall_all` is an audit superset only and is not applied, because it includes internal partitions; COMSOL default Sound Hard handles exterior walls and Continuity handles internal partitions, with explicit Sound Hard at the three P10 terminal selections and Pressure at the open 0° selection.

Coarse mesh: 42,495 elements, 10,170 vertices, minimum/mean quality 0.1336/0.6448, 25 kHz control and at least 4.111 elements across 9.4 mm. Normal mesh: 101,196 elements, 21,834 vertices, minimum/mean quality 0.2019/0.6769, 37.5 kHz control and at least 6.166 elements across. The normal/coarse hmax ratio is 0.667.

The only solve was a sparse, non-calibrating Pressure Acoustics Frequency Domain diagnostic at 500/1000/2000/4000/7000 Hz with `c=343 m/s`, `rho=1.2041 kg/m³`, hard walls and a 1 Pa open-port pressure source. The nominal Ø8.8 mm disk-average microphone pressures were `-0.4626079846`, `-0.02617930855`, `-0.9329848744`, `-2.134930141`, and `+0.1881683785 Pa`, all with explicit zero imaginary components in the lossless model. Values are finite and nonzero as a set; the source average equals 1 Pa within 3.33×10⁻¹⁶ Pa.

The final MPH was saved, removed from memory, reloaded in COMSOL 6.4 and re-evaluated with maximum absolute microphone difference 0 Pa. Final geometry and pressure PNGs are nonempty and decoded. The complete self-contained report, machine-readable geometry/selection/mesh/results files, solver log, both final MPH files, failed-attempt provenance and `SHA256SUMS` are in:

`outputs/simulation/COMSOL_SCHEME_3A/P02_P05_BASELINE/`

P02 disposition: **P02 PASS**. This is a nominal geometry/toolchain baseline, not experiment agreement, calibration, physical loss/Q validation or a Scheme 3A scientific conclusion.

P03 was not started. No HR01–HR08, complete V2.5, U4/S1/S2/S3 array, external field, classifier, calibration, print decision or final-test content was built, solved, read or modified.
