# DFDM/SEM 3D Benchmarking Usage

This repository stages and runs the AK135 Mrr `f0=0.0125` resolved-PPW benchmark, then compares DFDM 3D waveforms against SPECFEM3D_GLOBE waveforms.

Detailed repository notes are in [docs/BENCHMARK_DETAILS.md](docs/BENCHMARK_DETAILS.md).

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

By default, the build scripts use the solver submodules in this repository. External solver binaries are optional run-time overrides; see Useful Options below.

`scripts/build_specfem_perlmutter.sh` calls `scripts/prepare_specfem.sh` first, which sets `ASSUME_PERFECT_SPHERE = .true.` in the SPECFEM source. This is required, not cosmetic: the benchmark models a spherically symmetric Earth and DFDM places its source and receivers at the requested geocentric angles, so a stock build silently converts station coordinates to geocentric and moves every station by up to about 0.19 degrees. `scripts/run_sem_slurm.sh` refuses to run against a build that lacks it.

## Reproduce the Published SEM Cost Anchor

The paper's SPECFEM cost bar at hdur-80 is the cheapest mesh that still passes the correctness gate: `NEX=64`, `DT=0.15`, 4800-second records, 24 ranks on one shared node, billed at **0.147 node-hours**. Reproduce it with:

```bash
python3 scripts/stage_cases.py --case paper_sem_nex64_4800s --force
salloc -A <account> -C cpu -q shared_interactive -N 1 -n 24 -c 2 -t 03:00:00
NO_STAGE=1 scripts/run_sem_slurm.sh paper_sem_nex64_4800s
```

The solver takes roughly 47 minutes. `scripts/sem_cost.py` runs automatically at the end and writes `runs/paper_sem_nex64_4800s/sem_perf.json`, reporting node-hours as `tasks * cpus_per_task / 256 * solver_wall_hours` with meshing excluded, which is the convention used in the paper's cost tables.

To certify the anchor, run the convergence rung and score one against the other:

```bash
python3 scripts/stage_cases.py --case paper_sem_nex96_4800s --force
NO_STAGE=1 scripts/run_sem_slurm.sh paper_sem_nex96_4800s          # about 0.50 node-h
scripts/compare_sem_members.sh paper_sem_nex64_4800s paper_sem_nex96_4800s
```

`scripts/compare_sem_members.sh` applies the published gate: all 36 N/Z station-components must reach 0.995 full-trace correlation at both the 3600 s and 4750 s horizons, with the antipodal PKP window reported alongside. It writes a JSON score and a record-section figure with a magnified residual panel. The E component is near-nodal for this geometry and is excluded, and channel names are globbed as `?X` because `NEX < 128` writes `MX*` while `NEX >= 128` writes `BX*`.

For the converged reference the paper scores against, stage and run `target_nex75_sem320_4800s`, whose SEM arm is `NEX=320` at `DT=0.03` (far more expensive; see the cost note below).

## Stage Cases

Stage the case before launching separate SEM and DFDM jobs:

```bash
python3 scripts/stage_cases.py --case pilot_nex60_sem256_720s --force
python3 scripts/stage_cases.py --case target_nex75_sem320_4800s --force
```

`--force` refuses to delete a case directory that already holds solver outputs or figures; pass `--discard-results` when you really mean to overwrite them.

Available physical cases:

- `paper_sem_nex64_4800s`: SEM-only, the published 0.147 node-hour cost anchor, 1 shared node and 3 hours.
- `paper_sem_nex96_4800s`: SEM-only, the convergence rung that certifies the anchor, 1 shared node and 4 hours.
- `pilot_nex60_sem256_720s`: shorter pilot case, nominally 4 nodes and 4 hours.
- `target_nex75_sem320_4800s`: target 80-minute case, nominally 4 nodes and 48 hours.

### A note on the two case families

The `paper_*` cases follow the published protocol: the SEM time step is set from SPECFEM's own stability estimate (`DT=0.15` through `NEX=192`, `0.075` at `NEX=256`) and cost is time-loop only.

The `pilot_*` and `target_*` cases follow the older PREM-ladder convention `DT = 9.6/NEX`, which is 4 to 6 times below SPECFEM's stability estimate and exists only for cost comparability across that ladder. They are demonstration configurations with deliberately over-resolved SEM arms: `pilot_nex60_sem256_720s` bills about 3.4 node-hours, more than twenty times the published anchor. **Do not read a DFDM-to-SEM cost ratio off those cases**; the published ratios come from the `paper_*` family.

## Run SEM Only

```bash
sbatch -A <account> -C cpu -q regular -t 04:00:00 -N 4 --exclusive \
  --ntasks-per-node=128 --export=ALL,NO_STAGE=1 \
  scripts/run_sem_slurm.sh pilot_nex60_sem256_720s
```

For the target case, use `-t 48:00:00` and replace the case name with `target_nex75_sem320_4800s`.

The `paper_*` cases run on a fraction of one node and belong in a shared allocation instead:

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

For the target case, use `-t 48:00:00` and replace the case name with `target_nex75_sem320_4800s`.

## Compare Existing Outputs Only

Run this after the SEM and DFDM jobs for the same case have both finished:

```bash
bash scripts/compare_case.sh pilot_nex60_sem256_720s
```

The comparison writes figures and metrics under `runs/<case>/`.

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

## Useful Options

- `NO_STAGE=1`: do not stage or restage before running a solver wrapper.
- `FORCE_STAGE=1`: restage if using `scripts/run_sem_slurm.sh` or `scripts/run_dfdm_slurm.sh`.
- `SPECFEM_ROOT=/path/to/specfem3d_globe`: optional run-time override for an already-built SPECFEM tree. The directory must contain `bin/xmeshfem3D` and `bin/xspecfem3D`.
- `DFDM_EXE=/path/to/dfdm_elastic3d`: optional run-time override for an already-built DFDM executable.
- `COMPARE_DT=0.1`: set comparison resampling interval in seconds.
- `SKIP_SPHERE_CHECK=1`: run SEM against a build that was not prepared with `ASSUME_PERFECT_SPHERE`. Only for experiments that deliberately want geocentric station conversion; it invalidates the DFDM comparison.
- `SOURCE_SHIFT=120`: source time shift used by `scripts/compare_sem_members.sh` (1.5 x half duration; use 60 for an hdur-40 protocol).
