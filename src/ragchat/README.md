## Gradio RAG Chat

A simple chatbot UI that retrieves from your Chroma collection and answers with OpenAI.

### Launch

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
- Each retrieved chunk is sent as a separate user message for clarity, followed by the final question.
- Errors are printed to the terminal and surfaced in the UI when possible.


