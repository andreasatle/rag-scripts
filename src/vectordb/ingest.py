from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

from .manager import get_or_create_collection
from .embedding import EmbeddingConfig


@dataclass
class InsertOptions:
    recursive: bool = True
    file_glob: str = "*.txt"
    batch_size: int = 64


def _iter_text_files(target: Path, recursive: bool, file_glob: str) -> Iterable[Path]:
    if target.is_file():
        yield target
        return
    if recursive:
        yield from target.rglob(file_glob)
    else:
        yield from target.glob(file_glob)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _make_id(collection: str, path: Path, index: int) -> str:
    # Use the full (resolved) path to avoid collisions for same-named files
    return f"{collection}:{path.as_posix()}:{index}"


def insert_texts(
    db_path: str | os.PathLike[str],
    collection: str,
    source_path: str | os.PathLike[str],
    embedding: EmbeddingConfig | None = None,
    options: InsertOptions | None = None,
) -> int:
    opts = options or InsertOptions()
    src = Path(source_path).expanduser().resolve()
    coll = get_or_create_collection(db_path, collection, embedding)

    docs: List[str] = []
    metadatas: List[dict] = []
    ids: List[str] = []
    total_added = 0

    for file_path in _iter_text_files(src, opts.recursive, opts.file_glob):
        if not file_path.is_file():
            continue
        try:
            text = _read_text(file_path)
        except Exception:
            continue

        if not text.strip():
            continue

        doc_id = _make_id(collection, file_path, 0)
        docs.append(text)
        metadatas.append({
            "source": str(file_path),
            "name": file_path.name,
        })
        ids.append(doc_id)

        if len(docs) >= max(1, opts.batch_size):
            coll.add(documents=docs, metadatas=metadatas, ids=ids)
            total_added += len(docs)
            docs.clear(); metadatas.clear(); ids.clear()

    if docs:
        coll.add(documents=docs, metadatas=metadatas, ids=ids)
        total_added += len(docs)

    return total_added


