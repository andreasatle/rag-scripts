from __future__ import annotations

import concurrent.futures as cf
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

from .aws import (
    TextractJob,
    upload_file_to_s3,
    start_textract_job,
    poll_textract_job,
    fetch_textract_text,
    delete_s3_object,
    head_s3_object,
)


def find_pdfs(paths: Iterable[str], recursive: bool = True) -> List[Path]:
    results: List[Path] = []
    for p_str in paths:
        p = Path(p_str)
        if p.is_dir():
            iterator = p.rglob("*.pdf") if recursive else p.glob("*.pdf")
            for f in iterator:
                results.append(f)
        elif p.is_file() and p.suffix.lower() == ".pdf":
            results.append(p)
    # Deduplicate and sort for stability
    return sorted(set(results))


@dataclass
class Submission:
    local: Path
    bucket: str
    key: str


def submit_and_collect(
    pdfs: List[Path],
    bucket: str,
    key_prefix: str,
    output_dir: Path,
    concurrency: int = 4,
    poll_seconds: float = 5.0,
    timeout_seconds: float = 1800.0,
    delete_uploaded: bool = False,
) -> List[Tuple[Path, Path]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    submissions: List[Submission] = []
    for pdf in pdfs:
        key = f"{key_prefix.rstrip('/')}/{pdf.name}"
        submissions.append(Submission(local=pdf, bucket=bucket, key=key))

    # Upload and start jobs concurrently
    with cf.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []
        for s in submissions:
            futures.append(
                executor.submit(_run_single, s, output_dir, poll_seconds, timeout_seconds, delete_uploaded)
            )
        results: List[Tuple[Path, Path]] = []
        for fut in cf.as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                print(f"Failed job: {exc}")
        return results


def _run_single(
    sub: Submission,
    output_dir: Path,
    poll_seconds: float,
    timeout_seconds: float,
    delete_uploaded: bool,
) -> Tuple[Path, Path]:
    upload_file_to_s3(sub.local, sub.bucket, sub.key)
    # Confirm object is readable by Textract before starting the job
    head_s3_object(sub.bucket, sub.key)
    job = start_textract_job(sub.bucket, sub.key)
    poll_textract_job(job.job_id, poll_seconds=poll_seconds, timeout_seconds=timeout_seconds)
    text = fetch_textract_text(job.job_id)
    dst = output_dir / (sub.local.stem + ".txt")
    dst.write_text(text, encoding="utf-8")
    if delete_uploaded:
        try:
            delete_s3_object(sub.bucket, sub.key)
        except Exception as exc:
            print(f"Warning: failed to delete s3://{sub.bucket}/{sub.key}: {exc}")
    return sub.local, dst


def _run_single_with_id(
    sub: Submission,
    output_dir: Path,
    poll_seconds: float,
    timeout_seconds: float,
    delete_uploaded: bool,
) -> Tuple[Path, Path, str]:
    upload_file_to_s3(sub.local, sub.bucket, sub.key)
    head_s3_object(sub.bucket, sub.key)
    job = start_textract_job(sub.bucket, sub.key)
    poll_textract_job(job.job_id, poll_seconds=poll_seconds, timeout_seconds=timeout_seconds)
    text = fetch_textract_text(job.job_id)
    dst = output_dir / (sub.local.stem + ".txt")
    dst.write_text(text, encoding="utf-8")
    if delete_uploaded:
        try:
            delete_s3_object(sub.bucket, sub.key)
        except Exception as exc:
            print(f"Warning: failed to delete s3://{sub.bucket}/{sub.key}: {exc}")
    return sub.local, dst, job.job_id


def submit_and_collect_with_ids(
    pdfs: List[Path],
    bucket: str,
    key_prefix: str,
    output_dir: Path,
    concurrency: int = 4,
    poll_seconds: float = 5.0,
    timeout_seconds: float = 1800.0,
    delete_uploaded: bool = False,
) -> List[Tuple[Path, Path, str]]:
    """Same as submit_and_collect, but returns (src, dst, job_id)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    submissions: List[Submission] = []
    for pdf in pdfs:
        key = f"{key_prefix.rstrip('/')}/{pdf.name}"
        submissions.append(Submission(local=pdf, bucket=bucket, key=key))

    with cf.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(_run_single_with_id, s, output_dir, poll_seconds, timeout_seconds, delete_uploaded)
            for s in submissions
        ]
        results: List[Tuple[Path, Path, str]] = []
        for fut in cf.as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                print(f"Failed job: {exc}")
        return results


