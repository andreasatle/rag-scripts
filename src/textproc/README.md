## LLM Text Processing Pipeline

Run OCR-corrected text through an LLM with concurrency and timeouts.

### Usage

```bash
uv run llm-process-text INPUT_DIR -o OUTPUT_DIR [--env .env] [--model gpt-4o-mini] [--recursive] [-j 8] [--timeout-seconds 30] [--max-tokens 1000]
```

Requires `OPENAI_API_KEY` via env or `.env`.


