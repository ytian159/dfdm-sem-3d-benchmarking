#!/usr/bin/env python3
"""Install existing SPECFEM seismograms into a staged case instead of running SPECFEM.

The NEX320 SEM-Ref costs about 28 node-hours, so its seismograms ship with the
repository under cases/<family>/<sem_reference>/: the files SPECFEM wrote,
xz-compressed, with SHA256 checksums of the originals and the DATA directory
that produced them. This script decompresses them into
runs/<case>/sem_case/OUTPUT_FILES, where compare_case.sh and
compare_sem_members.sh read them exactly as if SPECFEM had just run.

--from DIR installs seismograms from any other directory on disk instead, e.g.
the OUTPUT_FILES of an earlier run. DIR may be the OUTPUT_FILES directory or
the SPECFEM run directory holding it.

Either way the DATA files that produced the seismograms must match the case's
staged DATA byte for byte; otherwise the traces belong to a different run.

Usage:
  install_sem_reference.py CASE [--from DIR] [--force]
  install_sem_reference.py --verify      # check every shipped set; install nothing
"""

import argparse
import hashlib
import json
import lzma
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage_cases  # noqa: E402


ROOT = stage_cases.ROOT
DATA_FILES = ("Par_file", "CMTSOLUTION", "STATIONS")
CHUNK = 1 << 20


def sha256_file(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def read_sums(ref_dir):
    sums = {}
    for line in (ref_dir / "SHA256SUMS").read_text().splitlines():
        if line.strip():
            digest, name = line.split(None, 1)
            sums[name.strip()] = digest
    return sums


def expected_channels(stations_text):
    """One (station, component) pair per STATIONS line and E/N/Z component."""
    out = []
    for line in stations_text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            out.extend(("%s.%s" % (parts[1], parts[0]), comp) for comp in "ENZ")
    return out


def missing_channels(names, stations_text):
    """SPECFEM names traces NET.STA.?X<comp>.sem.ascii (MX below NEX 128, BX above)."""
    have = set()
    for name in names:
        net, sta, chan = name.split(".")[:3]
        have.add(("%s.%s" % (net, sta), chan[-1]))
    return ["%s %s" % pair for pair in expected_channels(stations_text) if pair not in have]


def data_mismatches(src_data, want):
    """Names of DATA files in src_data that differ from want {name: text}."""
    bad = []
    for name in DATA_FILES:
        path = src_data / name
        if not path.is_file() or path.read_text() != want[name]:
            bad.append(name)
    return bad


def expected_data(cfg):
    base = stage_cases.BASE_SEM_DATA
    return {
        "Par_file": stage_cases.render_sem_par(cfg),
        "CMTSOLUTION": (base / "CMTSOLUTION").read_text(),
        "STATIONS": (base / "STATIONS").read_text(),
    }


def verify_shipped():
    """Check every shipped set: DATA matches its case, every trace decompresses to its checksum."""
    cases = stage_cases.load_cases()
    all_ok = True
    for name, cfg in sorted(cases.items()):
        ref = cfg.get("sem_reference")
        if not ref:
            continue
        ok = True
        ref_dir = stage_cases.CASE_ROOT / ref
        bad = data_mismatches(ref_dir / "DATA", expected_data(cfg))
        if bad:
            print("%s: DATA differs from case %s: %s" % (ref, name, ", ".join(bad)))
            ok = False
        sums = read_sums(ref_dir)
        missing = missing_channels(sums, (ref_dir / "DATA" / "STATIONS").read_text())
        if missing:
            print("%s: no trace for %s" % (ref, ", ".join(missing)))
            ok = False
        for trace, digest in sorted(sums.items()):
            packed = ref_dir / "OUTPUT_FILES" / (trace + ".xz")
            if not packed.is_file():
                print("%s: missing %s" % (ref, packed.relative_to(ROOT)))
                ok = False
                continue
            h = hashlib.sha256()
            with lzma.open(str(packed), "rb") as f:
                for block in iter(lambda: f.read(CHUNK), b""):
                    h.update(block)
            if h.hexdigest() != digest:
                print("%s: %s does not match SHA256SUMS" % (ref, trace))
                ok = False
        print("%s: %d traces for case %s %s" % (ref, len(sums), name, "verified" if ok else "FAILED"))
        all_ok = all_ok and ok
    return all_ok


def resolve_source(src):
    """Return (OUTPUT_FILES dir, DATA dir) for a directory given with --from."""
    src = Path(src).resolve()
    out_dir = src / "OUTPUT_FILES" if (src / "OUTPUT_FILES").is_dir() else src
    for data_dir in (out_dir.parent / "DATA", src / "DATA"):
        if data_dir.is_dir():
            return out_dir, data_dir
    raise SystemExit("No DATA directory next to %s; cannot check which run produced these "
                     "seismograms." % out_dir)


def install(case, src, force):
    cases = stage_cases.load_cases()
    if case not in cases:
        raise SystemExit("unknown case %s" % case)
    cfg = cases[case]
    if src is None and not cfg.get("sem_reference"):
        raise SystemExit("Case %s ships no SEM seismograms; run SPECFEM or use --from DIR." % case)
    case_dir = stage_cases.RUNS / case
    if not (case_dir / "case_metadata.json").is_file():
        stage_cases.RUNS.mkdir(exist_ok=True)
        stage_cases.stage_case(case, cfg, force=False)
        print("staged %s" % case_dir.relative_to(ROOT))
    meta = json.loads((case_dir / "case_metadata.json").read_text())
    sem_dir = ROOT / meta["sem_dir"]
    staged = {name: (sem_dir / "DATA" / name).read_text() for name in DATA_FILES}

    if src is None:
        ref = cfg["sem_reference"]
        ref_dir = stage_cases.CASE_ROOT / ref
        data_dir = ref_dir / "DATA"
        sums = read_sums(ref_dir)
        label = "shipped %s" % ref
    else:
        out_dir, data_dir = resolve_source(src)
        traces = sorted(p.name for p in out_dir.glob("*.sem.ascii"))
        if not traces:
            raise SystemExit("No *.sem.ascii seismograms in %s" % out_dir)
        sums = {name: sha256_file(out_dir / name) for name in traces}
        label = str(out_dir)

    bad = data_mismatches(data_dir, staged)
    if bad:
        raise SystemExit("%s was produced by different DATA than case %s (%s differ); "
                         "these seismograms belong to another run." % (label, case, ", ".join(bad)))
    missing = missing_channels(sums, staged["STATIONS"])
    if missing:
        raise SystemExit("%s lacks traces for %s" % (label, ", ".join(missing)))

    dest = sem_dir / "OUTPUT_FILES"
    present = sorted(p.name for p in dest.glob("*.sem.ascii")) if dest.is_dir() else []
    if present:
        if present == sorted(sums) and all(sha256_file(dest / n) == d for n, d in sums.items()):
            print("%s already holds these %d seismograms (%s); nothing to do."
                  % (dest.relative_to(ROOT), len(sums), label))
            return 0
        if not force:
            raise SystemExit("%s already holds other seismograms; re-run with --force to replace "
                             "them." % dest.relative_to(ROOT))
        shutil.rmtree(str(dest))
        perf = case_dir / "sem_perf.json"
        if perf.is_file():
            perf.unlink()
            print("removed %s (it described the replaced run)" % perf.relative_to(ROOT))
    dest.mkdir(parents=True, exist_ok=True)

    for name, digest in sorted(sums.items()):
        target = dest / name
        if src is None:
            with lzma.open(str(ref_dir / "OUTPUT_FILES" / (name + ".xz")), "rb") as f_in, \
                    open(str(target), "wb") as f_out:
                shutil.copyfileobj(f_in, f_out, CHUNK)
        else:
            shutil.copyfile(str(out_dir / name), str(target))
        if sha256_file(target) != digest:
            raise SystemExit("%s does not match its checksum after install" % target)

    (case_dir / "sem_seismograms.json").write_text(json.dumps({
        "source": label,
        "traces": len(sums),
        "sha256": sums,
        "note": "SPECFEM was not run for this case; the seismograms were installed from the "
                "source above, so there is no sem_perf.json.",
    }, indent=2) + "\n")
    print("installed %d seismograms from %s into %s" % (len(sums), label, dest.relative_to(ROOT)))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("case", nargs="?")
    ap.add_argument("--from", dest="src", help="install from this directory instead of the shipped set")
    ap.add_argument("--force", action="store_true", help="replace seismograms already in the case")
    ap.add_argument("--verify", action="store_true", help="verify every shipped set and exit")
    args = ap.parse_args()
    if args.verify:
        return 0 if verify_shipped() else 1
    if not args.case:
        ap.error("give a case name, or --verify")
    return install(args.case, args.src, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
