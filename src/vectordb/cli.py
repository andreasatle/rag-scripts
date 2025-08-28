from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .manager import create_persistent_db, delete_persistent_db, VDB_MARKER_FILENAME, get_collection
from .ingest import insert_texts, InsertOptions
from .embedding import EmbeddingConfig, DEFAULT_OPENAI_EMBEDDING_MODEL


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vector-db",
        description="Manage a persistent local vector database (ChromaDB)",
    )

    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help="Path to .env file to load (OPENAI_API_KEY, etc.)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Create or open a persistent database at path")
    p_create.add_argument("path", help="Directory for persistence (will be created if missing)")

    p_delete = sub.add_parser("delete", help="Delete the persistent database at path")
    p_delete.add_argument("path", help="Database directory to delete")
    p_delete.add_argument(
        "--force",
        action="store_true",
        help=f"Bypass safety check requiring '{VDB_MARKER_FILENAME}' marker file",
    )

    p_insert = sub.add_parser("insert", help="Insert text files into a collection")
    p_insert.add_argument("db", help="Path to persistent DB directory")
    p_insert.add_argument("collection", help="Target collection name")
    p_insert.add_argument("source", help="Directory or single .txt file with text chunks")
    p_insert.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not recurse directories when reading files",
    )
    p_insert.add_argument(
        "--glob",
        default="*.txt",
        help="Glob for selecting files in directory (default: *.txt)",
    )
    p_insert.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Number of documents per add() call (prevents exceeding provider token limits)",
    )
    p_insert.add_argument(
        "--embed-provider",
        default="openai",
        choices=["openai"],
        help="Embedding provider",
    )
    p_insert.add_argument(
        "--embed-model",
        default=DEFAULT_OPENAI_EMBEDDING_MODEL,
        help="Embedding model name",
    )

    p_info = sub.add_parser("info", help="Show brief info about a collection")
    p_info.add_argument("db", help="Path to persistent DB directory")
    p_info.add_argument("collection", help="Collection name")
    p_info.add_argument("--json", action="store_true", help="Output JSON")

    return parser


def _load_env_from_arg(maybe_path: str | None) -> None:
    if not maybe_path:
        # Best-effort load from default .env in project root/cwd if present
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

    _load_env_from_arg(getattr(args, "env", None))

    if args.command == "create":
        target = create_persistent_db(args.path)
        print(str(target))
        return 0

    if args.command == "delete":
        try:
            delete_persistent_db(args.path, force=bool(args.force))
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0

    if args.command == "insert":
        emb = EmbeddingConfig(provider=args.embed_provider, model=args.embed_model)
        opts = InsertOptions(recursive=not bool(args.no_recursive), file_glob=args.glob, batch_size=int(args.batch_size))
        count = insert_texts(args.db, args.collection, args.source, embedding=emb, options=opts)
        print(count)
        return 0

    if args.command == "info":
        try:
            coll = get_collection(args.db, args.collection)
            count = coll.count()  # type: ignore[attr-defined]
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if bool(getattr(args, "json", False)):
            try:
                import json
                print(json.dumps({"collection": args.collection, "count": int(count)}))
            except Exception:
                print(int(count))
        else:
            print(int(count))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


