#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
case_name="${1:-pilot_nex60_sem256_720s}"
case_dir="$repo/runs/$case_name"

test -s "$case_dir/case_metadata.json" || { echo "Missing $case_dir/case_metadata.json; run scripts/stage_cases.py first." >&2; exit 2; }

export MPLCONFIGDIR="${MPLCONFIGDIR:-$repo/runs/mplconfig}"
mkdir -p "$MPLCONFIGDIR"

echo "=== SEM/DFDM comparison start $(date) ==="
COMPARE_DT="${COMPARE_DT:-0.1}" python3 "$repo/scripts/plot_sem_dfdm.py" "$case_dir" \
  | tee "$case_dir/comparison_paths.txt"
echo "=== comparison done $(date) ==="
