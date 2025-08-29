from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import boto3


@dataclass
class TextractJob:
    job_id: str
    s3_bucket: str
    s3_object_key: str


def upload_file_to_s3(local_path: Path, bucket: str, key: str) -> None:
    s3 = boto3.client("s3")
    s3.upload_file(str(local_path), bucket, key)


def start_textract_job(bucket: str, key: str) -> TextractJob:
    client = boto3.client("textract")
    resp = client.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    return TextractJob(job_id=resp["JobId"], s3_bucket=bucket, s3_object_key=key)


def poll_textract_job(job_id: str, poll_seconds: float = 5.0, timeout_seconds: float = 1800.0) -> None:
    client = boto3.client("textract")
    start = time.time()
    while True:
        resp = client.get_document_text_detection(JobId=job_id, MaxResults=1)
        status = resp.get("JobStatus")
        if status in {"SUCCEEDED", "FAILED", "PARTIAL_SUCCESS"}:
            if status != "SUCCEEDED":
                raise RuntimeError(f"Textract job {job_id} ended with status {status}")
            return
        if time.time() - start > timeout_seconds:
            raise TimeoutError(f"Timed out waiting for Textract job {job_id}")
        time.sleep(poll_seconds)


def fetch_textract_text(job_id: str) -> str:
    client = boto3.client("textract")
    next_token: Optional[str] = None
    lines: List[str] = []
    while True:
        kwargs = {"JobId": job_id}
        if next_token:
            kwargs["NextToken"] = next_token
        resp = client.get_document_text_detection(**kwargs)
        for block in resp.get("Blocks", []):
            if block.get("BlockType") == "LINE":
                text = block.get("Text")
                if text:
                    lines.append(text)
        next_token = resp.get("NextToken")
        if not next_token:
            break
    return "\n".join(lines)


def fetch_textract_qc(job_id: str) -> dict:
    """Compute simple QC metrics from Textract detection results.

    Returns dict with keys: pages, words, lines, avg_conf, low_conf_share,
    handwriting_share, score (0-100).
    """
    client = boto3.client("textract")
    next_token: Optional[str] = None
    total_words = 0
    total_lines = 0
    total_pages = 0
    sum_conf_weighted = 0.0
    char_weight = 0
    low_conf_words = 0
    handwriting_lines = 0
    while True:
        kwargs = {"JobId": job_id}
        if next_token:
            kwargs["NextToken"] = next_token
        resp = client.get_document_text_detection(**kwargs)
        blocks = resp.get("Blocks", [])
        for b in blocks:
            btype = b.get("BlockType")
            if btype == "PAGE":
                total_pages += 1
            elif btype == "WORD":
                conf = float(b.get("Confidence") or 0.0)
                text = b.get("Text") or ""
                w = max(1, len(text))
                sum_conf_weighted += conf * w
                char_weight += w
                total_words += 1
                if conf < 80.0:
                    low_conf_words += 1
            elif btype == "LINE":
                total_lines += 1
                if (b.get("TextType") or "").upper() == "HANDWRITING":
                    handwriting_lines += 1
        next_token = resp.get("NextToken")
        if not next_token:
            break

    avg_conf = (sum_conf_weighted / char_weight) if char_weight else 0.0
    low_conf_share = (low_conf_words / total_words) if total_words else 1.0
    handwriting_share = (handwriting_lines / total_lines) if total_lines else 0.0

    # Simple score as discussed
    score = 0.7 * (avg_conf / 100.0) + 0.2 * (1.0 - low_conf_share) + 0.1 * (1.0 - handwriting_share)
    score = max(0, min(100, int(round(score * 100))))

    return {
        "pages": total_pages,
        "words": total_words,
        "lines": total_lines,
        "avg_conf": round(avg_conf, 2),
        "low_conf_share": round(low_conf_share, 3),
        "handwriting_share": round(handwriting_share, 3),
        "score": score,
    }


def delete_s3_object(bucket: str, key: str) -> None:
    s3 = boto3.client("s3")
    s3.delete_object(Bucket=bucket, Key=key)


def head_s3_object(bucket: str, key: str) -> None:
    s3 = boto3.client("s3")
    s3.head_object(Bucket=bucket, Key=key)


def get_bucket_region(bucket: str) -> Optional[str]:
    s3 = boto3.client("s3")
    resp = s3.get_bucket_location(Bucket=bucket)
    loc = resp.get("LocationConstraint")
    # us-east-1 is represented as None in older APIs
    return loc or "us-east-1"


# Convenience: ensure bucket exists (optionally create)
def ensure_bucket_exists(bucket: str, region: Optional[str] = None) -> None:
    s3 = boto3.client("s3")
    try:
        s3.head_bucket(Bucket=bucket)
        return
    except Exception:
        pass
    # Create when missing
    if region and region != "us-east-1":
        s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": region})
    else:
        s3.create_bucket(Bucket=bucket)

