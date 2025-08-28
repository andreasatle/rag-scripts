from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from .embedding import EmbeddingConfig, build_embedding_function


VDB_MARKER_FILENAME = ".vectordb"


@dataclass
class VectorDBConfig:
    persist_directory: Path
    # Future: add embedding function, model settings, collection defaults


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def create_persistent_db(path: str | os.PathLike[str]) -> Path:
    """
    Create (or open) a persistent ChromaDB database at the given path.

    Ensures a safety marker file exists to identify the directory as a vector DB root.
    Returns the resolved path.
    """
    resolved = Path(path).expanduser().resolve()
    _ensure_directory(resolved)

    marker = resolved / VDB_MARKER_FILENAME
    if not marker.exists():
        marker.write_text("chroma\n")

    # Initialize the client to materialize the persistence layout
    chromadb.PersistentClient(path=str(resolved))
    return resolved


def delete_persistent_db(path: str | os.PathLike[str], force: bool = False) -> None:
    """
    Delete the persistent database directory at path.

    Safety: requires a marker file in the directory unless force=True.
    """
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        return

    marker = resolved / VDB_MARKER_FILENAME
    if not force and not marker.exists():
        raise RuntimeError(
            f"Refusing to delete '{resolved}': safety marker '{VDB_MARKER_FILENAME}' missing. Use --force to override."
        )

    shutil.rmtree(resolved)


def get_client(path: str | os.PathLike[str]) -> ClientAPI:
    resolved = Path(path).expanduser().resolve()
    return chromadb.PersistentClient(path=str(resolved))


def get_or_create_collection(
    db_path: str | os.PathLike[str],
    name: str,
    embedding: EmbeddingConfig | None = None,
) -> Collection:
    client = get_client(db_path)
    ef = build_embedding_function(embedding or EmbeddingConfig())
    return client.get_or_create_collection(name=name, embedding_function=ef)


def get_collection(db_path: str | os.PathLike[str], name: str) -> Collection:
    """Get an existing collection without requiring an embedding function."""
    client = get_client(db_path)
    return client.get_collection(name=name)

