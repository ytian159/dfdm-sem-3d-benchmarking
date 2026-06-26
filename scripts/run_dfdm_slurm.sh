#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
case_name="${1:-pilot_nex60_sem256_720s}"

if [[ "${NO_STAGE:-0}" != "1" ]]; then
  if [[ "${FORCE_STAGE:-0}" == "1" || ! -s "$repo/runs/$case_name/case_metadata.json" ]]; then
    python3 "$repo/scripts/stage_cases.py" --case "$case_name" --force
  fi
fi

eval "$(python3 "$repo/scripts/case_env.py" "$case_name")"

export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MPICH_MAX_THREAD_SAFETY="${MPICH_MAX_THREAD_SAFETY:-serialized}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-close}"
export OMP_PLACES="${OMP_PLACES:-cores}"

dfdm_exe="${DFDM_EXE:-$repo/build/dfdm/dfdm_elastic3d}"
test -x "$dfdm_exe" || { echo "Missing $dfdm_exe; run scripts/build_dfdm.sh or set DFDM_EXE." >&2; exit 2; }

echo "=== DFDM solver start $(date) ==="
cd "$repo"
rm -rf "$DFDM_OUTPUT"
DFDM_MPI_PARTITION_MODE="${DFDM_MPI_PARTITION_MODE:-block3d}" \
/usr/bin/time -p srun -N "$DFDM_NODES" -n "$DFDM_TASKS" -c "$CPUS_PER_TASK" --cpu-bind=cores \
  "$dfdm_exe" "$DFDM_CONFIG" \
  --no-print-config --no-axis-counters --axis-kernel-mode fixed --sat-face-cache on \
  --perf-summary "$CASE_DIR/dfdm_perf.json" \
  > "$CASE_DIR/dfdm.out" \
  2> "$CASE_DIR/dfdm.time"
echo "=== DFDM done $(date) ==="
