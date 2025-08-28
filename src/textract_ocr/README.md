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

### Creating an S3 bucket with AWS CLI (quick)

```bash
# Configure AWS first if needed
aws configure

# Set your bucket name and region
BUCKET=my-textract-inputs-$(uuidgen | tr 'A-Z' 'a-z' | tr -d '-')
REGION=us-east-1  # change to your region

# Create the bucket (note: us-east-1 has a special case)
if [ "$REGION" = "us-east-1" ]; then
  aws s3api create-bucket --bucket "$BUCKET"
else
  aws s3api create-bucket --bucket "$BUCKET" --create-bucket-configuration LocationConstraint="$REGION"
fi

# Optional but recommended: block public access and enable default encryption
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket "$BUCKET" \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

echo "Bucket created: $BUCKET in $REGION"
```


