FROM python:3.10-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    libxml2-dev libxslt-dev \
    libffi-dev libssl-dev \
    tesseract-ocr tesseract-ocr-eng \
    ffmpeg \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy all app files to /app (root)
COPY . .

# Create upload directories
RUN mkdir -p uploads/documents uploads/images uploads/audio

# HF Spaces runs as non-root
RUN useradd -m -u 1000 pandauser \
    && chown -R pandauser:pandauser /app
USER pandauser

EXPOSE 7860

# CMD points directly to app:app — no path issues
CMD ["gunicorn", \
     "--bind", "0.0.0.0:7860", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "120", \
     "--worker-class", "gthread", \
     "--chdir", "/app", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]