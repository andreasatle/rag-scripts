import argparse
import sys
from pathlib import Path

from .pipeline import find_pdfs, submit_and_collect


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="textract-ocr",
        description="Batch OCR PDFs to text using AWS Textract",
    )
    p.add_argument("inputs", nargs="+", help="Files or directories to process")
    p.add_argument("-o", "--output-dir", default="out", help="Directory to write .txt outputs")
    p.add_argument("--bucket", required=True, help="S3 bucket for Textract inputs")
    p.add_argument("--prefix", default="textract-inputs", help="S3 key prefix for uploads")
    p.add_argument("--region", default=None, help="AWS region (uses env/config if omitted)")
    p.add_argument("-j", "--jobs", type=int, default=4, help="Concurrent jobs (default: 4)")
    p.add_argument("--no-recursive", action="store_true", help="Do not recurse into subdirectories")
    p.add_argument("--poll-seconds", type=float, default=5.0, help="Polling interval (seconds)")
    p.add_argument("--timeout-seconds", type=float, default=1800.0, help="Per-document timeout")
    p.add_argument("--keep-uploaded", action="store_true", help="Keep uploaded S3 objects (default deletes)")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = build_arg_parser().parse_args(argv)

    # Optional region override
    if args.region:
        import boto3
        boto3.setup_default_session(region_name=args.region)
    else:
        # Validate that the bucket region matches session region; hint if not
        try:
            import boto3
            from .aws import get_bucket_region
            session = boto3.session.Session()
            sess_region = session.region_name
            bucket_region = get_bucket_region(args.bucket)
            if sess_region and bucket_region and sess_region != bucket_region:
                print(
                    f"Warning: session region {sess_region} differs from bucket region {bucket_region}. "
                    f"Consider --region {bucket_region}.",
                    file=sys.stderr,
                )
        except Exception:
            pass

    pdfs = find_pdfs(args.inputs, recursive=not args.no_recursive)
    if not pdfs:
        print("No PDFs found", file=sys.stderr)
        return 2
    submit_and_collect(
        pdfs,
        bucket=args.bucket,
        key_prefix=args.prefix,
        output_dir=Path(args.output_dir),
        concurrency=args.jobs,
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.timeout_seconds,
        delete_uploaded=(not args.keep_uploaded),
    )
    return 0


