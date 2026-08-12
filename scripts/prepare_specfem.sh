#!/usr/bin/env bash
# Apply the benchmark's required SPECFEM build setting, idempotently.
#
# ASSUME_PERFECT_SPHERE=.true. disables the geographic-to-geocentric
# conversion of source and station coordinates. The benchmark runs a
# spherically symmetric Earth (ELLIPTICITY, TOPOGRAPHY and OCEANS all off)
# and DFDM places its source and receivers at the requested geocentric
# angles, so without this setting SPECFEM shifts every station by up to
# ~0.19 degrees (~21 km) relative to DFDM and the comparison is silently
# wrong: epicentral distances stop being the nominal 10, 20, ... degrees.
#
# This is a compile-time constant, so it must be set before building.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
spec_dir="${SPECFEM_ROOT:-$repo/external/specfem3d_globe}"
target="$spec_dir/setup/constants.h.in"

test -f "$target" || { echo "Missing $target; init the SPECFEM submodule first." >&2; exit 2; }

if grep -qE '^\s*logical, parameter :: ASSUME_PERFECT_SPHERE = \.true\.' "$target"; then
  echo "ASSUME_PERFECT_SPHERE already .true. in $target"
else
  sed -i -E 's/^(\s*logical, parameter :: ASSUME_PERFECT_SPHERE = )\.false\./\1.true./' "$target"
  grep -qE '^\s*logical, parameter :: ASSUME_PERFECT_SPHERE = \.true\.' "$target" \
    || { echo "Failed to set ASSUME_PERFECT_SPHERE in $target" >&2; exit 2; }
  echo "Set ASSUME_PERFECT_SPHERE = .true. in $target"
fi
