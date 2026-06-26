#!/usr/bin/env python3
"""Print shell assignments for a staged case."""

import argparse
import json
import shlex
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    args = parser.parse_args()
    meta_path = ROOT / "runs" / args.case / "case_metadata.json"
    meta = json.loads(meta_path.read_text())
    slurm = meta["slurm"]
    values = {
        "CASE_NAME": meta["name"],
        "CASE_DIR": str((ROOT / "runs" / args.case).resolve()),
        "SEM_DIR": str((ROOT / meta["sem_dir"]).resolve()),
        "DFDM_CONFIG": str((ROOT / meta["dfdm_config"]).resolve()),
        "DFDM_OUTPUT": str((ROOT / meta["dfdm_output"]).resolve()),
        "SEM_NODES": slurm["sem_nodes"],
        "SEM_TASKS": slurm["sem_tasks"],
        "DFDM_NODES": slurm["dfdm_nodes"],
        "DFDM_TASKS": slurm["dfdm_tasks"],
        "CPUS_PER_TASK": slurm["cpus_per_task"],
    }
    for key, value in values.items():
        print("export %s=%s" % (key, shlex.quote(str(value))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
