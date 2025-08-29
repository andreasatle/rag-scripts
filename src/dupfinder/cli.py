from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple
import sys


def file_hash(path: Path, algo: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def find_duplicates(root: Path, recursive: bool = True, algo: str = "sha256") -> Dict[str, List[Path]]:
    files = []
    it = root.rglob("*") if recursive else root.glob("*")
    for p in it:
        if p.is_file():
            files.append(p)

    # First group by size to avoid hashing uniques
    by_size: Dict[int, List[Path]] = {}
    for p in files:
        by_size.setdefault(p.stat().st_size, []).append(p)

    dup_groups: Dict[str, List[Path]] = {}
    for size, group in by_size.items():
        if len(group) < 2:
            continue
        for p in group:
            digest = file_hash(p, algo=algo)
            dup_groups.setdefault(digest, []).append(p)
    # Keep only actual duplicates (>=2)
    return {h: ps for h, ps in dup_groups.items() if len(ps) > 1}


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="find-duplicates", description="Find duplicate files by content hash")
    p.add_argument("path", help="Directory to scan")
    p.add_argument("--no-recursive", action="store_true", help="Do not recurse into subdirectories")
    p.add_argument("--algo", default="sha256", help="Hash algorithm (default sha256)")
    p.add_argument("--report", default=None, help="Write report to this file (txt)")
    return p


def main(argv: List[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = build_arg_parser().parse_args(argv)
    root = Path(args.path)
    if not root.exists() or not root.is_dir():
        print(f"Path not found or not a directory: {root}")
        return 1
    dups = find_duplicates(root, recursive=not bool(args.no_recursive), algo=args.algo)
    lines: List[str] = []
    if not dups:
        out = "No duplicates found"
        lines.append(out)
        print(out)
    else:
        for i, (h, paths) in enumerate(sorted(dups.items()), start=1):
            lines.append(f"== Group {i} ({len(paths)} files) | hash={h}")
            print(lines[-1])
            for p in sorted(paths):
                line = f" - {p}"
                lines.append(line)
                print(line)
    if args.report:
        Path(args.report).write_text("\n".join(lines), encoding="utf-8")
        print(f"Report written to {args.report}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


