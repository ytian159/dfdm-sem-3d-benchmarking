#!/usr/bin/env bash
# Run DFDM on one benchmark case and score it.
#
#   scripts/run_benchmark.sh <case>        (inside a 4-node allocation)
#
# <case> is prem_1d, ak135f_1d or semucb_crust1_3d. The run goes to runs/<case>/: the run file with its paths
# filled in (run.toml), DFDM's records (dfdm_output/), the solver log (dfdm.log), the cost (dfdm_cost.json) and,
# after scoring, score.json and the figures.
#
# Environment:
#   DFDM_EXE    the solver (default build/dfdm/dfdm_elastic3d, made by scripts/build_dfdm.sh)
#   MODEL_DIR   the 3-D model tables (default models/, made by scripts/get_3d_models.sh)
#   PYTHON      Python with numpy, scipy and matplotlib (default python3)
#   NO_SCORE=1  run only
set -euo pipefail

if [[ -n "${SLURM_SUBMIT_DIR:-}" && -f "$SLURM_SUBMIT_DIR/scripts/run_benchmark.sh" ]]; then
  repo=$SLURM_SUBMIT_DIR                       # under sbatch the script runs from a spool copy
else
  repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fi
case_name="${1:?usage: scripts/run_benchmark.sh <case>   (prem_1d, ak135f_1d, semucb_crust1_3d)}"
case_dir="$repo/cases/$case_name"
[[ -f "$case_dir/case.json" ]] || { echo "No case '$case_name' (expected $case_dir/case.json)." >&2; exit 2; }
[[ -n "${SLURM_JOB_ID:-}" ]] || {
  echo "Run this inside a Slurm allocation of 4 CPU nodes, for example:" >&2
  echo "  salloc -A <account> -C cpu -q interactive -N 4 -t 00:30:00" >&2
  exit 2
}

PYTHON=${PYTHON:-python3}
dfdm_exe="${DFDM_EXE:-$repo/build/dfdm/dfdm_elastic3d}"
[[ -x "$dfdm_exe" ]] || { echo "Missing $dfdm_exe; run scripts/build_dfdm.sh or set DFDM_EXE." >&2; exit 2; }

read -r nodes ranks needs3d < <("$PYTHON" -c "
import json, sys
c = json.load(open(sys.argv[1]))
print(c['dfdm']['nodes'], c['dfdm']['ranks'], int(c.get('needs_3d_models', False)))" "$case_dir/case.json")
model_dir="${MODEL_DIR:-$repo/models}"
if [[ "$needs3d" == 1 ]]; then
  for f in semucb_wm1.tomo3d crust1_specfem.txt; do
    [[ -s "$model_dir/$f" ]] || { echo "Missing $model_dir/$f; run scripts/get_3d_models.sh first." >&2; exit 2; }
  done
fi

run_dir="$repo/runs/$case_name"
out_dir="$run_dir/dfdm_output"
mkdir -p "$run_dir"
rm -rf "$out_dir"
mkdir -p "$out_dir"

# Extra input files that ship compressed (the bent crust base of the 3-D case).
"$PYTHON" - "$case_dir" "$run_dir" <<'EOF'
import json, lzma, os, sys
case_dir, run_dir = sys.argv[1:]
for name, src in json.load(open(os.path.join(case_dir, "case.json")))["dfdm"].get("extra_files", {}).items():
    with lzma.open(os.path.join(case_dir, src), "rb") as f:
        open(os.path.join(run_dir, name), "wb").write(f.read())
EOF

sed -e "s|@OUTPUT_DIR@|$out_dir|" -e "s|@MODEL_DIR@|$model_dir|" -e "s|@RUN_DIR@|$run_dir|" \
  "$case_dir/dfdm/run.toml" > "$run_dir/run.toml"

# Solver settings of the published runs. All of them change speed only; none changes the physics.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MPICH_MAX_THREAD_SAFETY=serialized
export DFDM_ALLOW_LATERAL_BANDS_EXPERIMENTAL=1 DFDM_MPI_PARTITION_MODE=cost DFDM_DIRECT_GHOST_FACE_REMAP=off
export DFDM_MORTAR_FLUX_MEASURE=1
export DFDM_COMPACT_STEP=1 DFDM_DIRECT_DERIVATIVE_TRIPLET=1 DFDM_FUSED_FIXED_SAT_CORRECTION=1 \
       DFDM_FUSED_STRESS_SAT_SCALE=1 DFDM_FIXED_BUNDLE_PAIR_T=1
export DFDM_ATT_DEVIATORIC_MEMORY=1 DFDM_FACTORED_SHELL_METRIC=1 DFDM_LTS_SPLIT_PRELOAD=1

per_node=$(( ranks / nodes ))
echo "=== DFDM $case_name: $ranks processes on $nodes nodes, start $(date) ==="
t0=$(date +%s.%N)
srun -N "$nodes" --ntasks-per-node="$per_node" -n "$ranks" -c 2 --cpu-bind=cores --mem=0 \
  "$dfdm_exe" "$run_dir/run.toml" \
  --no-print-config --no-axis-counters --axis-kernel-mode fixed --sat-face-cache on --mpi-halo-mode face \
  --perf-summary "$run_dir/dfdm_perf.json" > "$run_dir/dfdm.log" 2>&1
t1=$(date +%s.%N)
"$PYTHON" - "$t0" "$t1" "$nodes" "$ranks" "$run_dir" <<'EOF'
import json, os, sys
t0, t1, nodes, ranks, run_dir = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
wall = t1 - t0
out = dict(wall_s=round(wall, 2), nodes=nodes, ranks=ranks, node_hours=round(nodes * wall / 3600.0, 4))
try:
    out["solver_s"] = round(json.load(open(os.path.join(run_dir, "dfdm_perf.json")))["total_seconds"], 2)
except (OSError, KeyError, ValueError):
    pass
json.dump(out, open(os.path.join(run_dir, "dfdm_cost.json"), "w"), indent=1)
print("wall time   : %.1f s on %d nodes" % (wall, nodes))
print("node-hours  : %.3f" % out["node_hours"])
EOF
echo "=== DFDM done $(date) ==="

if [[ "${NO_SCORE:-0}" != 1 ]]; then
  "$PYTHON" "$repo/scripts/score_benchmark.py" "$case_name"
fi
