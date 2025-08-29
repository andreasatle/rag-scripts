## Duplicate Finder

Find duplicate files (by content hash) under a directory and print grouped report.

### Usage

```bash
uv run find-duplicates /path/to/dir --report ./dups.txt

# non-recursive
uv run find-duplicates /path/to/dir --no-recursive
```

- Groups duplicates by size then hash for speed.
- Report example:

```
== Group 1 (3 files) | hash=<sha256>
 - /path/a.pdf
 - /path/b.pdf
 - /path/copy_of_a.pdf
```


