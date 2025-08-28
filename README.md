## RAG Scripts

Utilities and CLIs to extract text, split/chunk, embed into a persistent vector DB (Chroma), and chat with a RAG UI.

### Quickstart

```bash
uv sync
```

### Modules

- Vector DB (Chroma) — create/delete/insert/query a persistent store
  - See [src/vectordb/README.md](src/vectordb/README.md)
- Gradio RAG Chat — chat UI that retrieves from your collection and answers with OpenAI
  - See [src/ragchat/README.md](src/ragchat/README.md)
- Textract OCR — batch PDFs through AWS Textract to text
  - See [src/textract_ocr/README.md](src/textract_ocr/README.md)
- LLM Text Processing — run processed text through OpenAI
  - See [src/textproc/README.md](src/textproc/README.md)
- Text Split/Legal Chunk — split/merge and legal-aware chunking helpers
  - See [src/textsplit/README.md](src/textsplit/README.md)
- DOCX → Text — extract text from .docx
  - See [src/docx_text/README.md](src/docx_text/README.md)

### Requirements

- Python 3.12+
- For embeddings and chat: `OPENAI_API_KEY` in environment or `.env`
- For Textract: AWS credentials via environment/shared files/IAM

### Scripts

Registered console scripts (see per-module docs for details):

- `vector-db` — vector DB management
- `rag-chat` — RAG chat UI
- `textract-ocr` — OCR pipeline
- `llm-process-text` — LLM processing
- `split-text-files`, `merge-split-files`, `legal-chunk-text` — splitting utilities
- `docx-to-text` — DOCX extraction
