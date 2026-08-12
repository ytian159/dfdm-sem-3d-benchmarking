#!/usr/bin/env python3
"""Report SPECFEM solver cost in node-hours using the published convention.

Node-hours are billed as

    node_hours = (sem_tasks * cpus_per_task / 256) * solver_wall_hours

on Perlmutter CPU nodes (128 physical cores = 256 SMT slots per node), i.e.
fractional-node accounting for sub-node runs. The wall clock is the solver
invocation only; meshing is excluded, matching the paper's cost tables.

Usage:
  sem_cost.py CASE_DIR [--json OUT.json]
"""

import argparse
import json
import re
from pathlib import Path


SLOTS_PER_NODE = 256


def first_real_seconds(path):
    """/usr/bin/time -p wrapping srun: every rank appends its own block."""
    if not path.is_file():
        return None
    for line in path.read_text().splitlines():
        m = re.match(r"^\s*real\s+([0-9.]+)\s*$", line)
        if m:
            return float(m.group(1))
    return None


def solver_internals(path):
    """Pull SPECFEM's own time-loop totals out of output_solver.txt."""
    out = {}
    if not path.is_file():
        return out
    text = path.read_text()
    m = re.findall(r"Total elapsed time in seconds\s*=\s*([0-9.E+-]+)", text)
    if m:
        out["solver_total_elapsed_seconds"] = float(m[-1])
    m = re.findall(r"Mean elapsed time per time step in seconds\s*=\s*([0-9.E+-]+)", text)
    if m:
        out["ms_per_step"] = 1000.0 * float(m[-1])
    m = re.findall(r"Time steps done\s*=\s*(\d+)\s+out of\s+(\d+)", text)
    if m:
        out["time_steps_done"] = int(m[-1][0])
        out["time_steps_total"] = int(m[-1][1])
    m = re.search(r"Writing the seismograms by main proc alone took\s*([0-9.E+-]+)", text)
    if m:
        out["seismogram_write_seconds"] = float(m.group(1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case_dir")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args()

    case_dir = Path(args.case_dir).resolve()
    meta = json.loads((case_dir / "case_metadata.json").read_text())
    slurm = meta["slurm"]
    tasks = int(slurm["sem_tasks"])
    cpus = int(slurm["cpus_per_task"])
    node_fraction = tasks * cpus / float(SLOTS_PER_NODE)

    out_files = Path(meta["sem_dir"])
    if not out_files.is_absolute():
        out_files = case_dir.parents[1] / out_files
    out_files = out_files / "OUTPUT_FILES"

    solver_wall = first_real_seconds(out_files / "output_solver.time")
    mesher_wall = first_real_seconds(out_files / "output_mesher.time")
    if solver_wall is None:
        raise SystemExit("no solver wall clock in %s/output_solver.time" % out_files)

    perf = {
        "case": meta["name"],
        "sem_nex": meta["sem_nex"],
        "sem_nproc": meta.get("sem_nproc"),
        "sem_dt": meta["sem_dt"],
        "record_minutes": meta["record_minutes"],
        "sem_tasks": tasks,
        "cpus_per_task": cpus,
        "node_fraction": node_fraction,
        "solver_wall_seconds": solver_wall,
        "node_hours": node_fraction * solver_wall / 3600.0,
        "mesher_wall_seconds": mesher_wall,
        "convention": "node_hours = tasks*cpus/256 * solver_wall_hours; mesher excluded",
    }
    perf.update(solver_internals(out_files / "output_solver.txt"))

    json_out = Path(args.json_out) if args.json_out else case_dir / "sem_perf.json"
    json_out.write_text(json.dumps(perf, indent=2) + "\n")

    print("case            : %s" % perf["case"])
    print("SEM mesh        : NEX %d, NPROC %s, DT %g, %g record minutes"
          % (perf["sem_nex"], perf["sem_nproc"], perf["sem_dt"], perf["record_minutes"]))
    print("layout          : %d ranks x %d cpus = %.4f node" % (tasks, cpus, node_fraction))
    print("solver wall     : %.1f s" % solver_wall)
    if mesher_wall is not None:
        print("mesher wall     : %.1f s (excluded from node-hours)" % mesher_wall)
    if "ms_per_step" in perf:
        print("time loop       : %d steps, %.1f ms/step"
              % (perf.get("time_steps_total", 0), perf["ms_per_step"]))
    print("NODE-HOURS      : %.4f" % perf["node_hours"])
    print("wrote %s" % json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
