## Vector DB (ChromaDB persistence)

Create, delete, insert into, inspect, and query a local persistent vector database backed by ChromaDB.

### Install

```bash
uv sync
```

### Create / Delete a DB

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
- Backed by ChromaDB's `PersistentClient`.

### Insert text into a collection

Insert `.txt` chunks from a directory (recursively) or a single file into a collection with OpenAI embeddings:

```bash
export OPENAI_API_KEY=...  # or put it in .env

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
```

Tips:
- If you hit provider token limits, reduce batch size: `--batch-size 16` (or smaller).

### Inspect collections

```bash
# Show document count (no embedding key required)
uv run vector-db info ./data/vdb my_collection

# List collections with counts
uv run vector-db ls ./data/vdb
uv run vector-db ls ./data/vdb --json
```

### Query a collection

```bash
export OPENAI_API_KEY=...
uv run vector-db query ./data/vdb my_collection "what are the key companies?" --top-k 5 --embed-model text-embedding-3-small

# JSON output
uv run vector-db query ./data/vdb my_collection "what are the key companies?" --json
```

### Programmatic use

```python
from vectordb.manager import get_or_create_collection, get_collection
from vectordb.search import query_collection
from vectordb.embedding import EmbeddingConfig

# open for insert/query
coll = get_or_create_collection("./data/vdb", "my_collection", EmbeddingConfig())

# query
res = query_collection("./data/vdb", "my_collection", "your question", top_k=5)
docs = res["documents"][0]
metas = res["metadatas"][0]
```


