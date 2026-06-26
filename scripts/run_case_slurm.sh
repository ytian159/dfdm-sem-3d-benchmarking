#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
case_name="${1:-pilot_nex60_sem256_720s}"

if [[ "${NO_STAGE:-0}" != "1" ]]; then
  python3 "$repo/scripts/stage_cases.py" --case "$case_name" --force
fi

eval "$(python3 "$repo/scripts/case_env.py" "$case_name")"

export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MPICH_MAX_THREAD_SAFETY="${MPICH_MAX_THREAD_SAFETY:-serialized}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-close}"
export OMP_PLACES="${OMP_PLACES:-cores}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-$repo/runs/mplconfig}"
mkdir -p "$MPLCONFIGDIR"

spec_root="${SPECFEM_ROOT:-$repo/external/specfem3d_globe}"
dfdm_exe="${DFDM_EXE:-$repo/build/dfdm/dfdm_elastic3d}"

test -x "$spec_root/bin/xmeshfem3D" || { echo "Missing $spec_root/bin/xmeshfem3D; run scripts/build_specfem_perlmutter.sh or set SPECFEM_ROOT." >&2; exit 2; }
test -x "$spec_root/bin/xspecfem3D" || { echo "Missing $spec_root/bin/xspecfem3D; run scripts/build_specfem_perlmutter.sh or set SPECFEM_ROOT." >&2; exit 2; }
test -x "$dfdm_exe" || { echo "Missing $dfdm_exe; run scripts/build_dfdm.sh or set DFDM_EXE." >&2; exit 2; }

echo "=== SPECFEM mesher start $(date) ==="
cd "$SEM_DIR"
rm -rf DATABASES_MPI OUTPUT_FILES bin
mkdir -p DATABASES_MPI OUTPUT_FILES bin
cp "$spec_root/bin/xmeshfem3D" bin/
cp "$spec_root/bin/xspecfem3D" bin/
/usr/bin/time -p srun -N "$SEM_NODES" -n "$SEM_TASKS" -c "$CPUS_PER_TASK" --cpu-bind=cores \
  ./bin/xmeshfem3D > OUTPUT_FILES/output_mesher.txt 2> OUTPUT_FILES/output_mesher.time

echo "=== SPECFEM solver start $(date) ==="
/usr/bin/time -p srun -N "$SEM_NODES" -n "$SEM_TASKS" -c "$CPUS_PER_TASK" --cpu-bind=cores \
  ./bin/xspecfem3D > OUTPUT_FILES/output_solver.txt 2> OUTPUT_FILES/output_solver.time

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

echo "=== SEM/DFDM comparison start $(date) ==="
COMPARE_DT="${COMPARE_DT:-0.1}" python3 "$repo/scripts/plot_sem_dfdm.py" "$CASE_DIR" \
  | tee "$CASE_DIR/comparison_paths.txt"
echo "=== done $(date) ==="
