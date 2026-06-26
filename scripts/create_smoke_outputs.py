#!/usr/bin/env python3
"""Create deterministic synthetic SEM/DFDM outputs for clone-time smoke tests."""

import math
import sys
from pathlib import Path

import numpy as np


STATIONS = ["AZ%02d" % i for i in range(1, 19)]
LATS = [16, 26, 36, 46, 56, 66, 76, 86, 84, 74, 64, 54, 44, 34, 24, 14, 4, -1]
LONS = [12] * 8 + [-168] * 10
DISTS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 175]


def local_basis(lat_deg, lon_deg):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    radial = np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])
    east = np.array([-math.sin(lon), math.cos(lon), 0.0])
    north = np.cross(radial, east)
    return east, north, radial


def pulse(t, center, width, freq):
    env = np.exp(-0.5 * ((t - center) / width) ** 2)
    return env * np.sin(2.0 * math.pi * freq * (t - center))


def main():
    if len(sys.argv) != 2:
        print("usage: create_smoke_outputs.py CASE_DIR", file=sys.stderr)
        return 2
    case_dir = Path(sys.argv[1]).resolve()
    sem_out = case_dir / "sem_case" / "OUTPUT_FILES"
    dfdm_out = case_dir / "DFDM_OUTPUT_ak135_mrr_hdur80_nex6_nez6"
    sem_out.mkdir(parents=True, exist_ok=True)
    dfdm_out.mkdir(parents=True, exist_ok=True)

    sem_t_native = np.arange(-120.0, 481.0, 1.0)
    physical_t = sem_t_native + 120.0
    dfdm_t = np.arange(0.0, 601.0, 1.0)

    for idx, (sta, lat, lon, dist) in enumerate(zip(STATIONS, LATS, LONS, DISTS)):
        center = 150.0 + 1.8 * dist
        z_sem = pulse(physical_t, center, 42.0, 0.0125) + 0.12 * pulse(physical_t, center + 90.0, 55.0, 0.018)
        n_sem = 0.18 * pulse(physical_t, center + 20.0, 50.0, 0.0125)
        e_sem = 0.04 * pulse(physical_t, center - 15.0, 35.0, 0.015)
        perturb = 1.0 + 0.012 * math.sin(0.7 * idx)
        z_dfdm = perturb * (pulse(dfdm_t, center + 2.0, 42.0, 0.0125) +
                            0.12 * pulse(dfdm_t, center + 92.0, 55.0, 0.018))
        n_dfdm = perturb * 0.18 * pulse(dfdm_t, center + 22.0, 50.0, 0.0125)
        e_dfdm = perturb * 0.04 * pulse(dfdm_t, center - 13.0, 35.0, 0.015)

        for comp, data in (("E", e_sem), ("N", n_sem), ("Z", z_sem)):
            arr = np.column_stack([sem_t_native, data])
            np.savetxt(str(sem_out / ("DF.%s.BX%s.sem.ascii" % (sta, comp))), arr, fmt="%.8e")

        east, north, radial = local_basis(lat, lon)
        xyz = e_dfdm[:, None] * east + n_dfdm[:, None] * north + z_dfdm[:, None] * radial
        arr = np.column_stack([dfdm_t, xyz])
        np.savetxt(str(dfdm_out / ("Uxyz_dfdm3d_geo_%s_nex6_N6.txt" % sta)), arr, fmt="%.8e")
    print(sem_out)
    print(dfdm_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
