from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict, Any

import gradio as gr

from vectordb.manager import get_collection_with_embedding
from vectordb.embedding import EmbeddingConfig, DEFAULT_OPENAI_EMBEDDING_MODEL


@dataclass
class RAGConfig:
    db_path: str
    collection: str
    embed_provider: str = "openai"
    embed_model: str = DEFAULT_OPENAI_EMBEDDING_MODEL
    top_k: int = 4
    system_prompt: str = "You are a helpful assistant. Use the provided context excerpts to answer. If unsure, say you don't know."
    model: str = "gpt-4o-mini"


def _load_openai_client():
    try:
        from openai import OpenAI  # type: ignore
    except Exception as import_err:
        raise RuntimeError("OpenAI SDK is not installed. Install with 'uv add .[clean]' or ensure pyproject has openai.") from import_err
    return OpenAI()


def build_chain(config: RAGConfig):
    coll = get_collection_with_embedding(
        config.db_path,
        config.collection,
        EmbeddingConfig(provider=config.embed_provider, model=config.embed_model),
    )
    openai_client = _load_openai_client()

    # Log collection size for quick diagnostics
    try:
        count = int(coll.count())  # type: ignore[attr-defined]
        print(
            f"[rag-chat] Connected to DB='{config.db_path}' collection='{config.collection}' items={count} embed_model='{config.embed_model}'"
        )
    except Exception:
        pass

    def chat_fn(message: str, history: List[Dict[str, Any]]):
        query = message.strip()
        if not query:
            return ""

        res = coll.query(query_texts=[query], n_results=config.top_k, include=["documents", "metadatas", "distances"])  # type: ignore[arg-type]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        if not docs:
            print("[rag-chat] Retrieval returned 0 matches. Verify DB path, collection name, and embedding model.")

        context_lines = []
        for i, (doc, meta) in enumerate(zip(docs, metas), start=1):
            name = (meta or {}).get("name", "")
            src = (meta or {}).get("source", "")
            context_lines.append(f"[{i}] {name} | {src}\n{doc}")
        context = "\n\n".join(context_lines) if context_lines else ""

        messages = []
        if config.system_prompt:
            messages.append({"role": "system", "content": config.system_prompt})
        if context_lines:
            print(f"[rag-chat] Using {len(context_lines)} context chunks")
            for i, (doc, meta) in enumerate(zip(docs, metas), start=1):
                name = (meta or {}).get("name", "")
                src = (meta or {}).get("source", "")
                label = name
                if src:
                    src_basename = Path(src).name
                    if not name:
                        label = src_basename
                    elif name != src_basename:
                        label = f"{name} | {src}"
                messages.append({
                    "role": "user",
                    "content": f"Context [{i}]: {label}\n{doc}",
                })
            messages.append({"role": "user", "content": f"Question: {query}"})
        else:
            messages.append({"role": "user", "content": query})
        print(f"messages: {messages}")
        try:
            completion = openai_client.chat.completions.create(
                model=config.model,
                messages=messages,
                temperature=0.2,
            )
            answer = completion.choices[0].message.content or ""
            return answer if isinstance(answer, str) and answer.strip() else "No answer generated."
        except Exception as exc:
            print(f"[rag-chat] OpenAI error: {exc}")
            return f"Error: {exc}"

    return chat_fn


def launch_app(config: RAGConfig):
    chat_fn = build_chain(config)
    with gr.Blocks() as demo:
        gr.Markdown(f"# RAG Chat — Collection: {config.collection}")
        chatbot = gr.Chatbot(type="messages", height=500)
        msg = gr.Textbox(placeholder="Ask a question...")
        clear = gr.Button("Clear")

        def user_submit(user_message, chat_history):
            if not user_message:
                return "", chat_history
            return "", chat_history + [{"role": "user", "content": user_message}]

        def bot_respond(chat_history):
            user_message = ""
            for m in reversed(chat_history):
                if isinstance(m, dict) and m.get("role") == "user":
                    user_message = str(m.get("content", ""))
                    break
            answer = chat_fn(user_message, chat_history)
            chat_history.append({"role": "assistant", "content": answer})
            return chat_history

        msg.submit(user_submit, [msg, chatbot], [msg, chatbot]).then(
            bot_respond, chatbot, chatbot
        )
        clear.click(lambda: [], None, chatbot, queue=False)

    demo.launch()


