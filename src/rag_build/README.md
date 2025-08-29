## RAG Build (end-to-end)

Orchestrates: OCR (Textract) → clean → non-overlap split → merge → overlap chunk → embed+insert → manifests.

### Usage

```bash
export OPENAI_API_KEY=...
uv run rag-build ./pdfs --db ./data/vdb --collection toy-project \
  --embed-model text-embedding-3-small -j 6 --min-chars 1500 --max-chars 2500 --overlap 300 --out ./build
```

Outputs:
- `build/manifests/docs.jsonl` – per-document records
- `build/manifests/chunks.jsonl` – per-chunk records
- `build/ocr_text/` – OCR text
- `build/clean_text/` – cleaned and merged text (per doc)

Notes:
- Current cleaner is a placeholder; wire `textproc` or your own LLM cleaning as a next step.
- Incremental behavior can be extended using sha256s in the manifests.

