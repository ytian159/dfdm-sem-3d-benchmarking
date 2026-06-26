#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export MPLCONFIGDIR="${MPLCONFIGDIR:-$repo/runs/mplconfig_smoke}"
mkdir -p "$MPLCONFIGDIR"

python3 "$repo/scripts/stage_cases.py" --case fixture_smoke --force
python3 "$repo/scripts/create_smoke_outputs.py" "$repo/runs/fixture_smoke"
COMPARE_DT=1.0 "$repo/scripts/compare_case.sh" fixture_smoke
python3 "$repo/scripts/check_no_external_paths.py"

test -s "$repo/runs/fixture_smoke/resolved_ppw_sem_dfdm_Z.png"
test -s "$repo/runs/fixture_smoke/resolved_ppw_sem_dfdm_diff_Z.png"
test -s "$repo/runs/fixture_smoke/resolved_ppw_sem_dfdm_compare_diff_Z.png"
test -s "$repo/runs/fixture_smoke/resolved_ppw_sem_dfdm_metrics.md"
echo "Smoke validation passed."
