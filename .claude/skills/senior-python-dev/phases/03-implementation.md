# Phase 3: Implementation

Write all source code following the design plan and coding standards.

## Objective

- Implement all files listed in `design-plan.md`
- Adhere strictly to `specs/coding-standards.md`
- Produce production-ready code, not prototype code
- Include Docker setup if the service is containerized

## Input

- Dependency: `design-plan.md` (from Phase 2)
- Reference: `specs/coding-standards.md`
- Template: `templates/python-service.md`, `templates/docker-setup.md`

## Execution Steps

### Step 1: Set Up Project Skeleton

```javascript
// Only if starting a new project — skip if adding to existing
const design = Read(`${workDir}/design-plan.md`);

// Create pyproject.toml
Write("pyproject.toml", generatePyproject(design));

// Create .env.example (never .env with real values)
Write(".env.example", generateEnvExample(design));

// Create .gitignore
Write(".gitignore", standardGitignore);

// Create src/ scaffold
Bash("mkdir -p src/{api/v1,services,repositories,models,schemas,utils}");
Bash("touch src/__init__.py src/api/__init__.py src/api/v1/__init__.py");
```

### Step 2: Implement in Layer Order

Always implement bottom-up: models → schemas → repositories → services → API.

```python
# --- MODELS (SQLAlchemy) ---
# src/models/item.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base

class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=func.now())

# --- SCHEMAS (Pydantic) ---
# src/schemas/item.py
from pydantic import BaseModel, ConfigDict

class ItemCreate(BaseModel):
    name: str
    description: str | None = None

class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None

# --- REPOSITORY ---
# src/repositories/item_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.item import Item

class ItemRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, item_id: int) -> Item | None:
        return await self.db.get(Item, item_id)

    async def create(self, name: str, description: str | None) -> Item:
        item = Item(name=name, description=description)
        self.db.add(item)
        await self.db.flush()
        return item

# --- SERVICE ---
# src/services/item_service.py
from src.repositories.item_repository import ItemRepository
from src.schemas.item import ItemCreate, ItemResponse
from src.exceptions import NotFoundError

class ItemService:
    def __init__(self, repo: ItemRepository) -> None:
        self.repo = repo

    async def get_item(self, item_id: int) -> ItemResponse:
        item = await self.repo.get_by_id(item_id)
        if not item:
            raise NotFoundError("Item", item_id)
        return ItemResponse.model_validate(item)

    async def create_item(self, data: ItemCreate) -> ItemResponse:
        item = await self.repo.create(data.name, data.description)
        return ItemResponse.model_validate(item)

# --- ROUTER ---
# src/api/v1/items.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.repositories.item_repository import ItemRepository
from src.services.item_service import ItemService
from src.schemas.item import ItemCreate, ItemResponse
from src.exceptions import NotFoundError

router = APIRouter(prefix="/items", tags=["items"])

def get_item_service(db: AsyncSession = Depends(get_db)) -> ItemService:
    return ItemService(ItemRepository(db))

@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    service: ItemService = Depends(get_item_service),
) -> ItemResponse:
    try:
        return await service.get_item(item_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/", response_model=ItemResponse, status_code=201)
async def create_item(
    data: ItemCreate,
    service: ItemService = Depends(get_item_service),
) -> ItemResponse:
    return await service.create_item(data)
```

### Step 3: LLM / MCP Integration (if required)

```python
# src/services/llm_service.py
import anthropic
from src.config import get_settings

class LLMService:
    """Wraps Anthropic API calls. Model is configurable via settings."""

    MODEL = "claude-sonnet-4-6"

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)

    def complete(self, system_prompt: str, user_message: str) -> str:
        message = self.client.messages.create(
            model=self.MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text


# mcp_server.py — expose tools to LLM agents
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
import asyncio

server = Server("my-mcp-server")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_item",
            description="Retrieve an item by its ID. Returns item details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {"type": "integer", "description": "The item's unique ID"}
                },
                "required": ["item_id"],
                "additionalProperties": False,
            },
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "get_item":
        result = await fetch_item(arguments["item_id"])
        return [types.TextContent(type="text", text=result.model_dump_json())]
    raise ValueError(f"Unknown tool: {name}")

if __name__ == "__main__":
    asyncio.run(stdio_server(server))
```

### Step 4: Docker Setup

```javascript
// Reference templates/docker-setup.md for full patterns
Write("Dockerfile", dockerfileContent);
Write("docker-compose.yml", dockerComposeContent);
Write(".dockerignore", dockerignoreContent);
```

### Step 5: Verify Code Quality

```javascript
// Run linting and type checking if tooling is available
Bash("ruff check src/");
Bash("mypy src/");
```

## Output

- All source `.py` files
- `Dockerfile`, `docker-compose.yml` (if applicable)
- `pyproject.toml` (if new project)
- `.env.example`

## Quality Checklist

- [ ] All files from design-plan.md are created or modified
- [ ] No type hint omissions
- [ ] No hardcoded secrets
- [ ] Layer boundaries respected (no cross-layer imports)
- [ ] Error handling uses custom exceptions, not bare strings
- [ ] `ruff` / `flake8` passes cleanly
- [ ] Docker setup works locally (`docker-compose up`)

## Next Phase

→ [Phase 4: Testing](04-testing.md)
