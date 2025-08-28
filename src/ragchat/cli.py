from __future__ import annotations

import argparse
from pathlib import Path

from .app import RAGConfig, launch_app


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rag-chat", description="Launch a Gradio RAG chatbot for a Chroma collection")
    p.add_argument("db", help="Path to persistent DB directory")
    p.add_argument("collection", help="Collection name")
    p.add_argument("--embed-model", default="text-embedding-3-small", help="Embedding model for queries")
    p.add_argument("--top-k", type=int, default=4, help="Top K retrieval")
    p.add_argument("--model", default="gpt-4o-mini", help="Chat completion model")
    p.add_argument("--system", default=None, help="System prompt override")
    p.add_argument("--env", default=None, help="Path to .env file to load (OPENAI_API_KEY, etc.)")
    return p


def _load_env(maybe_path: str | None) -> None:
    if not maybe_path:
        default = Path(".env")
        if default.exists():
            try:
                from dotenv import load_dotenv  # type: ignore
                load_dotenv(dotenv_path=default, override=False)
            except Exception:
                pass
        return
    p = Path(maybe_path)
    if p.exists():
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv(dotenv_path=p, override=False)
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _load_env(args.env)

    cfg = RAGConfig(
        db_path=args.db,
        collection=args.collection,
        embed_model=args.embed_model,
        top_k=int(args.top_k),
        model=args.model,
        system_prompt=args.system or "You are a helpful assistant. Use the provided context excerpts to answer. If unsure, say you don't know.",
    )
    launch_app(cfg)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


