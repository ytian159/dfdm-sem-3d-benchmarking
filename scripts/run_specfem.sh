#!/usr/bin/env bash
# Run SPECFEM3D_GLOBE NEX64 on a 1-D benchmark case and score it next to DFDM.
#
#   scripts/run_specfem.sh <case>        (prem_1d or ak135f_1d; inside a 1-node allocation)
#
# Uses the case's specfem/DATA (NEX64, 96 processes, attenuation on, ellipticity, gravity, rotation, topography and
# oceans off) and a SPECFEM build with ASSUME_PERFECT_SPHERE (scripts/build_specfem_perlmutter.sh). The cost is the
# solver's wall time on one whole node; the mesher is not counted. Results go to runs/<case>/specfem/.
#
# Environment: SPECFEM_ROOT (default external/specfem3d_globe), PYTHON (default python3).
set -euo pipefail

if [[ -n "${SLURM_SUBMIT_DIR:-}" && -f "$SLURM_SUBMIT_DIR/scripts/run_specfem.sh" ]]; then
  repo=$SLURM_SUBMIT_DIR
else
  repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fi
case_name="${1:?usage: scripts/run_specfem.sh <case>   (prem_1d or ak135f_1d)}"
data="$repo/cases/$case_name/specfem/DATA"
[[ -d "$data" ]] || { echo "Case '$case_name' has no SPECFEM input (only the 1-D cases do)." >&2; exit 2; }
[[ -n "${SLURM_JOB_ID:-}" ]] || {
  echo "Run this inside a Slurm allocation of one whole CPU node, for example:" >&2
  echo "  salloc -A <account> -C cpu -q interactive -N 1 -t 01:00:00" >&2
  exit 2
}
PYTHON=${PYTHON:-python3}
spec_root="${SPECFEM_ROOT:-$repo/external/specfem3d_globe}"
for b in xmeshfem3D xspecfem3D; do
  [[ -x "$spec_root/bin/$b" ]] || { echo "Missing $spec_root/bin/$b; run scripts/build_specfem_perlmutter.sh or set SPECFEM_ROOT." >&2; exit 2; }
done
grep -qE '^\s*logical, parameter :: ASSUME_PERFECT_SPHERE = \.true\.' "$spec_root/setup/constants.h" || {
  echo "SPECFEM in $spec_root was not built with ASSUME_PERFECT_SPHERE = .true.; run scripts/prepare_specfem.sh and rebuild." >&2
  exit 2
}

nproc_xi=$(awk '/^NPROC_XI/ {print $3}' "$data/Par_file")
ranks=$(( 6 * nproc_xi * nproc_xi ))
run="$repo/runs/$case_name/specfem"
rm -rf "$run"
mkdir -p "$run/DATABASES_MPI" "$run/OUTPUT_FILES" "$run/bin"
cp -r "$data" "$run/DATA"
cp "$spec_root/bin/xmeshfem3D" "$spec_root/bin/xspecfem3D" "$run/bin/"
# SPECFEM reads its model files from DATA/ (crust, topography); link the build's own.
for f in "$spec_root"/DATA/*; do
  [[ -e "$run/DATA/$(basename "$f")" ]] || ln -s "$f" "$run/DATA/$(basename "$f")"
done
cd "$run"
export OMP_NUM_THREADS=1

echo "=== SPECFEM mesher, $ranks processes, $(date) ==="
srun -N 1 -n "$ranks" -c 2 --cpu-bind=cores ./bin/xmeshfem3D > OUTPUT_FILES/mesher.log 2>&1
echo "=== SPECFEM solver, $(date) ==="
t0=$(date +%s.%N)
srun -N 1 -n "$ranks" -c 2 --cpu-bind=cores ./bin/xspecfem3D > OUTPUT_FILES/solver.log 2>&1
t1=$(date +%s.%N)
"$PYTHON" - "$t0" "$t1" "$repo/runs/$case_name" <<'EOF'
import json, os, sys
t0, t1, out = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
wall = t1 - t0
json.dump(dict(wall_s=round(wall, 2), nodes=1, node_hours=round(wall / 3600.0, 4)),
          open(os.path.join(out, "specfem_cost.json"), "w"), indent=1)
print("solver wall : %.1f s on 1 node" % wall)
print("node-hours  : %.3f" % (wall / 3600.0))
EOF
"$PYTHON" "$repo/scripts/score_benchmark.py" "$case_name" --specfem-output "$run/OUTPUT_FILES"
