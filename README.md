# DFDM / SPECFEM global benchmarks

This repository compares two codes that simulate seismic waves through the whole Earth: DFDM3D (the distributional
finite-difference method) and SPECFEM3D_GLOBE (the spectral-element method). Each benchmark runs DFDM for one
earthquake, compares its records with a reference solution, and prints DFDM's error and cost next to SPECFEM's.

| case | Earth model | reference | DFDM run |
|---|---|---|---|
| `prem_1d` | PREM (1-D, anisotropic, attenuating) | exact answer (DSM normal-mode summation) | 3 min on 4 nodes |
| `ak135f_1d` | AK135-F (1-D, attenuating) | exact answer (DSM) | 3 min on 4 nodes |
| `semucb_crust1_3d` | SEMUCB-WM1 mantle with CRUST1.0 (3-D) | SPECFEM with a fine mesh (NEX192) | 6 min on 4 nodes |

All three use an earthquake at 50 km depth under 6N 12E with an 80-s half duration and 80 minutes of records (18
stations at 10 to 175 degrees for the 1-D cases, 90 stations on seven azimuths for the 3-D case). The SPECFEM records
and the reference records ship with the repository, so only DFDM needs to run.

Results on Perlmutter (error = median misfit over the stations, %; lower is better):

| case | DFDM error | DFDM cost | SPECFEM NEX64 error | SPECFEM NEX64 cost |
|---|---|---|---|---|
| `prem_1d` | Z 2.04, R 3.02 | 0.159 node-hours | Z 3.20, R 2.91 | 0.190 node-hours |
| `ak135f_1d` | Z 3.41, R 2.72 | 0.166 node-hours | Z 3.37, R 2.76 | 0.232 node-hours |
| `semucb_crust1_3d` | Z 2.72, R 3.43, T 3.03 | 0.361 node-hours | Z 3.32, R 3.57, T 4.31 | 0.530 node-hours |

Z is the vertical component, R the horizontal component along the path from the earthquake, T the horizontal
component across it. More earthquakes, depths and models are compared in the DFDM3D repository's
[COMPARISON_WITH_SPECFEM.md](https://github.com/ytian159/DFDM3D/blob/main/docs/COMPARISON_WITH_SPECFEM.md).

## Requirements

- A Slurm cluster. The commands below are for Perlmutter CPU nodes; replace `<account>` with your allocation.
- DFDM: a C++17 compiler with OpenMP and MPI, CMake 3.14 or newer, and BLAS/LAPACK with their C interfaces (`CC`
  in Perlmutter's default environment; build and run in the same module environment). The DFDM3D README lists the
  details.
- Python 3 with numpy, scipy and matplotlib (`pip install --user -r requirements.txt`).
- SPECFEM3D_GLOBE only if you want to rerun SPECFEM yourself: a Fortran compiler with MPI (`ftn` on Perlmutter).

## Installation

```bash
git clone --recurse-submodules git@github.com:ytian159/dfdm-sem-3d-benchmarking.git
cd dfdm-sem-3d-benchmarking
bash scripts/build_dfdm.sh            # builds external/dfdm_3d_elastic into build/dfdm/
```

The 3-D case also needs two model tables, built from public data (SEMUCB-WM1 from the IRIS Earth Model
Collaboration, CRUST1.0 from SPECFEM's data folder). This takes about a minute; on Perlmutter run it on a compute
node:

```bash
salloc -A <account> -C cpu -q shared_interactive -N 1 -c 16 -t 00:30:00
bash scripts/get_3d_models.sh         # writes models/semucb_wm1.tomo3d and models/crust1_specfem.txt
```

The script checks both tables against the ones used for the results above. If the download from IRIS fails, it says
where to get the two files by hand.

## Running a benchmark

Get 4 CPU nodes, then run one case:

```bash
salloc -A <account> -C cpu -q interactive -N 4 -t 00:30:00
scripts/run_benchmark.sh prem_1d
```

The same script runs under `sbatch` (`sbatch -A <account> -C cpu -q debug -N 4 -t 00:30:00 scripts/run_benchmark.sh
prem_1d`, submitted from the repository folder). It runs DFDM, measures its cost and prints the scores:

```text
wall time   : 143.3 s on 4 nodes
node-hours  : 0.159

PREM (1-D): misfit against DSM, %, median (worst) over 18 stations
solution            Z (vertical)          R (along the path)    node-hours
--------------------------------------------------------------------------
DFDM                2.04 (9.51)           3.02 (10.83)          0.159
SPECFEM NEX64       3.20 (9.70)           2.91 (10.88)          0.190
```

The other cases:

```bash
scripts/run_benchmark.sh ak135f_1d
scripts/run_benchmark.sh semucb_crust1_3d     # needs scripts/get_3d_models.sh first
```

```text
SEMUCB-WM1 + CRUST1.0 (3-D): misfit against SPECFEM NEX192, %, median (worst) over 90 stations
solution            Z (vertical)          R (along the path)    T (across the path)   node-hours
------------------------------------------------------------------------------------------------
DFDM                2.72 (7.70)           3.43 (6.66)           3.03 (40.82)          0.361
SPECFEM NEX64       3.32 (12.55)          3.57 (12.78)          4.31 (18.04)          0.530
SPECFEM NEX96       1.34 (2.52)           1.66 (4.07)           2.32 (19.52)          0.916
```

To score finished runs again, or to look at the shipped SPECFEM records without running DFDM:

```bash
python3 scripts/score_benchmark.py semucb_crust1_3d
```

## How the score is computed

Every record is turned into the three components Z, R and T, put on one time axis (200 to 4750 s after the
earthquake, every 0.5 s) and low-passed at 25 mHz (periods longer than 40 s). For each station and component:

    misfit (%) = 100 x ||record - reference|| / ||reference||

The 80-s half duration source (SPECFEM's Gaussian moment rate, used by both codes) itself carries almost no energy at
periods shorter than about 70 s: its spectrum is down to 1 % of the peak at 72 s. These are long-period benchmarks;
in SPECFEM's rule of thumb (shortest accurate period about 256 / NEX x 17 s) they sit near NEX64 (68 s).

The tables give the median over the stations and, in brackets, the worst station. In the 3-D case, components whose
reference amplitude is below 5 % of the largest station's are left out (a relative error of a near-zero record says
little). The SPECFEM record times are shifted by 1.5 half durations (120 s) onto DFDM's clock, where the source
starts at time zero.

Cost is nodes times wall time. DFDM runs 504 processes on 4 whole nodes. The SPECFEM costs in the tables were measured
on one whole Perlmutter CPU node with 96 processes, at the time step SPECFEM chooses itself, for an 80-minute record.

**About the 3-D reference.** No exact answer exists for a 3-D Earth, so the 3-D case uses SPECFEM with a fine mesh
(NEX192) as the reference. It is not the truth: SPECFEM's own NEX64 and NEX96 runs differ from each other by 2 to 3 %
on other earthquakes, so differences smaller than that are within the uncertainty of the reference.

## Output files

Everything for a case goes to `runs/<case>/`:

| file | content |
|---|---|
| `score.json` | misfit per solution, component and station, and the costs |
| `fig_records_Z.png`, `_R.png`, `_T.png` | record sections along the 12E meridian: each trace scaled to its own peak, the reference in black; right panel: differences from the reference magnified 10 times |
| `dfdm_cost.json` | DFDM wall time, nodes and node-hours |
| `dfdm_output/Uxyz_dfdm3d_geo_<station>_*.txt` | DFDM records: time (s) and displacement (m) along x, y, z of the turned mesh (the scorer turns them back with `cases/<case>/dfdm/turn.json`) |
| `run.toml`, `dfdm.log` | the DFDM run file as run, and the solver's log |

## Running SPECFEM yourself (1-D cases)

To measure SPECFEM's cost on your own machine, build SPECFEM and run the case's NEX64 input on one whole node:

```bash
bash scripts/build_specfem_perlmutter.sh     # stock SPECFEM3D_GLOBE with ASSUME_PERFECT_SPHERE set
salloc -A <account> -C cpu -q interactive -N 1 -t 01:00:00
scripts/run_specfem.sh prem_1d
```

It writes `runs/prem_1d/specfem_cost.json` and scores the run as one more row, "SPECFEM (your run)". The input is in
`cases/<case>/specfem/DATA`. `ASSUME_PERFECT_SPHERE` makes SPECFEM place stations at the same geocentric positions
as DFDM; without it every station moves by up to 21 km.

The 3-D SPECFEM records were made with a SPECFEM build that reads the same SEMUCB-WM1 table as DFDM; stock SPECFEM
cannot read it, so the 3-D case ships SPECFEM's records only.

## Options

| variable | effect |
|---|---|
| `DFDM_EXE=/path/to/dfdm_elastic3d` | use another DFDM build |
| `MODEL_DIR=/path` | where `get_3d_models.sh` writes, and `run_benchmark.sh` reads, the 3-D model tables (default `models/`) |
| `PYTHON=/path/to/python3` | the Python used by the scripts |
| `NO_SCORE=1` | run DFDM without scoring |
| `SPECFEM_ROOT=/path/to/specfem3d_globe` | use another SPECFEM build |
| `DFDM_REAL=double` | with `build_dfdm.sh`: build DFDM in double precision |

## What is in a case

`cases/<case>/` holds everything a run needs:

- `case.json`: the earthquake, the stations, the scoring settings, the reference and the SPECFEM costs.
- `dfdm/run.toml`: the DFDM run file, written by the DFDM3D mesh planner (`python3 -m automesh shells`, plus
  `near-source` and `steps-from-probe` for the 3-D case). `run_benchmark.sh` fills in the paths marked `@...@`.
- `dfdm/turn.json`: the rotation that puts the earthquake in the middle of one chunk of the cubed-sphere mesh.
- `reference/*.npz`: the reference and SPECFEM records, already in Z, R, T on DFDM's clock, sampled every second
  after an anti-alias filter at 0.2 Hz (arrays `t`, `names`, `z`, `r`, `x`).
- `specfem/DATA` (1-D cases): the SPECFEM NEX64 input.

To run another earthquake or model, write a new run file with the DFDM3D planner (see the DFDM3D README, "Running a
simulation"); the reference must then come from your own SPECFEM or DSM run.

## The published-paper benchmark

The case of the paper on the 3-D solver (AK135 without attenuation, against SPECFEM NEX320, with the paper's SPECFEM
cost anchor) is kept unchanged in `cases/ak135_mrr_hdur80_f0125`; [docs/PAPER_BENCHMARK.md](docs/PAPER_BENCHMARK.md)
explains how to run it (`scripts/run_case_slurm.sh dfdm_4800s` and related scripts).
