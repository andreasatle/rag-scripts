from __future__ import annotations

from pathlib import Path
from typing import List
import argparse
import sys

from .core import process_word_document


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="word-links",
        description="Extract links from Word .docx and download linked files",
    )
    p.add_argument("input", help=".docx file or directory containing .docx files")
    p.add_argument("-o", "--output", help="Output directory (default: <docname>_files)")
    p.add_argument("--recursive", action="store_true", help="Recurse into subdirectories")
    p.add_argument("--dry-run", action="store_true", help="Do not download; print suggested filenames")
    return p


def main(argv: List[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = build_arg_parser().parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Path not found: {input_path}")
        return 1

    if input_path.is_file():
        process_word_document(input_path, args.output, dry_run=bool(args.dry_run))
        return 0

    if input_path.is_dir():
        files = list(input_path.rglob("*.docx") if args.recursive else input_path.glob("*.docx"))
        if not files:
            print(f"No .docx files found in {input_path}")
            return 2
        print(f"Found {len(files)} .docx files to process")
        for f in files:
            print("=" * 60)
            process_word_document(f, args.output, dry_run=bool(args.dry_run))
        return 0

    print(f"Error: {input_path} is not a file or directory")
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


