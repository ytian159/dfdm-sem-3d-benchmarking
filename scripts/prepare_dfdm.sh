#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
dfdm_dir="$repo/external/dfdm_3d_elastic"

git -C "$repo" submodule update --init external/dfdm_3d_elastic

if [[ -f "$dfdm_dir/src/axis_kernels_fixed.h" ]] \
  && grep -q "full_shell_nez_decoupled" "$dfdm_dir/src/config_toml3d.cpp" \
  && grep -q "hat_l2_projection_matrix" "$dfdm_dir/src/elastic3d.cpp"; then
  echo "DFDM PPW-control source present."
  git -C "$dfdm_dir" status --short
  exit 0
fi

echo "DFDM submodule does not contain the expected PPW-control source." >&2
echo "Update external/dfdm_3d_elastic to the current dfdm_3d_elastic main branch." >&2
exit 2
