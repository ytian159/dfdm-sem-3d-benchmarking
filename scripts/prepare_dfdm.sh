#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
dfdm_dir="$repo/external/dfdm_3d_elastic"

git -C "$repo" submodule update --init external/dfdm_3d_elastic

# The benchmark mesh needs per-layer lateral element counts and the 5-point crust.
if grep -q "allow_low_radial_order" "$dfdm_dir/src/config_toml3d.cpp" \
  && grep -q "DFDM_ALLOW_LATERAL_BANDS_EXPERIMENTAL" "$dfdm_dir/src/config_toml3d.cpp"; then
  echo "DFDM production source present."
  git -C "$dfdm_dir" status --short
  exit 0
fi

echo "DFDM submodule does not contain the production source this benchmark needs." >&2
echo "Update external/dfdm_3d_elastic to DFDM3D branch production-2026-10." >&2
exit 2
