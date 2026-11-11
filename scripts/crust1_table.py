#!/usr/bin/env python3
"""Write CRUST1.0 on a regular grid, exactly as SPECFEM3D_GLOBE 8.1 evaluates it, for DFDM's [material] crust_file.

    python3 scripts/crust1_table.py <out.txt> --crust1-dir <SPECFEM>/DATA/crust1.0 [--step 0.25]

SPECFEM does not use CRUST1.0's 1-degree cells directly: it averages each point over a cap of 80 points about 1 degree
wide (wider toward the Andes), gives sediments thinner than 2 km the upper-crust values, and leaves out ice and water
(src/meshfem3D/model_crust_1_0.f90 and src/shared/smooth_weights_vec.F90). This script does the same at every grid
node and writes, for the six layers below the water (three sediment layers, upper, middle and lower crust), the
thickness (km), vp, vs (km/s) and density (g/cm3). Latitudes are geocentric, as in SPECFEM built with
ASSUME_PERFECT_SPHERE and in DFDM. About half a minute of numpy.
"""
import argparse, math, sys
import numpy as np
CRUST = None             # set from --crust1-dir
NP, NLA, NLO = 9, 180, 360
NTHETA, NPHI = 4, 20
CAP0, MIN_SED = 1.0, 2.0
LAT_A, LON_A, RANGE_A = -20.0, -70.0, 70.0
SMALL = 1.0e-10           # SMALL_VAL_ANGLE

def load():
    """Arrays [layer, icolat-1, ilon-1] in file order (colatitude rows from the north, longitude from -180)."""
    out = {}
    for k in ("vp", "vs", "rho", "bnds"):
        a = np.loadtxt("%s/crust1.%s" % (CRUST, k)).reshape(NLA, NLO, NP)
        out[k] = np.transpose(a, (2, 0, 1))
    th = np.zeros((NP, NLA, NLO))
    th[:NP - 1] = -(out["bnds"][1:] - out["bnds"][:-1])
    return out["vp"], out["vs"], out["rho"], th

def init(crust_dir):
    """Read the four CRUST1.0 files and apply the minimum-sediment rule per cell, as SPECFEM's cap loop does."""
    global CRUST, VP, VS, RHO, TH, VPm, VSm, RHOm
    CRUST = crust_dir
    VP, VS, RHO, TH = load()
    sed = TH[2] + TH[3] + TH[4]
    thin = sed < MIN_SED
    VPm, VSm, RHOm = VP.copy(), VS.copy(), RHO.copy()
    for k in (2, 3, 4):
        VPm[k][thin] = VP[5][thin]; VSm[k][thin] = VS[5][thin]; RHOm[k][thin] = RHO[5][thin]

def cap_points(lat, lon):
    """SPECFEM's cap: lat, lon arrays (n,) -> xlat, xlon (n, 80), weight (n, 80)."""
    lat = np.where(lat == 90.0, 89.9999, np.where(lat == -90.0, -89.9999, lat))
    lon = np.where(lon == 180.0, 179.9999, np.where(lon == -180.0, -179.9999, lon))
    cap = np.full(lat.shape, CAP0)
    dist = np.sqrt((lon - LON_A) ** 2 + (lat - LAT_A) ** 2)
    inside = dist < RANGE_A
    dd = dist / RANGE_A - 1.0
    cap = np.where(inside, cap + (1.0 - np.exp(-dd * dd * 10.0)), cap)
    CAP = np.radians(cap)
    dtheta = 0.5 * CAP / NTHETA
    dphi = 2 * np.pi / NPHI
    cap_area = 2 * np.pi * (1.0 - np.cos(CAP))
    dweight = CAP / NTHETA * dphi / cap_area
    theta = np.radians(90.0 - lat); phi = np.radians(lon)
    st, ct, sp, cp = np.sin(theta), np.cos(theta), np.sin(phi), np.cos(phi)
    Rm = np.stack([np.stack([cp * ct, -sp, cp * st], -1), np.stack([sp * ct, cp, sp * st], -1),
                   np.stack([-st, np.zeros_like(st), ct], -1)], -2)          # (n, 3, 3)
    it = np.arange(1, NTHETA + 1); ip = np.arange(1, NPHI + 1)
    th_c = (2 * it - 1)[None, :] * dtheta[:, None]                          # (n, 4)
    w = np.repeat(np.sin(th_c) * dweight[:, None], NPHI, axis=1)             # (n, 80), itheta outer
    ph_c = (2 * ip - 1) * np.pi / NPHI
    tt = np.repeat(th_c, NPHI, axis=1); pp = np.tile(ph_c, NTHETA)[None, :]
    xc = np.stack([np.sin(tt) * np.cos(pp), np.sin(tt) * np.sin(pp), np.cos(tt) + 0 * pp], -1)   # (n, 80, 3)
    x = np.einsum("nij,nkj->nki", Rm, xc)
    xm, ym, zm = x[..., 0].copy(), x[..., 1].copy(), x[..., 2].copy()
    zm = np.where((zm > -SMALL) & (zm <= 0), -SMALL, np.where((zm < SMALL) & (zm >= 0), SMALL, zm))
    th_r = np.arctan2(np.sqrt(xm * xm + ym * ym), zm)
    xm = np.where((xm > -SMALL) & (xm <= 0), -SMALL, np.where((xm < SMALL) & (xm >= 0), SMALL, xm))
    ph_r = np.arctan2(ym, xm)
    # reduce() (src/shared/reduce.f90): a nudge of 1e-7 rad off the polar axis and off phi = 0 (TINYVAL 1e-9), then
    # phi brought into [0, 2 pi) by whole turns; theta from atan2 already lies in [0, pi]
    th_r = np.where(np.abs(th_r) < 1.0e-9, th_r + 1.0e-7, th_r)
    ph_r = np.where(np.abs(ph_r) < 1.0e-9, ph_r + 1.0e-7, ph_r)
    ph_r = np.where(ph_r < 0.0, ph_r + 2 * np.pi, ph_r)
    xlat = np.degrees(np.pi / 2 - th_r)
    xlon = np.degrees(ph_r)
    xlon = np.where(xlon > 180.0, xlon - 360.0, xlon)
    tot = w.sum(1)
    assert np.all(abs(tot - 1.0) <= 0.001), tot.min()
    return xlat, xlon, w

def smoothed(lat, lon):
    """(6 layers, n) thickness, vp, vs, rho of layers 3..8 (sediments 1-3, upper, middle, lower crust)."""
    xlat, xlon, w = cap_points(np.asarray(lat, float), np.asarray(lon, float))
    icol = (1 + (90.0 - xlat)).astype(int); icol = np.where(icol == 181, 180, icol)
    ilon = (1 + (180.0 + xlon)).astype(int); ilon = np.where(ilon == 361, 1, ilon)
    assert icol.min() >= 1 and icol.max() <= 180 and ilon.min() >= 1 and ilon.max() <= 360
    j, i = icol - 1, ilon - 1
    out = []
    for arr in (TH, VPm, VSm, RHOm):
        out.append(np.stack([np.sum(arr[k][j, i] * w, axis=1) for k in range(2, 8)]))
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--crust1-dir", required=True, help="SPECFEM's DATA/crust1.0 folder")
    ap.add_argument("--step", type=float, default=0.25)
    ap.add_argument("--check", type=int, default=3000)
    a = ap.parse_args()
    init(a.crust1_dir)
    if abs(180.0 / a.step - round(180.0 / a.step)) > 1e-9 or abs(360.0 / a.step - round(360.0 / a.step)) > 1e-9:
        raise SystemExit("--step must divide 180 and 360 degrees")
    nla, nlo = int(round(180.0 / a.step)) + 1, int(round(360.0 / a.step))
    dla, dlo = 180.0 / (nla - 1), 360.0 / nlo
    lats = -90.0 + dla * np.arange(nla)
    lons = -180.0 + dlo * np.arange(nlo)
    LA, LO = np.meshgrid(lats, lons, indexing="ij")
    fields = [np.zeros((6,) + LA.shape) for _ in range(4)]
    rows = 2000
    flat_la, flat_lo = LA.ravel(), LO.ravel()
    for s in range(0, flat_la.size, rows * 40):
        e = min(flat_la.size, s + rows * 40)
        part = smoothed(flat_la[s:e], flat_lo[s:e])
        for f, p in zip(fields, part):
            f.reshape(6, -1)[:, s:e] = p
    th, vp, vs, rho = fields
    moho = th.sum(0)
    print("grid %d x %d at %g deg; smoothed Moho %.2f to %.2f km; slowest vs in a layer thicker than 0.1 km %.3f km/s; upper-crust vs %.3f to %.3f" % (
        len(lats), len(lons), a.step, moho.min(), moho.max(), vs[th > 0.1].min(), vs[3].min(), vs[3].max()))
    with open(a.out, "w") as f:
        f.write("crust3d 1\nsource CRUST1.0 as SPECFEM3D_GLOBE 8.1 model_crust_1_0 (cap smoothing, 2-km sediment rule, no ice or water)\n")
        f.write("nlat %d lat0 -90 dlat %r\nnlon %d lon0 -180 dlon %r\nnlayers 6\nfields thickness_km vp_kms vs_kms rho_gcc\ndata\n" % (len(lats), dla, len(lons), dlo))
        for fld in (th, vp, vs, rho):
            for k in range(6):
                np.savetxt(f, fld[k], fmt="%.6g")
    # check: bilinear from the grid against SPECFEM's formula at random points
    rng = np.random.default_rng(7)
    qa = np.degrees(np.arcsin(rng.uniform(-1, 1, a.check))); qo = rng.uniform(-180, 180, a.check)
    ex = smoothed(qa, qo)
    fi = (qa + 90.0) / dla; i0 = np.clip(np.floor(fi).astype(int), 0, len(lats) - 2); gi = fi - i0
    fj = (qo + 180.0) / dlo; j0 = np.floor(fj).astype(int) % len(lons); j1 = (j0 + 1) % len(lons); gj = fj - np.floor(fj)
    def bil(F):
        return (F[:, i0, j0] * (1 - gi) * (1 - gj) + F[:, i0, j1] * (1 - gi) * gj + F[:, i0 + 1, j0] * gi * (1 - gj) + F[:, i0 + 1, j1] * gi * gj)
    gm = bil(th).sum(0); em = ex[0].sum(0)
    print("check at %d random points: Moho |grid - exact| median %.3f, 99th %.3f, max %.3f km; vs layers max |diff| %.3f km/s" % (
        a.check, np.median(abs(gm - em)), np.percentile(abs(gm - em), 99), abs(gm - em).max(), abs(bil(vs) - ex[2]).max()))
