# Quality Standards

Acceptance criteria for all outputs. Code, tests, and documentation must meet these bars before delivery.

---

## Code Quality

### Required (Must Pass)
- [ ] All functions have type hints (params + return type)
- [ ] No bare `except:` clauses
- [ ] No hardcoded secrets or API keys
- [ ] No `print()` statements (use `logging`)
- [ ] No unused imports
- [ ] No mutable default arguments
- [ ] No global mutable state
- [ ] Architecture layers are respected (no cross-layer imports)
- [ ] File is < 300 lines; if longer, modules must be split by responsibility
- [ ] All Pydantic models use `model_config = ConfigDict(from_attributes=True)` where needed

### Recommended (Aim For)
- Functions are ≤ 20 lines
- Cyclomatic complexity < 10 per function
- No nesting deeper than 3 levels
- Each class has a single clear responsibility

---

## Testing Quality

### Required
- [ ] Test file mirrors source structure: `tests/unit/test_services.py` for `src/services/`
- [ ] Every public function in `services/` has at least one unit test
- [ ] Every API endpoint has at least one integration test
- [ ] Tests use `pytest` and `pytest-asyncio` for async tests
- [ ] Tests are independent — no shared mutable state between tests
- [ ] Fixtures are in `conftest.py`, not duplicated across test files
- [ ] Tests do not test implementation details — test behavior and outputs

### Coverage Targets
| Layer | Minimum Coverage |
|-------|-----------------|
| `services/` | 80% |
| `repositories/` | 60% |
| `api/` (routes) | 70% |
| `utils/` | 90% |

### Test Naming
```python
# Pattern: test_{what}_{condition}_{expected_result}
def test_get_user_by_id_when_exists_returns_user(): ...
def test_get_user_by_id_when_not_found_raises_not_found_error(): ...
def test_create_user_with_duplicate_email_raises_conflict_error(): ...
```

---

## Documentation Quality

### README.md (Required sections)
- [ ] Project name + one-line description
- [ ] Prerequisites (Python version, Docker version, env vars list)
- [ ] Quick start (copy-paste commands that work)
- [ ] Project structure overview
- [ ] How to run tests
- [ ] Environment variables reference table
- [ ] How to contribute (or link to CONTRIBUTING.md)

### CONTRIBUTING.md (Required if team project)
- [ ] How to set up local dev environment
- [ ] Branch naming and PR conventions
- [ ] Commit message format
- [ ] Code review checklist

### Inline Comments
- Do NOT add comments to explain what the code does (that's what type hints and names are for)
- DO add comments to explain WHY a non-obvious decision was made
```python
# Bad
# Get the user
user = await db.get(User, user_id)

# Good
# Bypass cache here because this endpoint is used for auth validation
# and must always reflect the latest DB state
user = await db.get(User, user_id, populate_existing=True)
```

---

## Docker Quality

### Dockerfile Checklist
- [ ] Uses official slim/alpine base image (not latest — pin the version)
- [ ] Multi-stage build for production images
- [ ] Runs as non-root user
- [ ] No secrets in the image layer (use runtime env vars)
- [ ] `.dockerignore` excludes `.env`, `__pycache__`, `.git`, `tests/`

### docker-compose.yml Checklist
- [ ] All services have health checks
- [ ] Secrets come from env vars or `.env` file, not hardcoded
- [ ] Volumes defined for persistent data (DB, uploads)
- [ ] Networks explicitly defined (don't use default bridge for multi-service apps)

---

## AI/LLM Integration Quality

### Prompts
- [ ] System prompt and user prompt are in separate variables (never concatenated inline)
- [ ] Prompts are in their own file or constant — not scattered in business logic
- [ ] Model name is configurable via settings, not hardcoded

### MCP Servers
- [ ] Tool descriptions are clear and accurate — LLMs rely on them
- [ ] Input schema validation is strict (`"additionalProperties": false`)
- [ ] Tools return structured data (JSON) not raw strings where possible
- [ ] Server handles errors gracefully and returns meaningful error messages

---

## Delivery Checklist

Before marking a task complete, verify:

```
Code
 [ ] Linting passes (ruff or flake8)
 [ ] Type checking passes (mypy or pyright)
 [ ] No secrets committed

Tests
 [ ] All tests pass locally
 [ ] Coverage meets targets per layer

Docker
 [ ] `docker-compose up` starts without errors
 [ ] Health checks pass

Documentation
 [ ] README has quick-start instructions that work
 [ ] New env vars are documented
 [ ] Breaking changes are noted in CHANGELOG or PR description
```
