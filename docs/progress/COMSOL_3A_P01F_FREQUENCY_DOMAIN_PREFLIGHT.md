# P01F FREQUENCY PREFLIGHT PASS

Date: 2026-08-25  
Scope: restarted-MCP COMSOL 6.4 Frequency-Domain preflight only

## Disposition

P01F passed. This is a one-time MCP Frequency-Domain compatibility and integration test using a simple air tube. It is not P02, not a P05/HR/V2.5 simulation, not a scientific result, and not an experiment-simulation agreement test.

## Runtime and model identity

- Repaired MCP server restarted and the new Frequency/plist, complex-result, Average-operator and named-selection paths were visible to the client.
- COMSOL 6.4 local server session, 16 cores, initial model count 0.
- Model: `P01F_FREQ_TUBE`; `comp1`; 3D `geom1`; one `0.1 x 0.02 x 0.02 m` connected air block.
- Medium readback: `c_mat=userdef`, `c=343[m/s]`, `rho_mat=userdef`, `rho=1.2041[kg/m^3]`.
- Pressure Acoustics tag `acpr`.

The first unsolved selection attempt demonstrated that an `intersects` box at an end face also captures adjacent long walls. That model was removed from memory, the model list was verified empty, and the accepted model was rebuilt using corrected coordinate rules. No numeric boundary ID was guessed.

## Stable selections, boundaries and operator

| Tag | Coordinate/geometric rule | Entities | Use |
|---|---|---:|---|
| `sel_fluid_all` | Box/inside over full tube | domain `[1]` | unique air domain |
| `bnd_source` | Box/inside around `x=0` | boundary `[1]` | Pressure |
| `bnd_mic` | Box/inside around `x=0.1 m` | boundary `[6]` | Average probe |
| `bnd_wall_all` | Box/intersects with `x>=1e-5 m` | boundaries `[2,3,4,5,6]` | SoundHard |

- `pres_source`: Pressure bound to `bnd_source`; `p0=1[Pa]` read back.
- `hard_walls`: SoundHard bound to `bnd_wall_all`.
- `aveop_mic`: Average bound to `bnd_mic`; `aveop_mic(acpr.p_t)` evaluated before and after reload.

## Frequency study, mesh and license-backed solve

- Study/step stable tags: `std_freq/step1`.
- COMSOL Java feature type: `Frequency`.
- Requested, written and pre-solve-read-back plist: `500 1000 2000`.
- Solve method: stable `java_tag`; actual three-frequency solution completed.
- License evidence: the required Pressure Acoustics/Frequency Domain capability checked out on demand and completed the solve. The MCP does not expose a complete product checkout list.
- Mesh: physics controlled; control parameter `Frequency`; maximum frequency `2000[Hz]`; `autoMeshSize(6)`.
- Mesh statistics: 196 elements, 78 vertices, minimum quality 0.4574, mean quality 0.6859.

## Complex pressure results

Expression: `aveop_mic(acpr.p_t)`, unit Pa. Real and imaginary parts are the authoritative values; magnitude and phase are derived. The lossless model produced zero imaginary parts, which were retained explicitly rather than discarded.

| Frequency Hz | Real Pa | Imag Pa | Magnitude Pa | Phase deg |
|---:|---:|---:|---:|---:|
| 500 | 1.6418630270578525 | 0 | 1.6418630270578525 | 0 |
| 1000 | -3.8747721638555457 | 0 | 3.8747721638555457 | 180 |
| 2000 | -1.1536410773112789 | 0 | 1.1536410773112789 | 180 |

The frequency axis contains exactly three points and matches the plist. All numeric components are finite, values are not all zero, and the complete response is serializable by standard JSON.

## PNG, save and reload

- Accepted plot: stable tags `pg_pressure_2000_verified/surf_pressure_2000`, expression `abs(acpr.p_t)`, active final solved frequency 2000 Hz.
- `pressure_field_2000hz.png`: 57,749 bytes; nonempty and decoded successfully.
- Saved `p01f_frequency_domain_preflight.mph`: 1,579,951 bytes.
- Removed the model from memory and verified model count 0, then reloaded the saved MPH in COMSOL 6.4.
- Reload checks passed for `comp1`, `geom1`, `mesh1`, `acpr`, Pressure/SoundHard features, `std_freq/step1`, all four named selections, `aveop_mic`, solution, plots and exports.
- Reloaded `step1` remained Java type `Frequency` with plist `500 1000 2000`.
- Re-evaluated all three frequencies after reload. Maximum absolute difference was `0 Pa`, passing the frozen absolute tolerance `1e-12 Pa`.

Two pre-existing/localization helper defects were observed and preserved in the tool log: `model_list_components` uses the COMSOL 6.4-incompatible `get(int)` overload, and `geometry_list_features` expects a display label rather than stable tag `geom1`. Stable-tag mesh, physics, study, solve, expression and reload paths independently verified the required nodes, so these helpers did not affect P01F acceptance.

## Tests and acceptance

| Gate | Result |
|---|---|
| Red -> green regression evidence | PASS |
| P01F tests | PASS — 18/18 |
| Related regression tests | PASS — 29/29 |
| `compileall src tests` | PASS |
| `git diff --check` | PASS |
| Fresh COMSOL 6.4 session / empty list | PASS |
| Frequency type and plist readback | PASS |
| Named selections, Pressure, SoundHard, Average | PASS |
| License-backed three-frequency solve | PASS |
| Complete complex JSON-safe results | PASS |
| Nonempty decodable 3D Surface PNG | PASS |
| MPH removal/reload and result equality | PASS |
| Final artifacts and SHA-256 manifest | PASS |

The one full-pytest attempt exited during collection and was not repeated. The basic test file was isolated as 7 passes plus the known unrelated Windows/POSIX `test_generate_version_path` assertion failure.

## Artifact hashes

The final `SHA256SUMS.txt` is the authority for every deliverable, including this report. To avoid recursive self-hashing, this report lists the hashes of the non-report artifacts after final write; its own hash appears only in the manifest.

| Artifact | SHA-256 |
|---|---|
| `p01f_frequency_domain_preflight.mph` | `6c00e476d4dbffe9477d7bdecd61866bf5ec26d150d26ee15f5fed1cff2d7fd8` |
| `frequency_results.json` | `bcbfaa4625107b6455a3d4ba3c856ad2cdb3ad7a3ad51803adbc1eda838d120d` |
| `frequency_results.csv` | `eb16ac1633dbba3c5e09bb84efedafb5c941df078343e5368df61b7c6d20ab48` |
| `pressure_field_2000hz.png` | `ad63d7904d80509bc6518e9f46374d80ed5e898b6d92088dc06ca5dd5d977c1d` |
| `mesh_and_model_readback.json` | `7f8296895f3c6f26b09906b4e69045e6a86f2ef479968570f400e12abca7e418` |
| `tool_session_license_log.txt` | `ee03b565b91bcee77e8464e61d18bb4844cc2d3f0768be57e91e72ae6f82824b` |
| `test_summary.txt` | `43cfeaaf49cb108c5ac314c640d4b7535f83fa26c2504befe4f634bb5aa92bc6` |

## Scope guard

P02 was not started. No P05, HR, V2.5 or array model was built or solved. No final-test content was read. No experimental data, research schema, thresholds or scientific conclusions were modified. No reset, checkout, clean, stash, commit, push, tag or release was performed. Existing user modifications in both repositories were preserved.

No later phase was started.
