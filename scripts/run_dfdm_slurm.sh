#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
case_name="${1:?usage: run_dfdm_slurm.sh CASE}"

if [[ "${NO_STAGE:-0}" != "1" ]]; then
  if [[ "${FORCE_STAGE:-0}" == "1" || ! -s "$repo/runs/$case_name/case_metadata.json" ]]; then
    python3 "$repo/scripts/stage_cases.py" --case "$case_name" --force
  fi
fi

eval "$(python3 "$repo/scripts/case_env.py" "$case_name")"

if [[ "${HAS_DFDM:-1}" != "1" ]]; then
  echo "Case $case_name is SEM-only (no DFDM arm); nothing to run." >&2
  exit 2
fi

export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MPICH_MAX_THREAD_SAFETY="${MPICH_MAX_THREAD_SAFETY:-serialized}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-close}"
export OMP_PLACES="${OMP_PLACES:-cores}"
# The benchmark mesh varies the lateral element count by layer.
export DFDM_ALLOW_LATERAL_BANDS_EXPERIMENTAL=1

dfdm_exe="${DFDM_EXE:-$repo/build/dfdm/dfdm_elastic3d}"
test -x "$dfdm_exe" || { echo "Missing $dfdm_exe; run scripts/build_dfdm.sh or set DFDM_EXE." >&2; exit 2; }

echo "=== DFDM solver start $(date) ==="
cd "$repo"
rm -rf "$DFDM_OUTPUT"
DFDM_MPI_PARTITION_MODE="${DFDM_MPI_PARTITION_MODE:-cost}" \
/usr/bin/time -p srun -N "$DFDM_NODES" -n "$DFDM_TASKS" -c "$CPUS_PER_TASK" --cpu-bind=cores --mem=0 \
  "$dfdm_exe" "$DFDM_CONFIG" \
  --no-print-config --no-axis-counters --axis-kernel-mode fixed --sat-face-cache on --mpi-halo-mode face \
  --perf-summary "$CASE_DIR/dfdm_perf.json" \
  > "$CASE_DIR/dfdm.out" \
  2> "$CASE_DIR/dfdm.time"
echo "=== DFDM done $(date) ==="

# DFDM runs on whole nodes, so the cost is nodes x wall time of the solver invocation.
wall=$(awk '/^real /{print $2; exit}' "$CASE_DIR/dfdm.time")
awk -v w="$wall" -v n="$DFDM_NODES" -v r="$DFDM_TASKS" -v c="$CPUS_PER_TASK" 'BEGIN {
  printf "layout          : %d ranks x %d cpus on %d nodes\n", r, c, n
  printf "solver wall     : %.1f s\n", w
  printf "NODE-HOURS      : %.3f\n", n * w / 3600.0
}' | tee "$CASE_DIR/dfdm_cost.txt"
