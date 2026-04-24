# EvidenceChain Backend Dockerfile
# Python 3.11 on Debian slim with system deps for Tesseract, libmagic, poppler

FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput 2>/dev/null || true

# Expose port
EXPOSE 8080

# Default command (overridden by docker-compose)
CMD ["gunicorn", "evidencechain.wsgi:application", "--bind", "0.0.0.0:8080", "--workers", "3"]
