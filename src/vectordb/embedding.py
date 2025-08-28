from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from chromadb.utils import embedding_functions


DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"


@dataclass
class EmbeddingConfig:
    provider: str = "openai"
    model: str = DEFAULT_OPENAI_EMBEDDING_MODEL
    api_key: Optional[str] = None


def build_embedding_function(config: EmbeddingConfig):
    if config.provider == "openai":
        api_key = config.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set for OpenAI embeddings")
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=config.model,
        )

    raise ValueError(f"Unsupported embedding provider: {config.provider}")


