#!/usr/bin/env python3
"""Plot SEM/DFDM Z waveforms and residuals for a staged case."""

import glob
import json
import math
import os
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
STATIONS = ["AZ%02d" % i for i in range(1, 19)]
LATS = [16, 26, 36, 46, 56, 66, 76, 86, 84, 74, 64, 54, 44, 34, 24, 14, 4, -1]
LONS = [12] * 8 + [-168] * 10
DISTS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 175]
SOURCE_SHIFT = 120.0
BASELINE_END = 48.0


def resolve_path(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def local_basis(lat_deg, lon_deg):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    radial = np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])
    east = np.array([-math.sin(lon), math.cos(lon), 0.0])
    north = np.cross(radial, east)
    return east, north, radial


def load_sem(sem_output, sta):
    out = {}
    for comp in "ENZ":
        path = sem_output / ("DF.%s.BX%s.sem.ascii" % (sta, comp))
        d = np.loadtxt(str(path))
        t = d[:, 0] + SOURCE_SHIFT
        v = d[:, 1].copy()
        pre = (t >= 0.0) & (t <= BASELINE_END)
        if np.any(pre):
            v -= float(v[pre].mean())
        out["t"] = t
        out[comp.lower()] = v
    return out


def load_dfdm(dfdm_dir, sta, lat, lon):
    matches = sorted(glob.glob(str(dfdm_dir / ("Uxyz_dfdm3d_geo_%s_nex*_N*.txt" % sta))))
    if not matches:
        matches = sorted(glob.glob(str(dfdm_dir / ("Uxyz_dfdm3d_%s_nex*_N*.txt" % sta))))
    if not matches:
        raise FileNotFoundError("missing DFDM output for %s in %s" % (sta, dfdm_dir))
    d = np.loadtxt(matches[0])
    e_v, n_v, z_v = local_basis(lat, lon)
    xyz = d[:, 1:4]
    return {"t": d[:, 0], "e": xyz @ e_v, "n": xyz @ n_v, "z": xyz @ z_v}


def resample(rec, t_common):
    return {c: np.interp(t_common, rec["t"], rec[c]) for c in ("e", "n", "z")}


def rms_pct(test, base):
    den = float(np.sqrt(np.mean(base * base)))
    if den <= 0.0:
        return float("nan")
    return 100.0 * float(np.sqrt(np.mean((test - base) ** 2))) / den


def peak_ratio(test, base):
    den = float(np.max(np.abs(base)))
    if den <= 0.0:
        return float("nan")
    return float(np.max(np.abs(test))) / den


def load_rows(case_dir, dt):
    meta = json.loads((case_dir / "case_metadata.json").read_text())
    sem_output = resolve_path(meta["sem_dir"]) / "OUTPUT_FILES"
    dfdm_dir = resolve_path(meta["dfdm_output"])
    rows = []

    for sta, lat, lon, dist in zip(STATIONS, LATS, LONS, DISTS):
        sem = load_sem(sem_output, sta)
        dfdm = load_dfdm(dfdm_dir, sta, lat, lon)
        tmax = min(float(sem["t"][-1]), float(dfdm["t"][-1]))
        t = np.arange(0.0, tmax + 0.5 * dt, dt)
        sem_i = resample(sem, t)
        dfdm_i = resample(dfdm, t)
        s = sem_i["z"]
        d = dfdm_i["z"]
        scale = max(float(np.max(np.abs(s))), float(np.max(np.abs(d))), 1.0e-300)
        rows.append({
            "station": sta,
            "distance_deg": dist,
            "t": t,
            "sem": s,
            "dfdm": d,
            "diff": d - s,
            "scale": scale,
            "rms_pct": rms_pct(d, s),
            "peak_ratio": peak_ratio(d, s),
        })
    return rows


def configure_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.size": 22,
        "axes.titlesize": 27,
        "axes.labelsize": 23,
        "legend.fontsize": 18,
        "xtick.labelsize": 18,
        "ytick.labelsize": 16,
        "lines.linewidth": 1.7,
    })
    return plt


def label_for(row):
    return "%s %d deg Uz" % (row["station"], row["distance_deg"])


def draw_overlay(ax, row, show_legend):
    t = row["t"]
    scale = row["scale"]
    ax.plot(t, row["sem"] / scale, color="tab:blue", label="SEM")
    ax.plot(t, row["dfdm"] / scale, color="tab:red", ls="--", label="DFDM")
    ax.set_ylim(-1.12, 1.12)
    ax.set_ylabel(label_for(row), fontsize=18)
    ax.text(
        0.99,
        0.86,
        "RMS %.1f%%  peak %.3f" % (row["rms_pct"], row["peak_ratio"]),
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=16,
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.72),
    )
    if show_legend:
        ax.legend(loc="upper left", ncol=2, frameon=False)
    ax.grid(alpha=0.18)


def draw_diff(ax, row, show_legend):
    t = row["t"]
    y = row["diff"] / row["scale"]
    ax.plot(t, y, color="tab:purple", label="DFDM - SEM")
    ax.axhline(0.0, color="k", lw=0.7)
    ymax = max(0.04, 1.12 * float(np.max(np.abs(y))))
    ax.set_ylim(-ymax, ymax)
    ax.set_ylabel(label_for(row), fontsize=18)
    ax.text(
        0.99,
        0.86,
        "RMS %.1f%%" % row["rms_pct"],
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=16,
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.72),
    )
    if show_legend:
        ax.legend(loc="upper left", frameon=False)
    ax.grid(alpha=0.18)


def save_metrics(case_dir, rows):
    out = case_dir / "resolved_ppw_sem_dfdm_metrics.md"
    vals = [row["rms_pct"] for row in rows if math.isfinite(row["rms_pct"])]
    peak_vals = [row["peak_ratio"] for row in rows if math.isfinite(row["peak_ratio"])]
    lines = [
        "# SEM/DFDM Z Comparison",
        "",
        "- Reference: SEM",
        "- Test: DFDM",
        "- Stations: %d" % len(rows),
        "- Median Z RMS difference: %.2f %%" % float(np.median(vals)),
        "- Median Z peak ratio DFDM/SEM: %.4f" % float(np.median(peak_vals)),
        "",
        "| station | dist deg | DFDM/SEM Z RMS % | Z peak ratio DFDM/SEM |",
        "|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append("| %s | %d | %.2f | %.4f |" %
                     (row["station"], row["distance_deg"], row["rms_pct"], row["peak_ratio"]))
    out.write_text("\n".join(lines) + "\n")
    return out


def main():
    if len(sys.argv) != 2:
        print("usage: plot_sem_dfdm.py CASE_DIR", file=sys.stderr)
        return 2
    case_dir = Path(sys.argv[1]).resolve()
    dt = float(os.environ.get("COMPARE_DT", "0.1"))
    rows = load_rows(case_dir, dt)
    plt = configure_matplotlib()
    fig_h = 2.75 * len(rows)

    fig, axes = plt.subplots(len(rows), 1, figsize=(18, fig_h), sharex=True, squeeze=False)
    for i, row in enumerate(rows):
        draw_overlay(axes[i, 0], row, i == 0)
        if i == 0:
            axes[i, 0].set_title("AK135 Mrr hdur80 Z: SEM vs DFDM")
        if i == len(rows) - 1:
            axes[i, 0].set_xlabel("time (s)")
    fig.tight_layout()
    overlay_out = case_dir / "resolved_ppw_sem_dfdm_Z.png"
    fig.savefig(str(overlay_out), dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(len(rows), 1, figsize=(18, fig_h), sharex=True, squeeze=False)
    for i, row in enumerate(rows):
        draw_diff(axes[i, 0], row, i == 0)
        if i == 0:
            axes[i, 0].set_title("AK135 Mrr hdur80 Z: DFDM - SEM")
        if i == len(rows) - 1:
            axes[i, 0].set_xlabel("time (s)")
    fig.tight_layout()
    diff_out = case_dir / "resolved_ppw_sem_dfdm_diff_Z.png"
    fig.savefig(str(diff_out), dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(len(rows), 2, figsize=(24, fig_h), sharex=True, squeeze=False)
    for i, row in enumerate(rows):
        draw_overlay(axes[i, 0], row, i == 0)
        draw_diff(axes[i, 1], row, i == 0)
        if i == 0:
            axes[i, 0].set_title("SEM vs DFDM")
            axes[i, 1].set_title("DFDM - SEM")
        if i == len(rows) - 1:
            axes[i, 0].set_xlabel("time (s)")
            axes[i, 1].set_xlabel("time (s)")
    fig.tight_layout()
    combo_out = case_dir / "resolved_ppw_sem_dfdm_compare_diff_Z.png"
    fig.savefig(str(combo_out), dpi=150)
    plt.close(fig)

    metrics_out = save_metrics(case_dir, rows)
    for path in (overlay_out, diff_out, combo_out, metrics_out):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
