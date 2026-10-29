#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
case_name="${1:?usage: compare_case.sh CASE}"
case_dir="$repo/runs/$case_name"

test -s "$case_dir/case_metadata.json" || { echo "Missing $case_dir/case_metadata.json; run scripts/stage_cases.py first." >&2; exit 2; }

export MPLCONFIGDIR="${MPLCONFIGDIR:-$repo/runs/mplconfig}"
mkdir -p "$MPLCONFIGDIR"

eval "$(python3 "$repo/scripts/case_env.py" "$case_name")"

echo "=== SEM/DFDM comparison start $(date) ==="
COMPARE_DT="${COMPARE_DT:-0.1}" python3 "$repo/scripts/plot_sem_dfdm.py" "$case_dir" \
  | tee "$case_dir/comparison_paths.txt"
# Accuracy gate against the SEM seismograms (needs records through 4750 s).
python3 "$repo/scripts/score_sem_members.py" "$DFDM_OUTPUT" "$SEM_DIR/OUTPUT_FILES" \
  --label "$case_name: DFDM vs SEM" --test-name DFDM --ref-name SEM-Ref \
  --json "$case_dir/dfdm_score.json" --figure "$case_dir/dfdm_score.png" \
  --source-shift "${SOURCE_SHIFT:-120}"
echo "=== comparison done $(date) ==="
