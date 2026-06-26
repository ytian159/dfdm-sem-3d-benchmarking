#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
spec_dir="$repo/external/specfem3d_globe"
jobs="${JOBS:-16}"

git -C "$repo" submodule update --init external/specfem3d_globe

cd "$spec_dir"
if [[ ! -x ./configure ]]; then
  echo "Missing SPECFEM configure script in $spec_dir" >&2
  exit 2
fi

./configure FC="${FC:-ftn}" CC="${CC:-cc}" MPIFC="${MPIFC:-ftn}" --with-mpi
make -j "$jobs" xmeshfem3D xspecfem3D
echo "$spec_dir/bin/xmeshfem3D"
echo "$spec_dir/bin/xspecfem3D"
