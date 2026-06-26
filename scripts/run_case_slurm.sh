#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
case_name="${1:-pilot_nex60_sem256_720s}"

if [[ "${NO_STAGE:-0}" != "1" ]]; then
  python3 "$repo/scripts/stage_cases.py" --case "$case_name" --force
fi

NO_STAGE=1 "$repo/scripts/run_sem_slurm.sh" "$case_name"
NO_STAGE=1 "$repo/scripts/run_dfdm_slurm.sh" "$case_name"
"$repo/scripts/compare_case.sh" "$case_name"
echo "=== done $(date) ==="
