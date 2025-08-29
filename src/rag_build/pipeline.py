from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from textract_ocr.pipeline import find_pdfs, submit_and_collect
from textsplit.cli import split_text_minmax
from vectordb.embedding import EmbeddingConfig
from vectordb.manager import get_or_create_collection


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
) -> int:
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
    for p in pdfs:
        doc_id = p.stem
        docs.append(DocRecord(doc_id=doc_id, source_path=str(p), sha256_bytes=sha256_bytes(p)))

    # Submit OCR jobs
    results = submit_and_collect(
        pdfs, bucket="", key_prefix="", output_dir=ocr_dir, concurrency=jobs, poll_seconds=5.0, timeout_seconds=1800.0, delete_uploaded=False
    )
    # submit_and_collect as used here expects AWS setup; in practice you'll pass bucket via CLI in a future iteration

    # Update OCR paths
    for src, dst in results:
        for d in docs:
            if Path(d.source_path) == src:
                d.ocr_text_path = str(dst)
                d.status = "ocr_done"

    write_jsonl(manifests_dir / "docs.jsonl", (asdict(d) for d in docs))

    # 2) Clean (via placeholder) and 3) Non-overlap pre-clean split, then merge
    for d in docs:
        if not d.ocr_text_path:
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
    for d in docs:
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
    print(f"Build complete. Docs: {len(docs)}, Chunks: {len(chunk_records)}")
    return 0


