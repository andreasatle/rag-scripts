from __future__ import annotations

from typing import Dict, List, Any

from .manager import get_collection_with_embedding
from .embedding import EmbeddingConfig


def query_collection(
    db_path: str,
    collection: str,
    query_text: str,
    *,
    top_k: int = 5,
    embedding: EmbeddingConfig | None = None,
    include: List[str] | None = None,
) -> Dict[str, Any]:
    coll = get_collection_with_embedding(db_path, collection, embedding)
    res = coll.query(
        query_texts=[query_text],
        n_results=top_k,
        include=include or ["documents", "metadatas", "distances"],  # type: ignore[arg-type]
    )
    return res


