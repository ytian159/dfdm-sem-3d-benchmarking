# DFDM/SEM 3D Benchmarking Usage

This repository stages and runs the AK135 Mrr `f0=0.0125` (80 s half duration) global benchmark against SPECFEM3D_GLOBE. It covers two things:

- **Reproducing published SPECFEM numbers**, in particular the 0.147 node-hour cost anchor, using the `paper_*` cases.
- **Comparing DFDM 3D waveforms against SPECFEM**, using the `pilot_*` and `target_*` cases.

Read [the note on cost conventions](#cost-conventions) before quoting any cost ratio from this repository: the two case families bill very differently on purpose.

Detailed repository notes are in [docs/BENCHMARK_DETAILS.md](docs/BENCHMARK_DETAILS.md).

## Requirements

Python 3 with `numpy` and `matplotlib` (see `requirements.txt`). On Perlmutter:

```bash
module load cray-python
```

Slurm access to CPU nodes. The `paper_*` cases fit in a shared allocation; the DFDM cases want exclusive nodes.

## Clone

```bash
git clone --recurse-submodules git@github.com:ytian159/dfdm-sem-3d-benchmarking.git
cd dfdm-sem-3d-benchmarking
```

If the repo was cloned without submodules:

```bash
git submodule update --init --recursive
```

## Build

DFDM:

```bash
bash scripts/build_dfdm.sh
```

SPECFEM3D_GLOBE on Perlmutter-style Cray environments:

```bash
bash scripts/build_specfem_perlmutter.sh
```

By default the build scripts use the solver submodules in this repository. External solver binaries are optional run-time overrides; see [Useful Options](#useful-options).

`scripts/build_specfem_perlmutter.sh` calls `scripts/prepare_specfem.sh` first, which sets `ASSUME_PERFECT_SPHERE = .true.` in the SPECFEM source. This is required, not cosmetic. The benchmark models a spherically symmetric Earth and DFDM places its source and receivers at the requested geocentric angles, so a stock build converts station coordinates to geocentric and moves every station by up to about 0.19 degrees, which quietly breaks the nominal 10, 20, ... degree epicentral distances. Because it is a compile-time constant it must be set before building. `scripts/run_sem_slurm.sh` refuses to run against a build that lacks it.

## Cases

| case | arms | SEM mesh | SEM `DT` | record | layout | SEM cost |
|---|---|---|---|---|---|---|
| `paper_sem_nex64_4800s` | SEM | `NEX` 64 | 0.15 | 80 min | 24 ranks, shared node | 0.147 node-h (47 min) |
| `paper_sem_nex96_4800s` | SEM | `NEX` 96 | 0.10 | 80 min | 24 ranks, shared node | 0.503 node-h (2.7 h) |
| `pilot_nex60_sem256_720s` | SEM + DFDM | `NEX` 256 | 0.04 | 10 min | 384 ranks, 3 nodes | 2.1 node-h |
| `target_nex75_sem320_4800s` | SEM + DFDM | `NEX` 320 | 0.03 | 80 min | 384 ranks, 3 nodes | 27.8 node-h |
| `fixture_smoke` | synthetic | n/a | n/a | n/a | n/a | none |

SEM costs are solver-only, as billed in the published tables. Meshing is on top and is not negligible for the large meshes: the `NEX` 256 mesher takes about 26 minutes and writes a 35 GB database, against seconds and a few hundred MB at `NEX` 64.

A case is SEM-only when it declares no DFDM parameters. `scripts/run_dfdm_slurm.sh` refuses such a case, and `scripts/run_case_slurm.sh` skips the DFDM stage and the SEM/DFDM comparison.

## Reproduce the Published SEM Cost Anchor

The published SPECFEM cost bar at hdur-80 is the cheapest mesh that still passes the correctness gate: `NEX=64`, `DT=0.15`, 4800-second records on 24 ranks, billed at **0.147 node-hours**. The staged `DATA` directory for this case is byte-identical to the run that produced that number.

```bash
python3 scripts/stage_cases.py --case paper_sem_nex64_4800s --force

salloc -A <account> -C cpu -q shared_interactive -N 1 -n 24 -c 2 -t 02:00:00 \
  bash -lc "cd $PWD && NO_STAGE=1 scripts/run_sem_slurm.sh paper_sem_nex64_4800s"
```

The mesher takes seconds and the solver about 47 minutes. `scripts/sem_cost.py` runs automatically at the end and writes `runs/paper_sem_nex64_4800s/sem_perf.json`. Expect output close to:

```text
layout          : 24 ranks x 2 cpus = 0.1875 node
solver wall     : 2828.8 s
mesher wall     : 5.7 s (excluded from node-hours)
time loop       : 33000 steps, 85.5 ms/step
NODE-HOURS      : 0.1473
```

To certify the anchor, run the convergence rung and score one member against the other:

```bash
python3 scripts/stage_cases.py --case paper_sem_nex96_4800s --force

sbatch -A <account> -C cpu -q shared -t 04:00:00 -N 1 -n 24 -c 2 \
  --export=ALL,NO_STAGE=1 scripts/run_sem_slurm.sh paper_sem_nex96_4800s

scripts/compare_sem_members.sh paper_sem_nex64_4800s paper_sem_nex96_4800s
```

That scoring should end in `VERDICT: PASS (36/36 components)` with a worst full-trace correlation near 0.998 and PKP-window correlations near 1.0.

For the converged reference the paper scores against, stage and run `target_nex75_sem320_4800s`, whose SEM arm is `NEX=320` at `DT=0.03`, then score the anchor against it.

## Stage Cases

Staging writes a run directory under `runs/` with SPECFEM `DATA`, the DFDM TOML where applicable, and `case_metadata.json`:

```bash
python3 scripts/stage_cases.py --case pilot_nex60_sem256_720s --force
python3 scripts/stage_cases.py --case target_nex75_sem320_4800s --force
```

`--force` refuses to delete a case directory that already holds seismograms, DFDM traces, figures, or score and performance JSON. Pass `--discard-results` when you really do want to overwrite them, or move the directory aside first.

Staging also checks the two constraints SPECFEM imposes on the decomposition: `NEX` divisible by `8 * NPROC`, and rank count equal to `6 * NPROC^2`.

## Run SEM Only

Exclusive nodes for the DFDM-comparison cases:

```bash
sbatch -A <account> -C cpu -q regular -t 04:00:00 -N 4 --exclusive \
  --ntasks-per-node=128 --export=ALL,NO_STAGE=1 \
  scripts/run_sem_slurm.sh pilot_nex60_sem256_720s
```

For the target case use `-t 48:00:00` and the case name `target_nex75_sem320_4800s`.

The `paper_*` cases use a fraction of one node and belong in a shared allocation:

```bash
sbatch -A <account> -C cpu -q shared -t 03:00:00 -N 1 -n 24 -c 2 \
  --export=ALL,NO_STAGE=1 scripts/run_sem_slurm.sh paper_sem_nex64_4800s
```

Each wrapper reads its rank count, node count and decomposition from the staged `case_metadata.json`, so the allocation only has to be large enough to hold them.

## Run DFDM Only

```bash
sbatch -A <account> -C cpu -q regular -t 04:00:00 -N 4 --exclusive \
  --ntasks-per-node=128 --export=ALL,NO_STAGE=1 \
  scripts/run_dfdm_slurm.sh pilot_nex60_sem256_720s
```

For the target case use `-t 48:00:00` and the case name `target_nex75_sem320_4800s`.

## Run SEM, DFDM, Then Compare

Use this combined wrapper when one Slurm job should stage the case, run both solvers, and generate comparison figures:

```bash
sbatch -A <account> -C cpu -q regular -t 04:00:00 -N 4 --exclusive \
  --ntasks-per-node=128 scripts/run_case_slurm.sh pilot_nex60_sem256_720s
```

For the target case:

```bash
sbatch -A <account> -C cpu -q regular -t 48:00:00 -N 4 --exclusive \
  --ntasks-per-node=128 scripts/run_case_slurm.sh target_nex75_sem320_4800s
```

## Compare Existing Outputs

**DFDM against SEM**, after both jobs for a case have finished:

```bash
bash scripts/compare_case.sh pilot_nex60_sem256_720s
```

Writes to `runs/<case>/`: `resolved_ppw_sem_dfdm_Z.png`, `..._diff_Z.png`, `..._compare_diff_Z.png`, `..._metrics.md` and `comparison_paths.txt`. The metrics table reports correlation next to the RMS difference and peak ratio.

Stations whose first arrival falls outside the record carry no signal, so their ratios compare noise with noise. In the 10-minute pilot that is every station beyond about 80 degrees, where P has not yet arrived.

**One SEM member against another**, which is the published correctness gate:

```bash
scripts/compare_sem_members.sh paper_sem_nex64_4800s paper_sem_nex96_4800s
```

Writes `runs/<test_case>/sem_member_score_vs_<ref_case>.json` and a matching `.png` holding a record section and a magnified residual panel. The gate requires all 36 N/Z station-components to reach 0.995 full-trace correlation at both the 3600 s and 4750 s horizons; the antipodal PKP window is reported alongside. The E component is near-nodal for this source-receiver geometry and is excluded. Channels are globbed as `?X` because `NEX < 128` writes `MX*` while `NEX >= 128` writes `BX*`.

## Cost Accounting

`scripts/sem_cost.py` runs at the end of every SEM job and can be re-run at any time:

```bash
python3 scripts/sem_cost.py runs/paper_sem_nex64_4800s
```

It reports

```text
node_hours = sem_tasks * cpus_per_task / 256 * solver_wall_hours
```

on Perlmutter CPU nodes (128 physical cores, 256 SMT slots), so a 24-rank run at `-c 2` bills 0.1875 of a node. The wall clock is the solver invocation alone; meshing is excluded, matching the published cost tables. Results land in `runs/<case>/sem_perf.json` together with the step count and milliseconds per step.

Timing numbers are only comparable when they come from the same kind of allocation. Never mix a shared-node wall clock with an exclusive-node one in a ratio.

## Cost Conventions

The two case families choose the SEM time step differently, and this dominates their cost.

The `paper_*` cases take the time step from SPECFEM's own stability estimate: `DT=0.15` is proven stable and accurate through `NEX=192`, and `0.075` at `NEX=256`.

The `pilot_*` and `target_*` cases use the PREM-ladder convention `DT = 9.6/NEX` (0.04 at `NEX=256`, 0.03 at `NEX=320`). That sits 4 to 6 times below the stability estimate and exists only for cost comparability within that ladder. Their SEM arms are also far finer than the source band requires: `NEX=256` resolves a minimum period near 17 s for a source that excites nothing below about 80 s. The pilot therefore bills 2.1 node-hours and the target 27.8, against the anchor's 0.147, for a reference that is no better qualified.

Cost ratios taken from the `pilot_*` or `target_*` cases are not the published ratios. Quote costs from the `paper_*` family.

## Smoke Test

A clone-clean check that needs no solver and no allocation:

```bash
bash scripts/validate_smoke.sh
```

It stages the synthetic fixture, builds deterministic traces, runs the comparison, verifies the figures and metrics exist, and checks that no checked-in file contains a local machine path.

## Useful Options

- `NO_STAGE=1`: do not stage or restage before running a solver wrapper.
- `FORCE_STAGE=1`: restage when using `scripts/run_sem_slurm.sh` or `scripts/run_dfdm_slurm.sh`.
- `SPECFEM_ROOT=/path/to/specfem3d_globe`: run-time override for an already-built SPECFEM tree. The directory must contain `bin/xmeshfem3D` and `bin/xspecfem3D`.
- `DFDM_EXE=/path/to/dfdm_elastic3d`: run-time override for an already-built DFDM executable.
- `COMPARE_DT=0.1`: comparison resampling interval in seconds.
- `SKIP_SPHERE_CHECK=1`: run SEM against a build not prepared with `ASSUME_PERFECT_SPHERE`. Only for experiments that deliberately want geocentric station conversion; it invalidates the DFDM comparison.
- `SOURCE_SHIFT=120`: source time shift used by `scripts/compare_sem_members.sh` (1.5 times the half duration; use 60 for an hdur-40 protocol).
