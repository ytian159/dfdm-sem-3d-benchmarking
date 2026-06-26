#!/usr/bin/env python3
"""Fail if checked-in benchmark files contain local machine paths."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = [
    "/" + "pscratch/sd/y/ytian159",
    "/" + "global/homes/y/ytian159",
    "/" + "global/u1/y/ytian159",
    "/" + "global/cfs/cdirs/m4661",
]
SKIP_DIRS = {".git", "external", "runs", "build", "__pycache__", ".pytest_cache", ".mypy_cache"}
TEXT_SUFFIXES = {
    ".bash", ".cfg", ".cmake", ".h", ".hpp", ".json", ".md", ".patch", ".py", ".sh",
    ".slurm", ".txt", ".toml", ".yml", ".yaml", ""
}


def should_skip(path):
    return any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)


def main():
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        if path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        for pattern in FORBIDDEN:
            if pattern in text:
                hits.append("%s contains %s" % (path.relative_to(ROOT), pattern))
    if hits:
        print("\n".join(hits))
        return 1
    print("No forbidden local paths found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
