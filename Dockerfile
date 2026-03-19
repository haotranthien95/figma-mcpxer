# ---- Build stage ----
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --upgrade pip --quiet

COPY pyproject.toml .
# Install runtime deps only (no dev extras) into a target dir for clean copy
RUN pip install --no-cache-dir "." --target /app/packages

# ---- Runtime stage ----
FROM python:3.12-slim AS runtime

# Non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /app/packages /usr/local/lib/python3.12/site-packages

# Copy source code
COPY src/ ./src/

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["python", "-m", "figma_mcpxer"]
