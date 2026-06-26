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

spec_root="${SPECFEM_ROOT:-$repo/external/specfem3d_globe}"

test -x "$spec_root/bin/xmeshfem3D" || { echo "Missing $spec_root/bin/xmeshfem3D; run scripts/build_specfem_perlmutter.sh or set SPECFEM_ROOT." >&2; exit 2; }
test -x "$spec_root/bin/xspecfem3D" || { echo "Missing $spec_root/bin/xspecfem3D; run scripts/build_specfem_perlmutter.sh or set SPECFEM_ROOT." >&2; exit 2; }

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
echo "=== SPECFEM done $(date) ==="
