#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
dfdm_dir="$repo/external/dfdm_3d_elastic"

git -C "$repo" submodule update --init external/dfdm_3d_elastic

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
