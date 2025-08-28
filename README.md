## Textract OCR Pipeline (PDF → text)

This tool batches PDFs through AWS Textract and writes extracted text files.

### Install

Requires Python 3.12+ and AWS credentials (via environment or config).

```bash
uv sync
# or: pip install -e .
```

### Usage

```bash
uv run textract-ocr INPUTS... -o OUTDIR --bucket BUCKET [--prefix PREFIX] [--region REGION] [-j JOBS] [--no-recursive] [--poll-seconds SEC] [--timeout-seconds SEC] [--keep-uploaded]
```

- `--bucket` S3 bucket for uploads
- `--prefix` S3 key prefix (default `textract-inputs`)
- `--region` AWS region override
- `-j/--jobs` concurrent documents processed (default 4)
- `--no-recursive` disable directory recursion
- `--poll-seconds` Textract job status poll interval
- `--timeout-seconds` per-document timeout
- `--keep-uploaded` keep S3 objects (default behavior is to delete after success)

Example:

```bash
uv run textract-ocr ./docs/ -o ./out --bucket my-bucket --prefix incoming/ocr --region us-east-1 -j 8
```

AWS credentials can be provided via environment, shared credentials/config files, or IAM role.



## Vector DB (ChromaDB persistence)

Create and delete a local persistent vector database using ChromaDB.

Install dependencies first:

```bash
uv sync
```

Usage:

```bash
# Create (or open) a persistent DB directory; prints the resolved path
uv run vector-db create ./data/vdb

# Delete the DB directory; requires a safety marker (created by the command)
uv run vector-db delete ./data/vdb

# Force delete even if the safety marker is missing
uv run vector-db delete ./data/vdb --force
```

Notes:
- A marker file named `.vectordb` is created in the DB root to avoid accidental deletes.
- Backed by ChromaDB's `PersistentClient`; later commands will reuse this path for insert/query.

### Insert text into a collection

Insert `.txt` chunks from a directory (recursively) or a single file into a collection with OpenAI embeddings:

```bash
export OPENAI_API_KEY=...  # required for embeddings (or put it in .env)

# From a directory of .txt chunks
uv run vector-db insert ./data/vdb my_collection ./chunks/ --glob "*.txt"

# From a single file
uv run vector-db insert ./data/vdb my_collection ./one-file.txt

# Non-recursive
uv run vector-db insert ./data/vdb my_collection ./chunks/ --no-recursive

# Choose embedding model
uv run vector-db insert ./data/vdb my_collection ./chunks/ --embed-model text-embedding-3-large
 
# Load variables from a specific .env file
uv run vector-db --env ./.env insert ./data/vdb my_collection ./chunks/

### Inspect a collection

```bash
# Show document count (no embedding key required)
uv run vector-db info ./data/vdb my_collection

# JSON output
uv run vector-db info ./data/vdb my_collection --json
```

List collections in a DB:

```bash
uv run vector-db ls ./data/vdb
uv run vector-db ls ./data/vdb --json
```

Query a collection:

```bash
export OPENAI_API_KEY=...
uv run vector-db query ./data/vdb my_collection "what are the key companies?" --top-k 5 --embed-model text-embedding-3-small

# JSON output
uv run vector-db query ./data/vdb my_collection "what are the key companies?" --json
```

## Gradio RAG Chat

Launch a simple chatbot that retrieves from your Chroma collection and answers with OpenAI.

```bash
export OPENAI_API_KEY=...

# Start the app on http://127.0.0.1:7860
uv run rag-chat ./data/vdb my_collection \
  --embed-model text-embedding-3-small \
  --top-k 4 \
  --model gpt-4o-mini

# Load variables from a .env file
uv run rag-chat --env ./.env ./data/vdb my_collection
```

Notes:
- Uses the same embedding model as the collection for queries (default `text-embedding-3-small`).
- The chat UI displays answers; you can customize system prompt via `--system`.
```

Embedding guidance:
- `text-embedding-3-small` (OpenAI): 1,536 dimensions, cheap/good quality; recommended default.
- `text-embedding-3-large` (OpenAI): higher quality, larger vectors; better recall at higher cost.
- You can switch providers in the future by extending `vectordb.embedding`.
