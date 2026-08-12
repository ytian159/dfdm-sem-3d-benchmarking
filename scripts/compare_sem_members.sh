#!/usr/bin/env bash
# Score one staged SEM case against another (convergence / anchor qualification).
#
#   compare_sem_members.sh TEST_CASE REF_CASE
#
# e.g. compare_sem_members.sh paper_sem_nex64_4800s paper_sem_nex96_4800s
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
test_case="${1:?usage: compare_sem_members.sh TEST_CASE REF_CASE}"
ref_case="${2:?usage: compare_sem_members.sh TEST_CASE REF_CASE}"

test_out="$repo/runs/$test_case/sem_case/OUTPUT_FILES"
ref_out="$repo/runs/$ref_case/sem_case/OUTPUT_FILES"
for d in "$test_out" "$ref_out"; do
  compgen -G "$d/DF.AZ01.?X?.sem.ascii" > /dev/null \
    || { echo "No seismograms in $d; run the SEM job for that case first." >&2; exit 2; }
done

export MPLCONFIGDIR="${MPLCONFIGDIR:-$repo/runs/mplconfig}"
mkdir -p "$MPLCONFIGDIR"

out_dir="$repo/runs/$test_case"
python3 "$repo/scripts/score_sem_members.py" "$test_out" "$ref_out" \
  --label "$test_case vs $ref_case" \
  --json "$out_dir/sem_member_score_vs_${ref_case}.json" \
  --figure "$out_dir/sem_member_score_vs_${ref_case}.png" \
  --source-shift "${SOURCE_SHIFT:-120}"
