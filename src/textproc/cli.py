import argparse
import sys
from pathlib import Path
from typing import List

from .pipeline import run_pipeline


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llm-process-text",
        description="Process .txt files with OpenAI; user message is the file content",
    )
    p.add_argument("inputdir", help="Directory containing input .txt files")
    p.add_argument("outputdir", help="Directory to write processed .txt files")
    p.add_argument("--env-file", default=".env", help=".env path (default .env)")
    p.add_argument("--model", default="gpt-4o-mini", help="OpenAI model name")
    p.add_argument("--recursive", action="store_true", help="Recurse into subdirectories")
    p.add_argument("-j", "--jobs", type=int, default=4, help="Concurrent files (default 4)")
    p.add_argument("--timeout", type=float, default=60.0, help="Request timeout seconds (default 60)")
    p.add_argument("--max-tokens", type=int, default=2048, help="Max completion tokens (default 2048)")
    return p


def main(argv: List[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = build_arg_parser().parse_args(argv)
    return run_pipeline(
        input_dir=Path(args.inputdir),
        output_dir=Path(args.outputdir),
        env_file=Path(args.env_file) if args.env_file else None,
        model=args.model,
        recursive=args.recursive,
        concurrency=args.jobs,
        timeout_seconds=args.timeout,
        max_tokens=args.max_tokens,
    )


