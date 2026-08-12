#!/usr/bin/env python3
"""Score one SPECFEM member against a SPECFEM reference (paper gate protocol).

This is the convergence test that qualifies a cheap SEM mesh as the cost
anchor: a member passes when all 36 N/Z station-components reach >= 0.995
full-trace correlation against the reference at BOTH the 3600 s and 4750 s
horizons, with the antipodal PKP window reported alongside.

Channel names differ by mesh size (NEX < 128 writes MX*, NEX >= 128 writes
BX*), so channels are globbed as ?X. The E component is near-nodal for this
source-receiver geometry and is excluded, matching the published protocol.

Usage:
  score_sem_members.py TEST_OUTPUT_FILES REF_OUTPUT_FILES [--label NAME]
      [--json OUT.json] [--figure OUT.png] [--source-shift 120]
"""

import argparse
import glob
import json
import math
import os
from pathlib import Path

import numpy as np


STATIONS = ["AZ%02d" % i for i in range(1, 19)]
LATS = [16, 26, 36, 46, 56, 66, 76, 86, 84, 74, 64, 54, 44, 34, 24, 14, 4, -1]
LONS = [12] * 8 + [-168] * 10
DISTS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 175]

SCORED = ("N", "Z")
DT = 0.1
BASELINE_END = 48.0
PASS_BAR = 0.995
HORIZONS = (3600.0, 4750.0)
PKP_WINDOW = (1100.0, 1400.0)   # relative to the source shift, dist >= 140 deg
PKP_DIST_MIN = 140.0


def load_member(output_dir, sta, source_shift):
    """Load one station's scored traces; ?X glob covers MX and BX channels.

    Only N and Z are read: the E component is near-nodal for this
    source-receiver geometry, so it is excluded from the protocol.
    """
    out = {}
    for comp in SCORED:
        pattern = str(Path(output_dir) / ("DF.%s.?X%s.sem.ascii" % (sta, comp)))
        matches = sorted(glob.glob(pattern))
        if not matches:
            raise FileNotFoundError("no %s trace for %s in %s" % (comp, sta, output_dir))
        d = np.loadtxt(matches[0])
        t = d[:, 0] + source_shift
        v = d[:, 1].copy()
        pre = (t >= 0.0) & (t <= BASELINE_END)
        if np.any(pre):
            v -= float(v[pre].mean())
        out["t"] = t
        out[comp.lower()] = v
    return out


def resample(rec, t_common):
    return {c.lower(): np.interp(t_common, rec["t"], rec[c.lower()]) for c in SCORED}


def corr(a, b):
    den = math.sqrt(float(np.dot(a, a)) * float(np.dot(b, b)))
    return float(np.dot(a, b) / den) if den > 0.0 else 0.0


def score(test_dir, ref_dir, source_shift):
    rows = []
    for sta, lat, lon, dist in zip(STATIONS, LATS, LONS, DISTS):
        test = load_member(test_dir, sta, source_shift)
        ref = load_member(ref_dir, sta, source_shift)
        row = {"station": sta, "distance_deg": dist}
        for horizon in HORIZONS:
            tmax = min(float(test["t"][-1]), float(ref["t"][-1]), horizon)
            t = np.arange(0.0, tmax + 0.5 * DT, DT)
            a = resample(test, t)
            b = resample(ref, t)
            for comp in ("n", "z"):
                row["%s_%d" % (comp, int(horizon))] = corr(a[comp], b[comp])
            if horizon == HORIZONS[-1]:
                row["_t"] = t
                row["_test_z"] = a["z"]
                row["_ref_z"] = b["z"]
                if dist >= PKP_DIST_MIN:
                    lo, hi = source_shift + PKP_WINDOW[0], source_shift + PKP_WINDOW[1]
                    sel = (t >= lo) & (t <= hi)
                    for comp in ("n", "z"):
                        row["%s_pkp" % comp] = corr(a[comp][sel], b[comp][sel])
        rows.append(row)
    return rows


def verdict(rows):
    keys = ["%s_%d" % (c, int(h)) for h in HORIZONS for c in ("n", "z")]
    fails = []
    for row in rows:
        for key in keys:
            if row[key] < PASS_BAR:
                fails.append(("%s-%s" % (row["station"], key), row[key]))
    worst = min((row[key] for row in rows for key in keys), default=float("nan"))
    pkp_rows = [r for r in rows if r["distance_deg"] >= PKP_DIST_MIN]
    pkp_z = min((r["z_pkp"] for r in pkp_rows), default=float("nan"))
    pkp_n = min((r["n_pkp"] for r in pkp_rows), default=float("nan"))
    return {
        "components_scored": 2 * len(rows),
        "components_passing": 2 * len(rows) - len({f[0].rsplit("_", 1)[0] for f in fails}),
        "failures": sorted(fails, key=lambda kv: kv[1]),
        "worst_full_trace": worst,
        "pkp_z_min": pkp_z,
        "pkp_n_min": pkp_n,
        "pass": not fails,
    }


def make_figure(rows, path, label):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.size": 14, "axes.titlesize": 16, "axes.labelsize": 14,
        "legend.fontsize": 13, "xtick.labelsize": 13, "ytick.labelsize": 13,
        "lines.linewidth": 1.4,
    })
    fig, axes = plt.subplots(1, 2, figsize=(16, 11), sharey=True)
    peak = max(float(np.max(np.abs(r["_ref_z"]))) for r in rows)
    resid_peak = max(float(np.max(np.abs(r["_test_z"] - r["_ref_z"]))) for r in rows)
    mag = max(1.0, 0.4 * peak / resid_peak) if resid_peak > 0 else 1.0

    for i, row in enumerate(rows):
        off = i
        norm = peak
        axes[0].plot(row["_t"], off + row["_ref_z"] / norm, color="k", lw=1.1)
        axes[0].plot(row["_t"], off + row["_test_z"] / norm, color="tab:red", ls="--", lw=1.1)
        axes[1].plot(row["_t"], off + mag * (row["_test_z"] - row["_ref_z"]) / norm,
                     color="tab:blue", lw=1.0)
        for ax in axes:
            ax.text(row["_t"][0], off + 0.25, "%s  %d deg" % (row["station"], row["distance_deg"]),
                    fontsize=11, va="bottom")

    axes[0].set_title("%s: record section (Z)" % label)
    axes[1].set_title("residual (Z), magnified %.0fx" % mag)
    for ax in axes:
        ax.set_xlabel("time (s)")
        ax.set_yticks([])
        ax.grid(alpha=0.15)
    axes[0].plot([], [], color="k", label="reference")
    axes[0].plot([], [], color="tab:red", ls="--", label="member")
    axes[0].legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(str(path), dpi=140)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("test_dir")
    ap.add_argument("ref_dir")
    ap.add_argument("--label", default="SEM member vs reference")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--figure", dest="figure_out")
    ap.add_argument("--source-shift", type=float, default=120.0)
    args = ap.parse_args()

    os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig_sem_members")
    rows = score(args.test_dir, args.ref_dir, args.source_shift)
    v = verdict(rows)

    print("== %s ==" % args.label)
    print("%-6s %5s | %8s %8s | %8s %8s | %s"
          % ("sta", "deg", "n@3600", "z@3600", "n@4750", "z@4750", "PKP n/z"))
    for row in rows:
        pkp = ""
        if row["distance_deg"] >= PKP_DIST_MIN:
            pkp = "%.5f %.5f" % (row["n_pkp"], row["z_pkp"])
        print("%-6s %5d | %8.5f %8.5f | %8.5f %8.5f | %s"
              % (row["station"], row["distance_deg"],
                 row["n_3600"], row["z_3600"], row["n_4750"], row["z_4750"], pkp))

    print("\nworst full-trace correlation : %.5f (bar %.3f)" % (v["worst_full_trace"], PASS_BAR))
    print("PKP window  Z min / N min    : %.5f / %.5f" % (v["pkp_z_min"], v["pkp_n_min"]))
    if v["failures"]:
        print("below bar: %s" % ", ".join("%s %.5f" % f for f in v["failures"][:20]))
    print("VERDICT: %s (%d/%d components)"
          % ("PASS" if v["pass"] else "FAIL", v["components_passing"], v["components_scored"]))

    if args.json_out:
        payload = {
            "label": args.label,
            "test_dir": str(Path(args.test_dir).resolve()),
            "ref_dir": str(Path(args.ref_dir).resolve()),
            "source_shift": args.source_shift,
            "pass_bar": PASS_BAR,
            "horizons": list(HORIZONS),
            "verdict": v,
            "stations": [{k: r[k] for k in r if not k.startswith("_")} for r in rows],
        }
        Path(args.json_out).write_text(json.dumps(payload, indent=2) + "\n")
        print("wrote %s" % args.json_out)

    if args.figure_out:
        make_figure(rows, args.figure_out, args.label)
        print("wrote %s" % args.figure_out)

    return 0 if v["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
