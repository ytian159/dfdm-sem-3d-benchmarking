#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
dfdm_dir="$repo/external/dfdm_3d_elastic"

git -C "$repo" submodule update --init external/dfdm_3d_elastic

if [[ -f "$dfdm_dir/src/axis_kernels_fixed.h" ]] \
  && grep -q "full_shell_nez_decoupled" "$dfdm_dir/src/config_toml3d.cpp" \
  && grep -q "hat_l2_projection_matrix" "$dfdm_dir/src/elastic3d.cpp"; then
  echo "DFDM PPW-control patch stack already present."
  git -C "$dfdm_dir" status --short
  exit 0
fi

for patch in "$repo"/patches/dfdm/*.patch; do
  if git -C "$dfdm_dir" apply --reverse --check "$patch" >/dev/null 2>&1; then
    echo "already applied: ${patch#$repo/}"
  else
    git -C "$dfdm_dir" apply --check "$patch"
    git -C "$dfdm_dir" apply "$patch"
    echo "applied: ${patch#$repo/}"
  fi
done

git -C "$dfdm_dir" status --short
