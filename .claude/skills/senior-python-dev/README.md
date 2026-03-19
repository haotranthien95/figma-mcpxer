# senior-python-dev

A Claude Code skill that activates a senior Python backend developer persona.

## What It Does

When invoked, this skill provides the mindset, standards, and workflow of a senior Python developer who:

- Writes clean, readable, maintainable Python code
- Designs simple but solid layered architectures (FastAPI, SQLAlchemy, Pydantic)
- Integrates LLM models (Anthropic Claude) and MCP servers
- Containerizes services with Docker
- Writes meaningful pytest tests (unit + integration)
- Always produces documentation and guidelines so other developers can understand the project

## How to Trigger

```
"implement this feature"
"write python code for..."
"create a service"
"review my code"
"write tests for..."
"dockerize this"
"add docs"
"set up mcp"
"integrate llm"
"build an agent"
"create a guideline"
"senior dev review"
```

## Execution Flow

```
Phase 0: Read specs (coding-standards.md + quality-standards.md)
    ↓
Phase 1: Context Analysis   — understand codebase and task
    ↓
Phase 2: Solution Design    — architecture, modules, API contract
    ↓
Phase 3: Implementation     — Python source, Docker, MCP/LLM code
    ↓
Phase 4: Testing            — pytest unit + integration tests
    ↓
Phase 5: Documentation      — README, CONTRIBUTING, ARCHITECTURE
```

## Key Outputs

| Phase | What You Get |
|-------|-------------|
| Phase 1 | `context-report.json` — codebase understanding |
| Phase 2 | `design-plan.md` — architecture plan |
| Phase 3 | All source files, Dockerfile, docker-compose.yml |
| Phase 4 | Test files with fixtures, coverage report |
| Phase 5 | README.md, CONTRIBUTING.md, docs/ARCHITECTURE.md |

## Reference Documents

| Document | Purpose |
|----------|---------|
| [specs/coding-standards.md](specs/coding-standards.md) | Python conventions, patterns, anti-patterns |
| [specs/quality-standards.md](specs/quality-standards.md) | Acceptance criteria for code, tests, docs |
| [templates/python-service.md](templates/python-service.md) | FastAPI service scaffold |
| [templates/docker-setup.md](templates/docker-setup.md) | Dockerfile + docker-compose patterns |
