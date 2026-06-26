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

## Smoke Test

This does not run the physical solvers. It stages a tiny fixture, creates deterministic synthetic traces, regenerates figures, and checks that tracked files do not depend on machine-local paths.

```bash
bash scripts/validate_smoke.sh
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

If SPECFEM is already built elsewhere, set `SPECFEM_ROOT=/path/to/specfem3d_globe`.
If DFDM is already built elsewhere, set `DFDM_EXE=/path/to/dfdm_elastic3d`.

## Stage Cases

Stage the case before launching separate SEM and DFDM jobs:

```bash
python3 scripts/stage_cases.py --case pilot_nex60_sem256_720s --force
python3 scripts/stage_cases.py --case target_nex75_sem320_4800s --force
```

Available physical cases:

- `pilot_nex60_sem256_720s`: shorter pilot case, nominally 4 nodes and 4 hours.
- `target_nex75_sem320_4800s`: target 80-minute case, nominally 4 nodes and 48 hours.

`fixture_smoke` is only for `scripts/validate_smoke.sh`.

## Run SEM Only

```bash
sbatch -A <account> -C cpu -q regular -t 04:00:00 -N 4 --exclusive \
  --ntasks-per-node=128 --export=ALL,NO_STAGE=1 \
  scripts/run_sem_slurm.sh pilot_nex60_sem256_720s
```

For the target case, use `-t 48:00:00` and replace the case name with `target_nex75_sem320_4800s`.

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
- `SPECFEM_ROOT=/path/to/specfem3d_globe`: use an external SPECFEM build.
- `DFDM_EXE=/path/to/dfdm_elastic3d`: use an external DFDM executable.
- `COMPARE_DT=0.1`: set comparison resampling interval in seconds.
