#!/usr/bin/env python3
"""Stage SEM and DFDM benchmark cases using only repo-relative paths."""

import argparse
import hashlib
import json
import lzma
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT / "cases" / "ak135_mrr_hdur80_f0125"
BASE_DFDM = CASE_ROOT / "base" / "dfdm_ak135f_mrr_hdur80.toml"
DFDM_MESH = CASE_ROOT / "dfdm_mesh" / "mesh_bricks.txt.xz"
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


def stage_dfdm_mesh(dest):
    """Decompress the shipped DFDM mesh and check it against its SHA256SUMS entry."""
    want = (DFDM_MESH.parent / "SHA256SUMS").read_text().split()[0]
    h = hashlib.sha256()
    with lzma.open(str(DFDM_MESH), "rb") as f_in, open(str(dest), "wb") as f_out:
        for block in iter(lambda: f_in.read(1 << 20), b""):
            h.update(block)
            f_out.write(block)
    if h.hexdigest() != want:
        raise SystemExit("%s does not match its SHA256SUMS entry" % DFDM_MESH.relative_to(ROOT))


def render_sem_par(cfg):
    """Par_file text that staging writes for this case."""
    par = (BASE_SEM_DATA / "Par_file").read_text()
    par = replace_par_key(par, "NEX_XI", "%d" % int(cfg["sem_nex"]))
    par = replace_par_key(par, "NEX_ETA", "%d" % int(cfg["sem_nex"]))
    par = replace_par_key(par, "NPROC_XI", "%d" % int(cfg["sem_nproc"]))
    par = replace_par_key(par, "NPROC_ETA", "%d" % int(cfg["sem_nproc"]))
    par = replace_par_key(par, "DT", "%.12gd0" % float(cfg["sem_dt"]))
    par = replace_par_key(par, "RECORD_LENGTH_IN_MINUTES", "%.12gd0" % float(cfg["record_minutes"]))
    return par


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
    "DFDM_OUTPUT*/*.txt",
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
    has_dfdm = "dfdm_nt" in cfg
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
        dfdm_output = case_dir / "DFDM_OUTPUT"
        dfdm_mesh = case_dir / "dfdm_mesh_bricks.txt"
        stage_dfdm_mesh(dfdm_mesh)
        dfdm = BASE_DFDM.read_text()
        dfdm = replace_key(dfdm, "dt", "%.12g" % float(cfg["dfdm_dt"]))
        dfdm = replace_key(dfdm, "nt", "%d" % int(cfg["dfdm_nt"]))
        dfdm = replace_key(dfdm, "output_dir", "\"%s\"" % dfdm_output.relative_to(ROOT).as_posix())
        dfdm = replace_key(dfdm, "mesh_file", "\"%s\"" % dfdm_mesh.relative_to(ROOT).as_posix())
        dfdm_config = case_dir / "dfdm.toml"
        dfdm_config.write_text(dfdm)
        meta.update({
            "dfdm_config": dfdm_config.relative_to(ROOT).as_posix(),
            "dfdm_output": dfdm_output.relative_to(ROOT).as_posix(),
            "dfdm_mesh": dfdm_mesh.relative_to(ROOT).as_posix(),
            "dfdm_dt": float(cfg["dfdm_dt"]),
            "dfdm_nt": int(cfg["dfdm_nt"]),
        })

    if "sem_reference" in cfg:
        meta["sem_reference"] = cfg["sem_reference"]

    (sem_dir / "DATA" / "Par_file").write_text(render_sem_par(cfg))

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
