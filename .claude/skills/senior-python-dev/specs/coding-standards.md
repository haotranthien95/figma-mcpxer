# Coding Standards

Standards enforced when acting as senior Python backend developer. These rules are non-negotiable.

---

## Python Style

### Naming
- Variables and functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private helpers: `_single_underscore` prefix (not double)
- Never abbreviate unless the abbreviation is universally known (`db`, `api`, `id`, `url`)

### Functions
- One function = one responsibility. If you can't describe it in one sentence, split it.
- Max 20 lines per function. If longer, extract helpers.
- No positional-only args for functions with more than 3 params — use keyword args.
- Always add return type hints and param type hints.

```python
# Good
async def get_user_by_id(user_id: int, db: AsyncSession) -> User | None:
    return await db.get(User, user_id)

# Bad — no type hints, vague name
async def get(id, session):
    return await session.get(User, id)
```

### Type Hints
- Always use type hints. No exceptions for public functions or class methods.
- Use `from __future__ import annotations` at top of file for forward references.
- Prefer `X | None` over `Optional[X]` (Python 3.10+).
- Use `TypeAlias` for complex repeated types.

```python
from __future__ import annotations
from typing import TypeAlias

UserId: TypeAlias = int
```

### Data Models
- Use **Pydantic v2** for all input/output validation and serialization.
- Use **SQLAlchemy 2.x** (async) for database models.
- Keep Pydantic schemas and SQLAlchemy models in separate files.

```python
# src/models/user.py — SQLAlchemy model
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)

# src/schemas/user.py — Pydantic schema
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
```

### Configuration
- Use **pydantic-settings** with a `Settings` class. Never use `os.getenv()` scattered across the codebase.
- Load settings once via a cached singleton (`lru_cache`).

```python
# src/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str
    debug: bool = False

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

---

## Architecture Patterns

### Layered Structure (Strict)

```
API Layer     → routers/      — HTTP request handling, input validation, response formatting
Service Layer → services/     — Business logic, orchestration, LLM calls
Repository    → repositories/ — DB queries, external API calls (raw data in/out)
Models        → models/       — SQLAlchemy ORM models
Schemas       → schemas/      — Pydantic request/response models
Utils         → utils/        — Pure stateless helpers (no DB, no I/O side effects)
```

**Rule**: Upper layers call lower layers. Lower layers never import from upper.
**Rule**: Services never import from routers. Repositories never import from services.

### Dependency Injection
- Use FastAPI's `Depends()` for DB sessions, auth, settings injection — not global state.

```python
# api/v1/users.py
@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    user = await user_service.get_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

### Error Handling
- Define custom exception classes in `src/exceptions.py`.
- Use a global FastAPI exception handler — don't scatter try/except across routers.
- Never swallow exceptions silently (`except Exception: pass` is forbidden).

```python
# src/exceptions.py
class NotFoundError(Exception):
    def __init__(self, resource: str, id: int) -> None:
        super().__init__(f"{resource} with id={id} not found")
        self.resource = resource
        self.id = id
```

---

## AI Agent & MCP Patterns

### MCP Server Structure

```python
# mcp_server.py — minimal, readable MCP server
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server("my-service")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_data",
            description="Retrieve data by ID",
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "get_data":
        result = await fetch_data(arguments["id"])
        return [types.TextContent(type="text", text=str(result))]
    raise ValueError(f"Unknown tool: {name}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(stdio_server(server))
```

### LLM Integration Pattern

```python
# src/services/llm_service.py
import anthropic
from src.config import get_settings

class LLMService:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-6"

    async def complete(self, system: str, user: str) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text
```

---

## Anti-Patterns (Never Do)

| Anti-Pattern | Why | Instead |
|---|---|---|
| `import *` | Hides dependencies, pollutes namespace | Explicit imports only |
| Mutable default arguments | `def foo(items=[])` creates shared state | Use `None` and initialize inside |
| Global state | Hard to test, causes race conditions | Dependency injection |
| `print()` for debugging | Left in production code | Use `logging` with proper levels |
| Long chains `a.b.c.d.e` | Violates Law of Demeter, fragile | Intermediate variables |
| Bare `except:` | Swallows all errors including KeyboardInterrupt | `except SpecificError:` |
| Synchronous blocking in async | `time.sleep()` in async function | `asyncio.sleep()` |
| Hardcoded secrets | Security risk | pydantic-settings + `.env` |
| One massive file | Hard to navigate, test, review | Modules by responsibility |

---

## Git & GitHub Conventions

- Commit messages: `type(scope): short description` — e.g., `feat(auth): add JWT refresh token`
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`
- PRs must include: what changed, why, how to test, screenshots if UI
- Branch names: `feature/short-description`, `fix/issue-123`
- Always add `.gitignore` entries for: `.env`, `__pycache__/`, `.pytest_cache/`, `*.pyc`, `dist/`, `.venv/`
