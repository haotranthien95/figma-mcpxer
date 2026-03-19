# Phase 5: Documentation

Write documentation so any developer can understand, run, and contribute to the project without asking questions.

## Objective

- Write a complete README.md with working quick-start instructions
- Document the architecture for maintainers
- Write a CONTRIBUTING.md for new contributors
- Add env var reference table

## Input

- Dependency: All source files and test results from phases 3–4
- Reference: `specs/quality-standards.md` — documentation checklist

## Execution Steps

### Step 1: Gather Project Facts

```javascript
// Collect all the facts needed to write accurate docs
const pyproject = Read("pyproject.toml");
const envExample = Read(".env.example");
const mainFile = Read("src/main.py");
const dockerCompose = Read("docker-compose.yml");

const facts = {
  project_name: extractFromPyproject(pyproject, "name"),
  python_version: extractFromPyproject(pyproject, "python"),
  description: extractFromPyproject(pyproject, "description"),
  env_vars: parseEnvExample(envExample),
  api_prefix: extractApiPrefix(mainFile),
  services: extractDockerServices(dockerCompose),
};
```

### Step 2: Write README.md

```markdown
# {project_name}

> {one-line description}

## Prerequisites

- Python {python_version}+
- Docker & Docker Compose
- Copy `.env.example` to `.env` and fill in values

## Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/your-org/{project_name}.git
cd {project_name}

# 2. Copy environment config
cp .env.example .env
# Edit .env with your values

# 3. Start services
docker-compose up -d

# 4. The API is now running at http://localhost:8000
# Docs: http://localhost:8000/docs
```

## Project Structure

```
src/
├── api/v1/        # HTTP endpoints (routers only — no business logic here)
├── services/      # Business logic
├── repositories/  # DB queries and external API calls
├── models/        # SQLAlchemy ORM models
├── schemas/       # Pydantic request/response models
├── utils/         # Pure stateless helpers
├── config.py      # Settings (loaded from .env)
└── main.py        # FastAPI app entry point

tests/
├── unit/          # Test services in isolation (mocked dependencies)
└── integration/   # Test API endpoints against real DB
```

## Running Tests

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=src --cov-report=term-missing

# Run only unit tests
pytest tests/unit/
```

## Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
{env_vars_table}

## API Reference

The API is documented automatically at `/docs` (Swagger UI) and `/redoc`.

Base URL: `http://localhost:8000/v1`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
```

### Step 3: Write docs/ARCHITECTURE.md

```markdown
# Architecture

## Overview

This service follows a strict layered architecture:

```
HTTP Request
    ↓
[Router] — validates request, calls service, formats response
    ↓
[Service] — business logic, orchestration
    ↓
[Repository] — DB queries, external API calls
    ↓
[DB / External Service]
```

**Key rule**: Lower layers never import from upper layers.

## Data Flow Example

1. `POST /v1/items` arrives at `api/v1/items.py`
2. Router calls `ItemService.create_item(data)`
3. Service validates business rules, calls `ItemRepository.create()`
4. Repository writes to DB, returns ORM model
5. Service converts to Pydantic schema, returns to Router
6. Router returns 201 JSON response

## External Integrations

### LLM (Anthropic Claude)
- `src/services/llm_service.py` wraps all Anthropic API calls
- Model is configurable via `ANTHROPIC_MODEL` env var
- Prompts live in `src/prompts/` — never inline

### MCP Server (if applicable)
- `mcp_server.py` exposes tools to LLM agents
- Tool schemas are strict (`additionalProperties: false`)

## Error Handling Strategy

- Custom exceptions: `src/exceptions.py`
- Global handler in `src/main.py` maps to HTTP status codes
- No try/except in routers — clean separation

## Configuration

All configuration via `pydantic-settings` (`src/config.py`).
Values loaded from `.env` file or environment variables.
```

### Step 4: Write CONTRIBUTING.md

```markdown
# Contributing Guide

## Local Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dev dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install
```

## Workflow

1. Create a branch: `git checkout -b feature/your-feature-name`
2. Make changes following the coding standards in `specs/coding-standards.md`
3. Write tests (see `phases/04-testing.md`)
4. Run `pytest` and ensure all tests pass
5. Run `ruff check src/` and fix any lint issues
6. Open a PR with a clear description

## Commit Message Format

```
type(scope): short description

Types: feat, fix, refactor, test, docs, chore, ci
Examples:
  feat(items): add bulk create endpoint
  fix(auth): handle expired JWT correctly
  test(items): add edge cases for duplicate names
```

## Code Review Checklist

Before requesting review:
- [ ] Tests pass locally
- [ ] Coverage didn't decrease
- [ ] No hardcoded secrets
- [ ] Type hints on all new functions
- [ ] README updated if new env vars added
```

### Step 5: Final Validation

```javascript
// Verify all required doc sections are present
const readme = Read("README.md");
const checks = {
  has_quick_start: readme.includes("Quick Start"),
  has_project_structure: readme.includes("Project Structure"),
  has_env_vars: readme.includes("Environment Variables"),
  has_tests_section: readme.includes("Running Tests"),
};

const allPass = Object.values(checks).every(v => v);
if (!allPass) {
  console.error("README missing required sections:", checks);
}

Write(`${workDir}/docs-validation.json`, JSON.stringify(checks, null, 2));
```

## Output

- `README.md`
- `docs/ARCHITECTURE.md`
- `CONTRIBUTING.md`
- `docs-validation.json`

## Quality Checklist

- [ ] Quick start commands are copy-paste ready and work
- [ ] All env vars documented in a table
- [ ] Architecture section explains the layer separation
- [ ] CONTRIBUTING.md covers local setup + PR workflow
- [ ] No placeholder text left in docs (`{your name}`, `TODO:`, etc.)

## Completion

This is the final phase. Deliverables are ready for code review.
