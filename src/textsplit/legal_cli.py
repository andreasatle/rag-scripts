from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from .legal_chunker import chunk_text_for_rag


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="legal-chunk-text",
        description="Chunk legal .txt files into RAG-friendly overlapping chunks",
    )
    p.add_argument("inputdir", help="Directory containing input .txt files")
    p.add_argument("outputdir", help="Directory to write chunked .txt files")
    p.add_argument("--recursive", action="store_true", help="Recurse into subdirectories")
    p.add_argument("--min-chars", type=int, default=600, help="Minimum characters per chunk (default 600)")
    p.add_argument("--target-chars", type=int, default=1000, help="Target characters per chunk (default 1000)")
    p.add_argument("--max-chars", type=int, default=1400, help="Maximum characters per chunk (default 1400)")
    p.add_argument("--overlap-chars", type=int, default=150, help="Overlap characters between chunks (default 150)")
    p.add_argument("--no-section", action="store_true", help="Disable section-aware splitting (treat file as one section)")
    return p


def main(argv: List[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = build_arg_parser().parse_args(argv)

    in_dir = Path(args.inputdir)
    out_dir = Path(args.outputdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in (in_dir.rglob("*.txt") if args.recursive else in_dir.glob("*.txt")) if p.is_file())
    if not files:
        print("No .txt files found")
        return 2

    for src in files:
        text = src.read_text(encoding="utf-8")
        chunks = chunk_text_for_rag(
            text=text,
            min_chars=args.min_chars,
            target_chars=args.target_chars,
            max_chars=args.max_chars,
            overlap_chars=args.overlap_chars,
            by_section=not args.no_section,
        )

        total = len(chunks)
        rel = src.relative_to(in_dir)
        base_out_dir = out_dir / rel.parent
        base_out_dir.mkdir(parents=True, exist_ok=True)
        stem = src.stem
        if total <= 1:
            dst = base_out_dir / f"{stem}.txt"
            dst.write_text(chunks[0] if chunks else "", encoding="utf-8")
            print(f"Wrote {dst}")
            continue
        for idx, chunk in enumerate(chunks, start=1):
            dst = base_out_dir / f"{stem}_split_{idx}_of_{total}.txt"
            dst.write_text(chunk, encoding="utf-8")
            print(f"Wrote {dst}")
    return 0



