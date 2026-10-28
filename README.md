# DFDM/SEM 3D Benchmarking

Global wave propagation benchmark comparing DFDM 3D with SPECFEM3D_GLOBE: AK135 model, vertical dipole (Mrr) source at 50 km depth with an 80 s half duration, 18 stations from 10° to 175°. The scripts reproduce the published accuracy and cost numbers and can be adapted to other configurations.

The conventions behind the numbers (node-hour accounting, pass criteria, the perfect-sphere build) are in [docs/BENCHMARK_DETAILS.md](docs/BENCHMARK_DETAILS.md).

## Requirements

- Python 3 with `numpy` and `matplotlib` (`pip install --user -r requirements.txt`).
- SPECFEM: Fortran compiler with MPI (`ftn` on Perlmutter).
- DFDM: C++17 compiler with MPI and CMake 3.14 or newer (`CC` on Perlmutter).
- Slurm. Replace `<account>` in the commands below with your allocation.

SPECFEM is not needed to compare DFDM against the reference seismograms shipped with the repository.

## Installation

```bash
git clone --recurse-submodules git@github.com:ytian159/dfdm-sem-3d-benchmarking.git
cd dfdm-sem-3d-benchmarking
bash scripts/build_specfem_perlmutter.sh   # only to run SPECFEM
bash scripts/build_dfdm.sh                 # only to run DFDM
```

The SPECFEM build sets `ASSUME_PERFECT_SPHERE = .true.`; both codes place the stations on a perfect sphere, and the run script rejects a build without it. Existing builds can be used instead through `SPECFEM_ROOT` and `DFDM_EXE` (see Options).

## Benchmark cases

Cases are defined in `cases/ak135_mrr_hdur80_f0125/case_matrix.json`.

| case | description | solvers | SEM cost |
|---|---|---|---|
| `paper_sem_nex64_4800s` | published SEM cost anchor: NEX 64, 80-minute records | SPECFEM | 0.147 node-hours (47 min on 24 cores) |
| `paper_sem_nex96_4800s` | finer SEM mesh for the anchor convergence check | SPECFEM | 0.5 node-hours (2.7 h on 24 cores) |
| `target_nex75_sem320_4800s` | DFDM against the converged SEM reference: NEX 320, 80-minute records | DFDM + SPECFEM | 27.8 node-hours; seismograms shipped with the repository |
| `pilot_nex60_sem256_720s` | same comparison with 10-minute records | DFDM + SPECFEM | 2 node-hours |

The SEM arms of the target and pilot cases are over-resolved references. DFDM-to-SEM cost ratios are measured against the anchor, not against them.

## Running the benchmarks

Each run has three steps: stage the case (writes input files to `runs/<case>/`), run the solvers inside a Slurm allocation, and score or compare the output. The run scripts stage automatically when a case has not been staged yet.

### SEM cost anchor

```bash
python3 scripts/stage_cases.py --case paper_sem_nex64_4800s

salloc -A <account> -C cpu -q shared_interactive -N 1 -n 24 -c 2 -t 02:00:00 \
  bash -lc "cd $PWD && NO_STAGE=1 scripts/run_sem_slurm.sh paper_sem_nex64_4800s"
```

The run ends with the cost report, also written to `runs/paper_sem_nex64_4800s/sem_perf.json`:

```text
layout          : 24 ranks x 2 cpus = 0.1875 node
solver wall     : 2828.8 s
NODE-HOURS      : 0.1473
```

The anchor must run on a shared node: the published wall time is a shared-node wall time, and an exclusive node runs the same job about 2.3 times faster.

### Anchor accuracy check

The anchor is scored against the NEX 320 reference, whose seismograms ship with the repository. No allocation is needed:

```bash
python3 scripts/install_sem_reference.py target_nex75_sem320_4800s
scripts/compare_sem_members.sh paper_sem_nex64_4800s target_nex75_sem320_4800s
```

Expected: `VERDICT: PASS (36/36 components)`, worst correlation 0.99843. The score and a record-section figure are written to `runs/paper_sem_nex64_4800s/`.

To check against a freshly computed member instead, run `paper_sem_nex96_4800s` like the anchor and score with `scripts/compare_sem_members.sh paper_sem_nex64_4800s paper_sem_nex96_4800s`.

### DFDM against the SEM reference

The reference seismograms (54 traces, 33 MB compressed, with checksums) are in `cases/ak135_mrr_hdur80_f0125/sem_ref_nex320_4800s`. With `SEM_SEISMOGRAMS=shipped` the job installs them, runs DFDM, and produces the comparison figures:

```bash
sbatch -A <account> -C cpu -q regular -t 48:00:00 -N 4 --exclusive --ntasks-per-node=128 \
  --export=ALL,SEM_SEISMOGRAMS=shipped scripts/run_case_slurm.sh target_nex75_sem320_4800s
```

Without `SEM_SEISMOGRAMS`, the job runs SPECFEM at NEX 320 as well.

### Pilot case

Both solvers, 10-minute records, 4 nodes:

```bash
sbatch -A <account> -C cpu -q regular -t 04:00:00 -N 4 --exclusive --ntasks-per-node=128 \
  scripts/run_case_slurm.sh pilot_nex60_sem256_720s
```

### Running the arms separately

`scripts/run_sem_slurm.sh <case>` and `scripts/run_dfdm_slurm.sh <case>` run one solver each with the same sbatch shape; add `--export=ALL,NO_STAGE=1` to the second job so it does not restage over the first job's output. Compare finished outputs with:

```bash
bash scripts/compare_case.sh <case>
```

## Output files

All outputs for a case are under `runs/<case>/`.

| file | content |
|---|---|
| `sem_case/OUTPUT_FILES/DF.AZ??.?X?.sem.ascii` | SPECFEM seismograms (time, displacement); channel `MX` for NEX below 128, `BX` otherwise |
| `DFDM_OUTPUT_*/Uxyz_dfdm3d_geo_AZ??_*.txt` | DFDM seismograms (time, x, y, z displacement) |
| `sem_perf.json` | SPECFEM cost report |
| `sem_seismograms.json` | source and checksums of installed SEM seismograms |
| `resolved_ppw_sem_dfdm_Z.png`, `..._diff_Z.png`, `..._compare_diff_Z.png` | overlay, residual, and side-by-side figures (vertical component) |
| `resolved_ppw_sem_dfdm_metrics.md` | per-station correlation, RMS difference, peak ratio |
| `sem_member_score_vs_<ref>.json`, `.png` | SEM member score against a reference case |

## Options

Environment variables, set in front of a command or with `--export=ALL,NAME=value` on `sbatch`.

| variable | effect |
|---|---|
| `SEM_SEISMOGRAMS=shipped` | install the case's shipped SEM seismograms instead of running SPECFEM (target case only) |
| `SEM_SEISMOGRAMS=/path/to/OUTPUT_FILES` | install SPECFEM seismograms from an earlier run; the run's `DATA` directory must sit next to `OUTPUT_FILES` and match the case |
| `SPECFEM_ROOT=/path/to/specfem3d_globe` | use an existing SPECFEM build (`bin/xmeshfem3D`, `bin/xspecfem3D`, perfect-sphere constant set) |
| `DFDM_EXE=/path/to/dfdm_elastic3d` | use an existing DFDM build |
| `NO_STAGE=1` | do not touch the staged input files; use when resubmitting a job |
| `FORCE_STAGE=1` | regenerate the input files after editing the case definition; refuses if the case directory holds results |
| `COMPARE_DT=0.1` | resampling interval in seconds for the comparison |
| `SOURCE_SHIFT=120` | source shift used in scoring, 1.5 times the half duration |
| `SKIP_SPHERE_CHECK=1` | allow a stock SPECFEM build; invalidates the DFDM comparison |

`scripts/install_sem_reference.py <case>` installs the shipped seismograms directly; `--from DIR` installs from disk, `--force` replaces seismograms already in the case, `--verify` checks the shipped files.

## Customizing a case

**Mesh, time step, record length.** Edit the case in `case_matrix.json` or copy it under a new name:

- `sem_nex`, `sem_nproc`, `sem_dt`: SPECFEM mesh size, processes per chunk edge, time step. `sem_nex` must be divisible by `8 * sem_nproc`, and `slurm.sem_tasks` must equal `6 * sem_nproc^2`.
- `dfdm_nex`, `dfdm_ney`, `dfdm_nez`, `dfdm_dt`, `dfdm_nt`: DFDM elements per chunk edge and per radial shell, time step, number of steps. A case without these keys is SPECFEM-only.
- `record_minutes`: SPECFEM record length. `dfdm_dt * dfdm_nt` must be at least as long; the comparison stops at the shorter record.
- `slurm`: nodes and ranks per solver, and `cpus_per_task` (2 on Perlmutter, so that ranks do not share a physical core).

Then restage with `python3 scripts/stage_cases.py --case <name> --force` (add `--discard-results` to overwrite existing results).

**Source and stations.** Defined in `cases/ak135_mrr_hdur80_f0125/base/sem_DATA/CMTSOLUTION` and `STATIONS` for SPECFEM, and in the `[source]` and `[receivers]` sections of `cases/ak135_mrr_hdur80_f0125/base/dfdm_ak135_mrr_heaviside_hdur80_base.toml` for DFDM; both must agree. The station lists at the top of `scripts/plot_sem_dfdm.py` and `scripts/score_sem_members.py` must be updated as well. A new half duration changes `SOURCE_SHIFT`.

**Earth model.** `MODEL` in `base/sem_DATA/Par_file` and `material.model` in the base DFDM file; both must name the same model.

**Other machines.** Build both codes, point the scripts at them with `SPECFEM_ROOT` and `DFDM_EXE`, and adapt the `sbatch` lines. The cost report assumes 256 CPU slots per node (`SLOTS_PER_NODE` in `scripts/sem_cost.py`).
