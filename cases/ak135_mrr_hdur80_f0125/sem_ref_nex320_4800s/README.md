# SEM-Ref Seismograms (NEX 320, 80-minute records)

These are the SPECFEM3D_GLOBE seismograms of the SEM-Ref, the converged reference that the paper's SEM members and DFDM are scored against. Running it costs 27.8 node-hours, so the output ships here instead. The DFDM cases `dfdm_4800s` and `dfdm_720s` use it.

| | |
|---|---|
| code | SPECFEM3D_GLOBE v8.1.0, commit `b6fa4b6` (the `external/specfem3d_globe` pin), built with `ASSUME_PERFECT_SPHERE = .true.` |
| model | `1D_ak135f_no_mud`; no attenuation, oceans, ellipticity, topography, gravity or rotation |
| source | Mrr = 1e27 dyne-cm at 6° N, 12° E, 50 km depth; quasi-Heaviside, 80 s half duration |
| mesh and time step | `NEX` 320, `NPROC` 8 (384 ranks), `DT` 0.03 s, 164200 steps |
| run | June 2026 on Perlmutter: 384 ranks at `-c 2` on 3 exclusive CPU nodes, solver wall 33409 s |

## Contents

- `DATA/`: the `Par_file`, `CMTSOLUTION` and `STATIONS` the run read. They are byte-identical to what `scripts/stage_cases.py` writes for the SEM side of the DFDM cases.
- `OUTPUT_FILES/DF.AZ??.BX?.sem.ascii.xz`: all 54 traces (18 stations, E/N/Z) exactly as SPECFEM wrote them, xz-compressed. Each file has two columns: time in seconds (starting at -120 s, the source shift) and displacement in meters.
- `SHA256SUMS`: checksums of the uncompressed traces.
- `output_mesher.txt.xz`, `output_solver.txt.xz`: SPECFEM's own logs from the run.

## Use

```bash
python3 scripts/install_sem_reference.py dfdm_4800s
```

The run scripts do this automatically. It decompresses the traces into `runs/dfdm_4800s/sem_case/OUTPUT_FILES`, checks each one against `SHA256SUMS`, and refuses if the case's staged `DATA` differs from `DATA/` here. `scripts/validate_smoke.sh` runs the same checks without installing anything (`install_sem_reference.py --verify`).

To check the files by hand instead:

```bash
cd cases/ak135_mrr_hdur80_f0125/sem_ref_nex320_4800s/OUTPUT_FILES
xz -dk *.xz && sha256sum -c ../SHA256SUMS
```
