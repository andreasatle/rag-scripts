from __future__ import annotations

import argparse
from pathlib import Path
from typing import List
import sys

from .pipeline import run_build


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rag-build", description="End-to-end build: OCR -> clean -> chunk -> embed -> insert")
    p.add_argument("pdfs", help="Directory with input PDFs")
    p.add_argument("--db", required=True, help="Vector DB path")
    p.add_argument("--collection", required=True, help="Collection name")
    p.add_argument("--embed-model", default="text-embedding-3-small", help="Embedding model")
    p.add_argument("-j", "--jobs", type=int, default=6, help="Concurrency for OCR and cleaning (default 6)")
    p.add_argument("--min-chars", type=int, default=1500, help="Non-overlap min chars (pre-clean)")
    p.add_argument("--max-chars", type=int, default=2500, help="Non-overlap max chars (pre-clean)")
    p.add_argument("--overlap", type=int, default=300, help="Overlap size for final chunks")
    p.add_argument("--env", default=None, help="Path to .env for OPENAI_API_KEY, AWS, etc.")
    p.add_argument("--s3-bucket", default=None, help="S3 bucket for Textract (created if missing)")
    p.add_argument("--s3-prefix", default="textract-inputs", help="S3 key prefix")
    p.add_argument("--aws-region", default=None, help="AWS region (defaults to current session)")
    p.add_argument("--qc-min-chars", type=int, default=200, help="QC: minimum chars for OCR text (default 200)")
    p.add_argument("--qc-threshold", type=int, default=50, help="QC: minimum score to proceed (0-100, default 50)")
    p.add_argument("--out", default="build", help="Build output directory (manifests, text)")
    return p


def main(argv: List[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = build_arg_parser().parse_args(argv)
    return run_build(
        pdfs_dir=Path(args.pdfs), out_dir=Path(args.out), db_path=args.db, collection=args.collection,
        embed_model=args.embed_model, jobs=args.jobs, min_chars=args.min_chars, max_chars=args.max_chars,
        overlap=args.overlap, env_file=Path(args.env) if args.env else None,
        qc_min_chars=int(args.qc_min_chars), qc_threshold=int(args.qc_threshold),
        s3_bucket=args.s3_bucket, s3_prefix=args.s3_prefix, aws_region=args.aws_region,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


