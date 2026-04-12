FROM python:3.10-slim

# System deps for trafilatura, lxml, requests
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libxml2-dev \
    libxslt-dev \
    libffi-dev \
    libssl-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Hugging Face Spaces runs as non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose HF default port
EXPOSE 7860

# Start with gunicorn — 4 workers, threads for I/O
CMD ["gunicorn", \
     "--bind", "0.0.0.0:7860", \
     "--workers", "4", \
     "--threads", "2", \
     "--timeout", "120", \
     "--worker-class", "gthread", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]