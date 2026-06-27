# Benchmark Details

## Repository Layout

- `external/dfdm_3d_elastic`: DFDM 3D solver submodule.
- `external/specfem3d_globe`: public SPECFEM3D_GLOBE submodule.
- `cases/ak135_mrr_hdur80_f0125`: base DFDM TOML, SPECFEM `DATA` files, and case matrix.
- `scripts/stage_cases.py`: creates repo-relative run directories under `runs/`.
- `scripts/run_sem_slurm.sh`: runs only SPECFEM mesher and solver for a staged case.
- `scripts/run_dfdm_slurm.sh`: runs only DFDM for a staged case.
- `scripts/compare_case.sh`: regenerates figures and metrics from existing SEM and DFDM outputs.
- `scripts/run_case_slurm.sh`: stages a case, runs SEM, runs DFDM, then compares.
- `scripts/plot_sem_dfdm.py`: generates SEM/DFDM Z overlay, difference, combined, and metrics outputs.
- `scripts/validate_smoke.sh`: clone-clean smoke test using deterministic synthetic traces.

## Submodules

The public SPECFEM submodule tracks `SPECFEM/specfem3d_globe` branch `master`.

The DFDM submodule tracks `ytian159/dfdm_3d_elastic` branch `main`. The submodule commit contains the PPW-control 3D optimization source directly, including fixed axis kernels, full-shell radial `nez` decoupling, hat-face projection, and the benchmark validation utilities.

`scripts/prepare_dfdm.sh` updates the DFDM submodule and verifies these source markers before the DFDM build:

- `src/axis_kernels_fixed.h`
- `mesh3d.full_shell_nez_decoupled` support in `src/config_toml3d.cpp`
- `hat_l2_projection_matrix` in `src/elastic3d.cpp`

## Case Matrix

The case definitions live in `cases/ak135_mrr_hdur80_f0125/case_matrix.json`.

- `fixture_smoke`: small synthetic fixture for smoke validation only.
- `pilot_nex60_sem256_720s`: DFDM NEX60/NEZ30 against SPECFEM NEX256 for 10 record minutes.
- `target_nex75_sem320_4800s`: DFDM NEX75/NEZ30 against SPECFEM NEX320 for 80 record minutes.

Each staged case writes a `runs/<case>/case_metadata.json` file. The run wrappers read this metadata through `scripts/case_env.py`, so solver commands do not need hard-coded paths.

## Staged Run Tree

`scripts/stage_cases.py` creates:

- `runs/<case>/sem_case/DATA`: SPECFEM input files.
- `runs/<case>/dfdm_ak135_mrr_hdur80_refined.toml`: DFDM input file with repo-relative output path.
- `runs/<case>/case_metadata.json`: paths and case parameters consumed by plotting and run scripts.

## Solver Outputs

SPECFEM writes receiver traces under:

```text
runs/<case>/sem_case/OUTPUT_FILES/DF.AZ*.BX*.sem.ascii
```

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
