## Word Links Downloader

Extract hyperlinks from `.docx` files and download the linked PDFs/files.

### Usage

```bash
uv run word-links /path/to/docx_or_dir -o ./downloads --recursive
```

Outputs per document:
- `<docname>_files/links_found.txt` with all extracted links
- downloaded files in the output directory
- `failed_downloads.txt` and `retry_failed_downloads.py` if any failed


