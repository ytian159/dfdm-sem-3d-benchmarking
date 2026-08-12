#!/usr/bin/env python3
"""Stage SEM and DFDM benchmark cases using only repo-relative paths."""

import argparse
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT / "cases" / "ak135_mrr_hdur80_f0125"
BASE_DFDM = CASE_ROOT / "base" / "dfdm_ak135_mrr_heaviside_hdur80_base.toml"
BASE_SEM_DATA = CASE_ROOT / "base" / "sem_DATA"
MATRIX = CASE_ROOT / "case_matrix.json"
RUNS = ROOT / "runs"


def load_cases():
    data = json.loads(MATRIX.read_text())
    return {case["name"]: case for case in data["cases"]}


def replace_key(text, key, value):
    pattern = re.compile(r"^(\s*%s\s*=\s*)(.+)$" % re.escape(key), re.M)
    if not pattern.search(text):
        raise ValueError("missing key %s" % key)
    return pattern.sub(r"\g<1>%s" % value, text, count=1)


def replace_par_key(text, key, value):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.split("=", 1)[0].strip() == key:
            lhs = line.split("=", 1)[0].rstrip()
            comment = ""
            if "#" in line:
                comment = "  #" + line.split("#", 1)[1]
            lines[i] = "%-32s= %s%s" % (lhs, value, comment)
            return "\n".join(lines) + "\n"
    raise ValueError("missing Par_file key %s" % key)


def set_section_key(text, section, key, value):
    section_re = re.compile(r"^\[%s\]\s*$" % re.escape(section), re.M)
    match = section_re.search(text)
    if not match:
        raise ValueError("missing section [%s]" % section)

    next_match = re.search(r"^\[.+\]\s*$", text[match.end():], re.M)
    end = len(text) if next_match is None else match.end() + next_match.start()
    block = text[match.end():end]
    key_re = re.compile(r"^(\s*%s\s*=\s*)(.+)$" % re.escape(key), re.M)
    if key_re.search(block):
        block = key_re.sub(r"\g<1>%s" % value, block, count=1)
    else:
        if not block.endswith("\n"):
            block += "\n"
        block = "\n%s = %s" % (key, value) + block
    return text[:match.end()] + block + text[end:]


def copy_sem_data(sem_dir):
    data_dir = sem_dir / "DATA"
    data_dir.mkdir(parents=True, exist_ok=True)
    for src in BASE_SEM_DATA.iterdir():
        if src.is_file():
            shutil.copy2(str(src), str(data_dir / src.name))


def check_sem_decomposition(name, cfg):
    """SPECFEM requires NEX divisible by 8*NPROC, and ranks = 6*NPROC^2."""
    if cfg.get("synthetic"):
        return None
    nex = int(cfg["sem_nex"])
    nproc = int(cfg["sem_nproc"])
    if nex % (8 * nproc) != 0:
        raise SystemExit(
            "case %s: NEX=%d is not divisible by 8*NPROC=%d; SPECFEM will reject the mesh"
            % (name, nex, 8 * nproc))
    ranks = 6 * nproc * nproc
    declared = int(cfg["slurm"]["sem_tasks"])
    if ranks != declared:
        raise SystemExit(
            "case %s: sem_tasks=%d but 6*NPROC^2=%d; fix the case matrix"
            % (name, declared, ranks))
    return ranks


RESULT_GLOBS = [
    "sem_case/OUTPUT_FILES/*.sem.ascii",
    "DFDM_OUTPUT_*/*.txt",
    "*.png",
    "*_perf.json",
    "*_metrics.md",
    "*_score*.json",
]


def existing_results(case_dir):
    """Solver outputs / figures already in a case dir, so restaging cannot eat them."""
    found = []
    for pattern in RESULT_GLOBS:
        found.extend(sorted(case_dir.glob(pattern))[:1])
    return found


def stage_case(name, cfg, force, discard_results=False):
    case_dir = RUNS / name
    if case_dir.exists():
        if not force:
            raise SystemExit("%s exists; rerun with --force to restage" % case_dir)
        results = existing_results(case_dir)
        if results and not discard_results:
            listing = "\n  ".join(str(p.relative_to(ROOT)) for p in results)
            raise SystemExit(
                "%s holds solver results; restaging would delete them:\n  %s\n"
                "Re-run with --discard-results to overwrite, or move the directory aside."
                % (case_dir, listing))
        shutil.rmtree(str(case_dir))
    sem_dir = case_dir / "sem_case"
    has_dfdm = "dfdm_nex" in cfg
    copy_sem_data(sem_dir)

    check_sem_decomposition(name, cfg)

    meta = {
        "name": name,
        "note": cfg["note"],
        "source": cfg["source"],
        "equivalent_frequency_hz": cfg["equivalent_frequency_hz"],
        "record_minutes": float(cfg["record_minutes"]),
        "sem_dir": sem_dir.relative_to(ROOT).as_posix(),
        "sem_nex": int(cfg["sem_nex"]),
        "sem_nproc": int(cfg["sem_nproc"]),
        "sem_dt": float(cfg["sem_dt"]),
        "has_dfdm": has_dfdm,
        "slurm": cfg["slurm"],
    }

    if has_dfdm:
        dfdm_output = case_dir / ("DFDM_OUTPUT_ak135_mrr_hdur80_nex%d_nez%d" %
                                  (int(cfg["dfdm_nex"]), int(cfg["dfdm_nez"])))
        dfdm = BASE_DFDM.read_text()
        dfdm = replace_key(dfdm, "dt", "%.12g" % float(cfg["dfdm_dt"]))
        dfdm = replace_key(dfdm, "nt", "%d" % int(cfg["dfdm_nt"]))
        dfdm = replace_key(dfdm, "output_dir", "\"%s\"" % dfdm_output.relative_to(ROOT).as_posix())
        dfdm = replace_key(dfdm, "nex", "%d" % int(cfg["dfdm_nex"]))
        dfdm = replace_key(dfdm, "ney", "%d" % int(cfg["dfdm_ney"]))
        dfdm = replace_key(dfdm, "nez", "%d" % int(cfg["dfdm_nez"]))
        dfdm = set_section_key(dfdm, "mesh3d", "full_shell_nez_decoupled", "true")
        dfdm = set_section_key(dfdm, "solver", "axis_kernel_mode", "\"fixed\"")
        dfdm = set_section_key(dfdm, "solver", "sat_face_cache", "\"on\"")
        dfdm_config = case_dir / "dfdm_ak135_mrr_hdur80_refined.toml"
        dfdm_config.write_text(dfdm)
        meta.update({
            "dfdm_config": dfdm_config.relative_to(ROOT).as_posix(),
            "dfdm_output": dfdm_output.relative_to(ROOT).as_posix(),
            "dfdm_nex": int(cfg["dfdm_nex"]),
            "dfdm_ney": int(cfg["dfdm_ney"]),
            "dfdm_nez_shell": int(cfg["dfdm_nez"]),
            "dfdm_dt": float(cfg["dfdm_dt"]),
            "dfdm_nt": int(cfg["dfdm_nt"]),
        })

    par_path = sem_dir / "DATA" / "Par_file"
    par = par_path.read_text()
    par = replace_par_key(par, "NEX_XI", "%d" % int(cfg["sem_nex"]))
    par = replace_par_key(par, "NEX_ETA", "%d" % int(cfg["sem_nex"]))
    par = replace_par_key(par, "NPROC_XI", "%d" % int(cfg["sem_nproc"]))
    par = replace_par_key(par, "NPROC_ETA", "%d" % int(cfg["sem_nproc"]))
    par = replace_par_key(par, "DT", "%.12gd0" % float(cfg["sem_dt"]))
    par = replace_par_key(par, "RECORD_LENGTH_IN_MINUTES", "%.12gd0" % float(cfg["record_minutes"]))
    par_path.write_text(par)

    (case_dir / "case_metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", help="Case name to stage; default stages physical cases.")
    parser.add_argument("--all", action="store_true", help="Stage every case, including fixture_smoke.")
    parser.add_argument("--force", action="store_true", help="Remove existing run directories before staging.")
    parser.add_argument("--discard-results", action="store_true",
                        help="Allow --force to delete a case directory that already holds solver outputs.")
    args = parser.parse_args()

    cases = load_cases()
    if args.all:
        names = list(cases)
    elif args.case:
        names = args.case
    else:
        names = [name for name in cases if name != "fixture_smoke"]
    unknown = [name for name in names if name not in cases]
    if unknown:
        raise SystemExit("unknown case(s): %s" % ", ".join(unknown))

    RUNS.mkdir(exist_ok=True)
    manifest = {"cases": [stage_case(name, cases[name], args.force, args.discard_results)
                          for name in names]}
    (RUNS / "resolved_ppw_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for case in manifest["cases"]:
        print(case["name"])
        if case["has_dfdm"]:
            print("  DFDM config: %s" % case["dfdm_config"])
        else:
            print("  DFDM config: (none; SEM-only case)")
        print("  SEM case:    %s (NEX %d, NPROC %d, DT %g, %d ranks)" %
              (case["sem_dir"], case["sem_nex"], case["sem_nproc"], case["sem_dt"],
               case["slurm"]["sem_tasks"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
