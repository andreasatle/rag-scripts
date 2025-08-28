## Text Split/Chunk Utilities

Split large text files, merge parts, or legal-aware chunking.

### Scripts

- `split-text-files`: split large text files
- `merge-split-files`: merge split parts
- `legal-chunk-text`: legal-aware text chunking

### Examples

```bash
uv run split-text-files ./big-texts -o ./chunks
uv run merge-split-files ./chunks -o ./merged
uv run legal-chunk-text ./legal-texts -o ./legal-chunks
```


