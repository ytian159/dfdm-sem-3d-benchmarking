# DFDM/SEM 3D Benchmarking

Stages and runs the AK135 Mrr `f0=0.0125` (80 s half duration) global benchmark, comparing DFDM 3D waveforms against SPECFEM3D_GLOBE.

Everything beyond the quick start below (case matrix, DFDM comparison workflow, cost conventions, options) is in [docs/BENCHMARK_DETAILS.md](docs/BENCHMARK_DETAILS.md).

## Setup

Python 3 with `numpy` and `matplotlib` (`module load cray-python` on Perlmutter).

```bash
git clone --recurse-submodules git@github.com:ytian159/dfdm-sem-3d-benchmarking.git
cd dfdm-sem-3d-benchmarking
bash scripts/build_specfem_perlmutter.sh
```

The build sets `ASSUME_PERFECT_SPHERE = .true.` in the SPECFEM source; the benchmark geometry requires it and the run script refuses builds without it.

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

To certify the anchor, run the `NEX=96` convergence rung the same way (case `paper_sem_nex96_4800s`, about 2.7 hours), then score the two members:

```bash
scripts/compare_sem_members.sh paper_sem_nex64_4800s paper_sem_nex96_4800s
```

Expected: `VERDICT: PASS (36/36 components)` with a worst full-trace correlation near 0.998.

## Smoke Test

Clone-clean check, no solver or allocation needed:

```bash
bash scripts/validate_smoke.sh
```

## DFDM vs SPECFEM

The `pilot_nex60_sem256_720s` and `target_nex75_sem320_4800s` cases run both solvers and produce overlay and residual figures; the commands are in [docs/BENCHMARK_DETAILS.md](docs/BENCHMARK_DETAILS.md). Their SEM arms are deliberately over-resolved reference configurations. Do not quote DFDM-to-SEM cost ratios from them; the honest SEM bar is the anchor above.
