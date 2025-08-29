from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict, Any
import re

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
    history_max_messages: int = 8
    history_summarize: bool = False
    history_summary_max_chars: int = 800


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

        messages: List[Dict[str, Any]] = []
        if config.system_prompt:
            messages.append({"role": "system", "content": config.system_prompt})
        # Include prior conversation (excluding the latest user message), limited window
        prior_history: List[Dict[str, Any]] = []
        if history:
            if isinstance(history[-1], dict) and history[-1].get("role") == "user":
                prior_history = history[:-1]
            else:
                prior_history = history
        if prior_history:
            # Split into older (to summarize) and recent (verbatim)
            recent = prior_history[-config.history_max_messages :]
            older = prior_history[:-config.history_max_messages]

            if config.history_summarize and older:
                # naive compression: join with labels and trim
                parts: List[str] = []
                for m in older:
                    if not isinstance(m, dict):
                        continue
                    r = m.get("role")
                    c = m.get("content")
                    if r in ("user", "assistant") and isinstance(c, str) and c.strip():
                        parts.append(f"{r}: {c.strip()}")
                summary_text = ("\n".join(parts))[: max(0, config.history_summary_max_chars)]
                if summary_text:
                    messages.append({
                        "role": "system",
                        "content": f"Conversation summary (earlier turns):\n{summary_text}",
                    })

            for m in recent:
                if not isinstance(m, dict):
                    continue
                role = m.get("role")
                content = m.get("content")
                if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                    messages.append({"role": role, "content": content})
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
        try:
            completion = openai_client.chat.completions.create(
                model=config.model,
                messages=messages,
                temperature=0.2,
            )
            answer = completion.choices[0].message.content or ""

            # Build sources text separately (do not append to answer)
            sources_text = ""
            if context_lines:
                def _clean_display(name: str, src: str) -> str:
                    display = name or Path(src).name
                    base = Path(display).stem if display else display
                    # remove only '_split_<n>_of_<m>' suffixes
                    base = re.sub(r"_split_\d+_of_\d+$", "", base)
                    return base or (Path(src).stem if src else display)

                # Map each label to the list of context indices that contributed
                label_to_indices: Dict[str, List[int]] = {}
                order: List[str] = []
                for idx, meta in enumerate(metas, start=1):
                    nm = (meta or {}).get("name", "")
                    sp = (meta or {}).get("source", "")
                    label = _clean_display(nm, sp)
                    if label not in label_to_indices:
                        order.append(label)
                        label_to_indices[label] = []
                    label_to_indices[label].append(idx)

                lines: List[str] = []
                for label in order:
                    idxs = label_to_indices.get(label, [])
                    idx_str = ", ".join(str(i) for i in idxs) if idxs else ""
                    suffix = f" ({len(idxs)} chunks)" if len(idxs) > 1 else ""
                    lines.append(f"- [{idx_str}] {label}{suffix}")
                sources_text = "\n".join(lines)

            final_answer = answer if isinstance(answer, str) and answer.strip() else "No answer generated."
            return final_answer, sources_text
        except Exception as exc:
            print(f"[rag-chat] OpenAI error: {exc}")
            return f"Error: {exc}", ""

    return chat_fn


def launch_app(config: RAGConfig):
    chat_fn = build_chain(config)
    with gr.Blocks() as demo:
        gr.Markdown(f"# RAG Chat — Collection: {config.collection}")
        chatbot = gr.Chatbot(type="messages", height=500)
        with gr.Row():
            msg = gr.Textbox(placeholder="Ask a question...", scale=8)
            show_sources = gr.Button("Sources", scale=1)
            clear = gr.Button("Clear", scale=1)
        sources_state = gr.State("")
        sources_md = gr.Markdown(visible=False)

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
            answer, srcs = chat_fn(user_message, chat_history)
            chat_history.append({"role": "assistant", "content": answer})
            return chat_history, (srcs or "_No sources for this answer._")

        msg.submit(user_submit, [msg, chatbot], [msg, chatbot]).then(
            bot_respond, chatbot, [chatbot, sources_state]
        )
        show_sources.click(
            lambda s: gr.update(value=s, visible=True), inputs=sources_state, outputs=sources_md
        )
        clear.click(lambda: ([], gr.update(value="", visible=False), ""), None, [chatbot, sources_md, sources_state], queue=False)

    demo.launch()


