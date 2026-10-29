# DFDM/SEM 3D Benchmarking

Global wave propagation benchmark comparing DFDM 3D with SPECFEM3D_GLOBE: AK135 model, vertical dipole (Mrr) source at 50 km depth with an 80 s half duration, 18 stations from 10° to 175°. The scripts reproduce the published SEM cost anchor and score DFDM against a converged SEM reference.

The conventions behind the numbers (node-hour accounting, pass criteria, the perfect-sphere build) are in [docs/BENCHMARK_DETAILS.md](docs/BENCHMARK_DETAILS.md).

## Requirements

- Python 3 with `numpy` and `matplotlib` (`pip install --user -r requirements.txt`).
- DFDM: C++17 compiler with MPI and CMake 3.14 or newer (`CC` on Perlmutter).
- SPECFEM, only for the SEM cases: Fortran compiler with MPI (`ftn` on Perlmutter).
- Slurm. Replace `<account>` in the commands below with your allocation.

## Installation

```bash
git clone --recurse-submodules git@github.com:ytian159/dfdm-sem-3d-benchmarking.git
cd dfdm-sem-3d-benchmarking
bash scripts/build_dfdm.sh                 # DFDM3D, single precision as in the published runs
bash scripts/build_specfem_perlmutter.sh   # only to run SPECFEM
```

The SPECFEM build sets `ASSUME_PERFECT_SPHERE = .true.`; both codes place the stations on a perfect sphere, and the run script rejects a build without it. Existing builds can be used instead through `SPECFEM_ROOT` and `DFDM_EXE` (see Options).

## Benchmark cases

Cases are defined in `cases/ak135_mrr_hdur80_f0125/case_matrix.json`.

| case | description | solver | run time |
|---|---|---|---|
| `dfdm_4800s` | DFDM, 80-minute records, scored against the SEM reference | DFDM | 10 min on 4 nodes (0.67 node-hours) |
| `dfdm_720s` | the same DFDM run for the first 720 s; a quick check | DFDM | 2 min on 4 nodes (0.11 node-hours) |
| `paper_sem_nex64_4800s` | published SEM cost anchor: NEX 64, 80-minute records | SPECFEM | 47 min on 24 cores (0.147 node-hours) |
| `paper_sem_nex96_4800s` | finer SEM mesh for the anchor convergence check | SPECFEM | 2.7 h on 24 cores (0.5 node-hours) |

The SEM reference (SEM-Ref) is SPECFEM at NEX 320 with 80-minute records. It takes 27.8 node-hours to compute, so its seismograms ship with the repository and the DFDM cases use them automatically. It is over-resolved on purpose; DFDM-to-SEM cost ratios are measured against the anchor, not against it.

## Running the benchmarks

Each run stages the case (input files under `runs/<case>/`), runs the solver inside a Slurm allocation, and compares the output. The run scripts stage a case automatically the first time.

### DFDM against the SEM reference

```bash
sbatch -A <account> -C cpu -q regular -t 01:00:00 -N 4 --exclusive \
  scripts/run_case_slurm.sh dfdm_4800s
```

The job installs the SEM-Ref seismograms, runs DFDM on 504 ranks, and scores it. The output includes:

```text
layout          : 504 ranks x 2 cpus on 4 nodes
solver wall     : 602.5 s
NODE-HOURS      : 0.669
...
worst full-trace correlation : 0.99748 (bar 0.995)
PKP window  Z min / N min    : 0.99926 / 0.99936
VERDICT: PASS (36/36 components)
```

The quick check fits an interactive allocation:

```bash
salloc -A <account> -C cpu -q interactive -N 4 -t 00:30:00 \
  bash -lc "cd $PWD && scripts/run_case_slurm.sh dfdm_720s"
```

Its records are too short for the pass/fail score; it produces the figures and the per-station table only.

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

The anchor is scored against the SEM-Ref, which is installed in the `dfdm_4800s` case. No allocation is needed:

```bash
python3 scripts/install_sem_reference.py dfdm_4800s
scripts/compare_sem_members.sh paper_sem_nex64_4800s dfdm_4800s
```

Expected: `VERDICT: PASS (36/36 components)`, worst correlation 0.99843. The score and a record-section figure are written to `runs/paper_sem_nex64_4800s/`.

To check against a freshly computed member instead, run `paper_sem_nex96_4800s` like the anchor and score with `scripts/compare_sem_members.sh paper_sem_nex64_4800s paper_sem_nex96_4800s`.

### Running the solvers separately

`scripts/run_dfdm_slurm.sh <case>` and `scripts/run_sem_slurm.sh <case>` run one solver each, with the same allocations as above. `bash scripts/compare_case.sh <case>` compares finished outputs.

## Output files

All outputs for a case are under `runs/<case>/`.

| file | content |
|---|---|
| `dfdm_score.json`, `dfdm_score.png` | DFDM against the SEM-Ref: pass/fail per station and component, record sections, magnified residuals |
| `resolved_ppw_sem_dfdm_metrics.md`, `resolved_ppw_sem_dfdm_*.png` | per-station correlation, RMS difference and peak ratio, with overlay and residual figures (vertical component) |
| `dfdm_cost.txt`, `sem_perf.json` | DFDM and SPECFEM cost reports |
| `DFDM_OUTPUT/Uxyz_dfdm3d_geo_AZ??_*.txt` | DFDM seismograms (time, x, y, z displacement) |
| `sem_case/OUTPUT_FILES/DF.AZ??.?X?.sem.ascii` | SPECFEM seismograms (time, displacement); channel `MX` for NEX below 128, `BX` otherwise |
| `sem_seismograms.json` | source and checksums of installed SEM seismograms |
| `sem_member_score_vs_<ref>.json`, `.png` | score of a SEM case against a reference case |

## Options

Environment variables, set in front of a command or with `--export=ALL,NAME=value` on `sbatch`.

| variable | effect |
|---|---|
| `SEM_SEISMOGRAMS=run` | compute the SEM-Ref with SPECFEM instead of using the shipped seismograms (27.8 node-hours on 3 nodes) |
| `SEM_SEISMOGRAMS=/path/to/OUTPUT_FILES` | use SPECFEM seismograms from an earlier run; the run's `DATA` directory must sit next to `OUTPUT_FILES` and match the case |
| `SPECFEM_ROOT=/path/to/specfem3d_globe` | use an existing SPECFEM build (`bin/xmeshfem3D`, `bin/xspecfem3D`, perfect-sphere constant set) |
| `DFDM_EXE=/path/to/dfdm_elastic3d` | use an existing DFDM build |
| `DFDM_REAL=double` | build DFDM in double precision |
| `NO_STAGE=1` | do not touch the staged input files |
| `FORCE_STAGE=1` | regenerate the input files after editing the case definition; refuses if the case directory holds results |
| `COMPARE_DT=0.1` | resampling interval in seconds for the comparison |
| `SOURCE_SHIFT=120` | source shift used in scoring, 1.5 times the half duration |
| `SKIP_SPHERE_CHECK=1` | allow a stock SPECFEM build; invalidates the DFDM comparison |

`scripts/install_sem_reference.py <case>` installs the shipped seismograms directly; `--from DIR` installs from disk, `--force` replaces seismograms already in the case, `--verify` checks the shipped files.

## Customizing a case

**Time step and record length.** Edit the case in `case_matrix.json` or copy it under a new name:

- `dfdm_dt`, `dfdm_nt`: DFDM time step and number of steps; the DFDM record is `dfdm_dt * dfdm_nt` seconds. 0.290625 s is 0.90 times the measured stability limit of the shipped mesh; do not go higher.
- `sem_nex`, `sem_nproc`, `sem_dt`, `record_minutes`: SPECFEM mesh size, processes per chunk edge, time step and record length. `sem_nex` must be divisible by `8 * sem_nproc`, and `slurm.sem_tasks` must equal `6 * sem_nproc^2`. Changing these on a DFDM case means the shipped SEM-Ref no longer applies; run with `SEM_SEISMOGRAMS=run`.
- `slurm`: nodes and ranks per solver, and `cpus_per_task` (2 on Perlmutter, so that ranks do not share a physical core).

Then restage with `python3 scripts/stage_cases.py --case <name> --force` (add `--discard-results` to overwrite existing results).

**DFDM mesh.** The mesh is `cases/ak135_mrr_hdur80_f0125/dfdm_mesh/mesh_bricks.txt.xz`, and its element and point counts are in `cases/ak135_mrr_hdur80_f0125/base/dfdm_ak135f_mrr_hdur80.toml`. A new mesh comes from the DFDM3D mesh planner; [dfdm_mesh/README.md](cases/ak135_mrr_hdur80_f0125/dfdm_mesh/README.md) has the command.

**Source and stations.** SPECFEM reads them from `base/sem_DATA/CMTSOLUTION` and `STATIONS`, DFDM from the `[source]` and `[receivers]` sections of the base DFDM file (moment tensor in Cartesian components); both must agree. The station lists at the top of `scripts/plot_sem_dfdm.py` and `scripts/score_sem_members.py` must be updated as well. The DFDM mesh is built for a 50 km source, so a source at another depth needs a new mesh; a new half duration changes `SOURCE_SHIFT`.

**Earth model.** `MODEL` in `base/sem_DATA/Par_file` and `material.model` in the base DFDM file; both must name the same model. The DFDM mesh follows AK135's layers, so another model needs a new mesh.

**Other machines.** Build both codes, point the scripts at them with `SPECFEM_ROOT` and `DFDM_EXE`, and adapt the `sbatch` lines. The SEM cost report assumes 256 CPU slots per node (`SLOTS_PER_NODE` in `scripts/sem_cost.py`).
