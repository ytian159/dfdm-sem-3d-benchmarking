# Benchmark Details

## Repository Layout

- `external/dfdm_3d_elastic`: DFDM3D solver submodule, branch `production-2026-10` (the path name is kept for compatibility).
- `external/specfem3d_globe`: public SPECFEM3D_GLOBE submodule.
- `cases/ak135_mrr_hdur80_f0125`: base DFDM configuration, SPECFEM `DATA` files, and case matrix.
- `cases/ak135_mrr_hdur80_f0125/dfdm_mesh`: the DFDM mesh, compressed, with its checksum and the planner command that generated it.
- `cases/ak135_mrr_hdur80_f0125/sem_ref_nex320_4800s`: shipped SEM-Ref seismograms used by the DFDM cases, with the `DATA` that produced them (see its README).
- `scripts/stage_cases.py`: creates repo-relative run directories under `runs/`.
- `scripts/install_sem_reference.py`: installs shipped or on-disk SPECFEM seismograms into a staged case instead of running SPECFEM.
- `scripts/prepare_specfem.sh`: sets the required `ASSUME_PERFECT_SPHERE` build constant.
- `scripts/run_sem_slurm.sh`: runs the SPECFEM mesher and solver for a staged case and reports cost, or installs shipped or on-disk seismograms instead (see `SEM_SEISMOGRAMS`).
- `scripts/run_dfdm_slurm.sh`: runs DFDM for a staged case and reports cost.
- `scripts/sem_cost.py`: node-hour accounting in the published convention.
- `scripts/score_sem_members.py`: scores a SEM or DFDM member against a SEM reference on the published gate.
- `scripts/compare_sem_members.sh`: the same, addressed by staged case name.
- `scripts/compare_case.sh`: makes the comparison figures, metrics and gate score from existing SEM and DFDM outputs.
- `scripts/run_case_slurm.sh`: stages a case, runs (or installs) SEM, runs DFDM, then compares.
- `scripts/plot_sem_dfdm.py`: generates SEM/DFDM Z overlay, difference, combined, and metrics outputs.
- `scripts/validate_smoke.sh`: clone-clean smoke test using deterministic synthetic traces.

## Reproducing Published Numbers

The published hdur-80 SEM cost anchor is `NEX=64`, `DT=0.15`, 4800-second records on 24 ranks, billed at 0.147 node-hours. It is staged by the `paper_sem_nex64_4800s` case, whose `DATA` directory is byte-identical to the campaign run that produced that number.

A clean run of the staged case on Perlmutter (2026-08-12, `shared_interactive`, 24 ranks at `-c 2`) reproduced it: 2828.8 s solver wall over 33000 steps at 85.5 ms/step, 0.1473 node-hours, against the original run's 2832.7 s and 0.1475. Its seismograms correlate with the original run's at 1.00000 on all 36 N/Z components, and the case passes the gate against the `NEX=96` rung 36/36 with a worst full-trace correlation of 0.99812 and PKP-window correlations of 0.99998. Against the shipped `NEX=320` SEM-Ref it passes 36/36 with a worst full-trace correlation of 0.99843 and PKP-window minima of 0.99993 (Z) and 0.99990 (N).

The DFDM cases run the production setup of DFDM3D (branch `production-2026-10`), which is newer than the paper's elastic record: a 66,560-element mesh with the deep layers merged into taller elements and the crust at 5 radial points, at `dt` 0.290625 s, where the paper used the 832-brick mesh at 0.1875 s (1.17 node-hours on tag `cpu-freeze-2026-07-10`). A clean run of `dfdm_4800s` (2026-10-28, 504 ranks on 4 exclusive nodes) took 602.5 s, 0.669 node-hours, and passed the gate against the shipped SEM-Ref 36/36 with a worst full-trace correlation of 0.99748 and PKP-window minima of 0.99926 (Z) and 0.99936 (N); against the paper's elastic record it correlates at 0.9987 or better on all 36 components. The DFDM built by `scripts/build_dfdm.sh` reproduces the production solver's output bit for bit (all 822 receiver files of a 40-step production run).

Two conventions have to match for the SEM number to come out right.

**Cost.** `node_hours = sem_tasks * cpus_per_task / 256 * solver_wall_hours` on Perlmutter CPU nodes (128 physical cores, 256 SMT slots), so a 24-rank run at `-c 2` bills 0.1875 of a node. The wall clock is the solver invocation alone; meshing is excluded for both codes. `scripts/sem_cost.py` implements exactly this and writes `runs/<case>/sem_perf.json`. DFDM runs on whole exclusive nodes and is billed as nodes times the wall of its solver invocation, which includes reading the mesh; `scripts/run_dfdm_slurm.sh` writes it to `runs/<case>/dfdm_cost.txt`.

The anchor's wall clock is a shared-node wall, and that matters because memory bandwidth is a node-level resource: Slurm dedicates cores to the job, not memory channels. The same 24-rank job on an exclusive node runs about 2.3 times faster (37.9 ms/step against 85.5 shared), which shows both that the solver is memory-bound at this size and that on a busy shared node it gets roughly its proportional share of the channels. Billing an exclusive-node wall at the core fraction would credit the job the whole node's bandwidth while charging 18.75% of the node (0.063 node-hours); billing the whole exclusive node would charge 104 cores the job cannot use (0.337 node-hours). The convention here takes the shared wall as billed: the job pays for the bandwidth it actually got. Run the anchor on shared QOS, and never re-bill an exclusive-node wall at the core fraction.

**Correctness.** All 36 N/Z station-components must reach 0.995 full-trace correlation against the SEM reference at both the 3600 s and 4750 s horizons, with the antipodal PKP window (source shift plus 1100 to 1400 s, stations at 140 degrees and beyond) reported alongside. SEM traces are baselined over the first 48 s and shifted by the 120 s source shift; DFDM traces already carry the shift and are rotated from Cartesian to north and vertical. Both are resampled onto a common 0.1 s grid. `scripts/score_sem_members.py` implements this for SEM and DFDM members.

Two gotchas are handled in the tooling rather than left to the user: `NEX < 128` writes `MX*` channel names while `NEX >= 128` writes `BX*`, so channels are globbed as `?X`; and the E component is near-nodal for this source-receiver geometry, so the qualification set is N and Z only.

### Time step conventions

The `paper_*` cases take the time step from SPECFEM's own stability estimate: `DT=0.15` is proven stable and accurate through `NEX=192`, and `0.075` at `NEX=256`.

The SEM-Ref (`NEX=320`) instead uses the PREM-ladder convention `DT = 9.6/NEX` = 0.03 s, 4 to 6 times below the stability estimate. That makes it an over-resolved reference costing 27.8 node-hours against the anchor's 0.147; DFDM-to-SEM cost ratios are taken against the anchor, never against the SEM-Ref.

DFDM uses `dt = 0.290625` s, 0.90 times the measured stability limit of its mesh with the 5-point crust (0.32351 s).

### The perfect-sphere build constant

`ASSUME_PERFECT_SPHERE = .true.` is a compile-time constant in `setup/constants.h.in`, applied by `scripts/prepare_specfem.sh` before the build and verified at run time by `scripts/run_sem_slurm.sh`. Without it SPECFEM converts source and station latitudes to geocentric, displacing stations by up to about 0.19 degrees relative to DFDM, and the nominal epicentral distances of 10, 20, ... degrees no longer hold. The published runs used it; a stock build does not.

## Submodules

The public SPECFEM submodule tracks `SPECFEM/specfem3d_globe` branch `master`.

The DFDM submodule tracks `ytian159/DFDM3D` branch `production-2026-10`: the production solver (per-element point counts, the 5-point crust, the cost-weighted MPI partition), the mesh planner, and the self-test battery. `scripts/prepare_dfdm.sh` checks that the source supports per-layer lateral element counts and the 5-point crust before the build. `scripts/build_dfdm.sh` builds single precision (`DFDM_REAL=float`), as in the published runs.

## Case Matrix

The case definitions live in `cases/ak135_mrr_hdur80_f0125/case_matrix.json`.

| case | SEM side | DFDM side | layout | cost (solver only) |
|---|---|---|---|---|
| `paper_sem_nex64_4800s` | `NEX` 64, `DT` 0.15, 80 min | none | 24 ranks, shared node | 0.147 node-h (47 min) |
| `paper_sem_nex96_4800s` | `NEX` 96, `DT` 0.10, 80 min | none | 24 ranks, shared node | 0.503 node-h (2.7 h) |
| `dfdm_4800s` | SEM-Ref (shipped) | production mesh, `dt` 0.290625, 4800 s | 504 ranks, 4 nodes | 0.669 node-h (10 min) |
| `dfdm_720s` | SEM-Ref (shipped) | the same, 720 s | 504 ranks, 4 nodes | 0.110 node-h (1.7 min) |
| `fixture_smoke` | synthetic | synthetic | n/a | none |

A case is SEM-only when it declares no `dfdm_nt`; `scripts/run_dfdm_slurm.sh` refuses such a case and `scripts/run_case_slurm.sh` skips the DFDM stage. Each case carries its own `sem_nproc`, and staging checks the two constraints SPECFEM imposes: `NEX` divisible by `8 * NPROC`, and `sem_tasks` equal to `6 * NPROC^2`.

A case whose SEM seismograms ship with the repository names the set with `sem_reference`; both DFDM cases do. For those cases `scripts/run_sem_slurm.sh` installs the shipped seismograms instead of running SPECFEM, unless `SEM_SEISMOGRAMS=run` is set.

Each staged case writes a `runs/<case>/case_metadata.json` file. The run wrappers read this metadata through `scripts/case_env.py`, so solver commands do not need hard-coded paths.

Restaging with `--force` refuses to delete a case directory that already holds seismograms, DFDM traces, figures, or score and performance JSON; `--discard-results` overrides that.

## Running the DFDM Comparison Cases

Build DFDM once (`bash scripts/build_dfdm.sh`), then run a case in an interactive allocation, the default on Perlmutter:

```bash
salloc -A <account> -C cpu -q interactive -N 4 -t 01:00:00 \
  bash -lc "cd $PWD && scripts/run_case_slurm.sh dfdm_4800s"
```

The run installs the shipped SEM-Ref seismograms, runs DFDM on 504 ranks, prints the DFDM cost, and compares. `bash scripts/compare_case.sh <case>` redoes the comparison from finished outputs.

The `paper_*` cases use a fraction of one node and run in a shared interactive allocation:

```bash
salloc -A <account> -C cpu -q shared_interactive -N 1 -n 24 -c 2 -t 03:00:00 \
  bash -lc "cd $PWD && NO_STAGE=1 scripts/run_sem_slurm.sh paper_sem_nex64_4800s"
```

The interactive queues allow at most 4 nodes for 4 hours. The one job beyond that is recomputing the SEM-Ref (27.8 node-hours, about 9.5 hours on 3 nodes), which goes in a batch job:

```bash
sbatch -A <account> -C cpu -q regular -t 12:00:00 -N 4 --exclusive \
  --export=ALL,SEM_SEISMOGRAMS=run scripts/run_case_slurm.sh dfdm_4800s
```

## Options

- `NO_STAGE=1`: do not stage or restage before running a solver wrapper.
- `FORCE_STAGE=1`: restage before running a solver wrapper; refuses while the case directory holds results.
- `SEM_SEISMOGRAMS`: where the SEM side of a case comes from (read by `scripts/run_sem_slurm.sh`, and so by `scripts/run_case_slurm.sh`). Unset, cases with shipped seismograms install them and other cases run SPECFEM. `run` always runs SPECFEM; `shipped` requires the shipped set; `/path/to/OUTPUT_FILES` installs an earlier run's seismograms from disk, with the run's `DATA` next to that directory. Installed seismograms must come from the same `DATA` as the case's staged `DATA`; their source is recorded in `runs/<case>/sem_seismograms.json`, and no `sem_perf.json` is written.
- `SPECFEM_ROOT=/path/to/specfem3d_globe`: run-time override for an already-built SPECFEM tree (must contain `bin/xmeshfem3D` and `bin/xspecfem3D`).
- `DFDM_EXE=/path/to/dfdm_elastic3d`: run-time override for an already-built DFDM executable.
- `DFDM_REAL=double`: build DFDM in double precision (`scripts/build_dfdm.sh`; the default is `float`).
- `DFDM_MPI_PARTITION_MODE`: DFDM's MPI partition (default `cost`, which balances ranks by element cost).
- `COMPARE_DT=0.1`: comparison resampling interval in seconds.
- `SKIP_SPHERE_CHECK=1`: run SEM against a build not prepared with `ASSUME_PERFECT_SPHERE`. Only for experiments that deliberately want geocentric station conversion; it invalidates the DFDM comparison.
- `SOURCE_SHIFT=120`: source time shift used by `scripts/compare_sem_members.sh` and `scripts/compare_case.sh` (1.5 times the half duration; use 60 for an hdur-40 protocol).

## Staged Run Tree

`scripts/stage_cases.py` creates:

- `runs/<case>/sem_case/DATA`: SPECFEM input files.
- `runs/<case>/dfdm.toml`: DFDM input file with repo-relative paths.
- `runs/<case>/dfdm_mesh_bricks.txt`: the decompressed DFDM mesh, checked against its checksum.
- `runs/<case>/case_metadata.json`: paths and case parameters consumed by plotting and run scripts.

## Solver Outputs

SPECFEM writes receiver traces under:

```text
runs/<case>/sem_case/OUTPUT_FILES/DF.AZ*.?X*.sem.ascii
```

The channel band code is `MX` for `NEX < 128` and `BX` for `NEX >= 128`.

DFDM writes receiver traces under:

```text
runs/<case>/DFDM_OUTPUT/Uxyz_dfdm3d_geo_AZ*_nex*_N*.txt
```

`scripts/run_dfdm_slurm.sh` also writes `runs/<case>/dfdm_cost.txt` (nodes times solver wall) and `runs/<case>/dfdm_perf.json` (DFDM's own timing breakdown).

## Comparison Outputs

`scripts/compare_case.sh <case>` writes:

- `runs/<case>/resolved_ppw_sem_dfdm_Z.png`
- `runs/<case>/resolved_ppw_sem_dfdm_diff_Z.png`
- `runs/<case>/resolved_ppw_sem_dfdm_compare_diff_Z.png`
- `runs/<case>/resolved_ppw_sem_dfdm_metrics.md`
- `runs/<case>/comparison_paths.txt`
- `runs/<case>/dfdm_score.json`, `runs/<case>/dfdm_score.png`: the gate score of DFDM against the SEM-Ref, with record sections and magnified residuals for both scored components

The metrics table reports per-station correlation alongside the RMS difference and peak ratio. Stations whose first arrival falls outside the record carry no signal, so their ratios compare noise with noise; in `dfdm_720s` this affects every station beyond about 80 degrees. The gate needs records through 4750 s, so `dfdm_720s` gets metrics and figures but no verdict.

`scripts/compare_sem_members.sh <test_case> <ref_case>` writes:

- `runs/<test_case>/sem_member_score_vs_<ref_case>.json`
- `runs/<test_case>/sem_member_score_vs_<ref_case>.png`

`scripts/run_sem_slurm.sh` writes `runs/<case>/sem_perf.json` at the end of every SEM run.
