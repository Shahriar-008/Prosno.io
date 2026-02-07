#!/usr/bin/env bash
# Build and run a one-off container to generate a sample PDF

set -euo pipefail

IMAGE_NAME=prosno:local
OUT_DIR=$(pwd)/output
mkdir -p "$OUT_DIR"

echo "Building Docker image $IMAGE_NAME..."
docker build -t "$IMAGE_NAME" .

echo "Running container to generate PDF (output -> $OUT_DIR)..."
docker run --rm -v "$OUT_DIR:/output" "$IMAGE_NAME" python /app/bin/generate_sample_pdf.py /output/test_paper_docker.pdf

echo "Done. See $OUT_DIR/test_paper_docker.pdf"
