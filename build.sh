#!/usr/bin/env bash
# Build script for Render deployment

set -o errexit

# Install dependencies
pip install -r requirements.txt

# Run database seed (safe to run multiple times - checks for existing data)
python seed_nctb.py

echo "Build completed successfully!"
