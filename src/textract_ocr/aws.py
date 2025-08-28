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


