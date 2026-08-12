# Benchmark Details

## Repository Layout

- `external/dfdm_3d_elastic`: DFDM3D solver submodule (the path is retained for compatibility with existing benchmark scripts).
- `external/specfem3d_globe`: public SPECFEM3D_GLOBE submodule.
- `cases/ak135_mrr_hdur80_f0125`: base DFDM TOML, SPECFEM `DATA` files, and case matrix.
- `scripts/stage_cases.py`: creates repo-relative run directories under `runs/`.
- `scripts/prepare_specfem.sh`: sets the required `ASSUME_PERFECT_SPHERE` build constant.
- `scripts/run_sem_slurm.sh`: runs only SPECFEM mesher and solver for a staged case, then reports cost.
- `scripts/run_dfdm_slurm.sh`: runs only DFDM for a staged case.
- `scripts/sem_cost.py`: node-hour accounting in the published convention.
- `scripts/score_sem_members.py`: scores one SEM member against a SEM reference on the published gate.
- `scripts/compare_sem_members.sh`: the same, addressed by staged case name.
- `scripts/compare_case.sh`: regenerates figures and metrics from existing SEM and DFDM outputs.
- `scripts/run_case_slurm.sh`: stages a case, runs SEM, runs DFDM, then compares.
- `scripts/plot_sem_dfdm.py`: generates SEM/DFDM Z overlay, difference, combined, and metrics outputs.
- `scripts/validate_smoke.sh`: clone-clean smoke test using deterministic synthetic traces.

## Reproducing Published Numbers

The published hdur-80 SEM cost anchor is `NEX=64`, `DT=0.15`, 4800-second records on 24 ranks, billed at 0.147 node-hours. It is staged by the `paper_sem_nex64_4800s` case, whose `DATA` directory is byte-identical to the campaign run that produced that number.

Two conventions have to match for the number to come out right.

**Cost.** `node_hours = sem_tasks * cpus_per_task / 256 * solver_wall_hours` on Perlmutter CPU nodes (128 physical cores, 256 SMT slots), so a 24-rank run at `-c 2` bills 0.1875 of a node. The wall clock is the solver invocation alone; meshing is excluded for both codes. `scripts/sem_cost.py` implements exactly this and writes `runs/<case>/sem_perf.json`.

**Correctness.** All 36 N/Z station-components must reach 0.995 full-trace correlation against the SEM reference at both the 3600 s and 4750 s horizons, with the antipodal PKP window (source shift plus 1100 to 1400 s, stations at 140 degrees and beyond) reported alongside. Traces are baselined over the first 48 s, shifted by the 120 s source shift, and resampled onto a common 0.1 s grid. `scripts/score_sem_members.py` implements this.

Two gotchas are handled in the tooling rather than left to the user: `NEX < 128` writes `MX*` channel names while `NEX >= 128` writes `BX*`, so channels are globbed as `?X`; and the E component is near-nodal for this source-receiver geometry, so the qualification set is N and Z only.

### Time step conventions

The `paper_*` cases take the time step from SPECFEM's own stability estimate: `DT=0.15` is proven stable and accurate through `NEX=192`, and `0.075` at `NEX=256`.

The `pilot_*` and `target_*` cases instead use the PREM-ladder convention `DT = 9.6/NEX` (0.04 at `NEX=256`, 0.03 at `NEX=320`), which sits 4 to 6 times below the stability estimate. It exists for cost comparability within that ladder and makes those SEM arms far more expensive than a correctly sized reference: the pilot bills about 3.4 node-hours against the anchor's 0.147. Cost ratios quoted from the `pilot_*` or `target_*` cases are not the published ratios.

### The perfect-sphere build constant

`ASSUME_PERFECT_SPHERE = .true.` is a compile-time constant in `setup/constants.h.in`, applied by `scripts/prepare_specfem.sh` before the build and verified at run time by `scripts/run_sem_slurm.sh`. Without it SPECFEM converts source and station latitudes to geocentric, displacing stations by up to about 0.19 degrees relative to DFDM, and the nominal epicentral distances of 10, 20, ... degrees no longer hold. The published runs used it; a stock build does not.

## Submodules

The public SPECFEM submodule tracks `SPECFEM/specfem3d_globe` branch `master`.

The DFDM submodule tracks `ytian159/DFDM3D` branch `main`. The pinned milestone includes the consolidated global solver, PPW-control source, automesh tooling, benchmark harness, and permanent correctness gates. It retains the fixed axis kernels, full-shell radial `nez` decoupling, hat-face projection, and benchmark validation utilities required by this repository.

`scripts/prepare_dfdm.sh` updates the DFDM submodule and verifies these source markers before the DFDM build:

- `src/axis_kernels_fixed.h`
- `mesh3d.full_shell_nez_decoupled` support in `src/config_toml3d.cpp`
- `hat_l2_projection_matrix` in `src/elastic3d.cpp`

## Case Matrix

The case definitions live in `cases/ak135_mrr_hdur80_f0125/case_matrix.json`.

- `fixture_smoke`: small synthetic fixture for smoke validation only.
- `paper_sem_nex64_4800s`: SEM-only, the published 0.147 node-hour cost anchor.
- `paper_sem_nex96_4800s`: SEM-only, the convergence rung certifying that anchor (0.503 node-hours).
- `pilot_nex60_sem256_720s`: DFDM NEX60/NEZ30 against SPECFEM NEX256 for 10 record minutes.
- `target_nex75_sem320_4800s`: DFDM NEX75/NEZ30 against SPECFEM NEX320 for 80 record minutes.

A case is SEM-only when it declares no `dfdm_*` keys; `scripts/run_dfdm_slurm.sh` refuses such a case and `scripts/run_case_slurm.sh` skips the DFDM stage. Each case carries its own `sem_nproc`, and staging checks the two constraints SPECFEM imposes: `NEX` divisible by `8 * NPROC`, and `sem_tasks` equal to `6 * NPROC^2`.

Each staged case writes a `runs/<case>/case_metadata.json` file. The run wrappers read this metadata through `scripts/case_env.py`, so solver commands do not need hard-coded paths.

Restaging with `--force` refuses to delete a case directory that already holds seismograms, DFDM traces, figures, or score and performance JSON; `--discard-results` overrides that.

## Staged Run Tree

`scripts/stage_cases.py` creates:

- `runs/<case>/sem_case/DATA`: SPECFEM input files.
- `runs/<case>/dfdm_ak135_mrr_hdur80_refined.toml`: DFDM input file with repo-relative output path.
- `runs/<case>/case_metadata.json`: paths and case parameters consumed by plotting and run scripts.

## Solver Outputs

SPECFEM writes receiver traces under:

```text
runs/<case>/sem_case/OUTPUT_FILES/DF.AZ*.?X*.sem.ascii
```

The channel band code is `MX` for `NEX < 128` and `BX` for `NEX >= 128`.

DFDM writes receiver traces under:

```text
runs/<case>/DFDM_OUTPUT_*/Uxyz_dfdm3d_geo_AZ*_nex*_N*.txt
```

## Comparison Outputs

`scripts/compare_case.sh <case>` writes:

- `runs/<case>/resolved_ppw_sem_dfdm_Z.png`
- `runs/<case>/resolved_ppw_sem_dfdm_diff_Z.png`
- `runs/<case>/resolved_ppw_sem_dfdm_compare_diff_Z.png`
- `runs/<case>/resolved_ppw_sem_dfdm_metrics.md`
- `runs/<case>/comparison_paths.txt`

The metrics table reports per-station correlation alongside the RMS difference and peak ratio. Stations whose first arrival falls outside the record carry no signal, so their ratios compare noise with noise; in the 10-minute pilot this affects every station beyond about 80 degrees.

`scripts/compare_sem_members.sh <test_case> <ref_case>` writes:

- `runs/<test_case>/sem_member_score_vs_<ref_case>.json`
- `runs/<test_case>/sem_member_score_vs_<ref_case>.png`

`scripts/run_sem_slurm.sh` writes `runs/<case>/sem_perf.json` at the end of every SEM run.
