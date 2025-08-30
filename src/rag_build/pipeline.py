from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from textract_ocr.pipeline import find_pdfs, submit_and_stream_with_ids
from textract_ocr.aws import fetch_textract_qc, ensure_bucket_exists, delete_bucket_recursive
import uuid
from textsplit.cli import split_text_minmax
from vectordb.embedding import EmbeddingConfig
from vectordb.manager import get_or_create_collection
from tqdm import tqdm
import boto3


def sha256_bytes(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class DocRecord:
    doc_id: str
    source_path: str
    sha256_bytes: str
    ocr_text_path: Optional[str] = None
    cleaned_text_path: Optional[str] = None
    status: str = "pending"
    ocr_qc_score: Optional[int] = None
    ocr_qc_reason: Optional[str] = None


@dataclass
class ChunkRecord:
    chunk_id: str
    doc_id: str
    start_char: int
    end_char: int
    overlap: int
    embed_model: str
    inserted: bool = False


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def clean_text(text: str) -> str:
    # Minimal placeholder: pass-through for now
    # Future: call textproc pipeline or LLM API
    return text


def chunk_overlap(text: str, max_chars: int, overlap: int) -> List[Tuple[int, int, str]]:
    chunks: List[Tuple[int, int, str]] = []
    start = 0
    L = len(text)
    step = max(1, max_chars - overlap)
    while start < L:
        end = min(L, start + max_chars)
        chunks.append((start, end, text[start:end]))
        if end == L:
            break
        start = end - overlap
    return chunks


def run_build(
    pdfs_dir: Path,
    out_dir: Path,
    db_path: str,
    collection: str,
    embed_model: str,
    jobs: int,
    min_chars: int,
    max_chars: int,
    overlap: int,
    env_file: Optional[Path],
    qc_min_chars: int,
    qc_threshold: int,
    s3_bucket: Optional[str] = None,
    s3_prefix: str = "textract-inputs",
    aws_region: Optional[str] = None,
) -> int:
    # Load environment: explicit --env if provided, else best-effort ./.env
    if env_file and env_file.exists():
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv(dotenv_path=env_file, override=False)
            print(f"Loaded environment from {env_file}")
        except Exception as e:
            print(f"Warning: could not load env file {env_file}: {e}")
    else:
        default_env = Path(".env")
        if default_env.exists():
            try:
                from dotenv import load_dotenv  # type: ignore
                load_dotenv(dotenv_path=default_env, override=False)
                print(f"Loaded environment from {default_env}")
            except Exception:
                pass
    out_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir = out_dir / "manifests"
    ocr_dir = out_dir / "ocr_text"
    clean_dir = out_dir / "clean_text"

    # 1) OCR
    pdfs = find_pdfs([str(pdfs_dir)], recursive=True)
    if not pdfs:
        print("No PDFs found")
        return 2

    # Compute sha for doc_id determinism
    docs: List[DocRecord] = []
    for p in tqdm(pdfs, desc="Indexing PDFs"):
        doc_id = p.stem
        docs.append(DocRecord(doc_id=doc_id, source_path=str(p), sha256_bytes=sha256_bytes(p)))

    # Submit OCR jobs
    if not s3_bucket:
        # Create a random, globally unique bucket name (lowercase, hyphenated)
        s3_bucket = f"rag-textract-{uuid.uuid4().hex}"
        print(f"No --s3-bucket provided; creating temporary bucket: {s3_bucket}")
    # Ensure boto3 session region matches desired region
    if aws_region:
        try:
            boto3.setup_default_session(region_name=aws_region)
        except Exception:
            pass
    ensure_bucket_exists(s3_bucket, region=aws_region)
    # Stream per-doc pipeline
    job_id_by_src: dict[Path, str] = {}
    qc_failed_accum: List[DocRecord] = []
    for src, dst, jid in tqdm(submit_and_stream_with_ids(
        pdfs, bucket=s3_bucket, key_prefix=s3_prefix, output_dir=ocr_dir, concurrency=jobs, poll_seconds=5.0, timeout_seconds=1800.0, delete_uploaded=False
    ), desc="OCR streaming"):
        # Record OCR
        rec = next((d for d in docs if Path(d.source_path) == src), None)
        if not rec:
            continue
        rec.ocr_text_path = str(dst)
        rec.status = "ocr_done"
        job_id_by_src[src] = jid

        # QC this doc
        raw = Path(rec.ocr_text_path).read_text(encoding="utf-8")
        length = len(raw)
        non_ascii_ratio = sum(1 for ch in raw if ord(ch) > 127) / max(1, length)
        digit_ratio = sum(ch.isdigit() for ch in raw) / max(1, length)
        score = 100
        if length < qc_min_chars:
            score -= 40
        if non_ascii_ratio > 0.3:
            score -= int((non_ascii_ratio - 0.3) * 200)
        if digit_ratio > 0.6:
            score -= int((digit_ratio - 0.6) * 150)
        score = max(0, min(100, score))
        try:
            qc = fetch_textract_qc(job_id=jid)
        except Exception:
            qc = None
        rec.ocr_qc_score = score if not qc else int((score + qc.get("score", score)) / 2)
        if rec.ocr_qc_score < qc_threshold:
            rec.status = "qc_failed"
            rec.ocr_qc_reason = f"len={length}, non_ascii={non_ascii_ratio:.2f}, digits={digit_ratio:.2f}"
            qc_failed_accum.append(rec)
            write_jsonl(manifests_dir / "docs.jsonl", [asdict(rec)])
            continue
        else:
            rec.status = "qc_ok"
            write_jsonl(manifests_dir / "docs.jsonl", [asdict(rec)])

        # Clean & merge
        parts = split_text_minmax(raw, min_chars=min_chars, max_chars=max_chars)
        cleaned_parts = [clean_text(t) for t in parts]
        merged = "\n\n".join(cleaned_parts)
        dst_clean = clean_dir / (rec.doc_id + ".txt")
        dst_clean.parent.mkdir(parents=True, exist_ok=True)
        dst_clean.write_text(merged, encoding="utf-8")
        rec.cleaned_text_path = str(dst_clean)
        rec.status = "clean_done"
        write_jsonl(manifests_dir / "docs.jsonl", [asdict(rec)])

        # Chunk & embed
        emb = EmbeddingConfig(model=embed_model)
        coll = get_or_create_collection(db_path, collection, emb)
        spans = chunk_overlap(merged, max_chars=max_chars, overlap=overlap)
        if spans:
            documents: List[str] = []
            metadatas: List[dict] = []
            ids: List[str] = []
            chunk_records: List[ChunkRecord] = []
            for idx, (s, e, t) in enumerate(spans, start=1):
                cid = f"{rec.doc_id}:{idx}"
                documents.append(t)
                metadatas.append({"doc_id": rec.doc_id, "source": rec.source_path, "chunk_index": idx, "start_char": s, "end_char": e})
                ids.append(cid)
                chunk_records.append(ChunkRecord(chunk_id=cid, doc_id=rec.doc_id, start_char=s, end_char=e, overlap=overlap, embed_model=embed_model, inserted=True))
            coll.add(documents=documents, metadatas=metadatas, ids=ids)
            write_jsonl(manifests_dir / "chunks.jsonl", (asdict(c) for c in chunk_records))

    # After stream, write QC report if any
    if qc_failed_accum:
        report_path = out_dir / "qc_failed.txt"
        lines = [f"QC FAILED ({len(qc_failed_accum)})\n"]
        for d in qc_failed_accum:
            lines.append(f"- {d.doc_id} | {d.source_path} | score={d.ocr_qc_score} | reason={d.ocr_qc_reason}")
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"QC report written: {report_path}")

    # 2) QC on OCR text; skip downstream if below threshold
    for d in tqdm(docs, desc="QC"):
        if not d.ocr_text_path:
            continue
        raw = Path(d.ocr_text_path).read_text(encoding="utf-8")
        length = len(raw)
        non_ascii_ratio = sum(1 for ch in raw if ord(ch) > 127) / max(1, length)
        digit_ratio = sum(ch.isdigit() for ch in raw) / max(1, length)
        # Simple heuristic score 0-100
        score = 100
        if length < qc_min_chars:
            score -= 40
        if non_ascii_ratio > 0.3:
            score -= int((non_ascii_ratio - 0.3) * 200)
        if digit_ratio > 0.6:
            score -= int((digit_ratio - 0.6) * 150)
        score = max(0, min(100, score))
        # Combine content heuristics with Textract confidences if available
        try:
            jid = job_id_by_src.get(Path(d.source_path))
            qc = fetch_textract_qc(job_id=jid) if jid else None
        except Exception:
            qc = None
        d.ocr_qc_score = score if not qc else int((score + qc.get("score", score)) / 2)
        if score < qc_threshold:
            d.status = "qc_failed"
            d.ocr_qc_reason = f"len={length}, non_ascii={non_ascii_ratio:.2f}, digits={digit_ratio:.2f}"
        else:
            d.status = "qc_ok"

    write_jsonl(manifests_dir / "docs.jsonl", (asdict(d) for d in docs))

    # 3) Clean (via placeholder) and 4) Non-overlap pre-clean split, then merge
    for d in tqdm(docs, desc="Clean & merge"):
        if not d.ocr_text_path or d.status == "qc_failed":
            continue
        text = Path(d.ocr_text_path).read_text(encoding="utf-8")
        # Pre-clean split to shrink context
        parts = split_text_minmax(text, min_chars=min_chars, max_chars=max_chars)
        cleaned_parts = [clean_text(t) for t in parts]
        merged = "\n\n".join(cleaned_parts)
        dst = clean_dir / (d.doc_id + ".txt")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(merged, encoding="utf-8")
        d.cleaned_text_path = str(dst)
        d.status = "clean_done"

    write_jsonl(manifests_dir / "docs.jsonl", (asdict(d) for d in docs))

    # 5) Overlapping chunks + 6) Embed+insert
    emb = EmbeddingConfig(model=embed_model)
    coll = get_or_create_collection(db_path, collection, emb)
    chunk_records: List[ChunkRecord] = []
    for d in tqdm(docs, desc="Chunk & embed"):
        if not d.cleaned_text_path:
            continue
        text = Path(d.cleaned_text_path).read_text(encoding="utf-8")
        spans = chunk_overlap(text, max_chars=max_chars, overlap=overlap)
        if not spans:
            continue
        documents: List[str] = []
        metadatas: List[dict] = []
        ids: List[str] = []
        for idx, (s, e, t) in enumerate(spans, start=1):
            cid = f"{d.doc_id}:{idx}"
            documents.append(t)
            metadatas.append({"doc_id": d.doc_id, "source": d.source_path, "chunk_index": idx, "start_char": s, "end_char": e})
            ids.append(cid)
            chunk_records.append(ChunkRecord(chunk_id=cid, doc_id=d.doc_id, start_char=s, end_char=e, overlap=overlap, embed_model=embed_model, inserted=True))
        coll.add(documents=documents, metadatas=metadatas, ids=ids)

    write_jsonl(manifests_dir / "chunks.jsonl", (asdict(c) for c in chunk_records))

    # Cleanup temporary bucket if we created it
    if s3_bucket and s3_bucket.startswith("rag-textract-"):
        try:
            print(f"Cleaning up temporary bucket: {s3_bucket}")
            delete_bucket_recursive(s3_bucket)
        except Exception as e:
            print(f"Warning: failed to delete bucket {s3_bucket}: {e}")

    print(f"Build complete. Docs: {len(docs)}, Chunks: {len(chunk_records)}")
    return 0


