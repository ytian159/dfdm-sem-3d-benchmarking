#!/usr/bin/env bash
# Build DFDM (external/dfdm_3d_elastic) into build/dfdm/.
#
#   bash scripts/build_dfdm.sh
#
# Environment:
#   CXX              the MPI C++ compiler (default CC on Cray systems such as Perlmutter, else mpicxx)
#   JOBS             parallel build jobs (default 8)
#   DFDM_BUILD_DIR   build folder (default build/dfdm)
#   DFDM_REAL        propagation precision, float (default, as published) or double
#   DFDM_BLAS        auto (default), cray, openblas or lapacke: which BLAS/LAPACKE setup to configure (see below)
#   DFDM_CMAKE_ARGS  extra arguments for the CMake configure step
#
# BLAS/LAPACKE: on a Cray system (CRAY_LIBSCI_PREFIX set) the compiler wrapper supplies LibSci. Elsewhere DFDM's
# CMake prefers an OpenBLAS CMake package, but the OpenBLAS packaged by Debian, Ubuntu and similar distributions
# does not contain the LAPACKE functions, and the link then fails with "undefined reference to LAPACKE_dsyev".
# On such a system (a separate liblapacke present) this script links liblapacke plus OpenBLAS (or the reference
# BLAS) explicitly. Install them with, for example, apt-get install libopenmpi-dev openmpi-bin libopenblas-dev
# liblapacke-dev.
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

has_lib() {   # (not grep -q: under pipefail its early exit makes ldconfig fail with SIGPIPE)
  ldconfig -p 2>/dev/null | grep "lib$1\.so" >/dev/null
}

# Folder of a header as the compiler finds it (empty if not found).
header_dir() {
  echo "#include <$1>" | "${CXX:-c++}" -x c++ -E - 2>/dev/null \
    | sed -n "s|^# [0-9]* \"\(.*\)/$1\".*|\1|p" | head -n 1
}

blas_mode="${DFDM_BLAS:-auto}"
if [[ "$blas_mode" == auto ]]; then
  if [[ -n "${CRAY_LIBSCI_PREFIX:-}" ]]; then
    blas_mode=cray
  elif has_lib lapacke; then
    blas_mode=lapacke
  else
    blas_mode=openblas
  fi
fi

blas_args=()
if [[ "$blas_mode" == lapacke ]]; then
  if has_lib openblas; then blas_lib=openblas; else blas_lib="cblas;blas"; fi
  cblas_dir=$(header_dir cblas.h)
  lapacke_dir=$(header_dir lapacke.h)
  [[ -n "$cblas_dir" && -n "$lapacke_dir" ]] || {
    echo "Could not find cblas.h and lapacke.h; install the BLAS and LAPACKE development packages" >&2
    echo "(e.g. libopenblas-dev liblapacke-dev) or set DFDM_BLAS=openblas." >&2
    exit 2
  }
  echo "BLAS/LAPACKE: liblapacke + $blas_lib (headers in $cblas_dir and $lapacke_dir)"
  blas_args=(-DCMAKE_DISABLE_FIND_PACKAGE_OpenBLAS=ON
             "-DDFDM_BLAS_INCLUDE_DIR=$cblas_dir;$lapacke_dir"
             "-DDFDM_BLAS_LIBRARIES=lapacke;$blas_lib;lapack")
else
  echo "BLAS/LAPACKE: $blas_mode (DFDM's own CMake detection)"
fi

# The published DFDM runs propagate in single precision.
# shellcheck disable=SC2086
cmake -S "$repo/external/dfdm_3d_elastic" -B "$build_dir" -DCMAKE_BUILD_TYPE=Release \
  -DDFDM_REAL="${DFDM_REAL:-float}" "${blas_args[@]}" ${DFDM_CMAKE_ARGS:-}
cmake --build "$build_dir" --target dfdm_elastic3d -j "$jobs"
echo "$build_dir/dfdm_elastic3d"
