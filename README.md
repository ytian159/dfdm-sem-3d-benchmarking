# DFDM/SEM 3D Benchmarking

This repository runs one global earthquake simulation with two codes, DFDM 3D and SPECFEM3D_GLOBE, and compares their seismograms and their cost. The model is AK135 (no attenuation), the source is a vertical dipole (Mrr) at 50 km depth with an 80 s half duration, and 18 stations sit at 10° to 175° from the source. Everything is scripted so that you can get the published numbers back, or run your own variant, without editing paths.

The conventions behind the numbers (how node-hours are counted, what counts as a pass, why the build needs a perfect sphere) are in [docs/BENCHMARK_DETAILS.md](docs/BENCHMARK_DETAILS.md). This page tells you how to run things.

## 1. What you need

- Python 3 with `numpy` and `matplotlib`. If either is missing: `pip install --user -r requirements.txt`. On Perlmutter, `module load cray-python` gives you numpy; matplotlib still needs the pip command.
- To run SPECFEM: a Fortran compiler with MPI (the Cray `ftn` wrapper on Perlmutter).
- To run DFDM: a C++17 compiler with MPI and CMake 3.14 or newer (the Cray `CC` wrapper on Perlmutter).
- A Slurm account. Every example below uses `<account>`; put yours there.

You do not need SPECFEM at all if you only want to compare DFDM against the reference seismograms that ship with the repository (section 4).

## 2. Get the code and build

```bash
git clone --recurse-submodules git@github.com:ytian159/dfdm-sem-3d-benchmarking.git
cd dfdm-sem-3d-benchmarking
bash scripts/build_specfem_perlmutter.sh   # only if you will run SPECFEM
bash scripts/build_dfdm.sh                 # only if you will run DFDM
```

The SPECFEM build script sets `ASSUME_PERFECT_SPHERE = .true.` before compiling. The stations are placed on a perfect sphere in both codes; a stock SPECFEM build would move them by up to 0.19°. The run script checks for this and refuses a stock build.

If you already have a built SPECFEM or DFDM somewhere else, skip the build and point the scripts at it (section 6).

## 3. The cases

Each case is one simulation setup. They are defined in `cases/ak135_mrr_hdur80_f0125/case_matrix.json`.

| case | what it is | runs | cost |
|---|---|---|---|
| `paper_sem_nex64_4800s` | the published SEM cost anchor (NEX 64, 80-minute records) | SPECFEM only | 0.147 node-hours, 47 min on 24 cores |
| `paper_sem_nex96_4800s` | a finer SEM mesh, used to check the anchor | SPECFEM only | 0.5 node-hours, 2.7 h on 24 cores |
| `target_nex75_sem320_4800s` | DFDM against the converged SEM reference (NEX 320, 80-minute records) | DFDM + SPECFEM | SEM arm 27.8 node-hours, but its seismograms ship with the repo; the DFDM arm is long (see section 4) |
| `pilot_nex60_sem256_720s` | a 10-minute version of the same comparison | DFDM + SPECFEM | about 2 node-hours for SEM, 4 nodes for a few hours in total |
| `fixture_smoke` | synthetic traces for testing the scripts | nothing | seconds |

The SEM arms of the target and pilot cases are deliberately over-resolved references. Do not read a DFDM-to-SEM cost ratio from them; the fair SEM cost is the anchor, 0.147 node-hours.

## 4. Running

Every run has the same three steps: stage the case (writes the input files under `runs/<case>/`), run the solver(s) inside a Slurm allocation, and compare or score the results. The run scripts stage automatically if the case has not been staged yet.

### Reproduce the SEM cost anchor

This is the number the paper quotes for SPECFEM: 0.147 node-hours.

```bash
python3 scripts/stage_cases.py --case paper_sem_nex64_4800s

salloc -A <account> -C cpu -q shared_interactive -N 1 -n 24 -c 2 -t 02:00:00 \
  bash -lc "cd $PWD && NO_STAGE=1 scripts/run_sem_slurm.sh paper_sem_nex64_4800s"
```

It takes about 47 minutes and ends with a cost report, also written to `runs/paper_sem_nex64_4800s/sem_perf.json`:

```text
layout          : 24 ranks x 2 cpus = 0.1875 node
solver wall     : 2828.8 s
NODE-HOURS      : 0.1473
```

Run it on a shared node, as shown. The published number is a shared-node wall time, and the same job on an exclusive node is about 2.3 times faster, so the two are not comparable (details doc, "Cost").

### Check that the anchor is accurate

The anchor only counts if its seismograms match the converged reference. The reference seismograms ship with the repository, so this takes a minute and no allocation:

```bash
python3 scripts/install_sem_reference.py target_nex75_sem320_4800s
scripts/compare_sem_members.sh paper_sem_nex64_4800s target_nex75_sem320_4800s
```

Expected: `VERDICT: PASS (36/36 components)`, worst correlation 0.99843. The score and a record-section figure land in `runs/paper_sem_nex64_4800s/`.

If you would rather not rely on shipped files, run `paper_sem_nex96_4800s` the same way as the anchor (2.7 hours) and score against it instead: `scripts/compare_sem_members.sh paper_sem_nex64_4800s paper_sem_nex96_4800s`.

### Compare DFDM against the SEM reference

The reference (SEM-Ref) is the SEM arm of `target_nex75_sem320_4800s`. Rerunning it costs 27.8 node-hours, so its 54 traces ship in `cases/ak135_mrr_hdur80_f0125/sem_ref_nex320_4800s` (33 MB, compressed, with checksums; see the README there for where they come from). To use them instead of running SPECFEM, set `SEM_SEISMOGRAMS=shipped`. The job then installs the traces, runs DFDM, and makes the comparison figures:

```bash
sbatch -A <account> -C cpu -q regular -t 48:00:00 -N 4 --exclusive --ntasks-per-node=128 \
  --export=ALL,SEM_SEISMOGRAMS=shipped scripts/run_case_slurm.sh target_nex75_sem320_4800s
```

Be warned that the DFDM arm of this case is long. A 4-node attempt in June 2026 reached step 108,000 of 120,000 when its 48-hour limit expired. Budget more time or more nodes, and state the cost before you submit.

The pilot case is the cheap way to try the whole pipeline. It runs both solvers for 10 record minutes on 4 nodes:

```bash
sbatch -A <account> -C cpu -q regular -t 04:00:00 -N 4 --exclusive --ntasks-per-node=128 \
  scripts/run_case_slurm.sh pilot_nex60_sem256_720s
```

You can also run the two arms separately with `scripts/run_sem_slurm.sh <case>` and `scripts/run_dfdm_slurm.sh <case>` (same sbatch shape, add `--export=ALL,NO_STAGE=1` to the second one so it does not restage over the first arm's output), and then compare finished outputs with:

```bash
bash scripts/compare_case.sh <case>
```

### Test the scripts without running anything

```bash
bash scripts/validate_smoke.sh
```

This stages the synthetic case, makes the figures from it, checks that no file in the repository contains a local path, and verifies the checksums of the shipped reference seismograms. It needs no allocation.

## 5. Where the results are

Everything for a case is under `runs/<case>/`:

| file | what it is |
|---|---|
| `sem_case/OUTPUT_FILES/DF.AZ??.?X?.sem.ascii` | SPECFEM seismograms (two columns: time, displacement). The channel is `MX` for NEX below 128 and `BX` above. |
| `DFDM_OUTPUT_*/Uxyz_dfdm3d_geo_AZ??_*.txt` | DFDM seismograms (time, then x, y, z displacement). |
| `sem_perf.json` | SPECFEM cost report (only when SPECFEM was actually run). |
| `sem_seismograms.json` | where installed seismograms came from, with checksums (only when they were installed, not run). |
| `resolved_ppw_sem_dfdm_Z.png`, `..._diff_Z.png`, `..._compare_diff_Z.png` | overlay, residual, and side-by-side figures for the vertical component. |
| `resolved_ppw_sem_dfdm_metrics.md` | per-station correlation, RMS difference, and peak ratio. |
| `sem_member_score_vs_<ref>.json`, `.png` | the pass/fail score of one SEM case against another. |

## 6. Options

All options are environment variables. Set them in front of the command, or with `--export=ALL,NAME=value` on `sbatch`.

| variable | set it when |
|---|---|
| `SEM_SEISMOGRAMS=shipped` | you want the case's shipped SEM seismograms instead of running SPECFEM. Only the target case has them. |
| `SEM_SEISMOGRAMS=/path/to/OUTPUT_FILES` | you already have SPECFEM seismograms for this case on disk from an earlier run. The run's `DATA` directory must sit next to `OUTPUT_FILES`; the script checks that the inputs match the case and refuses otherwise. |
| `SPECFEM_ROOT=/path/to/specfem3d_globe` | you have a SPECFEM build elsewhere (it must contain `bin/xmeshfem3D` and `bin/xspecfem3D`, built with the perfect-sphere constant). |
| `DFDM_EXE=/path/to/dfdm_elastic3d` | you have a DFDM build elsewhere. |
| `NO_STAGE=1` | the case is already staged and you do not want the run script to touch its input files. Use it whenever you resubmit a job. |
| `FORCE_STAGE=1` | you changed the case definition and want the run script to regenerate the input files. Refuses if the case directory already holds results; delete or move them first. |
| `COMPARE_DT=0.1` | you want a different resampling interval (seconds) for the comparison. |
| `SOURCE_SHIFT=120` | you changed the half duration. The scoring shifts the SEM traces by 1.5 times the half duration. |
| `SKIP_SPHERE_CHECK=1` | you deliberately want a stock SPECFEM build. This breaks the DFDM comparison; use it only for SPECFEM-only experiments. |

`scripts/install_sem_reference.py` can also be called directly: `install_sem_reference.py <case>` installs the shipped set, `--from DIR` installs from disk, `--force` replaces seismograms already in the case, and `--verify` checks the shipped files without installing anything.

## 7. Changing what runs

**A different mesh, time step, or record length.** Edit the case in `cases/ak135_mrr_hdur80_f0125/case_matrix.json`, or copy an existing case under a new name. The keys are:

- `sem_nex`, `sem_nproc`, `sem_dt`: SPECFEM mesh size, processes per chunk edge, and time step. SPECFEM needs `sem_nex` divisible by `8 * sem_nproc`, and the number of MPI ranks (`slurm.sem_tasks`) must equal `6 * sem_nproc^2`. Staging checks both.
- `dfdm_nex`, `dfdm_ney`, `dfdm_nez`, `dfdm_dt`, `dfdm_nt`: DFDM elements per chunk edge and per radial shell, time step, and number of steps. Leave these out and the case becomes SPECFEM-only.
- `record_minutes`: record length for SPECFEM. DFDM runs `dfdm_dt * dfdm_nt` seconds; make that at least as long, since the comparison stops at the shorter of the two records.
- `slurm`: nodes and ranks for each arm, and the cores per rank (`cpus_per_task`, keep it at 2 on Perlmutter so that two ranks never share a physical core).

Then stage the case again (`python3 scripts/stage_cases.py --case <name> --force`) and run it as above. Staging refuses to delete a case directory that already holds results; add `--discard-results` if you mean to.

**A different source or stations.** The source and stations are set in two places that must agree: `cases/ak135_mrr_hdur80_f0125/base/sem_DATA/CMTSOLUTION` and `STATIONS` for SPECFEM, and the `[source]` and `[receivers]` sections of `cases/ak135_mrr_hdur80_f0125/base/dfdm_ak135_mrr_heaviside_hdur80_base.toml` for DFDM. The station list and distances are also written into `scripts/plot_sem_dfdm.py` and `scripts/score_sem_members.py` (the `STATIONS`, `LATS`, `LONS`, `DISTS` lists at the top); update those too. A new half duration also changes the source shift (`SOURCE_SHIFT`, 1.5 times the half duration).

**A different Earth model.** Change `MODEL` in `base/sem_DATA/Par_file` and `material.model` in the base DFDM file. Both codes must name the same model.

**A different machine.** The scripts assume Slurm with `srun`, and the build scripts assume the Cray compiler wrappers. On another system, build the two codes by hand, point the scripts at them with `SPECFEM_ROOT` and `DFDM_EXE`, and adjust the `sbatch` lines to your queue. The cost report assumes 256 CPU slots per node (Perlmutter); change `SLOTS_PER_NODE` in `scripts/sem_cost.py` if your nodes differ.

Whatever you change, run `bash scripts/validate_smoke.sh` afterwards; it catches broken staging and absolute paths before you spend an allocation.
