## Textract OCR Pipeline (PDF → text)

Batch PDFs through AWS Textract and write extracted text files.

### Install

```bash
uv sync
```

### Usage

```bash
uv run textract-ocr INPUTS... -o OUTDIR --bucket BUCKET [--prefix PREFIX] [--region REGION] [-j JOBS] [--no-recursive] [--poll-seconds SEC] [--timeout-seconds SEC] [--keep-uploaded]
```

Example:

```bash
uv run textract-ocr ./docs/ -o ./out --bucket my-bucket --prefix incoming/ocr --region us-east-1 -j 8
```

Requires AWS credentials via environment, shared files, or IAM role.


