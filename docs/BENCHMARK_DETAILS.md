# Benchmark Details

## Repository Layout

- `external/dfdm_3d_elastic`: DFDM 3D solver submodule.
- `external/specfem3d_globe`: public SPECFEM3D_GLOBE submodule.
- `patches/dfdm`: source patch stack applied by `scripts/prepare_dfdm.sh` before building DFDM. It reconstructs the PPW-control solver state from the published DFDM submodule commit.
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

The intended DFDM solver state is the PPW-control line at `eb1905ea1c8cd715399f1894bff9af0399750014` plus the current tracked PPW-control working patch. Until that full solver branch is published directly, the DFDM submodule tracks the published `main` branch, and `scripts/prepare_dfdm.sh` applies the patch stack in `patches/dfdm`.

When the DFDM `ppw-3d-control` branch is available on GitHub, update the DFDM submodule to that branch and remove the local patch stack.

## DFDM Patch Stack

`scripts/build_dfdm.sh` calls `scripts/prepare_dfdm.sh` before compiling. That preparation script updates the DFDM submodule and applies `patches/dfdm/*.patch` in filename order if the PPW-control source changes are not already present.

- `0001-base-to-ppw-control-code.patch`: large source diff from the published DFDM benchmark base branch to the PPW-control solver code.
- `0002-current-ppw-control-code.patch`: smaller follow-up diff for the current tracked PPW-control working changes.

These patches are source reconstruction patches, not benchmark inputs or generated outputs.

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
