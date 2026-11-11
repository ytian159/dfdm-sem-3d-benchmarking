#!/usr/bin/env bash
# Build the two model tables of the 3-D case (semucb_crust1_3d) from public data.
#
#   scripts/get_3d_models.sh            (about a minute; on Perlmutter run it on a compute node)
#
# 1. SEMUCB-WM1 mantle: downloads the IRIS EMC grids (about 21 MB), resamples them onto an exact 1-degree grid and
#    writes models/semucb_wm1.tomo3d, the table both DFDM and SPECFEM read (vsv, vsh in km/s from 30 to 2891 km;
#    anisotropic PREM above and below, vp and density scaled from the shear speeds, PREM attenuation).
# 2. CRUST1.0: writes models/crust1_specfem.txt, CRUST1.0 as SPECFEM evaluates it, from SPECFEM's DATA/crust1.0.
# Both files are checked against the checksums of the files used for the published runs.
#
# Environment: MODEL_DIR (default models/), PYTHON (default python3), DFDM3D_DIR (default external/dfdm_3d_elastic).
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
model_dir="${MODEL_DIR:-$repo/models}"
dfdm_dir="${DFDM3D_DIR:-$repo/external/dfdm_3d_elastic}"
PYTHON=${PYTHON:-python3}
mkdir -p "$model_dir/download"

git -C "$repo" submodule update --init external/specfem3d_globe >/dev/null 2>&1 || true
crust_dir="$repo/external/specfem3d_globe/DATA/crust1.0"
[[ -f "$crust_dir/crust1.vp" ]] || { echo "Missing $crust_dir; initialise the SPECFEM submodule." >&2; exit 2; }
[[ -f "$dfdm_dir/automesh/tools/semucb_emc_to_npz.py" ]] || { echo "Missing the DFDM3D planner in $dfdm_dir." >&2; exit 2; }

emc=https://ds.iris.edu/files/products/emc/emc-files
for f in semucb-2014-ucb-vs-viz-only.r0.1.nc semucb-2014-ucb-xi-viz-only.r0.1.nc; do
  if [[ ! -s "$model_dir/download/$f" ]]; then
    echo "downloading $f"
    if ! curl -fsSL -o "$model_dir/download/$f" "$emc/$f"; then
      rm -f "$model_dir/download/$f"
      echo "The download of $f failed. Download the SEMUCB-WM1 netCDF files (Vs and xi) by hand from the" >&2
      echo "IRIS Earth Model Collaboration page https://ds.iris.edu/ds/products/emc-semucb-wm1/ , put them in" >&2
      echo "$model_dir/download/ under the names $f" >&2
      echo "and semucb-2014-ucb-xi-viz-only.r0.1.nc, and run this script again." >&2
      exit 2
    fi
  fi
done

echo "SEMUCB-WM1 -> $model_dir/semucb_wm1.tomo3d"
"$PYTHON" "$dfdm_dir/automesh/tools/semucb_emc_to_npz.py" \
  "$model_dir/download/semucb-2014-ucb-vs-viz-only.r0.1.nc" \
  "$model_dir/download/semucb-2014-ucb-xi-viz-only.r0.1.nc" \
  "$model_dir/download/semucb_grid.npz" > "$model_dir/download/semucb_convert.log"
(cd "$dfdm_dir/automesh" && "$PYTHON" -m automesh tomo-export "$model_dir/download/semucb_grid.npz" \
  "$model_dir/semucb_wm1.tomo3d" --reference-name 1D_tiso_prem_onecrust > "$model_dir/download/semucb_export.log")

echo "CRUST1.0 -> $model_dir/crust1_specfem.txt"
"$PYTHON" "$repo/scripts/crust1_table.py" "$model_dir/crust1_specfem.txt" --crust1-dir "$crust_dir" \
  > "$model_dir/download/crust1.log"

cd "$model_dir"
if md5sum -c "$repo/cases/semucb_crust1_3d/models.md5"; then
  echo "Both tables are identical to the ones used for the published runs."
else
  echo "WARNING: a table differs from the one used for the published runs (see above)." >&2
  exit 1
fi
