# DFDM/SEM 3D Benchmarking

This repository stages and runs the AK135 Mrr `f0=0.0125` resolved-PPW benchmark used to compare DFDM 3D waveforms against SPECFEM3D_GLOBE waveforms, then regenerates SEM/DFDM overlay, residual, and metrics figures.

## Repository Layout

- `external/dfdm_3d_elastic`: DFDM 3D solver submodule.
- `external/specfem3d_globe`: public SPECFEM3D_GLOBE submodule.
- `patches/dfdm`: patch stack that reconstructs the local PPW-control DFDM state from the published DFDM ancestor branch.
- `cases/ak135_mrr_hdur80_f0125`: base DFDM TOML, SPECFEM `DATA` files, and case matrix.
- `scripts/stage_cases.py`: creates repo-relative run directories under `runs/`.
- `scripts/run_case_slurm.sh`: runs SPECFEM mesher/solver, DFDM solver, then comparison figures inside an existing Slurm allocation.
- `scripts/plot_sem_dfdm.py`: regenerates SEM/DFDM Z overlay, difference, combined, and metrics outputs.
- `scripts/validate_smoke.sh`: clone-clean smoke test using deterministic synthetic traces.

## Submodules

The public SPECFEM submodule tracks `SPECFEM/specfem3d_globe` branch `master`.

The intended DFDM solver state is the PPW-control line at `eb1905ea1c8cd715399f1894bff9af0399750014` plus the current tracked PPW-control working patch. In this checkout that branch was not publishable from the session, so the DFDM submodule tracks the published ancestor branch `codex/mpi-3d-elastic-perlmutter`, and `scripts/prepare_dfdm.sh` applies the patch stack in `patches/dfdm`.

When the DFDM `ppw-3d-control` branch is available on GitHub, update the DFDM submodule to that branch and remove the local patch stack.

## Quick Validation

```bash
git clone --recurse-submodules <repo-url> dfdm-sem-3d-benchmarking
cd dfdm-sem-3d-benchmarking
bash scripts/validate_smoke.sh
```

The smoke test does not run either solver. It stages the benchmark format, creates deterministic SEM/DFDM-like traces under `runs/fixture_smoke`, regenerates figures, and checks that checked-in files do not contain machine-local paths.

## Stage Physical Cases

```bash
python3 scripts/stage_cases.py --case pilot_nex60_sem256_720s --force
python3 scripts/stage_cases.py --case target_nex75_sem320_4800s --force
```

The generated run tree contains:

- `sem_case/DATA`: SPECFEM input files.
- `dfdm_ak135_mrr_hdur80_refined.toml`: DFDM input file with repo-relative output path.
- `case_metadata.json`: paths and case parameters consumed by plotting and run scripts.

## Build

DFDM:

```bash
bash scripts/build_dfdm.sh
```

SPECFEM3D_GLOBE on a Perlmutter-style environment:

```bash
bash scripts/build_specfem_perlmutter.sh
```

You can also build SPECFEM outside this repo and set `SPECFEM_ROOT=/path/to/specfem3d_globe`.

## Run In Slurm

Run inside an allocation or submit the script through `sbatch` with resources matching the case matrix.

```bash
# Pilot case, nominal resources: 4 nodes, 4 hours.
sbatch -A <account> -C cpu -q regular -t 04:00:00 -N 4 --exclusive \
  --ntasks-per-node=128 scripts/run_case_slurm.sh pilot_nex60_sem256_720s

# Target case, nominal resources: 4 nodes, 48 hours.
sbatch -A <account> -C cpu -q regular -t 48:00:00 -N 4 --exclusive \
  --ntasks-per-node=128 scripts/run_case_slurm.sh target_nex75_sem320_4800s
```

Outputs are written under `runs/<case>/`, including:

- `sem_case/OUTPUT_FILES/DF.AZ*.BX*.sem.ascii`
- `DFDM_OUTPUT_*/Uxyz_dfdm3d_geo_AZ*_nex*_N*.txt`
- `resolved_ppw_sem_dfdm_Z.png`
- `resolved_ppw_sem_dfdm_diff_Z.png`
- `resolved_ppw_sem_dfdm_compare_diff_Z.png`
- `resolved_ppw_sem_dfdm_metrics.md`
