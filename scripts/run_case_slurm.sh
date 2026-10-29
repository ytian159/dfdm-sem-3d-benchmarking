#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
case_name="${1:?usage: run_case_slurm.sh CASE}"

if [[ "${NO_STAGE:-0}" != "1" ]]; then
  if [[ "${FORCE_STAGE:-0}" == "1" || ! -s "$repo/runs/$case_name/case_metadata.json" ]]; then
    python3 "$repo/scripts/stage_cases.py" --case "$case_name" --force
  fi
fi

eval "$(python3 "$repo/scripts/case_env.py" "$case_name")"

NO_STAGE=1 "$repo/scripts/run_sem_slurm.sh" "$case_name"
if [[ "${HAS_DFDM:-1}" == "1" ]]; then
  NO_STAGE=1 "$repo/scripts/run_dfdm_slurm.sh" "$case_name"
  "$repo/scripts/compare_case.sh" "$case_name"
else
  echo "=== SEM-only case; skipping DFDM run and SEM/DFDM comparison ==="
  echo "Score it against a reference member with scripts/compare_sem_members.sh"
fi
echo "=== done $(date) ==="
