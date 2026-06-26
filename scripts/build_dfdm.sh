#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
"$repo/scripts/prepare_dfdm.sh"

build_dir="${DFDM_BUILD_DIR:-$repo/build/dfdm}"
jobs="${JOBS:-8}"

if [[ -z "${CXX:-}" ]]; then
  if command -v CC >/dev/null 2>&1; then
    export CXX=CC
  elif command -v mpicxx >/dev/null 2>&1; then
    export CXX=mpicxx
  fi
fi

cmake -S "$repo/external/dfdm_3d_elastic" -B "$build_dir" -DCMAKE_BUILD_TYPE=Release
cmake --build "$build_dir" --target dfdm_elastic3d -j "$jobs"
echo "$build_dir/dfdm_elastic3d"
