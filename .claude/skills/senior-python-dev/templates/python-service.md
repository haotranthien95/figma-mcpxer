# Python Service Template

Canonical structure for a FastAPI backend service. Copy and adapt — do not follow blindly.

---

## pyproject.toml

```toml
[project]
name = "my-service"
version = "0.1.0"
description = "Short service description"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",           # PostgreSQL async driver
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "anthropic>=0.40",         # Remove if no LLM integration
    "mcp>=1.0",                # Remove if no MCP server
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "httpx>=0.27",
    "aiosqlite>=0.20",         # In-memory SQLite for tests
    "ruff>=0.4",
    "mypy>=1.10",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## src/config.py

```python
from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str

    # LLM (optional — remove if not needed)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # App
    debug: bool = False
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

---

## src/database.py

```python
from __future__ import annotations
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from src.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    get_settings().database_url,
    echo=get_settings().debug,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

---

## src/exceptions.py

```python
from __future__ import annotations


class NotFoundError(Exception):
    def __init__(self, resource: str, id: int | str) -> None:
        super().__init__(f"{resource} with id={id} not found")
        self.resource = resource
        self.id = id


class ConflictError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ValidationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
```

---

## src/main.py

```python
from __future__ import annotations
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from src.exceptions import NotFoundError, ConflictError
from src.api.v1 import router as v1_router
from src.config import get_settings

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="My Service",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- Exception Handlers ---

@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})

# --- Routers ---

app.include_router(v1_router, prefix="/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

---

## .env.example

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mydb

# LLM (remove if not used)
ANTHROPIC_API_KEY=sk-ant-...

# App
DEBUG=false
LOG_LEVEL=INFO
```

---

## .gitignore (key entries)

```
.env
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
dist/
htmlcov/
.coverage
```
