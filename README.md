# DFDM/SEM 3D Benchmarking

Stages and runs the AK135 Mrr `f0=0.0125` (80 s half duration) global benchmark, comparing DFDM 3D waveforms against SPECFEM3D_GLOBE.

Everything beyond the quick start below (case matrix, DFDM comparison workflow, cost conventions, options) is in [docs/BENCHMARK_DETAILS.md](docs/BENCHMARK_DETAILS.md).

## Setup

Python 3 with `numpy` and `matplotlib` (`module load cray-python/3.11.7` on Perlmutter; the default `cray-python` module has no matplotlib).

```bash
git clone --recurse-submodules git@github.com:ytian159/dfdm-sem-3d-benchmarking.git
cd dfdm-sem-3d-benchmarking
bash scripts/build_specfem_perlmutter.sh
```

The build sets `ASSUME_PERFECT_SPHERE = .true.` in the SPECFEM source; the benchmark geometry requires it and the run script refuses builds without it.

## Shipped SEM-Ref

The `NEX=320` reference (SEM-Ref, the SEM arm of `target_nex75_sem320_4800s`) takes 27.8 node-hours to run, so its seismograms ship in [cases/ak135_mrr_hdur80_f0125/sem_ref_nex320_4800s](cases/ak135_mrr_hdur80_f0125/sem_ref_nex320_4800s) (33 MB, xz-compressed, checksummed). Install them into the case instead of running SPECFEM:

```bash
python3 scripts/install_sem_reference.py target_nex75_sem320_4800s
```

The run wrappers do the same when `SEM_SEISMOGRAMS=shipped` is set, and `SEM_SEISMOGRAMS=/path/to/OUTPUT_FILES` reuses an earlier run's seismograms from disk. Either way the installer refuses traces produced by different `DATA` than the case's, and SPECFEM is not run, so it need not be built.

## SEM Cost Anchor (0.147 node-hours)

The SPECFEM cost bar for this benchmark: `NEX=64`, `DT=0.15`, 4800-second records, 24 ranks on one shared node.

```bash
python3 scripts/stage_cases.py --case paper_sem_nex64_4800s --force

salloc -A <account> -C cpu -q shared_interactive -N 1 -n 24 -c 2 -t 02:00:00 \
  bash -lc "cd $PWD && NO_STAGE=1 scripts/run_sem_slurm.sh paper_sem_nex64_4800s"
```

The solver takes about 47 minutes and ends with the cost report (also written to `runs/paper_sem_nex64_4800s/sem_perf.json`):

```text
layout          : 24 ranks x 2 cpus = 0.1875 node
solver wall     : 2828.8 s
NODE-HOURS      : 0.1473
```

To certify the anchor, score it against the shipped SEM-Ref:

```bash
python3 scripts/install_sem_reference.py target_nex75_sem320_4800s
scripts/compare_sem_members.sh paper_sem_nex64_4800s target_nex75_sem320_4800s
```

Expected: `VERDICT: PASS (36/36 components)` with a worst full-trace correlation of 0.99843 and PKP-window minima of 0.99993 (Z) and 0.99990 (N).

For a check that does not rely on the shipped files, run the `NEX=96` convergence rung the same way as the anchor (case `paper_sem_nex96_4800s`, about 2.7 hours) and score against it with `scripts/compare_sem_members.sh paper_sem_nex64_4800s paper_sem_nex96_4800s`; the worst full-trace correlation is then near 0.998.

## Smoke Test

Clone-clean check, no solver or allocation needed:

```bash
bash scripts/validate_smoke.sh
```

## DFDM vs SPECFEM

The `pilot_nex60_sem256_720s` and `target_nex75_sem320_4800s` cases run both solvers and produce overlay and residual figures; the commands are in [docs/BENCHMARK_DETAILS.md](docs/BENCHMARK_DETAILS.md). Their SEM arms are deliberately over-resolved reference configurations. Do not quote DFDM-to-SEM cost ratios from them; the honest SEM bar is the anchor above. With `SEM_SEISMOGRAMS=shipped`, the target case runs only its DFDM arm against the shipped SEM-Ref.
