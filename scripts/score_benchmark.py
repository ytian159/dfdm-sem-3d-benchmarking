#!/usr/bin/env python3
"""Score a DFDM run of a benchmark case against the case's reference, next to the shipped SPECFEM records.

    python3 scripts/score_benchmark.py <case> [--output DIR] [--specfem-output DIR] [--no-figures]

<case> is a folder name under cases/ (prem_1d, ak135f_1d, semucb_crust1_3d). DFDM's records are read from
runs/<case>/dfdm_output (or --output). --specfem-output adds a SPECFEM run of your own (its OUTPUT_FILES folder)
as one more row.

Every record is turned into three components: vertical (Z), along the path from the earthquake (R) and across the
path (T). All records are put on the same time axis (200-4750 s, 0.5 s), low-passed at 25 mHz (fourth-order
Butterworth, forward and backward), and compared with the reference:

    misfit (%) = 100 * ||record - reference|| / ||reference||      per station and component

The table gives the median and the worst misfit over the stations. Components whose reference amplitude is below the
case's threshold (5 % of the largest station's, for the 3-D case) are left out, because a relative misfit of a
near-zero trace is not meaningful.

Writes runs/<case>/score.json and figures runs/<case>/fig_records_<component>.png: record sections along the
earthquake's meridian, each trace scaled to its own peak, with the differences from the reference magnified 10 times.
"""

import argparse
import glob
import json
import math
import os
import sys

import numpy as np
from scipy.signal import butter, sosfiltfilt

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMP_NAMES = {"z": "vertical", "r": "along the path", "x": "across the path"}
COMP_LABEL = {"z": "Z", "r": "R", "x": "T"}
DT = 0.5


def unit(lat, lon):
    a, b = math.radians(lat), math.radians(lon)
    return np.array([math.cos(a) * math.cos(b), math.cos(a) * math.sin(b), math.sin(a)])


def path_frame(lat0, lon0, az, dist):
    """Unit vectors (up, along the path, across the path = up x along) at a station, Earth-centred axes."""
    s = unit(lat0, lon0)
    a, b = math.radians(lat0), math.radians(lon0)
    north = np.array([-math.sin(a) * math.cos(b), -math.sin(a) * math.sin(b), math.cos(a)])
    east = np.array([-math.sin(b), math.cos(b), 0.0])
    t0 = math.cos(math.radians(az)) * north + math.sin(math.radians(az)) * east
    d = math.radians(dist)
    up = math.cos(d) * s + math.sin(d) * t0
    along = -math.sin(d) * s + math.cos(d) * t0
    return up, along, np.cross(up, along)


def east_north_up(lat, lon):
    a, b = math.radians(lat), math.radians(lon)
    return (np.array([-math.sin(b), math.cos(b), 0.0]),
            np.array([-math.sin(a) * math.cos(b), -math.sin(a) * math.sin(b), math.cos(a)]),
            unit(lat, lon))


class Scorer:
    def __init__(self, case):
        self.case = case
        sc = case["scoring"]
        self.T = np.arange(sc["window_s"][0], sc["window_s"][1], DT)
        self.sos = butter(4, sc["lowpass_hz"], btype="low", fs=1.0 / DT, output="sos")
        self.comps = sc["components"]
        self.eq = case["earthquake"]

    def prep(self, t, x):
        return sosfiltfilt(self.sos, np.interp(self.T, t, x))

    def frame(self, st):
        return path_frame(self.eq["latitude_deg"], self.eq["longitude_deg"], st["azimuth_deg"], st["distance_deg"])

    def load_npz(self, path):
        d = np.load(path)
        names = [str(n) for n in d["names"]]
        out = {}
        for i, n in enumerate(names):
            out[n] = {c: self.prep(d["t"], d[c][i]) for c in self.comps}
        return out

    def load_dfdm(self, out_dir, R):
        out, short = {}, []
        for st in self.case["stations"]:
            hits = sorted(glob.glob(os.path.join(out_dir, "Uxyz_dfdm3d_geo_%s_*.txt" % st["name"])))
            if not hits:
                continue
            d = np.loadtxt(hits[0], ndmin=2)
            if d[-1, 0] < self.T[-1]:
                short.append(st["name"])
                continue
            xyz = d[:, 1:4] @ R          # mesh axes -> geographic axes (rows: u_geo = R^T u_mesh)
            up, al, ac = self.frame(st)
            v = {"z": xyz @ up, "r": xyz @ al, "x": xyz @ ac}
            out[st["name"]] = {c: self.prep(d[:, 0], v[c]) for c in self.comps}
        if short:
            print("note: %d DFDM records end before %.0f s and are left out (run not finished?)" % (len(short), self.T[-1]))
        return out

    def load_specfem(self, out_dir, baseline):
        out = {}
        for st in self.case["stations"]:
            o = {}
            for c in "ENZ":
                hits = glob.glob(os.path.join(out_dir, "*.%s.?X%s.sem.ascii" % (st["name"], c)))
                if not hits:
                    break
                d = np.loadtxt(hits[0])
                t = d[:, 0] + 1.5 * self.eq["half_duration_s"]       # SPECFEM's clock starts 1.5 half durations early
                v = d[:, 1].copy()
                if baseline:
                    v -= float(v[(t >= 0.0) & (t <= 48.0)].mean())
                o[c] = v
            if len(o) < 3:
                continue
            e, n, u = east_north_up(st["lat"], st["lon"])
            xyz = np.outer(o["E"], e) + np.outer(o["N"], n) + np.outer(o["Z"], u)
            up, al, ac = self.frame(st)
            v = {"z": xyz @ up, "r": xyz @ al, "x": xyz @ ac}
            out[st["name"]] = {c: self.prep(t, v[c]) for c in self.comps}
        return out

    def score(self, rec, ref):
        thr = self.case["scoring"].get("min_relative_amplitude", 0.0)
        row = {}
        for c in self.comps:
            norms = {k: np.linalg.norm(ref[k][c]) for k in ref}
            top = max(norms.values())
            keys = [k for k in ref if k in rec and norms[k] > thr * top]
            if not keys:
                continue
            mis = [100.0 * np.linalg.norm(rec[k][c] - ref[k][c]) / norms[k] for k in keys]
            cor = [float(np.corrcoef(rec[k][c], ref[k][c])[0, 1]) for k in keys]
            row[c] = dict(median=float(np.median(mis)), worst=float(np.max(mis)), lowest_correlation=float(np.min(cor)),
                          stations=len(keys), by_station={k: float(m) for k, m in zip(keys, mis)})
        return row


def figures(case, scorer, ref_name, ref, sets, run_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 13, "axes.titlesize": 15, "axes.labelsize": 14, "legend.fontsize": 13,
                         "xtick.labelsize": 13, "ytick.labelsize": 13})
    line = [st for st in case["stations"] if st["azimuth_deg"] == 0 and st["name"] in ref]
    colors = {"DFDM": "#c0392b", "SPECFEM NEX64": "#2471a3", "SPECFEM NEX96": "#7d3c98"}
    paths = []
    for c in scorer.comps:
        if max(np.max(np.abs(ref[st["name"]][c])) for st in line) == 0:
            continue
        mag = 10
        fig, axes = plt.subplots(1, 2, figsize=(15, 10), sharey=True)
        for st in line:
            y0 = st["distance_deg"]
            peak = np.max(np.abs(ref[st["name"]][c]))
            if peak == 0:
                continue
            k = 4.0 / peak                 # each trace scaled to its own peak, 4 degrees tall
            axes[0].plot(scorer.T, y0 + k * ref[st["name"]][c], color="k", lw=1.6)
            for name, rec in sets:
                if st["name"] in rec:
                    style = "-" if name == "DFDM" else "--"
                    axes[0].plot(scorer.T, y0 + k * rec[st["name"]][c], style, color=colors.get(name, "0.4"), lw=1.0)
                    axes[1].plot(scorer.T, y0 + mag * k * (rec[st["name"]][c] - ref[st["name"]][c]), style,
                                 color=colors.get(name, "0.4"), lw=1.0)
        axes[0].plot([], [], color="k", lw=1.6, label=ref_name)
        for name, _ in sets:
            axes[0].plot([], [], "-" if name == "DFDM" else "--", color=colors.get(name, "0.4"), label=name)
            axes[1].plot([], [], "-" if name == "DFDM" else "--", color=colors.get(name, "0.4"), label=name)
        axes[0].set_title("%s component" % COMP_NAMES[c])
        axes[1].set_title("difference from %s, magnified %dx" % (ref_name, mag))
        for ax in axes:
            ax.set_xlabel("time (s)")
            ax.set_xlim(scorer.T[0], scorer.T[-1])
            ax.legend(loc="lower right")
        axes[0].set_ylabel("distance from the earthquake (degrees)")
        axes[0].set_ylim(0, 185)
        fig.tight_layout()
        p = os.path.join(run_dir, "fig_records_%s.png" % COMP_LABEL[c])
        fig.savefig(p, dpi=110)
        plt.close(fig)
        paths.append(p)
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("case")
    ap.add_argument("--output", help="DFDM output folder (default runs/<case>/dfdm_output)")
    ap.add_argument("--specfem-output", help="OUTPUT_FILES of your own SPECFEM run, scored as one more row")
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()

    case_dir = os.path.join(REPO, "cases", a.case)
    case = json.load(open(os.path.join(case_dir, "case.json")))
    run_dir = os.path.join(REPO, "runs", a.case)
    os.makedirs(run_dir, exist_ok=True)
    out_dir = a.output or os.path.join(run_dir, "dfdm_output")
    sc = Scorer(case)

    ref_name = case["reference"]["name"]
    ref = sc.load_npz(os.path.join(case_dir, case["reference"]["file"]))
    R = np.array(json.load(open(os.path.join(case_dir, case["dfdm"]["turn_file"])))["R"])
    sets, costs = [], {}
    dfdm = sc.load_dfdm(out_dir, R)
    if dfdm:
        sets.append(("DFDM", dfdm))
        cost_file = os.path.join(run_dir, "dfdm_cost.json")
        if os.path.exists(cost_file):
            costs["DFDM"] = json.load(open(cost_file))["node_hours"]
    else:
        print("no DFDM records in %s; scoring the shipped SPECFEM records only" % out_dir)
    for o in case.get("others", []):
        sets.append((o["name"], sc.load_npz(os.path.join(case_dir, o["file"]))))
        costs[o["name"]] = o.get("node_hours")
    if a.specfem_output:
        mine = sc.load_specfem(a.specfem_output, baseline=case["earthquake"]["mechanism"].startswith("Mrr"))
        sets.append(("SPECFEM (your run)", mine))
        perf = os.path.join(run_dir, "specfem_cost.json")
        if os.path.exists(perf):
            costs["SPECFEM (your run)"] = json.load(open(perf))["node_hours"]

    result = dict(case=a.case, reference=ref_name, rows={})
    print()
    print("%s: misfit against %s, %%, median (worst) over %d stations" % (case["title"], ref_name, len(ref)))
    head = "%-20s" % "solution" + "".join("%-22s" % ("%s (%s)" % (COMP_LABEL[c], COMP_NAMES[c])) for c in sc.comps) + "node-hours"
    print(head)
    print("-" * len(head))
    for name, rec in sets:
        row = sc.score(rec, ref)
        result["rows"][name] = dict(misfit=row, node_hours=costs.get(name))
        cells = "".join("%-22s" % ("%.2f (%.2f)" % (row[c]["median"], row[c]["worst"]) if c in row else "-") for c in sc.comps)
        nh = costs.get(name)
        print("%-20s%s%s" % (name, cells, "%.3f" % nh if nh else "-"))
    print()
    json.dump(result, open(os.path.join(run_dir, "score.json"), "w"), indent=1)
    print("wrote %s" % os.path.join(run_dir, "score.json"))
    if not a.no_figures:
        for p in figures(case, sc, ref_name, ref, sets, run_dir):
            print("wrote %s" % p)


if __name__ == "__main__":
    sys.exit(main())
