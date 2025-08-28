import argparse
import re
import sys
import shutil
from pathlib import Path
from typing import Dict, List, Tuple


SPLIT_RE = re.compile(r"^(?P<base>.+)_split_(?P<idx>\d+)_of_(?P<total>\d+)\.txt$")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="merge-split-files",
        description="Merge files ending with _split_n_of_m back into single .txt files",
    )
    p.add_argument("inputdir", help="Directory containing split .txt files")
    p.add_argument("outputdir", help="Directory to write merged .txt files")
    p.add_argument("--recursive", action="store_true", help="Recurse into subdirectories")
    p.add_argument(
        "--allow-partial",
        action="store_true",
        help="Merge even if some parts are missing (concatenate available parts in order)",
    )
    p.add_argument(
        "--ensure-newline-between",
        action="store_true",
        help="Insert a newline between parts only if the previous part does not end with one",
    )
    return p


def main(argv: List[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = build_arg_parser().parse_args(argv)

    in_dir = Path(args.inputdir)
    out_dir = Path(args.outputdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = list(
        p for p in (in_dir.rglob("*.txt") if args.recursive else in_dir.glob("*.txt")) if p.is_file()
    )
    groups: Dict[Tuple[Path, str], List[Tuple[int, int, Path]]] = {}
    for f in files:
        m = SPLIT_RE.match(f.name)
        if not m:
            continue
        base = m.group("base")
        idx = int(m.group("idx"))
        total = int(m.group("total"))
        rel_parent = f.parent.relative_to(in_dir)
        key = (rel_parent, base)
        groups.setdefault(key, []).append((idx, total, f))

    # If no split groups, still copy all non-split files to output
    if not groups:
        for f in files:
            if not SPLIT_RE.match(f.name):
                rel_parent = f.parent.relative_to(in_dir)
                dst_dir = out_dir / rel_parent
                dst_dir.mkdir(parents=True, exist_ok=True)
                dst = dst_dir / f.name
                shutil.copy2(f, dst)
                print(f"Wrote {dst}")
        return 0

    for (rel_parent, base), entries in groups.items():
        # Sort by idx
        entries.sort(key=lambda t: t[0])
        totals = {t for _, t, _ in entries}
        if len(totals) != 1:
            print(f"Warning: inconsistent totals for {rel_parent}/{base}, skipping")
            continue
        total = totals.pop()
        present = {idx for idx, _, _ in entries}
        missing = [i for i in range(1, total + 1) if i not in present]
        if missing and not args.allow_partial:
            print(f"Skipping {rel_parent}/{base}: missing parts {missing}")
            continue

        dst_dir = out_dir / rel_parent
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"{base}.txt"

        pieces: List[str] = []
        for idx, _, path in entries:
            try:
                content = path.read_text(encoding="utf-8")
                if args.ensure_newline_between and pieces and not pieces[-1].endswith("\n"):
                    pieces.append("\n")
                pieces.append(content)
            except Exception as e:
                print(f"Warning: failed to read {path}: {e}")
        merged = "".join(pieces)
        dst.write_text(merged, encoding="utf-8")
        print(f"Wrote {dst}")

    # Also copy any non-split files alongside merged outputs
    for f in files:
        if SPLIT_RE.match(f.name):
            continue
        rel_parent = f.parent.relative_to(in_dir)
        dst_dir = out_dir / rel_parent
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f.name
        shutil.copy2(f, dst)
        print(f"Wrote {dst}")

    return 0


