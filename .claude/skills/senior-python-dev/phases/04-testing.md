# Phase 4: Testing

Write pytest tests that verify behavior, not implementation details.

## Objective

- Write unit tests for all service layer functions
- Write integration tests for all API endpoints
- Set up fixtures properly in `conftest.py`
- Meet coverage targets from `specs/quality-standards.md`

## Input

- Dependency: Source files from Phase 3
- Reference: `specs/quality-standards.md` — coverage targets

## Execution Steps

### Step 1: Set Up Test Infrastructure

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.main import app
from src.database import Base, get_db
from src.config import get_settings

# Use a separate test DB (SQLite in-memory for speed, or test Postgres via docker-compose)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(engine):
    TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()  # isolate each test

@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

### Step 2: Write Unit Tests (Service Layer)

```python
# tests/unit/test_item_service.py
import pytest
from unittest.mock import AsyncMock
from src.services.item_service import ItemService
from src.schemas.item import ItemCreate
from src.exceptions import NotFoundError
from src.models.item import Item

@pytest.fixture
def mock_repo():
    return AsyncMock()

@pytest.fixture
def service(mock_repo):
    return ItemService(mock_repo)


class TestGetItem:
    async def test_get_item_when_exists_returns_response(self, service, mock_repo):
        mock_repo.get_by_id.return_value = Item(id=1, name="Widget", description="A widget")
        result = await service.get_item(1)
        assert result.id == 1
        assert result.name == "Widget"

    async def test_get_item_when_not_found_raises_not_found_error(self, service, mock_repo):
        mock_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            await service.get_item(999)


class TestCreateItem:
    async def test_create_item_returns_new_item(self, service, mock_repo):
        mock_repo.create.return_value = Item(id=42, name="Gadget", description=None)
        result = await service.create_item(ItemCreate(name="Gadget"))
        assert result.id == 42
        assert result.name == "Gadget"
        mock_repo.create.assert_called_once_with("Gadget", None)
```

### Step 3: Write Integration Tests (API Layer)

```python
# tests/integration/test_items_api.py
import pytest

class TestGetItemEndpoint:
    async def test_returns_200_when_item_exists(self, client, db_session):
        # Arrange: create item directly in DB
        from src.models.item import Item
        item = Item(name="Test Item", description="desc")
        db_session.add(item)
        await db_session.flush()

        # Act
        response = await client.get(f"/v1/items/{item.id}")

        # Assert
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Test Item"
        assert body["id"] == item.id

    async def test_returns_404_when_item_does_not_exist(self, client):
        response = await client.get("/v1/items/99999")
        assert response.status_code == 404


class TestCreateItemEndpoint:
    async def test_returns_201_with_created_item(self, client):
        response = await client.post("/v1/items/", json={"name": "New Item"})
        assert response.status_code == 201
        assert response.json()["name"] == "New Item"
        assert "id" in response.json()

    async def test_returns_422_when_name_missing(self, client):
        response = await client.post("/v1/items/", json={})
        assert response.status_code == 422
```

### Step 4: Run Tests and Check Coverage

```javascript
Bash("pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html");

// Coverage targets (from quality-standards.md):
// services/: 80%, api/: 70%, repositories/: 60%, utils/: 90%
```

### Step 5: Write Coverage Report

```javascript
const coverageOutput = Bash("pytest --cov=src --cov-report=json -q");
Write(`${workDir}/coverage-report.json`, coverageOutput);
```

## Output

- `tests/conftest.py`
- `tests/unit/test_*.py`
- `tests/integration/test_*.py`
- `coverage-report.json`

## Quality Checklist

- [ ] All tests pass (`pytest` exit code 0)
- [ ] Coverage meets targets per layer
- [ ] No test imports from other test files (no cross-test dependencies)
- [ ] Tests test behavior, not private method implementation
- [ ] Test names follow `test_{what}_{condition}_{expected}` pattern
- [ ] Fixtures are in `conftest.py`, not duplicated
- [ ] DB state is rolled back between tests (isolation)

## Next Phase

→ [Phase 5: Documentation](05-documentation.md)
