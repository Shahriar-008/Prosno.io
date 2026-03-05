FROM python:3.11-slim-bookworm

# Install system dependencies required by WeasyPrint (Cairo/Pango/GDK)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2 \
    libpango-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-noto \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY . /app

# Create writable directories for file generation
RUN mkdir -p /tmp/prosno_output /tmp/prosno_uploads

# Ensure fonts from repo are available (already in app/static/fonts)
ENV PYTHONUNBUFFERED=1
ENV PROSNO_SKIP_GLOBAL_APP=1
ENV PRODUCTION=1
ENV OUTPUT_FOLDER=/tmp/prosno_output
ENV UPLOAD_FOLDER=/tmp/prosno_uploads

EXPOSE 8000

# Health check so Coolify knows when the app is ready
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8000/ || exit 1

# Use gunicorn as entrypoint
CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:8000", "--timeout", "120", "--workers", "2"]
