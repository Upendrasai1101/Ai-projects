FROM python:3.10-slim

# System dependencies for lxml, trafilatura, cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
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

# Install Python deps first (Docker layer cache — faster rebuilds)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy all app files
COPY . .

# Hugging Face Spaces runs containers as non-root user (UID 1000)
RUN useradd -m -u 1000 pandauser \
    && chown -R pandauser:pandauser /app
USER pandauser

# HF Spaces default port — MUST be 7860
EXPOSE 7860

# Gunicorn: 4 workers, 2 threads each, 120s timeout
# gthread worker handles Flask I/O-bound search calls well
CMD ["gunicorn", \
     "--bind", "0.0.0.0:7860", \
     "--workers", "4", \
     "--threads", "2", \
     "--timeout", "120", \
     "--worker-class", "gthread", \
     "--log-level", "info", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]