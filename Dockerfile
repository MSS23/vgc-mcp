FROM python:3.12-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ src/

# Regular (non-editable) install with remote dependencies
RUN pip install --no-cache-dir ".[remote]"

# Run as an unprivileged user; the API cache is its only writable state
RUN useradd --create-home --uid 10001 app
ENV VGC_CACHE_DIR=/home/app/cache
USER app

EXPOSE 8000

# Health check (no curl in the image)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)" || exit 1

# Run HTTP server
CMD ["vgc-mcp-http"]
