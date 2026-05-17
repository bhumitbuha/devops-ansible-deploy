# Multi-stage build: build stage installs dependencies, runtime stage is lean
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim AS runtime

LABEL maintainer="bhumitbuha2016@gmail.com"
LABEL version="1.0"
LABEL description="DevOps deployment demo — Flask service"

WORKDIR /app

# Copy installed packages and executables from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn

# Copy application source
COPY app.py .

# Non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Health check built into the image
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "30", "app:app"]
