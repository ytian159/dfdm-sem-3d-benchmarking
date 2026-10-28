# Benchmark Details

## Repository Layout

- `external/dfdm_3d_elastic`: DFDM3D solver submodule (the path is retained for compatibility with existing benchmark scripts).
- `external/specfem3d_globe`: public SPECFEM3D_GLOBE submodule.
- `cases/ak135_mrr_hdur80_f0125`: base DFDM TOML, SPECFEM `DATA` files, and case matrix.
- `cases/ak135_mrr_hdur80_f0125/sem_ref_nex320_4800s`: shipped SEM-Ref seismograms for `target_nex75_sem320_4800s`, with the `DATA` that produced them (see its README).
- `scripts/stage_cases.py`: creates repo-relative run directories under `runs/`.
- `scripts/install_sem_reference.py`: installs shipped or on-disk SPECFEM seismograms into a staged case instead of running SPECFEM.
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

A clean run of the staged case on Perlmutter (2026-08-12, `shared_interactive`, 24 ranks at `-c 2`) reproduced it: 2828.8 s solver wall over 33000 steps at 85.5 ms/step, 0.1473 node-hours, against the original run's 2832.7 s and 0.1475. Its seismograms correlate with the original run's at 1.00000 on all 36 N/Z components, and the case passes the gate against the `NEX=96` rung 36/36 with a worst full-trace correlation of 0.99812 and PKP-window correlations of 0.99998. Against the shipped `NEX=320` SEM-Ref it passes 36/36 with a worst full-trace correlation of 0.99843 and PKP-window minima of 0.99993 (Z) and 0.99990 (N).

Two conventions have to match for the number to come out right.

**Cost.** `node_hours = sem_tasks * cpus_per_task / 256 * solver_wall_hours` on Perlmutter CPU nodes (128 physical cores, 256 SMT slots), so a 24-rank run at `-c 2` bills 0.1875 of a node. The wall clock is the solver invocation alone; meshing is excluded for both codes. `scripts/sem_cost.py` implements exactly this and writes `runs/<case>/sem_perf.json`.

The anchor's wall clock is a shared-node wall, and that matters because memory bandwidth is a node-level resource: Slurm dedicates cores to the job, not memory channels. The same 24-rank job on an exclusive node runs about 2.3 times faster (37.9 ms/step against 85.5 shared), which shows both that the solver is memory-bound at this size and that on a busy shared node it gets roughly its proportional share of the channels. Billing an exclusive-node wall at the core fraction would credit the job the whole node's bandwidth while charging 18.75% of the node (0.063 node-hours); billing the whole exclusive node would charge 104 cores the job cannot use (0.337 node-hours). The convention here takes the shared wall as billed: the job pays for the bandwidth it actually got. Run the anchor on shared QOS, and never re-bill an exclusive-node wall at the core fraction.

**Correctness.** All 36 N/Z station-components must reach 0.995 full-trace correlation against the SEM reference at both the 3600 s and 4750 s horizons, with the antipodal PKP window (source shift plus 1100 to 1400 s, stations at 140 degrees and beyond) reported alongside. Traces are baselined over the first 48 s, shifted by the 120 s source shift, and resampled onto a common 0.1 s grid. `scripts/score_sem_members.py` implements this.

Two gotchas are handled in the tooling rather than left to the user: `NEX < 128` writes `MX*` channel names while `NEX >= 128` writes `BX*`, so channels are globbed as `?X`; and the E component is near-nodal for this source-receiver geometry, so the qualification set is N and Z only.

### Time step conventions

The `paper_*` cases take the time step from SPECFEM's own stability estimate: `DT=0.15` is proven stable and accurate through `NEX=192`, and `0.075` at `NEX=256`.

The `pilot_*` and `target_*` cases instead use the PREM-ladder convention `DT = 9.6/NEX` (0.04 at `NEX=256`, 0.03 at `NEX=320`), which sits 4 to 6 times below the stability estimate. It exists for cost comparability within that ladder and makes those SEM arms far more expensive than a correctly sized reference: the pilot bills 2.1 node-hours and the target 27.8 against the anchor's 0.147. Cost ratios quoted from the `pilot_*` or `target_*` cases are not the published ratios.

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

| case | arms | SEM mesh | SEM `DT` | record | layout | SEM cost (solver only) |
|---|---|---|---|---|---|---|
| `paper_sem_nex64_4800s` | SEM | `NEX` 64 | 0.15 | 80 min | 24 ranks, shared node | 0.147 node-h (47 min) |
| `paper_sem_nex96_4800s` | SEM | `NEX` 96 | 0.10 | 80 min | 24 ranks, shared node | 0.503 node-h (2.7 h) |
| `pilot_nex60_sem256_720s` | SEM + DFDM | `NEX` 256 | 0.04 | 10 min | 384 ranks, 3 nodes | 2.1 node-h |
| `target_nex75_sem320_4800s` | SEM + DFDM | `NEX` 320 | 0.03 | 80 min | 384 ranks, 3 nodes | 27.8 node-h |
| `fixture_smoke` | synthetic | n/a | n/a | n/a | n/a | none |

Meshing is on top of these and is not negligible for the large meshes: the `NEX` 256 mesher takes about 26 minutes and writes a 35 GB database, against seconds and a few hundred MB at `NEX` 64.

A case is SEM-only when it declares no `dfdm_*` keys; `scripts/run_dfdm_slurm.sh` refuses such a case and `scripts/run_case_slurm.sh` skips the DFDM stage. Each case carries its own `sem_nproc`, and staging checks the two constraints SPECFEM imposes: `NEX` divisible by `8 * NPROC`, and `sem_tasks` equal to `6 * NPROC^2`.

A case whose SEM seismograms ship with the repository names the set with `sem_reference`; only `target_nex75_sem320_4800s` does.

Each staged case writes a `runs/<case>/case_metadata.json` file. The run wrappers read this metadata through `scripts/case_env.py`, so solver commands do not need hard-coded paths.

Restaging with `--force` refuses to delete a case directory that already holds seismograms, DFDM traces, figures, or score and performance JSON; `--discard-results` overrides that.

## Running the DFDM Comparison Cases

Build DFDM once (`bash scripts/build_dfdm.sh`), then either run everything in one job:

```bash
sbatch -A <account> -C cpu -q regular -t 04:00:00 -N 4 --exclusive \
  --ntasks-per-node=128 scripts/run_case_slurm.sh pilot_nex60_sem256_720s
```

or run the arms separately with `scripts/run_sem_slurm.sh` and `scripts/run_dfdm_slurm.sh` (same sbatch shape, add `--export=ALL,NO_STAGE=1`), then compare finished outputs with:

```bash
bash scripts/compare_case.sh pilot_nex60_sem256_720s
```

For the target case use `-t 48:00:00` and the case name `target_nex75_sem320_4800s`.

The target case's SEM arm ships with the repository, so its DFDM arm can run alone: submit `scripts/run_case_slurm.sh target_nex75_sem320_4800s` with the same sbatch shape plus `--export=ALL,SEM_SEISMOGRAMS=shipped`. The job installs the shipped seismograms, runs DFDM, and compares, and needs no SPECFEM build. When resubmitting after a failed attempt, also export `NO_STAGE=1`; otherwise restaging refuses the case directory because it already holds the installed seismograms.

The `paper_*` cases use a fraction of one node and belong in a shared allocation instead:

```bash
sbatch -A <account> -C cpu -q shared -t 03:00:00 -N 1 -n 24 -c 2 \
  --export=ALL,NO_STAGE=1 scripts/run_sem_slurm.sh paper_sem_nex64_4800s
```

## Options

- `NO_STAGE=1`: do not stage or restage before running a solver wrapper.
- `FORCE_STAGE=1`: restage when using `scripts/run_sem_slurm.sh` or `scripts/run_dfdm_slurm.sh`.
- `SEM_SEISMOGRAMS=shipped`: install the case's shipped SEM seismograms instead of running SPECFEM (read by `scripts/run_sem_slurm.sh`, and so by `scripts/run_case_slurm.sh`). `SEM_SEISMOGRAMS=/path/to/OUTPUT_FILES` installs an earlier run's seismograms from disk instead; the directory needs the run's `DATA` next to it. Either way the installer refuses traces produced by different `DATA` than the case's staged `DATA`, records their source in `runs/<case>/sem_seismograms.json`, and writes no `sem_perf.json`.
- `SPECFEM_ROOT=/path/to/specfem3d_globe`: run-time override for an already-built SPECFEM tree (must contain `bin/xmeshfem3D` and `bin/xspecfem3D`).
- `DFDM_EXE=/path/to/dfdm_elastic3d`: run-time override for an already-built DFDM executable.
- `COMPARE_DT=0.1`: comparison resampling interval in seconds.
- `SKIP_SPHERE_CHECK=1`: run SEM against a build not prepared with `ASSUME_PERFECT_SPHERE`. Only for experiments that deliberately want geocentric station conversion; it invalidates the DFDM comparison.
- `SOURCE_SHIFT=120`: source time shift used by `scripts/compare_sem_members.sh` (1.5 times the half duration; use 60 for an hdur-40 protocol).

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
