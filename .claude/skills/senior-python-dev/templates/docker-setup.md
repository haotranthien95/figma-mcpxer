# Docker Setup Template

Standard Dockerfile and docker-compose.yml patterns for Python backend services.

---

## Dockerfile (Multi-Stage, Production-Ready)

```dockerfile
# ---- Build stage ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --upgrade pip

COPY pyproject.toml .
RUN pip install --no-cache-dir ".[dev]" --target /app/packages

# ---- Runtime stage ----
FROM python:3.11-slim AS runtime

# Create non-root user (security best practice)
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /app/packages /usr/local/lib/python3.11/site-packages

# Copy source code
COPY src/ ./src/

# Set ownership
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## docker-compose.yml (Local Development)

```yaml
version: "3.9"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/mydb
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DEBUG=true
      - LOG_LEVEL=DEBUG
    depends_on:
      db:
        condition: service_healthy
    volumes:
      # Hot reload in dev — remove for production
      - ./src:/app/src
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: mydb
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  postgres_data:

networks:
  default:
    name: myservice_network
```

---

## .dockerignore

```
.env
.git/
.gitignore
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
tests/
docs/
*.md
.venv/
dist/
```

---

## Common Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| `Connection refused` on startup | App starts before DB is ready | Use `depends_on` with `condition: service_healthy` |
| Secrets baked into image | `ENV` in Dockerfile | Use runtime env vars via `environment:` in compose |
| Container runs as root | No `USER` directive | Add `useradd` + `USER appuser` |
| Code changes not reflected | No volume mount | Add `- ./src:/app/src` volume (dev only) |
| Port already in use | Another service on 8000 | Change left side of port mapping `"8001:8000"` |
| Slow rebuilds | Copying everything before pip install | Copy `pyproject.toml` first, then source code |

---

## MCP Server docker-compose (if applicable)

```yaml
services:
  mcp-server:
    build:
      context: .
      dockerfile: Dockerfile.mcp
    stdin_open: true   # Required for stdio transport
    tty: true
    environment:
      - DATABASE_URL=${DATABASE_URL}
    volumes:
      - ./mcp_server.py:/app/mcp_server.py
```
